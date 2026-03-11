"""
tests.test_cli
--------------
Functional tests for CLI commands.
Tests the CLI layer without executing actual installations.
"""

import unittest
from unittest.mock import patch
from devsetup.cli.main import main


class TestCLIHelp(unittest.TestCase):

    def test_help_exits_zero(self):
        with self.assertRaises(SystemExit) as ctx:
            main(["--help"])
        self.assertEqual(ctx.exception.code, 0)

    def test_version_exits_zero(self):
        with self.assertRaises(SystemExit) as ctx:
            main(["--version"])
        self.assertEqual(ctx.exception.code, 0)

    def test_no_command_returns_zero(self):
        result = main([])
        self.assertEqual(result, 0)


class TestCLIList(unittest.TestCase):

    def test_list_exits_zero(self):
        result = main(["list"])
        self.assertEqual(result, 0)


class TestCLIInstall(unittest.TestCase):

    def test_install_unknown_environment_returns_nonzero(self):
        result = main(["install", "nonexistent_env_xyz"])
        self.assertNotEqual(result, 0)

    def test_install_unknown_tool_returns_nonzero(self):
        result = main(["install", "--tool", "unknowntool999"])
        self.assertNotEqual(result, 0)

    def test_install_force_flag_forwarded(self):
        with patch("devsetup.installers.manager.install_environment") as mock_env, \
             patch("devsetup.core.environment_loader.load") as mock_load:
            mock_env.return_value = None
            mock_load.return_value = {
                "id": "web", "name": "Web", "installers": ["git"]
            }
            main(["install", "web", "--force"])
            mock_env.assert_called_once_with(["git"], force=True)

    def test_install_without_force_defaults_false(self):
        with patch("devsetup.installers.manager.install_environment") as mock_env, \
             patch("devsetup.core.environment_loader.load") as mock_load:
            mock_env.return_value = None
            mock_load.return_value = {
                "id": "web", "name": "Web", "installers": ["git"]
            }
            main(["install", "web"])
            mock_env.assert_called_once_with(["git"], force=False)


class TestCLIInfo(unittest.TestCase):

    def test_info_known_tool_exits_zero(self):
        result = main(["info", "git"])
        self.assertEqual(result, 0)

    def test_info_unknown_tool_returns_nonzero(self):
        result = main(["info", "unknowntool999"])
        self.assertNotEqual(result, 0)


if __name__ == "__main__":
    unittest.main()
