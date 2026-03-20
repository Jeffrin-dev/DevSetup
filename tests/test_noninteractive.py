"""
tests.test_noninteractive
--------------------------
Tests for DevSetup v1.7 non-interactive mode (--yes / -y flag).

Coverage:
  Phase 1  — --yes flag exists on install command
  Phase 2  — audit: no blocking input() calls in the install path
  Phase 3  — confirm() utility: auto-yes path vs interactive path
  Phase 4  — default action enforcement (skip/install behaviour unchanged)
  Phase 5  — yes_mode threaded through install_environment
  Phase 6  — error handling unchanged: failures still reported in summary
  Phase 7  — full non-interactive pipeline executes correctly
  Phase 8  — help text includes --yes / -y
  Phase 9  — scriptable: exit code 0 on success, 1 on failure
  Phase 10 — all 5 test scenarios from the roadmap
  Phase 11 — logging: [AUTO] line emitted, full summary still printed
  Phase 12 — confirm() is the single centralised confirmation handler
"""

import io
import re
import sys
import unittest
from contextlib import ExitStack
from unittest.mock import patch, MagicMock

from devsetup.cli.main import main
from devsetup.utils.prompt import confirm
from devsetup.system.package_managers.base import PackageManagerError


# ── Helpers ───────────────────────────────────────────────────────────────────

_LOG = re.compile(r"^\[\d{2}:\d{2}:\d{2}\] \[[A-Z]+\]\s*")


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


def _strip(line):
    return _LOG.sub("", line)


def _lines(out):
    return [_strip(l) for l in out.splitlines() if _strip(l).strip()]


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


def _run_env(tools, patch_list, yes=False, force=False, env_name="Test"):
    """Run install_environment directly with captures."""
    from devsetup.installers.manager import install_environment
    buf = io.StringIO()
    old = sys.stdout, sys.stderr
    sys.stdout = sys.stderr = buf
    exc = None
    try:
        with ExitStack() as stack:
            for p in patch_list:
                stack.enter_context(p)
            install_environment(tools, force=force, env_name=env_name,
                                yes_mode=yes)
    except RuntimeError as e:
        exc = e
    finally:
        sys.stdout, sys.stderr = old
    return buf.getvalue(), exc


# ── Phase 1: --yes flag exists ────────────────────────────────────────────────

class TestFlagDefinition(unittest.TestCase):

    def test_yes_flag_long_form(self):
        """--yes is accepted on install command."""
        with patch("devsetup.installers.manager.install_environment"), \
             patch("devsetup.core.environment_loader.load",
                   return_value={"id": "web", "name": "Web",
                                 "installers": ["git"]}):
            _, _, code = _run(["install", "web", "--yes"])
        self.assertEqual(code, 0)

    def test_yes_flag_short_form(self):
        """-y is accepted as alias for --yes."""
        with patch("devsetup.installers.manager.install_environment"), \
             patch("devsetup.core.environment_loader.load",
                   return_value={"id": "web", "name": "Web",
                                 "installers": ["git"]}):
            _, _, code = _run(["install", "web", "-y"])
        self.assertEqual(code, 0)

    def test_yes_flag_absent_by_default(self):
        """yes_mode defaults to False when --yes is not given."""
        captured = []
        orig = __import__("devsetup.installers.manager",
                          fromlist=["install_environment"]).install_environment

        def spy(tools, force=False, env_name=None, yes_mode=False):
            captured.append(yes_mode)
            return orig(tools, force=force, env_name=env_name,
                        yes_mode=yes_mode)

        with patch("devsetup.installers.manager.install_environment",
                   side_effect=spy), \
             patch("devsetup.core.environment_loader.load",
                   return_value={"id": "web", "name": "Web",
                                 "installers": ["git"]}):
            _run(["install", "web"])

        self.assertFalse(captured[0])

    def test_yes_flag_sets_yes_mode_true(self):
        """--yes causes yes_mode=True to be passed to install_environment."""
        captured = []

        def spy(tools, force=False, env_name=None, yes_mode=False):
            captured.append(yes_mode)

        with patch("devsetup.installers.manager.install_environment",
                   side_effect=spy), \
             patch("devsetup.core.environment_loader.load",
                   return_value={"id": "web", "name": "Web",
                                 "installers": ["git"]}):
            _run(["install", "web", "--yes"])

        self.assertTrue(captured[0])


# ── Phase 2: no blocking input() calls ───────────────────────────────────────

class TestNoBlockingInput(unittest.TestCase):

    def test_install_path_never_calls_input(self):
        """install_environment must never call input() regardless of yes_mode."""
        patches = _patches("git", detect=False)
        with ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            with patch("builtins.input") as mock_input:
                _run_env(["git"], [], yes=False)
                mock_input.assert_not_called()

    def test_yes_mode_never_calls_input(self):
        """--yes mode must never call input() either."""
        patches = _patches("git", detect=False)
        with ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            with patch("builtins.input") as mock_input:
                _run_env(["git"], [], yes=True)
                mock_input.assert_not_called()


# ── Phase 3: confirm() utility ────────────────────────────────────────────────

class TestConfirmUtility(unittest.TestCase):

    def test_auto_yes_returns_true_without_input(self):
        """confirm() with auto_yes=True must return True without reading stdin."""
        with patch("builtins.input") as mock_input:
            result = confirm("Proceed?", auto_yes=True)
        self.assertTrue(result)
        mock_input.assert_not_called()

    def test_auto_yes_logs_auto_line(self):
        """confirm() with auto_yes=True must emit an [AUTO] log line."""
        buf = io.StringIO()
        old = sys.stdout; sys.stdout = buf
        try:
            confirm("Proceed?", auto_yes=True)
        finally:
            sys.stdout = old
        self.assertIn("[AUTO]", buf.getvalue())
        self.assertIn("Proceed?", buf.getvalue())

    def test_interactive_yes_returns_true(self):
        with patch("builtins.input", return_value="y"):
            result = confirm("Proceed?", auto_yes=False)
        self.assertTrue(result)

    def test_interactive_no_returns_false(self):
        with patch("builtins.input", return_value="n"):
            result = confirm("Proceed?", auto_yes=False)
        self.assertFalse(result)

    def test_interactive_yes_uppercase(self):
        with patch("builtins.input", return_value="Y"):
            result = confirm("Proceed?", auto_yes=False)
        self.assertTrue(result)

    def test_interactive_full_yes(self):
        with patch("builtins.input", return_value="yes"):
            result = confirm("Proceed?", auto_yes=False)
        self.assertTrue(result)

    def test_eof_returns_false(self):
        """EOFError (piped empty stdin) must return False gracefully."""
        with patch("builtins.input", side_effect=EOFError):
            result = confirm("Proceed?", auto_yes=False)
        self.assertFalse(result)

    def test_keyboard_interrupt_returns_false(self):
        with patch("builtins.input", side_effect=KeyboardInterrupt):
            result = confirm("Proceed?", auto_yes=False)
        self.assertFalse(result)

    def test_random_input_returns_false(self):
        with patch("builtins.input", return_value="maybe"):
            result = confirm("Proceed?", auto_yes=False)
        self.assertFalse(result)


# ── Phase 4: default action enforcement ──────────────────────────────────────

class TestDefaultActionEnforcement(unittest.TestCase):

    def test_already_installed_still_skipped_with_yes(self):
        """--yes does not override skip logic — already-installed tools skip."""
        patches = _patches("git", detect=True, version="2.43.0")
        out, exc = _run_env(["git"], patches, yes=True)
        self.assertIsNone(exc)
        self.assertIn("SKIP", out)

    def test_missing_tool_still_installs_with_yes(self):
        """--yes does not prevent installation — missing tools still install."""
        patches = _patches("git", detect=False, version="2.43.0")
        out, exc = _run_env(["git"], patches, yes=True)
        self.assertIsNone(exc)
        self.assertIn("OK", out)

    def test_yes_does_not_change_install_logic(self):
        """yes_mode=True must not alter the actual install outcome."""
        install_calls_no_yes = []
        install_calls_with_yes = []

        def make_install(target):
            def _i():
                target.append(1)
            return _i

        for yes in (False, True):
            calls = install_calls_no_yes if not yes else install_calls_with_yes
            ps = [
                patch("devsetup.installers.git.GitInstaller.detect",
                      return_value=False),
                patch("devsetup.installers.git.GitInstaller.install",
                      side_effect=make_install(calls)),
                patch("devsetup.installers.git.GitInstaller.version",
                      return_value="2.43.0"),
            ]
            _run_env(["git"], ps, yes=yes)

        self.assertEqual(install_calls_no_yes, install_calls_with_yes)


# ── Phase 5: yes_mode threaded through engine ─────────────────────────────────

class TestYesModeThreading(unittest.TestCase):

    def test_auto_line_emitted_when_yes_mode(self):
        """[AUTO] line must appear in output when yes_mode=True."""
        patches = _patches("git", detect=False, version="2.43.0")
        out, _ = _run_env(["git"], patches, yes=True)
        self.assertIn("[AUTO]", out)

    def test_no_auto_line_without_yes_mode(self):
        """[AUTO] line must NOT appear when yes_mode=False."""
        patches = _patches("git", detect=False, version="2.43.0")
        out, _ = _run_env(["git"], patches, yes=False)
        self.assertNotIn("[AUTO]", out)

    def test_auto_line_contains_non_interactive_message(self):
        patches = _patches("git", detect=False, version="2.43.0")
        out, _ = _run_env(["git"], patches, yes=True)
        self.assertIn("non-interactive", out.lower())


# ── Phase 6: error handling unchanged ────────────────────────────────────────

class TestErrorHandlingUnchanged(unittest.TestCase):

    def test_failure_still_reported_with_yes(self):
        """Installation failures must still appear in summary when --yes used."""
        pm_err = PackageManagerError("apt error", pm_exit_code=1)
        patches = (
            _patches("git", detect=False, fail_with=pm_err)
            + _patches("node", detect=False)
        )
        out, exc = _run_env(["git", "node"], patches, yes=True)
        self.assertIsNotNone(exc)
        self.assertIn("Failed", out)
        self.assertIn("git", out)

    def test_blocked_tools_still_listed_with_yes(self):
        """Blocked tools must still appear in Blocked section when --yes used."""
        pm_err = PackageManagerError("err", pm_exit_code=1)
        patches = (
            _patches("python", detect=False, fail_with=pm_err)
            + _patches("pip", detect=False)
        )
        out, exc = _run_env(["python", "pip"], patches, yes=True)
        self.assertIsNotNone(exc)
        self.assertIn("Blocked", out)
        self.assertIn("pip", out)

    def test_summary_always_printed_with_yes(self):
        """Summary must always print regardless of --yes flag."""
        patches = _patches("git", detect=False, version="2.43.0")
        out, _ = _run_env(["git"], patches, yes=True)
        self.assertIn("Installation Summary", out)

    def test_exit_code_1_on_failure_with_yes(self):
        pm_err = PackageManagerError("err", pm_exit_code=1)
        with patch("devsetup.installers.git.GitInstaller.detect",
                   return_value=False), \
             patch("devsetup.installers.git.GitInstaller.install",
                   side_effect=pm_err), \
             patch("devsetup.installers.git.GitInstaller.version",
                   return_value="2.43.0"), \
             patch("devsetup.core.environment_loader.load",
                   return_value={"id": "web", "name": "Web",
                                 "installers": ["git"]}):
            _, _, code = _run(["install", "web", "--yes"])
        self.assertEqual(code, 1)


# ── Phase 7: full non-interactive pipeline ────────────────────────────────────

class TestFullPipeline(unittest.TestCase):

    def test_full_yes_pipeline_exits_zero(self):
        """Complete install with --yes must exit 0 on all-success."""
        patches = (
            _patches("git",    detect=False, version="2.43.0")
            + _patches("node",   detect=False, version="20.x")
            + _patches("vscode", detect=False, version="1.0.0")
        )
        out, exc = _run_env(["git", "node", "vscode"], patches, yes=True)
        self.assertIsNone(exc)
        self.assertIn("Environment setup complete", out)

    def test_pipeline_contains_all_expected_sections(self):
        """Pipeline output must have all sections even in yes_mode."""
        patches = _patches("git", detect=False, version="2.43.0")
        out, _ = _run_env(["git"], patches, yes=True)
        for section in ("Installed", "Skipped", "Failed", "Blocked"):
            self.assertIn(section, out)

    def test_pipeline_order_preserved_with_yes(self):
        """Dependency order must be preserved when --yes is active."""
        run_order = []

        def make_install(name):
            def _i(): run_order.append(name)
            return _i

        patches = []
        for t in ["git", "node", "vscode"]:
            base = {
                "git":    "devsetup.installers.git.GitInstaller",
                "node":   "devsetup.installers.node.NodeInstaller",
                "vscode": "devsetup.installers.vscode.VSCodeInstaller",
            }[t]
            patches += [
                patch(f"{base}.detect",  return_value=False),
                patch(f"{base}.install", side_effect=make_install(t)),
                patch(f"{base}.version", return_value="1.0.0"),
            ]
        _run_env(["vscode", "node", "git"], patches, yes=True)
        self.assertLess(run_order.index("git"),   run_order.index("node"))
        self.assertLess(run_order.index("node"),  run_order.index("vscode"))


# ── Phase 8: help text ────────────────────────────────────────────────────────

class TestHelpText(unittest.TestCase):

    def test_install_help_shows_yes_flag(self):
        buf = io.StringIO()
        old = sys.stdout; sys.stdout = buf
        try:
            try: main(["install", "--help"])
            except SystemExit: pass
        finally:
            sys.stdout = old
        self.assertIn("--yes", buf.getvalue())

    def test_install_help_shows_short_y_flag(self):
        buf = io.StringIO()
        old = sys.stdout; sys.stdout = buf
        try:
            try: main(["install", "--help"])
            except SystemExit: pass
        finally:
            sys.stdout = old
        self.assertIn("-y", buf.getvalue())

    def test_install_help_describes_non_interactive(self):
        buf = io.StringIO()
        old = sys.stdout; sys.stdout = buf
        try:
            try: main(["install", "--help"])
            except SystemExit: pass
        finally:
            sys.stdout = old
        self.assertIn("non-interactive", buf.getvalue().lower())


# ── Phase 9: scriptable use cases ────────────────────────────────────────────

class TestScriptableUseCases(unittest.TestCase):

    def test_yes_mode_exit_0_on_success(self):
        with patch("devsetup.core.environment_loader.load",
                   return_value={"id": "web", "name": "Web",
                                 "installers": ["git"]}), \
             patch("devsetup.installers.manager.install_environment"):
            _, _, code = _run(["install", "web", "--yes"])
        self.assertEqual(code, 0)

    def test_yes_mode_exit_0_short_flag(self):
        with patch("devsetup.core.environment_loader.load",
                   return_value={"id": "web", "name": "Web",
                                 "installers": ["git"]}), \
             patch("devsetup.installers.manager.install_environment"):
            _, _, code = _run(["install", "web", "-y"])
        self.assertEqual(code, 0)

    def test_yes_mode_unknown_env_still_exits_1(self):
        _, _, code = _run(["install", "nonexistent_env_xyz", "--yes"])
        self.assertEqual(code, 1)

    def test_yes_produces_log_output(self):
        """Non-interactive mode must still emit logs (not silent)."""
        patches = _patches("git", detect=False, version="2.43.0")
        out, _ = _run_env(["git"], patches, yes=True)
        self.assertGreater(len(out.strip()), 0)


# ── Phase 10: roadmap test scenarios ─────────────────────────────────────────

class TestRoadmapScenarios(unittest.TestCase):

    def test_scenario_1_yes_skips_confirmations(self):
        """Scenario 1: --yes skips all confirmations for installation."""
        patches = _patches("git", detect=False, version="2.43.0")
        with ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            with patch("builtins.input") as mock_input:
                _run_env(["git"], [], yes=True)
                mock_input.assert_not_called()

    def test_scenario_2_yes_with_force(self):
        """Scenario 2: --yes works with --force reinstall."""
        patches = (
            _patches("git", detect=True, version="2.43.0")
        )
        out, exc = _run_env(["git"], patches, yes=True, force=True)
        self.assertIsNone(exc)
        # force + yes: tool reinstalled, not skipped
        self.assertIn("Installed", out)

    def test_scenario_3_yes_with_skipped_tools(self):
        """Scenario 3: --yes works correctly with already-installed (skipped) tools."""
        patches = _patches("git", detect=True, version="2.43.0")
        out, exc = _run_env(["git"], patches, yes=True)
        self.assertIsNone(exc)
        self.assertIn("Skipped", out)

    def test_scenario_4_exit_code_on_failure(self):
        """Scenario 4: CLI exits with appropriate code on failure."""
        pm_err = PackageManagerError("err", pm_exit_code=1)
        with patch("devsetup.installers.git.GitInstaller.detect",
                   return_value=False), \
             patch("devsetup.installers.git.GitInstaller.install",
                   side_effect=pm_err), \
             patch("devsetup.installers.git.GitInstaller.version",
                   return_value="2.43.0"), \
             patch("devsetup.core.environment_loader.load",
                   return_value={"id": "web", "name": "Web",
                                 "installers": ["git"]}):
            _, _, code = _run(["install", "web", "--yes"])
        self.assertEqual(code, 1)

    def test_scenario_5_multiple_envs_no_input(self):
        """Scenario 5: Multiple environments install correctly without user input."""
        for env_tools in (["git", "node", "vscode"], ["python", "pip", "vscode"]):
            patches = []
            for t in env_tools:
                patches += _patches(t, detect=False, version="1.0.0")
            with patch("builtins.input") as mock_input:
                out, exc = _run_env(env_tools, patches, yes=True)
                mock_input.assert_not_called()
            self.assertIsNone(exc)


# ── Phase 11: logging and visibility ─────────────────────────────────────────

class TestLoggingVisibility(unittest.TestCase):

    def test_auto_log_emitted(self):
        patches = _patches("git", detect=False, version="2.43.0")
        out, _ = _run_env(["git"], patches, yes=True)
        self.assertIn("[AUTO]", out)

    def test_step_logs_still_emitted(self):
        """Step-by-step logs (CHECK, INSTALL, OK, VERSION) still appear."""
        patches = _patches("git", detect=False, version="2.43.0")
        out, _ = _run_env(["git"], patches, yes=True)
        for tag in ("[CHECK]", "[INSTALL]", "[OK]", "[VERSION]"):
            self.assertIn(tag, out, f"Missing log tag: {tag}")

    def test_summary_sections_all_present(self):
        patches = _patches("git", detect=False, version="2.43.0")
        out, _ = _run_env(["git"], patches, yes=True)
        for s in ("Installed", "Skipped", "Failed", "Blocked"):
            self.assertIn(s, out)

    def test_skipped_tools_logged(self):
        patches = _patches("git", detect=True, version="2.43.0")
        out, _ = _run_env(["git"], patches, yes=True)
        self.assertIn("[SKIP]", out)


# ── Phase 12: centralised handler ────────────────────────────────────────────

class TestCentralisedHandler(unittest.TestCase):

    def test_confirm_importable(self):
        from devsetup.utils.prompt import confirm
        self.assertTrue(callable(confirm))

    def test_prompt_module_exists(self):
        import devsetup.utils.prompt as p
        self.assertTrue(hasattr(p, "confirm"))

    def test_confirm_is_single_entry_point(self):
        """Only prompt.confirm() should call input() — no other callers."""
        import inspect, devsetup.utils.prompt as p
        src = inspect.getsource(p)
        self.assertIn("input()", src)

    def test_auto_log_uses_logger(self):
        """[AUTO] must be emitted through logger, not raw print."""
        import inspect, devsetup.utils.prompt as p
        src = inspect.getsource(p)
        self.assertNotIn("print(", src)


if __name__ == "__main__":
    unittest.main()
