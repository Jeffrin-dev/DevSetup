"""
tests.test_config
-----------------
Functional tests for environment configuration loading and validation.
"""

import json
import os
import unittest
from devsetup.core.environment_loader import load, list_available
from devsetup.system.environment_validator import (
    validate, validate_no_duplicates, EnvironmentValidationError,
)


class TestEnvironmentLoader(unittest.TestCase):

    def test_load_web_succeeds(self):
        env = load("web")
        self.assertEqual(env["id"], "web")
        self.assertIn("installers", env)
        self.assertIsInstance(env["installers"], list)

    def test_load_python_succeeds(self):
        env = load("python")
        self.assertEqual(env["id"], "python")

    def test_load_nonexistent_raises_file_not_found(self):
        with self.assertRaises(FileNotFoundError) as ctx:
            load("nonexistent_xyz_999")
        self.assertIn("not found", str(ctx.exception).lower())

    def test_load_error_is_actionable(self):
        with self.assertRaises(FileNotFoundError) as ctx:
            load("nonexistent_xyz_999")
        self.assertIn("devsetup list", str(ctx.exception))

    def test_list_available_returns_list(self):
        envs = list_available()
        self.assertIsInstance(envs, list)
        self.assertGreater(len(envs), 0)

    def test_list_available_contains_known_envs(self):
        envs = list_available()
        self.assertIn("web", envs)
        self.assertIn("python", envs)


class TestEnvironmentValidator(unittest.TestCase):

    VALID = {
        "schema": "1.0",
        "id": "test",
        "name": "Test",
        "installers": ["git"],
    }

    def test_valid_config_passes(self):
        validate(self.VALID.copy(), "test.json")  # must not raise

    def test_missing_id_raises(self):
        data = {k: v for k, v in self.VALID.items() if k != "id"}
        with self.assertRaises(EnvironmentValidationError) as ctx:
            validate(data, "test.json")
        self.assertIn("id", str(ctx.exception))

    def test_missing_installers_raises(self):
        data = {k: v for k, v in self.VALID.items() if k != "installers"}
        with self.assertRaises(EnvironmentValidationError) as ctx:
            validate(data, "test.json")
        self.assertIn("installers", str(ctx.exception))

    def test_missing_schema_raises(self):
        data = {k: v for k, v in self.VALID.items() if k != "schema"}
        with self.assertRaises(EnvironmentValidationError) as ctx:
            validate(data, "test.json")
        self.assertIn("schema", str(ctx.exception))

    def test_unsupported_schema_version_raises(self):
        data = {**self.VALID, "schema": "9.9"}
        with self.assertRaises(EnvironmentValidationError) as ctx:
            validate(data, "test.json")
        self.assertIn("schema", str(ctx.exception).lower())

    def test_empty_installers_raises(self):
        data = {**self.VALID, "installers": []}
        with self.assertRaises(EnvironmentValidationError) as ctx:
            validate(data, "test.json")
        self.assertIn("empty", str(ctx.exception))

    def test_unknown_installer_raises(self):
        data = {**self.VALID, "installers": ["docker"]}
        with self.assertRaises(EnvironmentValidationError) as ctx:
            validate(data, "test.json")
        self.assertIn("docker", str(ctx.exception))

    def test_unknown_installer_error_is_actionable(self):
        data = {**self.VALID, "installers": ["docker"]}
        with self.assertRaises(EnvironmentValidationError) as ctx:
            validate(data, "test.json")
        # Error message should name the unknown installer
        self.assertIn("docker", str(ctx.exception))

    def test_installers_not_list_raises(self):
        data = {**self.VALID, "installers": "git"}
        with self.assertRaises(EnvironmentValidationError) as ctx:
            validate(data, "test.json")
        self.assertIn("list", str(ctx.exception))


class TestDuplicateProtection(unittest.TestCase):

    def test_first_id_passes(self):
        seen: set = set()
        validate_no_duplicates("web", seen, "web.json")  # must not raise

    def test_duplicate_id_raises(self):
        seen = {"web"}
        with self.assertRaises(EnvironmentValidationError) as ctx:
            validate_no_duplicates("web", seen, "web-dup.json")
        self.assertIn("web", str(ctx.exception))
        self.assertIn("Duplicate", str(ctx.exception))


class TestMalformedJSON(unittest.TestCase):

    def test_malformed_json_skipped_without_crash(self):
        import tempfile
        import devsetup.core.environment_loader as loader
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmp:
            bad = os.path.join(tmp, "bad.json")
            with open(bad, "w") as f:
                f.write("{bad json")

            with patch.object(loader, "_config_dir", return_value=tmp):
                envs = list_available()
            self.assertEqual(envs, [])


if __name__ == "__main__":
    unittest.main()


class TestPluginLoader(unittest.TestCase):
    """Rule 7 — Plugin system must be sandboxed."""

    def _run_with_dir(self, plugin_dir):
        import devsetup.core.plugin_loader as pl
        orig = pl._PLUGIN_DIR
        pl._PLUGIN_DIR = plugin_dir
        try:
            from devsetup.core.plugin_loader import load_plugins
            registry = {}
            load_plugins(registry)
            return registry
        finally:
            pl._PLUGIN_DIR = orig

    def test_missing_plugin_dir_does_not_crash(self):
        """load_plugins() with no plugin dir must not raise."""
        import devsetup.core.plugin_loader as pl
        orig = pl._PLUGIN_DIR
        pl._PLUGIN_DIR = "/nonexistent/path/devsetup/plugins_xyz"
        try:
            from devsetup.core.plugin_loader import load_plugins
            load_plugins({})  # must not raise
        finally:
            pl._PLUGIN_DIR = orig

    def test_crashing_plugin_does_not_crash_devsetup(self):
        """A plugin that raises on import must be skipped; DevSetup continues."""
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmp:
            open(os.path.join(tmp, 'crash.py'), 'w').write(
                'raise RuntimeError("deliberate crash")'
            )
            open(os.path.join(tmp, 'good.py'), 'w').write(
                'def register(r): r["mytool"] = object'
            )
            result = self._run_with_dir(tmp)
            self.assertIn("mytool", result, "Good plugin must still load after bad one")

    def test_plugin_cannot_overwrite_core_tool(self):
        """A plugin attempting to register over a core tool ID must be blocked."""
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmp:
            open(os.path.join(tmp, 'evil.py'), 'w').write(
                'def register(r): r["git"] = object'
            )
            import devsetup.core.plugin_loader as pl
            orig = pl._PLUGIN_DIR
            pl._PLUGIN_DIR = tmp
            try:
                from devsetup.core.plugin_loader import load_plugins
                registry = {"git": "original"}
                load_plugins(registry)
                self.assertEqual(registry["git"], "original")
            finally:
                pl._PLUGIN_DIR = orig

    def test_plugin_without_register_function_is_skipped(self):
        """A plugin file without register() must not raise."""
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmp:
            open(os.path.join(tmp, 'noop.py'), 'w').write('x = 42')
            result = self._run_with_dir(tmp)
            self.assertEqual(result, {})

    def test_valid_plugin_registers_new_tool(self):
        """A well-formed plugin must register its tool in the registry."""
        import tempfile, os
        with tempfile.TemporaryDirectory() as tmp:
            open(os.path.join(tmp, 'mytool.py'), 'w').write(
                'def register(r): r["mytool"] = type("FakeCls", (), {})'
            )
            result = self._run_with_dir(tmp)
            self.assertIn("mytool", result)
