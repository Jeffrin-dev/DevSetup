"""
tests.test_installers
---------------------
Functional tests for installer modules.
Tests detection and interface contract without executing actual installs.
"""

import unittest
from unittest.mock import patch
from devsetup.installers.base import BaseInstaller
from devsetup.installers.git import GitInstaller
from devsetup.installers.node import NodeInstaller
from devsetup.installers.python import PythonInstaller
from devsetup.installers.pip import PipInstaller
from devsetup.installers.vscode import VSCodeInstaller
from devsetup.installers.manager import (
    get_installer, install_tool, is_registered,
)

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


class TestInstallToolSafety(unittest.TestCase):

    def test_skips_when_detected(self):
        with patch("devsetup.installers.git.GitInstaller.detect", return_value=True), \
             patch("devsetup.installers.git.GitInstaller.version", return_value="2.43.0"), \
             patch("devsetup.installers.git.GitInstaller.install") as mock_install:
            result = install_tool("git")
            self.assertEqual(result, "skipped")
            mock_install.assert_not_called()

    def test_installs_when_not_detected(self):
        with patch("devsetup.installers.git.GitInstaller.detect", return_value=False), \
             patch("devsetup.installers.git.GitInstaller.install") as mock_install:
            mock_install.return_value = None
            result = install_tool("git")
            self.assertEqual(result, "installed")
            mock_install.assert_called_once()

    def test_force_reinstalls_even_when_detected(self):
        with patch("devsetup.installers.git.GitInstaller.detect", return_value=True), \
             patch("devsetup.installers.git.GitInstaller.version", return_value="2.43.0"), \
             patch("devsetup.installers.git.GitInstaller.install") as mock_install:
            mock_install.return_value = None
            result = install_tool("git", force=True)
            self.assertEqual(result, "installed")
            mock_install.assert_called_once()

    def test_returns_failed_on_exception(self):
        with patch("devsetup.installers.git.GitInstaller.detect", return_value=False), \
             patch("devsetup.installers.git.GitInstaller.install",
                   side_effect=RuntimeError("boom")):
            result = install_tool("git")
            self.assertEqual(result, "failed")


if __name__ == "__main__":
    unittest.main()
