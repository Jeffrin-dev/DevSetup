"""
tests.test_summary
------------------
Integration tests for the InstallSummary system (v1.2).

Phase 13 scenarios
------------------
  1. All tools installed
  2. All tools skipped
  3. Mixed installed / skipped
  4. Failure mid-install
  5. Empty environment

Additional unit tests cover:
  - InstallSummary.record() classification
  - Duplicate-entry guard (Phase 6)
  - Execution-order preservation (Phase 7)
  - env_name shown in output (Phase 11)
  - Count prefix (Phase 12)
  - Summary isolation from execution logic (Phase 14)
  - Exit code reflects failed list (Phase 10)
"""

import io
import re
import sys
import unittest
from contextlib import ExitStack
from unittest.mock import patch

from devsetup.installers.manager import install_environment, _print_summary
from devsetup.installers.result import (
    InstallSummary,
    InstallerResult,
    InstallerStatus,
    ExitCode,
    ErrorCategory,
)
from devsetup.system.package_managers.base import PackageManagerError


# ── Output helpers ────────────────────────────────────────────────────────────

_LOG_PREFIX = re.compile(r"^\[\d{2}:\d{2}:\d{2}\] \[[A-Z]+\]\s*")


def _strip(line: str) -> str:
    """Remove the '[HH:MM:SS] [LEVEL]   ' logger prefix from a line."""
    return _LOG_PREFIX.sub("", line)


def _content_lines(output: str):
    """Return stripped content of each non-blank output line."""
    return [_strip(l) for l in output.splitlines() if _strip(l).strip()]


def _section_content(output: str, header_prefix: str, next_header_prefix: str | None = None):
    """
    Return the stripped content lines that belong to the section
    starting with *header_prefix* and ending before *next_header_prefix*.
    """
    lines = _content_lines(output)
    try:
        start = next(i for i, l in enumerate(lines) if l.startswith(header_prefix))
    except StopIteration:
        return []
    if next_header_prefix is None:
        return lines[start + 1:]
    try:
        end = next(i for i, l in enumerate(lines[start + 1:], start + 1)
                   if l.startswith(next_header_prefix))
        return lines[start + 1:end]
    except StopIteration:
        return lines[start + 1:]


def _run_env(tools, tool_patches_list, env_name="Test Env"):
    """
    Run install_environment with a list of pre-built patch objects.
    Returns (captured_output: str, exception: RuntimeError | None).
    """
    buf = io.StringIO()
    old_out, old_err = sys.stdout, sys.stderr
    sys.stdout = buf
    sys.stderr = buf
    exc_caught = None
    try:
        with ExitStack() as stack:
            for p in tool_patches_list:
                stack.enter_context(p)
            install_environment(tools, env_name=env_name)
    except RuntimeError as e:
        exc_caught = e
    finally:
        sys.stdout = old_out
        sys.stderr = old_err
    return buf.getvalue(), exc_caught


def _patches_for(tool: str, *, detect: bool, fail_with=None):
    """Return a list of patch objects for a single tool."""
    cls_map = {
        "git":    "devsetup.installers.git.GitInstaller",
        "node":   "devsetup.installers.node.NodeInstaller",
        "python": "devsetup.installers.python.PythonInstaller",
        "pip":    "devsetup.installers.pip.PipInstaller",
        "vscode": "devsetup.installers.vscode.VSCodeInstaller",
    }
    base = cls_map[tool]
    p = [
        patch(f"{base}.detect",  return_value=detect),
        patch(f"{base}.version", return_value="1.0.0"),
        patch(f"{base}.install",
              side_effect=fail_with if fail_with is not None else None,
              return_value=None if fail_with is None else ...),
    ]
    return p


# ── Unit: InstallSummary ──────────────────────────────────────────────────────

class TestInstallSummaryUnit(unittest.TestCase):

    def _r(self, tool, status, exit_code=0, category=None):
        return InstallerResult(
            installer_id=tool, status=status, exit_code=exit_code,
            message=f"{tool} {status.value}", error_category=category,
        )

    def test_record_success(self):
        s = InstallSummary()
        s.record(self._r("git", InstallerStatus.SUCCESS))
        self.assertIn("git", s.installed)
        self.assertNotIn("git", s.skipped)
        self.assertIsNone(s.failed_result)

    def test_record_skip(self):
        s = InstallSummary()
        s.record(self._r("node", InstallerStatus.SKIP))
        self.assertIn("node", s.skipped)
        self.assertNotIn("node", s.installed)

    def test_record_fail(self):
        s = InstallSummary()
        r = self._r("python", InstallerStatus.FAIL, exit_code=4,
                    category=ErrorCategory.PACKAGE_MANAGER_ERROR)
        s.record(r)
        self.assertIsNotNone(s.failed_result)
        self.assertEqual(s.failed_result.installer_id, "python")
        self.assertTrue(s.has_failure)

    def test_duplicate_guard(self):
        """Phase 6 — same tool recorded twice must not create duplicate entries."""
        s = InstallSummary()
        r = self._r("git", InstallerStatus.SUCCESS)
        s.record(r)
        s.record(r)
        self.assertEqual(s.installed.count("git"), 1)

    def test_execution_order_preserved(self):
        """Phase 7 — installed list must reflect the order tools were recorded."""
        s = InstallSummary()
        for tool in ["vscode", "git", "node"]:
            s.record(self._r(tool, InstallerStatus.SUCCESS))
        self.assertEqual(s.installed, ["vscode", "git", "node"])

    def test_total_run_counts_all_buckets(self):
        s = InstallSummary()
        s.record(self._r("git",    InstallerStatus.SUCCESS))
        s.record(self._r("node",   InstallerStatus.SKIP))
        s.record(self._r("python", InstallerStatus.FAIL, exit_code=1,
                          category=ErrorCategory.INSTALLER_FAILURE))
        self.assertEqual(s.total_run, 3)

    def test_has_failure_false_on_clean_run(self):
        s = InstallSummary()
        s.record(self._r("git",  InstallerStatus.SUCCESS))
        s.record(self._r("node", InstallerStatus.SKIP))
        self.assertFalse(s.has_failure)


# ── Unit: _print_summary output format ───────────────────────────────────────

class TestPrintSummaryFormat(unittest.TestCase):

    def _run_print(self, summary):
        """Call _print_summary and return the raw text it would log."""
        lines = []
        with patch("devsetup.installers.manager.info", side_effect=lambda m: lines.append(m)):
            _print_summary(summary)
        return "\n".join(lines)

    def test_env_name_shown_in_header(self):
        """Phase 11 — environment name must appear above Installation Summary."""
        s = InstallSummary(env_name="Web")
        out = self._run_print(s)
        self.assertIn("Environment: Web", out)
        self.assertLess(out.index("Environment: Web"), out.index("Installation Summary"))

    def test_env_name_omitted_when_none(self):
        s = InstallSummary(env_name=None)
        out = self._run_print(s)
        self.assertNotIn("Environment:", out)

    def test_installed_count_prefix(self):
        """Phase 12 — non-empty installed list shows '(N)' count."""
        s = InstallSummary(installed=["git", "node"])
        out = self._run_print(s)
        self.assertIn("Installed (2):", out)

    def test_skipped_count_prefix(self):
        s = InstallSummary(skipped=["vscode"])
        out = self._run_print(s)
        self.assertIn("Skipped (1):", out)

    def test_empty_installed_shows_none(self):
        s = InstallSummary()
        out = self._run_print(s)
        lines = out.splitlines()
        inst_idx = next(i for i, l in enumerate(lines) if l.startswith("Installed"))
        below = [l.strip() for l in lines[inst_idx + 1:] if l.strip()]
        self.assertEqual(below[0], "none")

    def test_empty_skipped_shows_none(self):
        s = InstallSummary()
        out = self._run_print(s)
        lines = out.splitlines()
        skip_idx = next(i for i, l in enumerate(lines) if l.startswith("Skipped"))
        below = [l.strip() for l in lines[skip_idx + 1:] if l.strip()]
        self.assertEqual(below[0], "none")

    def test_failed_shows_none_when_clean(self):
        s = InstallSummary()
        out = self._run_print(s)
        lines = out.splitlines()
        fail_idx = next(i for i, l in enumerate(lines) if l.strip() == "Failed:")
        below = [l.strip() for l in lines[fail_idx + 1:] if l.strip()]
        self.assertEqual(below[0], "none")

    def test_failed_shows_tool_with_details(self):
        """Phase 9 — failure highlighted with installer ID, exit code, category."""
        fr = InstallerResult.fail(
            "node", "pm error",
            exit_code=ExitCode.PACKAGE_MANAGER_FAILURE,
            error_category=ErrorCategory.PACKAGE_MANAGER_ERROR,
        )
        s = InstallSummary(failed_result=fr)
        out = self._run_print(s)
        self.assertIn("node", out)
        self.assertIn("exit_code=4", out)
        self.assertIn("PACKAGE_MANAGER_ERROR", out)

    def test_fixed_section_order(self):
        """Phase 5 — Installed before Skipped before Failed in output."""
        s = InstallSummary(installed=["git"], skipped=["node"])
        out = self._run_print(s)
        self.assertLess(out.index("Installed"), out.index("Skipped"))
        self.assertLess(out.index("Skipped"),   out.index("Failed"))


# ── Integration: Phase 13 scenarios ──────────────────────────────────────────

class TestSummaryIntegration(unittest.TestCase):
    """Phase 13 — five pipeline scenarios each producing a correct summary."""

    def test_scenario_all_installed(self):
        """All three tools install successfully."""
        patches = (
            _patches_for("git",    detect=False)
            + _patches_for("node",   detect=False)
            + _patches_for("vscode", detect=False)
        )
        out, exc = _run_env(["git", "node", "vscode"], patches)

        self.assertIsNone(exc, f"Expected no exception, got: {exc}")
        cl = _content_lines(out)

        self.assertTrue(any("Installed (3):" in l for l in cl), f"Count prefix missing: {cl}")
        self.assertTrue(any(l.strip() == "git"    for l in cl))
        self.assertTrue(any(l.strip() == "node"   for l in cl))
        self.assertTrue(any(l.strip() == "vscode" for l in cl))

        skipped_body = _section_content(out, "Skipped", "Failed")
        self.assertTrue(any("none" in l for l in skipped_body),
                        f"Skipped should show none: {skipped_body}")

        failed_body = _section_content(out, "Failed:")
        self.assertTrue(any("none" in l for l in failed_body),
                        f"Failed should show none: {failed_body}")

    def test_scenario_all_skipped(self):
        """All tools already installed — all three skipped."""
        patches = (
            _patches_for("git",    detect=True)
            + _patches_for("node",   detect=True)
            + _patches_for("vscode", detect=True)
        )
        out, exc = _run_env(["git", "node", "vscode"], patches)
        cl = _content_lines(out)

        self.assertIsNone(exc)
        self.assertTrue(any("Skipped (3):" in l for l in cl),
                        f"Skipped (3): missing from: {cl}")

        inst_body = _section_content(out, "Installed", "Skipped")
        self.assertTrue(any("none" in l for l in inst_body),
                        f"Installed should show none: {inst_body}")

    def test_scenario_mixed_installed_and_skipped(self):
        """git installs fresh; node is skipped; vscode installs fresh."""
        patches = (
            _patches_for("git",    detect=False)
            + _patches_for("node",   detect=True)
            + _patches_for("vscode", detect=False)
        )
        out, exc = _run_env(["git", "node", "vscode"], patches)
        cl = _content_lines(out)

        self.assertIsNone(exc)
        self.assertTrue(any("Installed (2):" in l for l in cl))
        self.assertTrue(any("Skipped (1):"   in l for l in cl))

    def test_scenario_failure_mid_install(self):
        """Phase 4 — git ok, node fails → summary still prints; vscode never runs."""
        pm_err = PackageManagerError("network error", pm_exit_code=1)
        patches = (
            _patches_for("git",    detect=False)
            + _patches_for("node",   detect=False, fail_with=pm_err)
            + _patches_for("vscode", detect=False)
        )
        out, exc = _run_env(["git", "node", "vscode"], patches)

        # Pipeline stopped with RuntimeError naming the failed tool
        self.assertIsNotNone(exc)
        self.assertIn("node", str(exc))

        # Summary must have been printed despite the failure
        self.assertIn("Installation Summary", out)

        cl = _content_lines(out)
        # git installed
        self.assertTrue(any("Installed (1):" in l for l in cl))
        # node in Failed section
        failed_body = _section_content(out, "Failed:")
        self.assertTrue(any("node" in l for l in failed_body),
                        f"node missing from Failed: {failed_body}")

        # vscode must NOT appear in Installed or Skipped sections
        inst_body   = _section_content(out, "Installed", "Skipped")
        skipped_body = _section_content(out, "Skipped",  "Failed:")
        self.assertFalse(any("vscode" in l for l in inst_body),
                         "vscode should not be in Installed")
        self.assertFalse(any("vscode" in l for l in skipped_body),
                         "vscode should not be in Skipped")

    def test_scenario_empty_environment(self):
        """Empty tool list — summary prints all sections showing 'none'."""
        out, exc = _run_env([], [], env_name="Empty")
        self.assertIsNone(exc)
        cl = _content_lines(out)

        self.assertTrue(any("Installation Summary" in l for l in cl))
        self.assertTrue(any("Environment: Empty" in l for l in cl))
        # All three sections present
        for section in ("Installed", "Skipped", "Failed"):
            self.assertTrue(any(section in l for l in cl), f"{section} section missing")
        # All three show 'none'
        none_count = sum(1 for l in cl if l.strip() == "none")
        self.assertEqual(none_count, 3, f"Expected 3 × 'none', got {none_count}: {cl}")

    def test_env_name_appears_in_summary_output(self):
        """Phase 11 — environment name is printed in summary block."""
        patches = _patches_for("git", detect=False)
        out, _ = _run_env(["git"], patches, env_name="Web")
        self.assertIn("Environment: Web", out)

    def test_execution_order_in_output(self):
        """Phase 7 — tools appear in the order they were installed."""
        patches = (
            _patches_for("vscode", detect=False)
            + _patches_for("git",    detect=False)
            + _patches_for("node",   detect=False)
        )
        out, _ = _run_env(["vscode", "git", "node"], patches)
        cl = _content_lines(out)

        inst_start = next(i for i, l in enumerate(cl) if "Installed" in l)
        skip_start = next(i for i, l in enumerate(cl) if "Skipped"   in l)
        installed_items = [l.strip() for l in cl[inst_start + 1:skip_start]
                           if l.strip() and l.strip() != "none"]
        self.assertEqual(installed_items, ["vscode", "git", "node"])


# ── Phase 14: Summary isolation ───────────────────────────────────────────────

class TestSummaryIsolation(unittest.TestCase):
    """Phase 14 — summary generation must not affect installation logic."""

    def test_summary_does_not_influence_pipeline_flow(self):
        """Replacing _print_summary must not change which installers run."""
        from devsetup.installers import manager as m

        install_calls = []

        def fake_install_tool(tool_name, force=False):
            install_calls.append(tool_name)
            return InstallerResult.success(tool_name)

        summary_calls = []
        orig_print = m._print_summary
        m._print_summary = lambda s: summary_calls.append(s)
        try:
            with patch.object(m, "install_tool",        side_effect=fake_install_tool), \
                 patch.object(m, "get_os",              return_value="linux"), \
                 patch.object(m, "get_package_manager", return_value="apt"):
                m.install_environment(["git", "node", "vscode"])
        finally:
            m._print_summary = orig_print

        self.assertEqual(install_calls, ["git", "node", "vscode"])
        self.assertEqual(len(summary_calls), 1)
        self.assertIsInstance(summary_calls[0], InstallSummary)

    def test_summary_receives_accurate_results(self):
        """_print_summary receives an InstallSummary that accurately reflects outcomes."""
        from devsetup.installers import manager as m

        captured = []
        orig_print = m._print_summary
        m._print_summary = lambda s: captured.append(s)
        pm_err = PackageManagerError("err", pm_exit_code=1)
        try:
            with patch("devsetup.installers.git.GitInstaller.detect",        return_value=False), \
                 patch("devsetup.installers.git.GitInstaller.install",        return_value=None), \
                 patch("devsetup.installers.node.NodeInstaller.detect",       return_value=True), \
                 patch("devsetup.installers.node.NodeInstaller.version",      return_value="20.x"), \
                 patch("devsetup.installers.vscode.VSCodeInstaller.detect",   return_value=False), \
                 patch("devsetup.installers.vscode.VSCodeInstaller.install",  side_effect=pm_err):
                m.install_environment(["git", "node", "vscode"])
        except RuntimeError:
            pass
        finally:
            m._print_summary = orig_print

        self.assertEqual(len(captured), 1)
        s = captured[0]
        self.assertIn("git",  s.installed)
        self.assertIn("node", s.skipped)
        self.assertIsNotNone(s.failed_result)
        self.assertEqual(s.failed_result.installer_id, "vscode")


# ── Phase 10: Exit code integration ──────────────────────────────────────────

class TestExitCodeIntegration(unittest.TestCase):
    """Phase 10 — CLI exit code must be 0 when no failures, 1 otherwise."""

    def test_exit_0_when_no_failures(self):
        from devsetup.cli.main import main
        with patch("devsetup.core.environment_loader.load",
                   return_value={"id": "web", "name": "Web", "installers": ["git"]}), \
             patch("devsetup.installers.manager.install_environment", return_value=None):
            code = main(["install", "web"])
        self.assertEqual(code, 0)

    def test_exit_1_when_failure_present(self):
        from devsetup.cli.main import main
        with patch("devsetup.core.environment_loader.load",
                   return_value={"id": "web", "name": "Web", "installers": ["git"]}), \
             patch("devsetup.installers.manager.install_environment",
                   side_effect=RuntimeError(
                       "Installation stopped: git failed (exit_code=1, category=INSTALLER_FAILURE)."
                   )):
            code = main(["install", "web"])
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main()
