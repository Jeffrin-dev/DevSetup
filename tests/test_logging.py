"""
tests.test_logging
-------------------
Tests for DevSetup v1.8 logging system.

Coverage:
  Phase 1  — logging requirements: structured, levelled, timestamped
  Phase 2  — Logger module: set_verbose, set_log_file, verbose()
  Phase 3  — Structured format: [TIMESTAMP] [LEVEL] Message
  Phase 4  — --verbose on install command: VERBOSE messages appear
  Phase 5  — no raw print() outside logger.py
  Phase 6  — error/warning log levels work correctly
  Phase 7  — full timestamp (YYYY-MM-DD HH:MM:SS) in verbose mode only
  Phase 8  — per-tool logging: start, skip, success, failure, version
  Phase 9  — verbose + --yes combination
  Phase 10 — help text includes --verbose and --log-file
  Phase 11 — VERBOSE level gated on verbose mode; all other levels always shown
  Phase 12 — --log-file tees output to file
  Phase 13 — all 5 roadmap scenarios
"""

import io
import os
import re
import sys
import tempfile
import unittest
from contextlib import ExitStack
from unittest.mock import patch

from devsetup.cli.main import main
from devsetup.utils import logger as log_module
from devsetup.utils.logger import (
    set_verbose, set_log_file, verbose, info, warn, error,
    _is_verbose, _timestamp, _timestamp_full,
)
from devsetup.system.package_managers.base import PackageManagerError


# ── Helpers ───────────────────────────────────────────────────────────────────

def _run(argv):
    """Run main(argv), return (stdout, stderr, exit_code)."""
    buf_out, buf_err = io.StringIO(), io.StringIO()
    old = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = buf_out, buf_err
    try:
        code = main(argv)
    finally:
        sys.stdout, sys.stderr = old
    return buf_out.getvalue(), buf_err.getvalue(), code


def _patches(tool, *, detect, fail_with=None, version="1.0.0"):
    base = {
        "git":    "devsetup.installers.git.GitInstaller",
        "node":   "devsetup.installers.node.NodeInstaller",
        "python": "devsetup.installers.python.PythonInstaller",
        "pip":    "devsetup.installers.pip.PipInstaller",
        "vscode": "devsetup.installers.vscode.VSCodeInstaller",
    }[tool]
    return [
        patch(f"{base}.detect",  return_value=detect),
        patch(f"{base}.version", return_value=version),
        patch(f"{base}.install",
              side_effect=fail_with if fail_with else None,
              return_value=None if not fail_with else ...),
    ]


def _capture(fn):
    """Capture stdout from a zero-arg callable."""
    buf = io.StringIO()
    old = sys.stdout; sys.stdout = buf
    try:
        fn()
    finally:
        sys.stdout = old
    return buf.getvalue()


def _reset_logger():
    """Reset logger module state between tests."""
    log_module._verbose_override = None
    log_module._log_file_path    = None
    os.environ.pop("DEVSETUP_VERBOSE",  None)
    os.environ.pop("DEVSETUP_LOG_FILE", None)


# ── Phase 2: Logger module API ────────────────────────────────────────────────

class TestLoggerAPI(unittest.TestCase):

    def setUp(self):    _reset_logger()
    def tearDown(self): _reset_logger()

    def test_set_verbose_enables_verbose(self):
        set_verbose(True)
        self.assertTrue(_is_verbose())

    def test_set_verbose_disables_verbose(self):
        set_verbose(False)
        self.assertFalse(_is_verbose())

    def test_set_verbose_overrides_env_var(self):
        os.environ["DEVSETUP_VERBOSE"] = "1"
        set_verbose(False)
        self.assertFalse(_is_verbose())

    def test_env_var_enables_verbose(self):
        os.environ["DEVSETUP_VERBOSE"] = "1"
        self.assertTrue(_is_verbose())

    def test_verbose_function_emits_when_active(self):
        set_verbose(True)
        out = _capture(lambda: verbose("test message"))
        self.assertIn("[VERBOSE]", out)
        self.assertIn("test message", out)

    def test_verbose_function_silent_when_inactive(self):
        set_verbose(False)
        out = _capture(lambda: verbose("test message"))
        self.assertEqual(out, "")

    def test_set_log_file_stored(self):
        set_log_file("/tmp/test.log")
        self.assertEqual(log_module._log_file_path, "/tmp/test.log")

    def test_set_log_file_none_clears(self):
        set_log_file("/tmp/test.log")
        set_log_file(None)
        self.assertIsNone(log_module._log_file_path)

    def test_verbose_callable(self):
        self.assertTrue(callable(verbose))

    def test_set_verbose_callable(self):
        self.assertTrue(callable(set_verbose))

    def test_set_log_file_callable(self):
        self.assertTrue(callable(set_log_file))


# ── Phase 3: Structured log format ───────────────────────────────────────────

class TestLogFormat(unittest.TestCase):

    def setUp(self):    _reset_logger()
    def tearDown(self): _reset_logger()

    def test_info_format_has_level_tag(self):
        out = _capture(lambda: info("hello"))
        self.assertRegex(out.strip(), r"^\[.+\] \[INFO\]\s+hello$")

    def test_warn_format_has_level_tag(self):
        out = _capture(lambda: warn("careful"))
        self.assertRegex(out.strip(), r"^\[.+\] \[WARN\]\s+careful$")

    def test_error_format_has_level_tag(self):
        buf = io.StringIO()
        old = sys.stderr; sys.stderr = buf
        error("oops")
        sys.stderr = old
        self.assertRegex(buf.getvalue().strip(), r"^\[.+\] \[ERROR\]\s+oops$")

    def test_verbose_format_has_level_tag(self):
        set_verbose(True)
        out = _capture(lambda: verbose("detail"))
        self.assertRegex(out.strip(), r"^\[.+\] \[VERBOSE\]\s+detail$")

    def test_normal_timestamp_is_short(self):
        ts = _timestamp()
        self.assertRegex(ts, r"^\d{2}:\d{2}:\d{2}$")

    def test_normal_log_contains_short_timestamp(self):
        out = _capture(lambda: info("msg"))
        self.assertRegex(out.strip(), r"^\[\d{2}:\d{2}:\d{2}\]")

    def test_log_format_is_machine_parseable(self):
        """Every non-blank log line must match [TIMESTAMP] [LEVEL] message."""
        out = _capture(lambda: info("parseable"))
        for line in out.splitlines():
            if line.strip():
                self.assertRegex(
                    line.strip(),
                    r"^\[[\d:]{8}\] \[[A-Z]+\s*\]",
                    f"Line does not match log format: {line!r}",
                )


# ── Phase 7: Timestamp handling ───────────────────────────────────────────────

class TestTimestamps(unittest.TestCase):

    def setUp(self):    _reset_logger()
    def tearDown(self): _reset_logger()

    def test_verbose_timestamp_is_full(self):
        ts = _timestamp_full()
        self.assertRegex(ts, r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")

    def test_normal_timestamp_always_short_regardless_of_verbose(self):
        for v in (True, False):
            set_verbose(v)
            ts = _timestamp()
            self.assertRegex(ts, r"^\d{2}:\d{2}:\d{2}$",
                             f"Short timestamp broken when verbose={v}")

    def test_info_always_uses_short_timestamp(self):
        for v in (True, False):
            set_verbose(v)
            out = _capture(lambda: info("msg"))
            self.assertRegex(out.strip(), r"^\[\d{2}:\d{2}:\d{2}\]",
                             f"Short timestamp broken for INFO when verbose={v}")

    def test_verbose_line_uses_full_timestamp(self):
        set_verbose(True)
        out = _capture(lambda: verbose("detail"))
        self.assertRegex(out.strip(), r"^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\]")

    def test_normal_mode_no_date_in_timestamp(self):
        set_verbose(False)
        out = _capture(lambda: info("msg"))
        self.assertNotRegex(out.strip(), r"^\[\d{4}-")

    def test_timestamps_do_not_raise_on_any_platform(self):
        for v in (True, False):
            set_verbose(v)
            try:
                ts  = _timestamp()
                tsf = _timestamp_full()
                self.assertIsInstance(ts,  str)
                self.assertIsInstance(tsf, str)
            except Exception as e:
                self.fail(f"timestamp raised with verbose={v}: {e}")


# ── Phase 4: --verbose on install command ────────────────────────────────────

class TestVerboseInstallFlag(unittest.TestCase):

    def setUp(self):    _reset_logger()
    def tearDown(self): _reset_logger()

    def test_verbose_flag_accepted_on_install_env(self):
        with patch("devsetup.core.environment_loader.load",
                   return_value={"id": "web", "name": "Web",
                                 "installers": ["git"]}), \
             patch("devsetup.installers.manager.install_environment"):
            _, _, code = _run(["install", "web", "--verbose"])
        self.assertEqual(code, 0)

    def test_verbose_flag_activates_verbose_mode(self):
        with patch("devsetup.core.environment_loader.load",
                   return_value={"id": "web", "name": "Web",
                                 "installers": ["git"]}), \
             patch("devsetup.installers.manager.install_environment"):
            _run(["install", "web", "--verbose"])
        self.assertTrue(log_module._is_verbose())

    def test_verbose_install_shows_verbose_messages(self):
        ps = _patches("git", detect=False, version="2.43.0")
        with ExitStack() as stack:
            for p in ps:
                stack.enter_context(p)
            out, _, code = _run(["install", "--tool", "git", "--verbose"])
        self.assertEqual(code, 0)
        self.assertIn("[VERBOSE]", out)

    def test_without_verbose_no_verbose_messages(self):
        ps = _patches("git", detect=False, version="2.43.0")
        with ExitStack() as stack:
            for p in ps:
                stack.enter_context(p)
            out, _, _ = _run(["install", "--tool", "git"])
        self.assertNotIn("[VERBOSE]", out)

    def test_verbose_lines_carry_full_timestamp(self):
        ps = _patches("git", detect=False, version="2.43.0")
        with ExitStack() as stack:
            for p in ps:
                stack.enter_context(p)
            out, _, _ = _run(["install", "--tool", "git", "--verbose"])
        verbose_lines = [l for l in out.splitlines() if "[VERBOSE]" in l]
        self.assertTrue(len(verbose_lines) > 0, "Expected at least one [VERBOSE] line")
        for line in verbose_lines:
            self.assertRegex(line.strip(),
                             r"^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\]")

    def test_verbose_shows_dep_resolution_detail(self):
        ps = (
            _patches("git",  detect=False, version="2.43.0")
            + _patches("node", detect=False, version="20.x")
        )
        with ExitStack() as stack:
            for p in ps:
                stack.enter_context(p)
            with patch("devsetup.core.environment_loader.load",
                       return_value={"id": "web", "name": "Web",
                                     "installers": ["git", "node"]}):
                out, _, _ = _run(["install", "web", "--verbose"])
        self.assertIn("[VERBOSE]", out)
        self.assertIn("DependencyResolver", out)


# ── Phase 11: Log level gating ───────────────────────────────────────────────

class TestLogLevelGating(unittest.TestCase):

    def setUp(self):    _reset_logger()
    def tearDown(self): _reset_logger()

    def test_info_always_shown(self):
        set_verbose(False)
        out = _capture(lambda: info("msg"))
        self.assertIn("[INFO]", out)

    def test_warn_always_shown(self):
        set_verbose(False)
        out = _capture(lambda: warn("msg"))
        self.assertIn("[WARN]", out)

    def test_error_always_shown(self):
        buf = io.StringIO(); old = sys.stderr; sys.stderr = buf
        error("msg"); sys.stderr = old
        self.assertIn("[ERROR]", buf.getvalue())

    def test_verbose_hidden_without_flag(self):
        set_verbose(False)
        out = _capture(lambda: verbose("detail"))
        self.assertEqual(out.strip(), "")

    def test_verbose_shown_with_flag(self):
        set_verbose(True)
        out = _capture(lambda: verbose("detail"))
        self.assertIn("[VERBOSE]", out)

    def test_normal_install_produces_no_verbose_lines(self):
        ps = _patches("git", detect=False, version="2.43.0")
        with ExitStack() as stack:
            for p in ps:
                stack.enter_context(p)
            out, _, _ = _run(["install", "--tool", "git"])
        self.assertNotIn("[VERBOSE]", out)

    def test_verbose_install_produces_verbose_lines(self):
        ps = _patches("git", detect=False, version="2.43.0")
        with ExitStack() as stack:
            for p in ps:
                stack.enter_context(p)
            out, _, _ = _run(["install", "--tool", "git", "--verbose"])
        self.assertIn("[VERBOSE]", out)


# ── Phase 8: Per-tool logging ─────────────────────────────────────────────────

class TestPerToolLogging(unittest.TestCase):

    def setUp(self):    _reset_logger()
    def tearDown(self): _reset_logger()

    def test_install_start_logged(self):
        ps = _patches("git", detect=False, version="2.43.0")
        with ExitStack() as stack:
            for p in ps: stack.enter_context(p)
            out, _, _ = _run(["install", "--tool", "git"])
        self.assertIn("[INSTALL]", out)

    def test_skip_logged_when_already_installed(self):
        ps = _patches("git", detect=True, version="2.43.0")
        with ExitStack() as stack:
            for p in ps: stack.enter_context(p)
            out, _, _ = _run(["install", "--tool", "git"])
        self.assertIn("[SKIP]", out)

    def test_success_logged_after_install(self):
        ps = _patches("git", detect=False, version="2.43.0")
        with ExitStack() as stack:
            for p in ps: stack.enter_context(p)
            out, _, _ = _run(["install", "--tool", "git"])
        self.assertIn("[OK]", out)

    def test_failure_logged_on_pm_error(self):
        pm_err = PackageManagerError("apt error", pm_exit_code=1)
        ps = _patches("git", detect=False, fail_with=pm_err)
        with ExitStack() as stack:
            for p in ps: stack.enter_context(p)
            _, err, _ = _run(["install", "--tool", "git"])
        self.assertIn("[FAIL]", err)

    def test_version_logged_after_successful_install(self):
        ps = _patches("git", detect=False, version="2.43.0")
        with ExitStack() as stack:
            for p in ps: stack.enter_context(p)
            out, _, _ = _run(["install", "--tool", "git"])
        self.assertIn("[VERSION]", out)
        self.assertIn("2.43.0", out)

    def test_version_logged_in_verbose_mode(self):
        ps = _patches("git", detect=False, version="2.43.0")
        with ExitStack() as stack:
            for p in ps: stack.enter_context(p)
            out, _, _ = _run(["install", "--tool", "git", "--verbose"])
        self.assertIn("Version detected", out)
        self.assertIn("2.43.0", out)

    def test_check_logged_before_detect(self):
        ps = _patches("git", detect=True, version="2.43.0")
        with ExitStack() as stack:
            for p in ps: stack.enter_context(p)
            out, _, _ = _run(["install", "--tool", "git"])
        self.assertIn("[CHECK]", out)


# ── Phase 9: Verbose + non-interactive ───────────────────────────────────────

class TestVerboseWithYes(unittest.TestCase):

    def setUp(self):    _reset_logger()
    def tearDown(self): _reset_logger()

    def test_verbose_yes_combination_exits_0(self):
        with patch("devsetup.core.environment_loader.load",
                   return_value={"id": "web", "name": "Web",
                                 "installers": ["git"]}), \
             patch("devsetup.installers.manager.install_environment"):
            _, _, code = _run(["install", "web", "--yes", "--verbose"])
        self.assertEqual(code, 0)

    def test_verbose_yes_shows_both_auto_and_verbose_lines(self):
        ps = _patches("git", detect=False, version="2.43.0")
        with ExitStack() as stack:
            for p in ps: stack.enter_context(p)
            with patch("devsetup.core.environment_loader.load",
                       return_value={"id": "web", "name": "Web",
                                     "installers": ["git"]}):
                out, _, _ = _run(["install", "web", "--yes", "--verbose"])
        self.assertIn("[AUTO]",    out)
        self.assertIn("[VERBOSE]", out)

    def test_skipped_tools_logged_in_verbose_yes_mode(self):
        ps = _patches("git", detect=True, version="2.43.0")
        with ExitStack() as stack:
            for p in ps: stack.enter_context(p)
            with patch("devsetup.core.environment_loader.load",
                       return_value={"id": "web", "name": "Web",
                                     "installers": ["git"]}):
                out, _, _ = _run(["install", "web", "--yes", "--verbose"])
        self.assertIn("[SKIP]", out)

    def test_verbose_yes_dep_order_logged(self):
        ps = (
            _patches("git",  detect=False, version="2.43.0")
            + _patches("node", detect=False, version="20.x")
        )
        with ExitStack() as stack:
            for p in ps: stack.enter_context(p)
            with patch("devsetup.core.environment_loader.load",
                       return_value={"id": "web", "name": "Web",
                                     "installers": ["git", "node"]}):
                out, _, _ = _run(["install", "web", "--yes", "--verbose"])
        self.assertIn("[DEPS]",    out)
        self.assertIn("[VERBOSE]", out)
        self.assertIn("[AUTO]",    out)


# ── Phase 12: Log file output ─────────────────────────────────────────────────

class TestLogFile(unittest.TestCase):

    def setUp(self):    _reset_logger()
    def tearDown(self): _reset_logger()

    def test_log_file_flag_accepted(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log",
                                         delete=False) as f:
            path = f.name
        try:
            with patch("devsetup.core.environment_loader.load",
                       return_value={"id": "web", "name": "Web",
                                     "installers": ["git"]}), \
                 patch("devsetup.installers.manager.install_environment"):
                _, _, code = _run(["install", "web", "--log-file", path])
            self.assertEqual(code, 0)
        finally:
            os.unlink(path)

    def test_log_file_receives_output(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log",
                                         delete=False) as f:
            path = f.name
        try:
            ps = _patches("git", detect=False, version="2.43.0")
            with ExitStack() as stack:
                for p in ps: stack.enter_context(p)
                _run(["install", "--tool", "git", "--log-file", path])
            with open(path) as fh:
                contents = fh.read()
            self.assertGreater(len(contents.strip()), 0)
            self.assertTrue(
                any(tag in contents for tag in ("[CHECK]", "[OK]", "[INSTALL]")),
                f"No expected log tags in file: {contents[:200]}",
            )
        finally:
            os.unlink(path)

    def test_log_file_tees_to_both_console_and_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log",
                                         delete=False) as f:
            path = f.name
        try:
            ps = _patches("git", detect=False, version="2.43.0")
            with ExitStack() as stack:
                for p in ps: stack.enter_context(p)
                out, _, _ = _run(["install", "--tool", "git", "--log-file", path])
            with open(path) as fh:
                file_contents = fh.read()
            self.assertGreater(len(out.strip()), 0)
            self.assertGreater(len(file_contents.strip()), 0)
        finally:
            os.unlink(path)

    def test_log_file_contains_tool_name_and_ok(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log",
                                         delete=False) as f:
            path = f.name
        try:
            ps = _patches("git", detect=False, version="2.43.0")
            with ExitStack() as stack:
                for p in ps: stack.enter_context(p)
                _run(["install", "--tool", "git", "--log-file", path])
            with open(path) as fh:
                contents = fh.read()
            self.assertIn("git", contents)
            self.assertIn("[OK]", contents)
        finally:
            os.unlink(path)

    def test_set_log_file_via_api(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log",
                                         delete=False) as f:
            path = f.name
        try:
            set_log_file(path)
            _capture(lambda: info("test line"))
            with open(path) as fh:
                contents = fh.read()
            self.assertIn("test line", contents)
        finally:
            set_log_file(None)
            os.unlink(path)

    def test_invalid_log_file_path_does_not_crash(self):
        set_log_file("/nonexistent_dir_xyz/devsetup_test.log")
        # Must not raise
        out = _capture(lambda: info("should not crash"))
        self.assertIn("[INFO]", out)


# ── Phase 10: Help text ───────────────────────────────────────────────────────

class TestHelpText(unittest.TestCase):

    def _install_help(self):
        buf = io.StringIO(); old = sys.stdout; sys.stdout = buf
        try: main(["install", "--help"])
        except SystemExit: pass
        finally: sys.stdout = old
        return buf.getvalue()

    def _top_help(self):
        buf = io.StringIO(); old = sys.stdout; sys.stdout = buf
        try: main(["--help"])
        except SystemExit: pass
        finally: sys.stdout = old
        return buf.getvalue()

    def test_verbose_flag_in_install_help(self):
        self.assertIn("--verbose", self._install_help())

    def test_log_file_flag_in_install_help(self):
        self.assertIn("--log-file", self._install_help())

    def test_force_flag_has_description(self):
        help_text = self._install_help()
        self.assertIn("--force", help_text)
        # v1.9 fix: --force must have a real description, not just the flag name
        self.assertIn("Reinstall", help_text)

    def test_debug_flag_has_description(self):
        help_text = self._install_help()
        self.assertIn("--debug", help_text)
        self.assertIn("debug", help_text.lower())

    def test_install_help_has_examples_section(self):
        self.assertIn("Examples:", self._install_help())

    def test_top_help_has_examples_section(self):
        self.assertIn("Examples:", self._top_help())

    def test_top_help_examples_include_web(self):
        self.assertIn("devsetup install web", self._top_help())

    def test_top_help_examples_include_list(self):
        self.assertIn("devsetup list", self._top_help())

    def test_install_help_examples_include_yes(self):
        self.assertIn("--yes", self._install_help())

    def test_install_help_examples_include_ci_cd(self):
        self.assertIn("CI/CD", self._install_help())


# ── Phase 5: No raw print() outside logger ───────────────────────────────────

class TestNoRawPrint(unittest.TestCase):

    def test_no_raw_print_outside_logger(self):
        """All output must route through devsetup.utils.logger._emit."""
        import ast, os

        violations = []
        for root, dirs, files in os.walk("devsetup"):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                path = os.path.join(root, fname)
                if "logger.py" in path:
                    continue
                src = open(path).read()
                for node in ast.walk(ast.parse(src)):
                    if isinstance(node, ast.Call):
                        func = node.func
                        if isinstance(func, ast.Name) and func.id == "print":
                            violations.append(f"{path}:{node.lineno}")

        self.assertEqual(violations, [],
                         f"Raw print() calls found outside logger: {violations}")


# ── Phase 6: Error and warning levels ────────────────────────────────────────

class TestErrorAndWarnLevels(unittest.TestCase):

    def setUp(self):    _reset_logger()
    def tearDown(self): _reset_logger()

    def test_error_goes_to_stderr_not_stdout(self):
        buf_out, buf_err = io.StringIO(), io.StringIO()
        old = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = buf_out, buf_err
        try:
            error("test error")
        finally:
            sys.stdout, sys.stderr = old
        self.assertIn("[ERROR]", buf_err.getvalue())
        self.assertNotIn("[ERROR]", buf_out.getvalue())

    def test_info_goes_to_stdout_not_stderr(self):
        buf_out, buf_err = io.StringIO(), io.StringIO()
        old = sys.stdout, sys.stderr
        sys.stdout, sys.stderr = buf_out, buf_err
        try:
            info("test info")
        finally:
            sys.stdout, sys.stderr = old
        self.assertIn("[INFO]", buf_out.getvalue())
        self.assertNotIn("[INFO]", buf_err.getvalue())

    def test_warn_goes_to_stdout(self):
        out = _capture(lambda: warn("test warn"))
        self.assertIn("[WARN]", out)

    def test_fail_goes_to_stderr(self):
        from devsetup.utils.logger import fail
        buf = io.StringIO(); old = sys.stderr; sys.stderr = buf
        fail("test fail"); sys.stderr = old
        self.assertIn("[FAIL]", buf.getvalue())

    def test_blocked_goes_to_stderr(self):
        from devsetup.utils.logger import blocked
        buf = io.StringIO(); old = sys.stderr; sys.stderr = buf
        blocked("dep failed"); sys.stderr = old
        self.assertIn("[BLOCKED]", buf.getvalue())

    def test_invalid_goes_to_stderr(self):
        from devsetup.utils.logger import invalid
        buf = io.StringIO(); old = sys.stderr; sys.stderr = buf
        invalid("bad config"); sys.stderr = old
        self.assertIn("[INVALID]", buf.getvalue())


# ── Phase 1: logging requirements ────────────────────────────────────────────

class TestLoggingRequirements(unittest.TestCase):

    def setUp(self):    _reset_logger()
    def tearDown(self): _reset_logger()

    def test_all_log_lines_are_structured(self):
        """Every non-blank log line must match [TIMESTAMP] [LEVEL] format."""
        ps = _patches("git", detect=False, version="2.43.0")
        with ExitStack() as stack:
            for p in ps: stack.enter_context(p)
            out, _, _ = _run(["install", "--tool", "git"])
        for line in out.splitlines():
            if line.strip():
                self.assertRegex(
                    line.strip(),
                    r"^\[[\d:]{8}\] \[[A-Z]+\s*\]",
                    f"Line not structured: {line!r}",
                )

    def test_all_log_levels_use_capitalised_level_names(self):
        """[LEVEL] must always be uppercase."""
        ps = _patches("git", detect=False, version="2.43.0")
        with ExitStack() as stack:
            for p in ps: stack.enter_context(p)
            out, err, _ = _run(["install", "--tool", "git"])
        all_output = out + err
        levels = re.findall(r"\[([A-Za-z]+)\]", all_output)
        for level in levels:
            if level not in ("h", "H"):   # argparse uses [h] for metavar
                self.assertEqual(level, level.upper(),
                                 f"Level not uppercase: [{level}]")

    def test_log_output_is_deterministic_between_runs(self):
        """Same inputs must produce same log structure (not content) twice."""
        ps1 = _patches("git", detect=True, version="2.43.0")
        ps2 = _patches("git", detect=True, version="2.43.0")

        with ExitStack() as stack:
            for p in ps1: stack.enter_context(p)
            out1, _, _ = _run(["install", "--tool", "git"])

        with ExitStack() as stack:
            for p in ps2: stack.enter_context(p)
            out2, _, _ = _run(["install", "--tool", "git"])

        # Structure (levels, count) must be identical; timestamps differ
        levels1 = re.findall(r"\[([A-Z]+)\s*\]", out1)
        levels2 = re.findall(r"\[([A-Z]+)\s*\]", out2)
        self.assertEqual(levels1, levels2,
                         "Log level sequence differs between identical runs")


# ── Phase 13: Roadmap scenarios ───────────────────────────────────────────────

class TestRoadmapScenarios(unittest.TestCase):

    def setUp(self):    _reset_logger()
    def tearDown(self): _reset_logger()

    def test_scenario_1_normal_install_no_verbose(self):
        """Normal install shows standard levels only — no [VERBOSE]."""
        ps = _patches("git", detect=False, version="2.43.0")
        with ExitStack() as stack:
            for p in ps: stack.enter_context(p)
            out, _, code = _run(["install", "--tool", "git"])
        self.assertEqual(code, 0)
        self.assertNotIn("[VERBOSE]", out)
        self.assertTrue(any(tag in out for tag in ("[CHECK]", "[OK]", "[INSTALL]")))

    def test_scenario_2_verbose_install(self):
        """install --verbose shows [VERBOSE] lines."""
        ps = _patches("git", detect=False, version="2.43.0")
        with ExitStack() as stack:
            for p in ps: stack.enter_context(p)
            out, _, code = _run(["install", "--tool", "git", "--verbose"])
        self.assertEqual(code, 0)
        self.assertIn("[VERBOSE]", out)

    def test_scenario_3_noninteractive_verbose(self):
        """--yes --verbose shows [AUTO] and [VERBOSE] together."""
        ps = _patches("git", detect=False, version="2.43.0")
        with ExitStack() as stack:
            for p in ps: stack.enter_context(p)
            with patch("devsetup.core.environment_loader.load",
                       return_value={"id": "web", "name": "Web",
                                     "installers": ["git"]}):
                out, _, code = _run(["install", "web", "--yes", "--verbose"])
        self.assertEqual(code, 0)
        self.assertIn("[VERBOSE]", out)
        self.assertIn("[AUTO]",    out)

    def test_scenario_4_error_case(self):
        """Failures produce [FAIL] on stderr and exit code 1."""
        pm_err = PackageManagerError("err", pm_exit_code=1)
        ps = _patches("git", detect=False, fail_with=pm_err)
        with ExitStack() as stack:
            for p in ps: stack.enter_context(p)
            _, err, code = _run(["install", "--tool", "git"])
        self.assertEqual(code, 1)
        self.assertIn("[FAIL]", err)

    def test_scenario_5_all_log_lines_follow_format(self):
        """Every output line must match [TIMESTAMP] [LEVEL] format."""
        ps = _patches("git", detect=False, version="2.43.0")
        with ExitStack() as stack:
            for p in ps: stack.enter_context(p)
            out, _, _ = _run(["install", "--tool", "git"])
        for line in out.splitlines():
            if line.strip():
                self.assertRegex(
                    line.strip(),
                    r"^\[[\d:]{8}(\s[\d:]{10})?\] \[[A-Z]+\s*\]",
                    f"Line does not match log format: {line!r}",
                )


if __name__ == "__main__":
    unittest.main()
