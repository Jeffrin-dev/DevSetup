"""
tests.test_installers
---------------------
Functional tests for installer modules.
Tests detection, interface contract, skip/install/force/fail logic,
and failure simulation for all error categories.
"""

import subprocess
import unittest
from unittest.mock import patch, MagicMock

from devsetup.installers.base import BaseInstaller
from devsetup.installers.git import GitInstaller
from devsetup.installers.node import NodeInstaller
from devsetup.installers.python import PythonInstaller
from devsetup.installers.pip import PipInstaller
from devsetup.installers.vscode import VSCodeInstaller
from devsetup.installers.manager import (
    get_installer, install_tool, is_registered,
)
from devsetup.installers.result import (
    InstallerResult, InstallerStatus, ExitCode, ErrorCategory,
)
from devsetup.system.package_managers.base import PackageManagerError

ALL_INSTALLERS = [GitInstaller, NodeInstaller, PythonInstaller, PipInstaller, VSCodeInstaller]
ALL_TOOL_NAMES = ["git", "node", "python", "pip", "vscode"]


class TestInstallerInterface(unittest.TestCase):
    """All installers must implement the standard BaseInstaller interface."""

    def test_all_subclass_base_installer(self):
        for cls in ALL_INSTALLERS:
            with self.subTest(cls=cls.__name__):
                self.assertTrue(issubclass(cls, BaseInstaller))

    def test_all_have_tool_name(self):
        for cls in ALL_INSTALLERS:
            with self.subTest(cls=cls.__name__):
                self.assertIsInstance(cls.tool_name, str)
                self.assertGreater(len(cls.tool_name), 0)

    def test_detect_returns_bool(self):
        for cls in ALL_INSTALLERS:
            with self.subTest(cls=cls.__name__):
                result = cls().detect()
                self.assertIsInstance(result, bool)

    def test_version_returns_string(self):
        for cls in ALL_INSTALLERS:
            with self.subTest(cls=cls.__name__):
                result = cls().version()
                self.assertIsInstance(result, str)

    def test_version_when_not_installed_returns_string(self):
        for cls in ALL_INSTALLERS:
            with self.subTest(cls=cls.__name__):
                installer = cls()
                with patch.object(installer, "detect", return_value=False):
                    result = installer.version()
                    self.assertIsInstance(result, str)


class TestRegistry(unittest.TestCase):

    def test_known_tools_are_registered(self):
        for tool in ALL_TOOL_NAMES:
            with self.subTest(tool=tool):
                self.assertTrue(is_registered(tool))

    def test_unknown_tool_not_registered(self):
        self.assertFalse(is_registered("unknowntool_xyz_999"))

    def test_get_installer_returns_base_installer(self):
        for tool in ALL_TOOL_NAMES:
            with self.subTest(tool=tool):
                installer = get_installer(tool)
                self.assertIsInstance(installer, BaseInstaller)

    def test_get_installer_unknown_raises_key_error(self):
        with self.assertRaises(KeyError):
            get_installer("unknowntool_xyz_999")


class TestInstallerResult(unittest.TestCase):
    """InstallerResult named constructors and properties."""

    def test_success_result(self):
        r = InstallerResult.success("git", "git installed.")
        self.assertEqual(r.status, InstallerStatus.SUCCESS)
        self.assertEqual(r.exit_code, ExitCode.SUCCESS)
        self.assertEqual(r.installer_id, "git")
        self.assertIsNone(r.error_category)
        self.assertTrue(r.succeeded)
        self.assertFalse(r.failed)

    def test_skip_result(self):
        r = InstallerResult.skip("git", "git already installed.")
        self.assertEqual(r.status, InstallerStatus.SKIP)
        self.assertEqual(r.exit_code, ExitCode.SUCCESS)
        self.assertTrue(r.succeeded)
        self.assertFalse(r.failed)

    def test_fail_result_defaults(self):
        r = InstallerResult.fail("git", "Something went wrong.")
        self.assertEqual(r.status, InstallerStatus.FAIL)
        self.assertEqual(r.exit_code, ExitCode.INSTALLATION_FAILURE)
        self.assertEqual(r.error_category, ErrorCategory.INSTALLER_FAILURE)
        self.assertFalse(r.succeeded)
        self.assertTrue(r.failed)

    def test_fail_result_pm_category(self):
        r = InstallerResult.fail(
            "git", "apt failed",
            exit_code=ExitCode.PACKAGE_MANAGER_FAILURE,
            error_category=ErrorCategory.PACKAGE_MANAGER_ERROR,
        )
        self.assertEqual(r.exit_code, ExitCode.PACKAGE_MANAGER_FAILURE)
        self.assertEqual(r.error_category, ErrorCategory.PACKAGE_MANAGER_ERROR)


class TestInstallToolSafety(unittest.TestCase):
    """install_tool() skip / install / force / fail paths."""

    def test_returns_installer_result(self):
        with patch("devsetup.installers.git.GitInstaller.detect", return_value=True), \
             patch("devsetup.installers.git.GitInstaller.version", return_value="2.x"):
            result = install_tool("git")
            self.assertIsInstance(result, InstallerResult)

    def test_skips_when_detected(self):
        with patch("devsetup.installers.git.GitInstaller.detect", return_value=True), \
             patch("devsetup.installers.git.GitInstaller.version", return_value="2.43.0"), \
             patch("devsetup.installers.git.GitInstaller.install") as mock_install:
            result = install_tool("git")
            self.assertEqual(result.status, InstallerStatus.SKIP)
            self.assertTrue(result.succeeded)
            mock_install.assert_not_called()

    def test_installs_when_not_detected(self):
        with patch("devsetup.installers.git.GitInstaller.detect", return_value=False), \
             patch("devsetup.installers.git.GitInstaller.install") as mock_install:
            mock_install.return_value = None
            result = install_tool("git")
            self.assertEqual(result.status, InstallerStatus.SUCCESS)
            self.assertTrue(result.succeeded)
            mock_install.assert_called_once()

    def test_force_reinstalls_even_when_detected(self):
        with patch("devsetup.installers.git.GitInstaller.detect", return_value=True), \
             patch("devsetup.installers.git.GitInstaller.version", return_value="2.43.0"), \
             patch("devsetup.installers.git.GitInstaller.install") as mock_install:
            mock_install.return_value = None
            result = install_tool("git", force=True)
            self.assertEqual(result.status, InstallerStatus.SUCCESS)
            mock_install.assert_called_once()

    def test_returns_fail_on_generic_exception(self):
        with patch("devsetup.installers.git.GitInstaller.detect", return_value=False), \
             patch("devsetup.installers.git.GitInstaller.install",
                   side_effect=Exception("boom")):
            result = install_tool("git")
            self.assertEqual(result.status, InstallerStatus.FAIL)
            self.assertTrue(result.failed)
            self.assertEqual(result.error_category, ErrorCategory.INSTALLER_FAILURE)


class TestFailureSimulation(unittest.TestCase):
    """
    Phase 11 — Failure simulation tests.
    Confirms engine stops correctly and errors propagate with proper categories.
    """

    def test_package_manager_error_gives_pm_category(self):
        """PM returns non-zero exit code → PACKAGE_MANAGER_ERROR."""
        pm_err = PackageManagerError("apt returned exit code 1", pm_exit_code=1)
        with patch("devsetup.installers.git.GitInstaller.detect", return_value=False), \
             patch("devsetup.installers.git.GitInstaller.install",
                   side_effect=pm_err):
            result = install_tool("git")
            self.assertTrue(result.failed)
            self.assertEqual(result.exit_code, ExitCode.PACKAGE_MANAGER_FAILURE)
            self.assertEqual(result.error_category, ErrorCategory.PACKAGE_MANAGER_ERROR)

    def test_command_not_found_gives_correct_category(self):
        """Binary missing on PATH → COMMAND_NOT_FOUND."""
        with patch("devsetup.installers.git.GitInstaller.detect", return_value=False), \
             patch("devsetup.installers.git.GitInstaller.install",
                   side_effect=FileNotFoundError("sudo: not found")):
            result = install_tool("git")
            self.assertTrue(result.failed)
            self.assertEqual(result.exit_code, ExitCode.INSTALLATION_FAILURE)
            self.assertEqual(result.error_category, ErrorCategory.COMMAND_NOT_FOUND)

    def test_unsupported_os_gives_correct_exit_code(self):
        """Installer raises RuntimeError with unsupported OS message."""
        with patch("devsetup.installers.git.GitInstaller.detect", return_value=False), \
             patch("devsetup.installers.git.GitInstaller.install",
                   side_effect=RuntimeError("Cannot install git on unsupported OS: freebsd")):
            result = install_tool("git")
            self.assertTrue(result.failed)
            self.assertEqual(result.exit_code, ExitCode.UNSUPPORTED_OS)
            self.assertEqual(result.error_category, ErrorCategory.OS_NOT_SUPPORTED)

    def test_permission_denied_via_pm_error(self):
        """Permission denied wraps as PackageManagerError."""
        pm_err = PackageManagerError("Permission denied running: sudo apt-get install git", pm_exit_code=-1)
        with patch("devsetup.installers.git.GitInstaller.detect", return_value=False), \
             patch("devsetup.installers.git.GitInstaller.install",
                   side_effect=pm_err):
            result = install_tool("git")
            self.assertTrue(result.failed)
            self.assertEqual(result.error_category, ErrorCategory.PACKAGE_MANAGER_ERROR)

    def test_pipeline_stops_at_first_failure(self):
        """install_environment() must stop after first FAIL; subsequent tools not run."""
        git_calls = []
        node_calls = []

        def git_install():
            git_calls.append(1)
            raise PackageManagerError("network error", pm_exit_code=1)

        def node_install():
            node_calls.append(1)

        with patch("devsetup.installers.git.GitInstaller.detect", return_value=False), \
             patch("devsetup.installers.git.GitInstaller.install", side_effect=git_install), \
             patch("devsetup.installers.node.NodeInstaller.detect", return_value=False), \
             patch("devsetup.installers.node.NodeInstaller.install", side_effect=node_install):
            from devsetup.installers.manager import install_environment
            with self.assertRaises(RuntimeError) as ctx:
                install_environment(["git", "node"])

        self.assertEqual(len(git_calls), 1)
        self.assertEqual(len(node_calls), 0)
        self.assertIn("git", str(ctx.exception))

    def test_pipeline_failure_raises_runtime_error_with_exit_code(self):
        """RuntimeError message from install_environment includes exit_code and category."""
        pm_err = PackageManagerError("apt error", pm_exit_code=1)
        with patch("devsetup.installers.git.GitInstaller.detect", return_value=False), \
             patch("devsetup.installers.git.GitInstaller.install", side_effect=pm_err):
            from devsetup.installers.manager import install_environment
            with self.assertRaises(RuntimeError) as ctx:
                install_environment(["git"])
        msg = str(ctx.exception)
        self.assertIn("exit_code", msg)
        self.assertIn("category", msg)

    def test_detection_failure_returns_fail_result(self):
        """detect() throwing an exception returns FAIL with DETECTION_ERROR exit code."""
        with patch("devsetup.installers.git.GitInstaller.detect",
                   side_effect=OSError("proc error")):
            result = install_tool("git")
            self.assertTrue(result.failed)
            self.assertEqual(result.exit_code, ExitCode.DETECTION_ERROR)

    def test_invalid_package_name_via_pm_error(self):
        """PM returns non-zero for unknown package name."""
        pm_err = PackageManagerError(
            "apt command failed: sudo apt-get install -y notapackage",
            pm_exit_code=100,
        )
        with patch("devsetup.installers.git.GitInstaller.detect", return_value=False), \
             patch("devsetup.installers.git.GitInstaller.install", side_effect=pm_err):
            result = install_tool("git")
            self.assertTrue(result.failed)
            self.assertEqual(result.exit_code, ExitCode.PACKAGE_MANAGER_FAILURE)
            self.assertEqual(result.error_category, ErrorCategory.PACKAGE_MANAGER_ERROR)


class TestPackageManagerError(unittest.TestCase):
    """PackageManagerError carries exit code and formats cleanly."""

    def test_carries_pm_exit_code(self):
        err = PackageManagerError("something failed", pm_exit_code=1)
        self.assertEqual(err.pm_exit_code, 1)

    def test_str_includes_exit_code_when_nonnegative(self):
        err = PackageManagerError("something failed", pm_exit_code=4)
        self.assertIn("exit code", str(err).lower())
        self.assertIn("4", str(err))

    def test_str_omits_exit_code_when_minus_one(self):
        err = PackageManagerError("binary not found", pm_exit_code=-1)
        self.assertNotIn("exit code: -1", str(err))

    def test_is_runtime_error(self):
        err = PackageManagerError("x")
        self.assertIsInstance(err, RuntimeError)


if __name__ == "__main__":
    unittest.main()
