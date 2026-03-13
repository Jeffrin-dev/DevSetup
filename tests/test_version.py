"""
tests.test_version
------------------
Test suite for DevSetup v1.3 — Tool Version Verification.

Covers:
  - Version parser (Phase 3 & 9)
  - InstallerResult.version field (Phase 6)
  - Post-install version verification (Phase 4 & 10)
  - Skip path version reporting (Phase 11)
  - Verification failure → FAIL result (Phase 10)
  - Version in summary output (Phase 7)
  - Timeout protection (Phase 14)
  - Debug mode version logging (Phase 12)
  - Safety wrapper _get_version (Phase 13)
"""

import io
import re
import sys
import unittest
from unittest.mock import patch, MagicMock

from devsetup.utils.version_parser import parse_version
from devsetup.installers.result import (
    InstallerResult,
    InstallerStatus,
    InstallSummary,
    ExitCode,
    ErrorCategory,
)
from devsetup.installers.manager import install_tool, _get_version, _print_summary
from devsetup.system.package_managers.base import PackageManagerError


# ── Phase 3 & 9 — Version Parser ─────────────────────────────────────────────

class TestVersionParser(unittest.TestCase):
    """parse_version() must extract clean version strings from raw output."""

    def test_git_format(self):
        self.assertEqual(parse_version("git version 2.43.0"), "2.43.0")

    def test_node_v_prefix_stripped(self):
        self.assertEqual(parse_version("v20.11.1"), "20.11.1")

    def test_python_format(self):
        self.assertEqual(parse_version("Python 3.11.7"), "3.11.7")

    def test_pip_format(self):
        raw = "pip 23.0.1 from /usr/lib/python3/dist-packages/pip (python 3.11)"
        self.assertEqual(parse_version(raw), "23.0.1")

    def test_code_format(self):
        self.assertEqual(parse_version("1.86.0\nabc123\nx64"), "1.86.0")

    def test_multiline_reads_first_line_only(self):
        raw = "1.86.0\nabc123commit\nx64"
        self.assertEqual(parse_version(raw), "1.86.0")

    def test_empty_string_returns_unknown(self):
        self.assertEqual(parse_version(""), "unknown")

    def test_none_like_whitespace_returns_unknown(self):
        self.assertEqual(parse_version("   "), "unknown")

    def test_no_version_pattern_returns_unknown(self):
        # Issue 4 fix: raw text with no digit must return 'unknown', never leak the string
        result = parse_version("something without numbers")
        self.assertEqual(result, "unknown")

    def test_two_part_version(self):
        self.assertEqual(parse_version("tool 1.0"), "1.0")

    def test_four_part_version(self):
        # VS Code-style: 1.86.0.24388.0
        self.assertEqual(parse_version("1.86.0.24388.0"), "1.86.0.24388.0")


# ── Phase 6 — InstallerResult.version field ───────────────────────────────────

class TestInstallerResultVersionField(unittest.TestCase):

    def test_success_carries_version(self):
        r = InstallerResult.success("git", version="2.43.0")
        self.assertEqual(r.version, "2.43.0")

    def test_skip_carries_version(self):
        r = InstallerResult.skip("node", version="20.11.1")
        self.assertEqual(r.version, "20.11.1")

    def test_fail_has_no_version(self):
        r = InstallerResult.fail("git", "something failed")
        self.assertIsNone(r.version)

    def test_success_version_defaults_none(self):
        r = InstallerResult.success("git")
        self.assertIsNone(r.version)

    def test_skip_version_defaults_none(self):
        r = InstallerResult.skip("git")
        self.assertIsNone(r.version)

    def test_verification_failure_exit_code(self):
        r = InstallerResult.fail(
            "node", "version check failed",
            exit_code=ExitCode.VERIFICATION_FAILURE,
            error_category=ErrorCategory.VERIFICATION_FAILURE,
        )
        self.assertEqual(r.exit_code, ExitCode.VERIFICATION_FAILURE)
        self.assertEqual(r.error_category, ErrorCategory.VERIFICATION_FAILURE)
        self.assertTrue(r.failed)


# ── Phase 11 — Skip path version reporting ────────────────────────────────────

class TestSkipPathVersionReporting(unittest.TestCase):

    def test_skip_result_contains_version(self):
        with patch("devsetup.installers.git.GitInstaller.detect", return_value=True), \
             patch("devsetup.installers.git.GitInstaller.version", return_value="2.43.0"):
            result = install_tool("git")
        self.assertEqual(result.status, InstallerStatus.SKIP)
        self.assertEqual(result.version, "2.43.0")

    def test_skip_result_version_none_when_version_raises(self):
        """If version() throws during skip, result.version is None (not a FAIL)."""
        with patch("devsetup.installers.git.GitInstaller.detect", return_value=True), \
             patch("devsetup.installers.git.GitInstaller.version",
                   side_effect=Exception("timeout")):
            result = install_tool("git")
        # Still SKIP — version failure on skip path is non-fatal
        self.assertEqual(result.status, InstallerStatus.SKIP)
        self.assertIsNone(result.version)

    def test_version_log_called_on_skip(self):
        """[VERSION] must be logged when a tool is skipped."""
        logged = []
        with patch("devsetup.installers.git.GitInstaller.detect", return_value=True), \
             patch("devsetup.installers.git.GitInstaller.version", return_value="2.43.0"), \
             patch("devsetup.installers.manager.version_log", side_effect=logged.append):
            install_tool("git")
        self.assertTrue(len(logged) > 0)
        self.assertIn("2.43.0", logged[0])


# ── Phase 4 & 10 — Post-install verification ─────────────────────────────────

class TestPostInstallVerification(unittest.TestCase):

    def test_success_result_contains_version_after_install(self):
        with patch("devsetup.installers.git.GitInstaller.detect", return_value=False), \
             patch("devsetup.installers.git.GitInstaller.install", return_value=None), \
             patch("devsetup.installers.git.GitInstaller.version", return_value="2.43.0"):
            result = install_tool("git")
        self.assertEqual(result.status, InstallerStatus.SUCCESS)
        self.assertEqual(result.version, "2.43.0")

    def test_verification_failure_after_install_returns_fail(self):
        """Phase 10 — if version() returns nothing post-install, status must be FAIL."""
        with patch("devsetup.installers.git.GitInstaller.detect", return_value=False), \
             patch("devsetup.installers.git.GitInstaller.install", return_value=None), \
             patch("devsetup.installers.git.GitInstaller.version", return_value="not installed"):
            result = install_tool("git")
        self.assertEqual(result.status, InstallerStatus.FAIL)
        self.assertEqual(result.exit_code, ExitCode.VERIFICATION_FAILURE)
        self.assertEqual(result.error_category, ErrorCategory.VERIFICATION_FAILURE)

    def test_verification_failure_when_version_raises(self):
        """Phase 14 — timeout or crash in version() is a verification failure."""
        import subprocess
        with patch("devsetup.installers.git.GitInstaller.detect", return_value=False), \
             patch("devsetup.installers.git.GitInstaller.install", return_value=None), \
             patch("devsetup.installers.git.GitInstaller.version",
                   side_effect=subprocess.TimeoutExpired("git", 5)):
            result = install_tool("git")
        self.assertEqual(result.status, InstallerStatus.FAIL)
        self.assertEqual(result.exit_code, ExitCode.VERIFICATION_FAILURE)

    def test_version_log_called_on_successful_install(self):
        """[VERSION] must be logged after successful installation."""
        logged = []
        with patch("devsetup.installers.git.GitInstaller.detect", return_value=False), \
             patch("devsetup.installers.git.GitInstaller.install", return_value=None), \
             patch("devsetup.installers.git.GitInstaller.version", return_value="2.43.0"), \
             patch("devsetup.installers.manager.version_log", side_effect=logged.append):
            install_tool("git")
        self.assertTrue(len(logged) > 0)
        self.assertIn("2.43.0", logged[0])


# ── Phase 7 — Version display in summary ─────────────────────────────────────

class TestSummaryVersionDisplay(unittest.TestCase):

    def _run_print(self, summary: InstallSummary):
        lines = []
        with patch("devsetup.installers.manager.info", side_effect=lambda m: lines.append(m)):
            _print_summary(summary)
        return "\n".join(lines)

    def test_installed_tool_shows_version(self):
        r = InstallerResult.success("git", version="2.43.0")
        s = InstallSummary(installed=["git"], result_map={"git": r})
        out = self._run_print(s)
        self.assertIn("git (2.43.0)", out)

    def test_skipped_tool_shows_version(self):
        r = InstallerResult.skip("node", version="20.11.1")
        s = InstallSummary(skipped=["node"], result_map={"node": r})
        out = self._run_print(s)
        self.assertIn("node (20.11.1)", out)

    def test_tool_without_version_shows_no_suffix(self):
        r = InstallerResult.success("git", version=None)
        s = InstallSummary(installed=["git"], result_map={"git": r})
        out = self._run_print(s)
        # Should contain the tool name but NOT a trailing '(None)'
        self.assertIn("git", out)
        self.assertNotIn("(None)", out)
        self.assertNotIn("git ()", out)

    def test_multiple_tools_all_show_versions(self):
        r_git  = InstallerResult.success("git",  version="2.43.0")
        r_node = InstallerResult.skip("node", version="20.11.1")
        s = InstallSummary(
            installed=["git"],
            skipped=["node"],
            result_map={"git": r_git, "node": r_node},
        )
        out = self._run_print(s)
        self.assertIn("git (2.43.0)", out)
        self.assertIn("node (20.11.1)", out)


# ── Phase 13 — _get_version safety ───────────────────────────────────────────

class TestGetVersionSafety(unittest.TestCase):

    def test_returns_version_string_on_success(self):
        from devsetup.installers.git import GitInstaller
        installer = GitInstaller()
        with patch.object(installer, "version", return_value="2.43.0"):
            result = _get_version(installer, "git")
        self.assertEqual(result, "2.43.0")

    def test_returns_none_when_version_raises(self):
        from devsetup.installers.git import GitInstaller
        installer = GitInstaller()
        with patch.object(installer, "version", side_effect=RuntimeError("crash")):
            result = _get_version(installer, "git")
        self.assertIsNone(result)

    def test_returns_none_when_version_returns_not_installed(self):
        from devsetup.installers.git import GitInstaller
        installer = GitInstaller()
        with patch.object(installer, "version", return_value="not installed"):
            result = _get_version(installer, "git")
        self.assertIsNone(result)

    def test_returns_none_when_version_returns_empty(self):
        from devsetup.installers.git import GitInstaller
        installer = GitInstaller()
        with patch.object(installer, "version", return_value=""):
            result = _get_version(installer, "git")
        self.assertIsNone(result)

    def test_returns_none_on_timeout(self):
        import subprocess
        from devsetup.installers.git import GitInstaller
        installer = GitInstaller()
        with patch.object(installer, "version",
                          side_effect=subprocess.TimeoutExpired("git", 5)):
            result = _get_version(installer, "git")
        self.assertIsNone(result)


# ── Phase 12 — Debug mode version logging ────────────────────────────────────

class TestDebugModeVersionLogging(unittest.TestCase):

    def test_debug_logs_parsed_version(self):
        """In debug mode, parsed version is written to debug output."""
        import os
        debug_lines = []
        from devsetup.installers.git import GitInstaller
        installer = GitInstaller()

        os.environ["DEVSETUP_DEBUG"] = "1"
        try:
            with patch.object(installer, "version", return_value="2.43.0"), \
                 patch("devsetup.installers.manager.debug",
                        side_effect=lambda m: debug_lines.append(m)):
                _get_version(installer, "git")
        finally:
            del os.environ["DEVSETUP_DEBUG"]

        self.assertTrue(
            any("2.43.0" in l for l in debug_lines),
            f"Expected version in debug lines, got: {debug_lines}",
        )


# ── ExitCode and ErrorCategory completeness ───────────────────────────────────

class TestExitCodeCompleteness(unittest.TestCase):

    def test_verification_failure_exit_code_value(self):
        self.assertEqual(ExitCode.VERIFICATION_FAILURE, 5)

    def test_verification_failure_category_string(self):
        self.assertEqual(ErrorCategory.VERIFICATION_FAILURE, "VERIFICATION_FAILURE")

    def test_all_exit_codes_distinct(self):
        codes = [
            ExitCode.SUCCESS,
            ExitCode.INSTALLATION_FAILURE,
            ExitCode.DETECTION_ERROR,
            ExitCode.UNSUPPORTED_OS,
            ExitCode.PACKAGE_MANAGER_FAILURE,
            ExitCode.VERIFICATION_FAILURE,
        ]
        self.assertEqual(len(codes), len(set(codes)))


# ── InstallSummary.result_map ─────────────────────────────────────────────────

class TestInstallSummaryResultMap(unittest.TestCase):

    def test_record_populates_result_map(self):
        s = InstallSummary()
        r = InstallerResult.success("git", version="2.43.0")
        s.record(r)
        self.assertIn("git", s.result_map)
        self.assertEqual(s.result_map["git"].version, "2.43.0")

    def test_result_map_contains_skip_result(self):
        s = InstallSummary()
        r = InstallerResult.skip("node", version="20.11.1")
        s.record(r)
        self.assertIn("node", s.result_map)
        self.assertEqual(s.result_map["node"].version, "20.11.1")

    def test_result_map_does_not_duplicate(self):
        s = InstallSummary()
        r = InstallerResult.success("git", version="2.43.0")
        s.record(r)
        s.record(r)  # duplicate — should be ignored
        self.assertEqual(len(s.result_map), 1)

    def test_result_map_preserves_all_three_statuses(self):
        s = InstallSummary()
        s.record(InstallerResult.success("git",    version="2.43.0"))
        s.record(InstallerResult.skip("node",   version="20.11.1"))
        s.record(InstallerResult.fail(
            "vscode", "boom",
            exit_code=ExitCode.VERIFICATION_FAILURE,
            error_category=ErrorCategory.VERIFICATION_FAILURE,
        ))
        self.assertEqual(len(s.result_map), 3)
        self.assertEqual(s.result_map["git"].version,  "2.43.0")
        self.assertEqual(s.result_map["node"].version, "20.11.1")
        self.assertIsNone(s.result_map["vscode"].version)


if __name__ == "__main__":
    unittest.main()
