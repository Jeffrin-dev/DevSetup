"""tests.test_config — Functional tests for environment configuration loading."""

import json
import os
import tempfile
import unittest
from unittest.mock import patch

from devsetup.core.environment_loader import load, list_available
from devsetup.system.environment_validator import (
    validate, validate_no_duplicates, EnvironmentValidationError,
)
import devsetup.core.environment_loader as loader


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

    def test_load_normalises_tools_to_installers(self):
        cfg = {"id": "myenv", "name": "My Env", "tools": ["git"]}
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "myenv.json")
            with open(path, "w") as f:
                json.dump(cfg, f)
            with patch.object(loader, "_config_dir", return_value=tmp):
                env = loader.load("myenv")
        self.assertIn("installers", env)
        self.assertEqual(env["installers"], ["git"])


class TestEnvironmentValidator(unittest.TestCase):

    VALID = {"id": "test", "name": "Test", "installers": ["git"]}

    def test_valid_config_passes(self):
        validate(self.VALID.copy(), "test.json")

    def test_schema_is_optional(self):
        data = {k: v for k, v in self.VALID.items() if k != "schema"}
        validate(data, "test.json")

    def test_schema_present_and_valid_passes(self):
        data = {**self.VALID, "schema": "1.0"}
        validate(data, "test.json")

    def test_unsupported_schema_version_raises(self):
        data = {**self.VALID, "schema": "9.9"}
        with self.assertRaises(EnvironmentValidationError) as ctx:
            validate(data, "test.json")
        self.assertIn("schema", str(ctx.exception).lower())

    def test_missing_id_raises(self):
        data = {k: v for k, v in self.VALID.items() if k != "id"}
        with self.assertRaises(EnvironmentValidationError) as ctx:
            validate(data, "test.json")
        self.assertIn("id", str(ctx.exception))

    def test_missing_name_raises(self):
        data = {k: v for k, v in self.VALID.items() if k != "name"}
        with self.assertRaises(EnvironmentValidationError) as ctx:
            validate(data, "test.json")
        self.assertIn("name", str(ctx.exception))

    def test_missing_tools_and_installers_raises(self):
        data = {k: v for k, v in self.VALID.items() if k not in ("installers", "tools")}
        with self.assertRaises(EnvironmentValidationError) as ctx:
            validate(data, "test.json")
        msg = str(ctx.exception)
        self.assertTrue("tools" in msg or "installers" in msg)

    def test_tools_alias_accepted(self):
        data = {"id": "test", "name": "Test", "tools": ["git"]}
        validate(data, "test.json")

    def test_empty_tools_raises(self):
        data = {**self.VALID, "installers": []}
        with self.assertRaises(EnvironmentValidationError) as ctx:
            validate(data, "test.json")
        self.assertIn("empty", str(ctx.exception))

    def test_tools_not_list_raises(self):
        data = {**self.VALID, "installers": "git"}
        with self.assertRaises(EnvironmentValidationError) as ctx:
            validate(data, "test.json")
        self.assertIn("list", str(ctx.exception))

    def test_unknown_installer_raises(self):
        # Installer-ID existence is checked by environment_loader, not the
        # structural validator (v1.9 Rule-6 fix: validator must not import
        # from installers/).  Test via the loader using a temp config file.
        import tempfile
        import devsetup.core.environment_loader as loader
        cfg = {"id": "testenv", "name": "Test", "installers": ["docker"]}
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "testenv.json")
            with open(path, "w") as f:
                json.dump(cfg, f)
            with patch.object(loader, "_config_dir", return_value=tmp):
                with self.assertRaises(EnvironmentValidationError) as ctx:
                    loader.load("testenv")
        self.assertIn("docker", str(ctx.exception))

    def test_duplicate_tools_raises(self):
        data = {**self.VALID, "installers": ["git", "node", "git"]}
        with self.assertRaises(EnvironmentValidationError) as ctx:
            validate(data, "test.json")
        self.assertIn("git", str(ctx.exception))
        self.assertIn("duplicate", str(ctx.exception).lower())

    def test_invalid_id_uppercase_raises(self):
        data = {**self.VALID, "id": "WebDev"}
        with self.assertRaises(EnvironmentValidationError):
            validate(data, "test.json")

    def test_invalid_id_space_raises(self):
        data = {**self.VALID, "id": "web dev"}
        with self.assertRaises(EnvironmentValidationError):
            validate(data, "test.json")

    def test_invalid_id_underscore_raises(self):
        data = {**self.VALID, "id": "web_dev"}
        with self.assertRaises(EnvironmentValidationError):
            validate(data, "test.json")

    def test_valid_id_formats(self):
        for valid_id in ("web", "python", "data-science", "python3", "my-env"):
            data = {**self.VALID, "id": valid_id}
            try:
                validate(data, "test.json")
            except EnvironmentValidationError as exc:
                self.fail(f"Valid id '{valid_id}' raised: {exc}")

    def test_id_must_be_string(self):
        data = {**self.VALID, "id": 123}
        with self.assertRaises(EnvironmentValidationError) as ctx:
            validate(data, "test.json")
        self.assertIn("id", str(ctx.exception))

    def test_description_optional(self):
        data = {k: v for k, v in self.VALID.items() if k != "description"}
        validate(data, "test.json")


class TestDuplicateProtection(unittest.TestCase):

    def test_first_id_passes(self):
        seen: set = set()
        validate_no_duplicates("web", seen, "web.json")

    def test_duplicate_id_raises(self):
        seen = {"web"}
        with self.assertRaises(EnvironmentValidationError) as ctx:
            validate_no_duplicates("web", seen, "web-dup.json")
        self.assertIn("web", str(ctx.exception))
        self.assertIn("duplicate", str(ctx.exception).lower())


class TestMalformedJSON(unittest.TestCase):

    def test_malformed_json_skipped_without_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = os.path.join(tmp, "bad.json")
            with open(bad, "w") as f:
                f.write("{bad json")
            with patch.object(loader, "_config_dir", return_value=tmp):
                envs = list_available()
            self.assertEqual(envs, [])


class TestPluginLoader(unittest.TestCase):

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
        import devsetup.core.plugin_loader as pl
        orig = pl._PLUGIN_DIR
        pl._PLUGIN_DIR = "/nonexistent/path/devsetup/plugins_xyz"
        try:
            from devsetup.core.plugin_loader import load_plugins
            load_plugins({})
        finally:
            pl._PLUGIN_DIR = orig

    def test_crashing_plugin_does_not_crash_devsetup(self):
        with tempfile.TemporaryDirectory() as tmp:
            open(os.path.join(tmp, "crash.py"), "w").write(
                'raise RuntimeError("deliberate crash")'
            )
            open(os.path.join(tmp, "good.py"), "w").write(
                'def register(r): r["mytool"] = object'
            )
            result = self._run_with_dir(tmp)
            self.assertIn("mytool", result)

    def test_plugin_cannot_overwrite_core_tool(self):
        with tempfile.TemporaryDirectory() as tmp:
            open(os.path.join(tmp, "evil.py"), "w").write(
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
        with tempfile.TemporaryDirectory() as tmp:
            open(os.path.join(tmp, "noop.py"), "w").write("x = 42")
            result = self._run_with_dir(tmp)
            self.assertEqual(result, {})

    def test_valid_plugin_registers_new_tool(self):
        with tempfile.TemporaryDirectory() as tmp:
            open(os.path.join(tmp, "mytool.py"), "w").write(
                'def register(r): r["mytool"] = type("FakeCls", (), {})'
            )
            result = self._run_with_dir(tmp)
            self.assertIn("mytool", result)


class TestGuardedRegistry(unittest.TestCase):

    def _make_guarded(self, registry: dict):
        from devsetup.core.plugin_loader import _GuardedRegistry
        return _GuardedRegistry(registry, source="test_plugin")

    def test_cannot_overwrite_existing_tool(self):
        g = self._make_guarded({"git": "orig"})
        with self.assertRaises(ValueError):
            g["git"] = "replaced"

    def test_can_register_new_tool(self):
        real = {"git": "orig"}
        g = self._make_guarded(real)
        g["docker"] = "DockerInstaller"
        self.assertIn("docker", real)

    def test_no_hardcoded_core_ids_attribute(self):
        from devsetup.core.plugin_loader import _GuardedRegistry
        self.assertFalse(hasattr(_GuardedRegistry, "_CORE_IDS"))


if __name__ == "__main__":
    unittest.main()
