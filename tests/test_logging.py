"""
tests.test_logging
-------------------
Tests for DevSetup v1.8 logging improvements.

Coverage:
  Phase 1  — logging requirements: structured, levelled, timestamped
  Phase 2  — Logger module: set_verbose, set_log_file, verbose()
  Phase 3  — Structured format: [TIMESTAMP] [LEVEL] Message
  Phase 4  — --verbose on install command: VERBOSE messages appear
  Phase 5  — no raw print() outside logger.py
  Phase 6  — error/warning log levels work correctly
  Phase 7  — full timestamp (YYYY-MM-DD HH:MM:SS) in verbose mode
  Phase 8  — per-tool logging: start, skip, success, failure, version
  Phase 9  — verbose + --yes combination
  Phase 10 — help text includes --verbose and --log-file
  Phase 11 — VERBOSE level gated on verbose mode; INFO/WARN/ERROR always shown
  Phase 12 — --log-file tees output to file
  Phase 13 — all 5 roadmap test scenarios
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

    def setUp(self):
        _reset_logger()

    def tearDown(self):
        _reset_logger()

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

    def setUp(self):
        _reset_logger()

    def tearDown(self):
        _reset_logger()

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
        """Normal mode: HH:MM:SS (no date part)."""
        set_verbose(False)
        ts = _timestamp()
        self.assertRegex(ts, r"^\d{2}:\d{2}:\d{2}$")

    def test_normal_log_contains_short_timestamp(self):
        set_verbose(False)
        out = _capture(lambda: info("msg"))
        self.assertRegex(out.strip(), r"^\[\d{2}:\d{2}:\d{2}\]")


# ── Phase 7: Timestamp handling ───────────────────────────────────────────────

class TestTimestamps(unittest.TestCase):

    def setUp(self):
        _reset_logger()

    def tearDown(self):
        _reset_logger()

    def test_verbose_timestamp_is_full(self):
        """_timestamp_full() always returns YYYY-MM-DD HH:MM:SS for VERBOSE lines."""
        from devsetup.utils.logger import _timestamp_full
        ts = _timestamp_full()
        self.assertRegex(ts, r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")

    def test_normal_timestamp_always_short(self):
        """_timestamp() always returns HH:MM:SS regardless of verbose mode."""
        for v in (True, False):
            set_verbose(v)
            ts = _timestamp()
            self.assertRegex(ts, r"^\d{2}:\d{2}:\d{2}$",
                             f"Short timestamp broken when verbose={v}")

    def test_info_always_has_short_timestamp(self):
        """[INFO] lines always use short timestamp even in verbose mode."""
        for v in (True, False):
            set_verbose(v)
            out = _capture(lambda: info("msg"))
            self.assertRegex(out.strip(), r"^\[\d{2}:\d{2}:\d{2}\]",
                             f"Short timestamp broken for INFO when verbose={v}")

    def test_verbose_line_has_full_timestamp(self):
        """[VERBOSE] lines use full YYYY-MM-DD HH:MM:SS timestamp."""
        set_verbose(True)
        out = _capture(lambda: verbose("detail"))
        self.assertRegex(out.strip(), r"^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\]")

    def test_normal_mode_no_date_in_timestamp(self):
        set_verbose(False)
        out = _capture(lambda: info("msg"))
        self.assertNotRegex(out.strip(), r"^\[\d{4}-")

    def test_timestamp_cross_platform(self):
        """Timestamp must not raise on any supported platform."""
        from devsetup.utils.logger import _timestamp_full
        for v in (True, False):
            set_verbose(v)
            try:
                ts = _timestamp()
                tsf = _timestamp_full()
                self.assertIsInstance(ts, str)
                self.assertIsInstance(tsf, str)
            except Exception as e:
                self.fail(f"timestamp raised with verbose={v}: {e}")


# ── Phase 4: --verbose on install command ────────────────────────────────────

class TestVerboseInstallFlag(unittest.TestCase):

    def setUp(self):
        _reset_logger()

    def tearDown(self):
        _reset_logger()

    def test_verbose_flag_accepted_on_install(self):
        with patch("devsetup.core.environment_loader.load",
                   return_value={"id": "web", "name": "Web",
                                 "installers": ["git"]}), \
             patch("devsetup.installers.manager.install_environment"):
            _, _, code = _run(["install", "web", "--verbose"])
        self.assertEqual(code, 0)

    def test_verbose_flag_sets_verbose_mode(self):
        captured = []
        orig = log_module._is_verbose

        def spy():
            result = orig()
            captured.append(result)
            return result

        with patch.object(log_module, "_is_verbose", side_effect=spy), \
             patch("devsetup.core.environment_loader.load",
                   return_value={"id": "web", "name": "Web",
                                 "installers": ["git"]}), \
             patch("devsetup.installers.manager.install_environment"):
            _run(["install", "web", "--verbose"])

        # set_verbose(True) was called, so subsequent _is_verbose() should be True
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

    def test_verbose_shows_full_timestamp(self):
        """[VERBOSE] lines must carry a full YYYY-MM-DD timestamp."""
        ps = _patches("git", detect=False, version="2.43.0")
        with ExitStack() as stack:
            for p in ps:
                stack.enter_context(p)
            out, _, _ = _run(["install", "--tool", "git", "--verbose"])
        # Only VERBOSE lines have full timestamp — other levels keep HH:MM:SS
        verbose_lines = [l for l in out.splitlines() if "[VERBOSE]" in l]
        self.assertTrue(len(verbose_lines) > 0, "Expected at least one [VERBOSE] line")
        for line in verbose_lines:
            self.assertRegex(line.strip(),
                             r"^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\]")

    def test_verbose_dep_resolution_logged(self):
        """Verbose install must show [VERBOSE] dep resolution messages."""
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
        # Dependency resolver messages
        self.assertIn("DependencyResolver", out)


# ── Phase 11: Log level gating ───────────────────────────────────────────────

class TestLogLevelGating(unittest.TestCase):

    def setUp(self):
        _reset_logger()

    def tearDown(self):
        _reset_logger()

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

    def test_normal_install_no_verbose_lines(self):
        ps = _patches("git", detect=False, version="2.43.0")
        with ExitStack() as stack:
            for p in ps:
                stack.enter_context(p)
            out, _, _ = _run(["install", "--tool", "git"])
        self.assertNotIn("[VERBOSE]", out)

    def test_verbose_install_has_verbose_lines(self):
        ps = _patches("git", detect=False, version="2.43.0")
        with ExitStack() as stack:
            for p in ps:
                stack.enter_context(p)
            out, _, _ = _run(["install", "--tool", "git", "--verbose"])
        self.assertIn("[VERBOSE]", out)


# ── Phase 8: Per-tool logging ─────────────────────────────────────────────────

class TestPerToolLogging(unittest.TestCase):

    def setUp(self):
        _reset_logger()

    def tearDown(self):
        _reset_logger()

    def test_install_start_logged(self):
        ps = _patches("git", detect=False, version="2.43.0")
        with ExitStack() as stack:
            for p in ps: stack.enter_context(p)
            out, _, _ = _run(["install", "--tool", "git"])
        self.assertIn("[INSTALL]", out)

    def test_skip_logged_when_detected(self):
        ps = _patches("git", detect=True, version="2.43.0")
        with ExitStack() as stack:
            for p in ps: stack.enter_context(p)
            out, _, _ = _run(["install", "--tool", "git"])
        self.assertIn("[SKIP]", out)

    def test_success_logged_on_install(self):
        ps = _patches("git", detect=False, version="2.43.0")
        with ExitStack() as stack:
            for p in ps: stack.enter_context(p)
            out, _, _ = _run(["install", "--tool", "git"])
        self.assertIn("[OK]", out)

    def test_failure_logged_on_error(self):
        pm_err = PackageManagerError("apt error", pm_exit_code=1)
        ps = _patches("git", detect=False, fail_with=pm_err)
        with ExitStack() as stack:
            for p in ps: stack.enter_context(p)
            _, err, _ = _run(["install", "--tool", "git"])
        self.assertIn("[FAIL]", err)

    def test_version_logged_after_install(self):
        ps = _patches("git", detect=False, version="2.43.0")
        with ExitStack() as stack:
            for p in ps: stack.enter_context(p)
            out, _, _ = _run(["install", "--tool", "git"])
        self.assertIn("[VERSION]", out)
        self.assertIn("2.43.0", out)

    def test_version_logged_in_verbose_mode(self):
        """Verbose mode shows [VERBOSE] version detection detail."""
        ps = _patches("git", detect=False, version="2.43.0")
        with ExitStack() as stack:
            for p in ps: stack.enter_context(p)
            out, _, _ = _run(["install", "--tool", "git", "--verbose"])
        self.assertIn("Version detected", out)
        self.assertIn("2.43.0", out)


# ── Phase 9: Verbose + non-interactive ───────────────────────────────────────

class TestVerboseWithYes(unittest.TestCase):

    def setUp(self):
        _reset_logger()

    def tearDown(self):
        _reset_logger()

    def test_verbose_yes_combination_exits_0(self):
        with patch("devsetup.core.environment_loader.load",
                   return_value={"id": "web", "name": "Web",
                                 "installers": ["git"]}), \
             patch("devsetup.installers.manager.install_environment"):
            _, _, code = _run(["install", "web", "--yes", "--verbose"])
        self.assertEqual(code, 0)

    def test_verbose_yes_shows_auto_and_verbose(self):
        ps = _patches("git", detect=False, version="2.43.0")
        with ExitStack() as stack:
            for p in ps: stack.enter_context(p)
            with patch("devsetup.core.environment_loader.load",
                       return_value={"id": "web", "name": "Web",
                                     "installers": ["git"]}):
                out, _, _ = _run(["install", "web", "--yes", "--verbose"])
        self.assertIn("[AUTO]",    out)
        self.assertIn("[VERBOSE]", out)

    def test_skipped_tools_logged_with_verbose_yes(self):
        ps = _patches("git", detect=True, version="2.43.0")
        with ExitStack() as stack:
            for p in ps: stack.enter_context(p)
            with patch("devsetup.core.environment_loader.load",
                       return_value={"id": "web", "name": "Web",
                                     "installers": ["git"]}):
                out, _, _ = _run(["install", "web", "--yes", "--verbose"])
        self.assertIn("[SKIP]", out)


# ── Phase 12: Log file output ─────────────────────────────────────────────────

class TestLogFile(unittest.TestCase):

    def setUp(self):
        _reset_logger()

    def tearDown(self):
        _reset_logger()

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
            with open(path, "r") as fh:
                contents = fh.read()
            self.assertGreater(len(contents.strip()), 0)
            # CHECK/OK/VERSION are the levels emitted by install --tool
            self.assertTrue(
                any(tag in contents for tag in ("[CHECK]", "[OK]", "[INSTALL]")),
                f"No expected log tags found in file: {contents[:200]}",
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
                out, _, _ = _run(["install", "--tool", "git",
                                   "--log-file", path])
            with open(path, "r") as fh:
                file_contents = fh.read()
            # Both console and file should have content
            self.assertGreater(len(out.strip()), 0)
            self.assertGreater(len(file_contents.strip()), 0)
        finally:
            os.unlink(path)

    def test_log_file_contains_install_log(self):
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

    def test_invalid_log_file_does_not_crash(self):
        """A bad log file path must not crash the install."""
        set_log_file("/nonexistent_dir/devsetup_test.log")
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

    def test_verbose_flag_in_install_help(self):
        self.assertIn("--verbose", self._install_help())

    def test_log_file_flag_in_install_help(self):
        self.assertIn("--log-file", self._install_help())

    def test_verbose_description_in_help(self):
        help_text = self._install_help().lower()
        self.assertIn("verbose", help_text)

    def test_log_file_description_in_help(self):
        help_text = self._install_help().lower()
        self.assertIn("log", help_text)


# ── Phase 5: No raw print() outside logger ───────────────────────────────────

class TestNoRawPrint(unittest.TestCase):

    def test_logger_uses_emit_not_print(self):
        """logger.py must route everything through _emit, not raw print()."""
        import inspect, devsetup.utils.logger as lg
        src = inspect.getsource(lg)
        lines = src.splitlines()
        emit_body = False
        in_docstring = False
        violations = []
        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            # Track docstring boundaries
            if stripped.count('"""') % 2 == 1:
                in_docstring = not in_docstring
            if in_docstring or stripped.startswith("#"):
                continue
            if "def _emit(" in stripped:
                emit_body = True
            elif stripped.startswith("def ") and emit_body:
                emit_body = False
            if not emit_body and "print(" in stripped:
                violations.append(f"line {i}: {stripped}")
        self.assertEqual(violations, [],
                         f"Raw print() outside _emit: {violations}")


# ── Phase 13: Roadmap test scenarios ─────────────────────────────────────────

class TestRoadmapScenarios(unittest.TestCase):

    def setUp(self):
        _reset_logger()

    def tearDown(self):
        _reset_logger()

    def test_scenario_1_normal_install_no_verbose(self):
        """Scenario 1: normal install → only INFO, WARN, ERROR shown."""
        ps = _patches("git", detect=False, version="2.43.0")
        with ExitStack() as stack:
            for p in ps: stack.enter_context(p)
            out, _, code = _run(["install", "--tool", "git"])
        self.assertEqual(code, 0)
        self.assertNotIn("[VERBOSE]", out)
        # install --tool emits CHECK/INSTALL/OK — not [INFO] for single-tool path
        self.assertTrue(
            any(tag in out for tag in ("[CHECK]", "[OK]", "[INSTALL]")),
        )

    def test_scenario_2_verbose_install(self):
        """Scenario 2: install with --verbose → VERBOSE messages appear."""
        ps = _patches("git", detect=False, version="2.43.0")
        with ExitStack() as stack:
            for p in ps: stack.enter_context(p)
            out, _, code = _run(["install", "--tool", "git", "--verbose"])
        self.assertEqual(code, 0)
        self.assertIn("[VERBOSE]", out)

    def test_scenario_3_noninteractive_verbose(self):
        """Scenario 3: --yes --verbose → detailed automated log."""
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
        """Scenario 4: error cases → proper messages and codes."""
        pm_err = PackageManagerError("err", pm_exit_code=1)
        ps = _patches("git", detect=False, fail_with=pm_err)
        with ExitStack() as stack:
            for p in ps: stack.enter_context(p)
            _, err, code = _run(["install", "--tool", "git"])
        self.assertEqual(code, 1)
        self.assertIn("[FAIL]", err)

    def test_scenario_5_logs_consistent(self):
        """Scenario 5: all log lines follow [TIMESTAMP] [LEVEL] format."""
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
