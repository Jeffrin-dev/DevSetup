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
