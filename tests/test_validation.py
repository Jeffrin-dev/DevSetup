"""
tests.test_validation
---------------------
Comprehensive validation tests for DevSetup v1.5 — Phase 15.

Covers every validation rule introduced or extended in v1.5:

Phase 2 — Required fields
Phase 3 — Field types
Phase 4 — Tools list rules
Phase 5 — Installer reference validation
Phase 6 — Duplicate tool detection
Phase 7 — Environment ID format
Phase 8 — Duplicate environment IDs
Phase 9 — JSON structure
Phase 12 — Error message quality
Phase 13 — Validation logging
"""

import io
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

from devsetup.system.environment_validator import (
    EnvironmentValidationError,
    validate,
    validate_no_duplicates,
    get_tools_list,
)
from devsetup.core.environment_loader import load, list_available
import devsetup.core.environment_loader as loader_mod


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _valid(**overrides) -> dict:
    """Return a minimal valid v1.5 config dict."""
    base = {
        "id": "test",
        "name": "Test Env",
        "tools": ["git"],
    }
    base.update(overrides)
    return base


def _valid_v10(**overrides) -> dict:
    """Return a minimal valid v1.0 config dict (with schema + installers)."""
    base = {
        "schema": "1.0",
        "id": "test",
        "name": "Test Env",
        "installers": ["git"],
    }
    base.update(overrides)
    return base


# ── Phase 2: Required fields ──────────────────────────────────────────────────

class TestRequiredFields(unittest.TestCase):

    def test_id_required(self):
        data = _valid()
        del data["id"]
        with self.assertRaises(EnvironmentValidationError) as ctx:
            validate(data, "t.json")
        self.assertIn("id", str(ctx.exception))

    def test_name_required(self):
        data = _valid()
        del data["name"]
        with self.assertRaises(EnvironmentValidationError) as ctx:
            validate(data, "t.json")
        self.assertIn("name", str(ctx.exception))

    def test_tools_required(self):
        data = {"id": "test", "name": "Test"}
        with self.assertRaises(EnvironmentValidationError) as ctx:
            validate(data, "t.json")
        msg = str(ctx.exception)
        self.assertTrue("tools" in msg or "installers" in msg)

    def test_description_optional(self):
        data = _valid()
        validate(data, "t.json")   # no description — must not raise

    def test_schema_optional_v15(self):
        """v1.5 — schema not required."""
        data = _valid()
        validate(data, "t.json")   # no schema field — must not raise

    def test_schema_optional_present_and_valid(self):
        """schema present and valid must still be accepted."""
        data = {**_valid(), "schema": "1.0"}
        validate(data, "t.json")   # must not raise

    def test_all_required_fields_present_passes(self):
        validate(_valid(), "t.json")


# ── Phase 3: Field types ──────────────────────────────────────────────────────

class TestFieldTypes(unittest.TestCase):

    def test_id_must_be_string(self):
        with self.assertRaises(EnvironmentValidationError):
            validate(_valid(id=99), "t.json")

    def test_id_must_be_nonempty(self):
        with self.assertRaises(EnvironmentValidationError):
            validate(_valid(id=""), "t.json")

    def test_id_cannot_be_none(self):
        with self.assertRaises(EnvironmentValidationError):
            validate(_valid(id=None), "t.json")

    def test_name_must_be_string(self):
        with self.assertRaises(EnvironmentValidationError):
            validate(_valid(name=["Web"]), "t.json")

    def test_name_must_be_nonempty(self):
        with self.assertRaises(EnvironmentValidationError):
            validate(_valid(name=""), "t.json")

    def test_description_must_be_string_when_present(self):
        with self.assertRaises(EnvironmentValidationError) as ctx:
            validate(_valid(description=42), "t.json")
        self.assertIn("description", str(ctx.exception))

    def test_description_string_passes(self):
        validate(_valid(description="A valid description."), "t.json")

    def test_description_absent_passes(self):
        data = _valid()
        data.pop("description", None)
        validate(data, "t.json")


# ── Phase 4: Tools list rules ─────────────────────────────────────────────────

class TestToolsList(unittest.TestCase):

    def test_empty_tools_raises(self):
        with self.assertRaises(EnvironmentValidationError) as ctx:
            validate(_valid(tools=[]), "t.json")
        self.assertIn("empty", str(ctx.exception))

    def test_tools_as_string_raises(self):
        data = {"id": "test", "name": "Test", "tools": "git,node"}
        with self.assertRaises(EnvironmentValidationError) as ctx:
            validate(data, "t.json")
        self.assertIn("list", str(ctx.exception))

    def test_tools_as_dict_raises(self):
        data = {"id": "test", "name": "Test", "tools": {"git": True}}
        with self.assertRaises(EnvironmentValidationError) as ctx:
            validate(data, "t.json")
        self.assertIn("list", str(ctx.exception))

    def test_single_valid_tool_passes(self):
        validate(_valid(tools=["git"]), "t.json")

    def test_multiple_valid_tools_pass(self):
        validate(_valid(tools=["git", "node", "vscode"]), "t.json")

    def test_installers_field_backward_compat(self):
        """v1.0 'installers' field must still be accepted."""
        validate(_valid_v10(), "t.json")

    def test_tools_takes_precedence_over_installers(self):
        """When both present, 'tools' is used."""
        data = {"id": "test", "name": "Test", "tools": ["git"], "installers": ["node"]}
        result = get_tools_list(data)
        self.assertEqual(result, ["git"])


# ── Phase 5: Installer reference validation ───────────────────────────────────

class TestInstallerReferences(unittest.TestCase):

    def test_unknown_tool_raises(self):
        with self.assertRaises(EnvironmentValidationError) as ctx:
            validate(_valid(tools=["docker"]), "t.json")
        self.assertIn("docker", str(ctx.exception))

    def test_all_known_tools_pass(self):
        for tool in ("git", "node", "python", "pip", "vscode"):
            with self.subTest(tool=tool):
                validate(_valid(tools=[tool]), "t.json")

    def test_mix_of_known_and_unknown_raises(self):
        with self.assertRaises(EnvironmentValidationError) as ctx:
            validate(_valid(tools=["git", "unknown_xyz"]), "t.json")
        self.assertIn("unknown_xyz", str(ctx.exception))

    def test_error_names_the_bad_tool(self):
        with self.assertRaises(EnvironmentValidationError) as ctx:
            validate(_valid(tools=["nope"]), "t.json")
        self.assertIn("nope", str(ctx.exception))


# ── Phase 6: Duplicate tool detection ────────────────────────────────────────

class TestDuplicateTools(unittest.TestCase):

    def test_duplicate_in_tools_raises(self):
        with self.assertRaises(EnvironmentValidationError) as ctx:
            validate(_valid(tools=["git", "node", "git"]), "t.json")
        self.assertIn("git", str(ctx.exception))
        self.assertIn("duplicate", str(ctx.exception).lower())

    def test_duplicate_first_entry_raises(self):
        with self.assertRaises(EnvironmentValidationError) as ctx:
            validate(_valid(tools=["node", "node"]), "t.json")
        self.assertIn("node", str(ctx.exception))

    def test_duplicate_in_installers_raises(self):
        data = _valid_v10(installers=["git", "pip", "git"])
        with self.assertRaises(EnvironmentValidationError) as ctx:
            validate(data, "t.json")
        self.assertIn("git", str(ctx.exception))

    def test_no_duplicates_passes(self):
        validate(_valid(tools=["git", "node", "vscode"]), "t.json")

    def test_single_tool_passes(self):
        validate(_valid(tools=["git"]), "t.json")


# ── Phase 7: Environment ID format ───────────────────────────────────────────

class TestIDFormat(unittest.TestCase):

    def test_uppercase_raises(self):
        with self.assertRaises(EnvironmentValidationError):
            validate(_valid(id="Web"), "t.json")

    def test_mixed_case_raises(self):
        with self.assertRaises(EnvironmentValidationError):
            validate(_valid(id="WebDev"), "t.json")

    def test_space_raises(self):
        with self.assertRaises(EnvironmentValidationError):
            validate(_valid(id="web dev"), "t.json")

    def test_underscore_raises(self):
        with self.assertRaises(EnvironmentValidationError):
            validate(_valid(id="web_dev"), "t.json")

    def test_starts_with_digit_raises(self):
        with self.assertRaises(EnvironmentValidationError):
            validate(_valid(id="1web"), "t.json")

    def test_starts_with_hyphen_raises(self):
        with self.assertRaises(EnvironmentValidationError):
            validate(_valid(id="-web"), "t.json")

    def test_valid_simple(self):
        validate(_valid(id="web"), "t.json")

    def test_valid_with_hyphen(self):
        validate(_valid(id="data-science"), "t.json")

    def test_valid_with_digits(self):
        validate(_valid(id="python3"), "t.json")

    def test_valid_single_letter(self):
        validate(_valid(id="a"), "t.json")

    def test_all_existing_environments_pass_id_check(self):
        """web, python, data-science all satisfy the ID format rule."""
        for env_id in ("web", "python", "data-science"):
            data = _valid(id=env_id)
            try:
                validate(data, f"{env_id}.json")
            except EnvironmentValidationError as exc:
                self.fail(f"Existing env id '{env_id}' failed: {exc}")

    def test_error_message_mentions_id_format(self):
        with self.assertRaises(EnvironmentValidationError) as ctx:
            validate(_valid(id="Bad Id"), "t.json")
        msg = str(ctx.exception).lower()
        self.assertIn("id", msg)


# ── Phase 8: Duplicate environment IDs ───────────────────────────────────────

class TestDuplicateEnvironmentIDs(unittest.TestCase):

    def test_first_id_no_raise(self):
        validate_no_duplicates("web", set(), "web.json")

    def test_duplicate_raises(self):
        seen = {"web"}
        with self.assertRaises(EnvironmentValidationError) as ctx:
            validate_no_duplicates("web", seen, "web-copy.json")
        self.assertIn("web", str(ctx.exception))
        self.assertIn("duplicate", str(ctx.exception).lower())

    def test_different_ids_no_raise(self):
        seen = {"web"}
        validate_no_duplicates("python", seen, "python.json")

    def test_duplicate_skipped_in_list_available(self):
        """list_available() must skip the second config with a duplicate id."""
        cfg_a = {"id": "dup-env", "name": "Dup", "tools": ["git"]}
        cfg_b = {"id": "dup-env", "name": "Dup Copy", "tools": ["git"]}

        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "a_dup.json"), "w") as f:
                json.dump(cfg_a, f)
            with open(os.path.join(tmp, "b_dup.json"), "w") as f:
                json.dump(cfg_b, f)
            with patch.object(loader_mod, "_config_dir", return_value=tmp):
                envs = list_available()

        self.assertEqual(envs.count("dup-env"), 1,
                         "Duplicate id should appear only once")


# ── Phase 9: JSON structure ───────────────────────────────────────────────────

class TestJSONStructure(unittest.TestCase):

    def test_invalid_json_raises_on_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = os.path.join(tmp, "bad.json")
            with open(bad, "w") as f:
                f.write("{id: web, tools: [git]}")   # not valid JSON
            with patch.object(loader_mod, "_config_dir", return_value=tmp):
                with self.assertRaises(EnvironmentValidationError):
                    loader_mod.load("bad")

    def test_invalid_json_skipped_in_list_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "bad.json"), "w") as f:
                f.write("{bad json}")
            with patch.object(loader_mod, "_config_dir", return_value=tmp):
                envs = list_available()
        self.assertEqual(envs, [])

    def test_valid_json_with_extra_fields_passes(self):
        """Unknown extra fields must be tolerated (no strict schema rejection)."""
        data = _valid(extra_field="ignored_value")
        validate(data, "t.json")   # must not raise

    def test_json_array_at_root_raises(self):
        """Root must be a JSON object, not an array."""
        with tempfile.TemporaryDirectory() as tmp:
            bad = os.path.join(tmp, "array.json")
            with open(bad, "w") as f:
                json.dump(["git", "node"], f)
            with patch.object(loader_mod, "_config_dir", return_value=tmp):
                envs = list_available()
        self.assertEqual(envs, [])


# ── Phase 12: Error message quality ──────────────────────────────────────────

class TestErrorMessageQuality(unittest.TestCase):
    """
    Every error message must identify the problem clearly:
      - environment id (or source file)
      - what is wrong
    """

    def test_missing_id_names_field(self):
        data = _valid()
        del data["id"]
        with self.assertRaises(EnvironmentValidationError) as ctx:
            validate(data, "web.json")
        self.assertIn("id", str(ctx.exception))

    def test_missing_name_names_field(self):
        data = _valid()
        del data["name"]
        with self.assertRaises(EnvironmentValidationError) as ctx:
            validate(data, "web.json")
        self.assertIn("name", str(ctx.exception))

    def test_unknown_installer_names_tool(self):
        with self.assertRaises(EnvironmentValidationError) as ctx:
            validate(_valid(tools=["badtool"]), "web.json")
        self.assertIn("badtool", str(ctx.exception))

    def test_duplicate_tool_names_tool(self):
        with self.assertRaises(EnvironmentValidationError) as ctx:
            validate(_valid(tools=["git", "git"]), "web.json")
        self.assertIn("git", str(ctx.exception))

    def test_invalid_id_describes_problem(self):
        with self.assertRaises(EnvironmentValidationError) as ctx:
            validate(_valid(id="Bad Id!"), "web.json")
        msg = str(ctx.exception)
        self.assertIn("id", msg.lower())
        self.assertIn("Bad Id!", msg)

    def test_bad_schema_names_version(self):
        with self.assertRaises(EnvironmentValidationError) as ctx:
            validate({**_valid(), "schema": "99.0"}, "web.json")
        self.assertIn("99.0", str(ctx.exception))


# ── Phase 13: Validation logging ─────────────────────────────────────────────

class TestValidationLogging(unittest.TestCase):
    """
    list_available() must emit [VALID] ✓ for passing configs and
    [INVALID] ✗ for failing configs (Phase 13).
    """

    def _capture_list(self, tmp_dir):
        """Run list_available() patched to tmp_dir; return (envs, stdout, stderr)."""
        buf_out = io.StringIO()
        buf_err = io.StringIO()
        old_out, old_err = sys.stdout, sys.stderr
        sys.stdout = buf_out
        sys.stderr = buf_err
        try:
            with patch.object(loader_mod, "_config_dir", return_value=tmp_dir):
                envs = list_available()
        finally:
            sys.stdout = old_out
            sys.stderr = old_err
        return envs, buf_out.getvalue(), buf_err.getvalue()

    def test_valid_env_logged_with_check_mark(self):
        cfg = {"id": "myenv", "name": "My Env", "tools": ["git"]}
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "myenv.json"), "w") as f:
                json.dump(cfg, f)
            envs, stdout, _ = self._capture_list(tmp)

        self.assertIn("myenv", envs)
        self.assertIn("✓", stdout)
        self.assertIn("myenv", stdout)

    def test_invalid_env_logged_with_cross(self):
        cfg = {"id": "bad env!", "name": "Bad", "tools": ["git"]}
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "bad.json"), "w") as f:
                json.dump(cfg, f)
            envs, _, stderr = self._capture_list(tmp)

        self.assertNotIn("bad env!", envs)
        self.assertIn("✗", stderr)

    def test_invalid_level_in_output(self):
        cfg = {"id": "x", "name": "X", "tools": ["unknowntoolxyz"]}
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "x.json"), "w") as f:
                json.dump(cfg, f)
            _, _, stderr = self._capture_list(tmp)

        self.assertIn("[INVALID]", stderr)

    def test_valid_level_in_output(self):
        cfg = {"id": "myenv", "name": "My Env", "tools": ["git"]}
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "myenv.json"), "w") as f:
                json.dump(cfg, f)
            _, stdout, _ = self._capture_list(tmp)

        self.assertIn("[VALID]", stdout)

    def test_mixed_valid_and_invalid_both_logged(self):
        good = {"id": "goodenv", "name": "Good", "tools": ["git"]}
        bad  = {"id": "bad env!", "name": "Bad", "tools": ["git"]}
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "good.json"), "w") as f:
                json.dump(good, f)
            with open(os.path.join(tmp, "bad.json"), "w") as f:
                json.dump(bad, f)
            envs, stdout, stderr = self._capture_list(tmp)

        self.assertIn("goodenv", envs)
        self.assertIn("[VALID]",   stdout)
        self.assertIn("[INVALID]", stderr)


# ── get_tools_list helper ─────────────────────────────────────────────────────

class TestGetToolsList(unittest.TestCase):

    def test_returns_tools_when_present(self):
        data = {"tools": ["git"], "installers": ["node"]}
        self.assertEqual(get_tools_list(data), ["git"])

    def test_returns_installers_when_tools_absent(self):
        data = {"installers": ["node"]}
        self.assertEqual(get_tools_list(data), ["node"])

    def test_returns_none_when_neither_present(self):
        self.assertIsNone(get_tools_list({"id": "x"}))

    def test_returns_empty_list_when_set_explicitly(self):
        self.assertEqual(get_tools_list({"tools": []}), [])


# ── Full pipeline: load() with v1.5 configs ───────────────────────────────────

class TestLoadPipeline(unittest.TestCase):

    def _write_and_load(self, cfg, env_id):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, f"{env_id}.json"), "w") as f:
                json.dump(cfg, f)
            with patch.object(loader_mod, "_config_dir", return_value=tmp):
                return loader_mod.load(env_id)

    def test_v15_config_loads_correctly(self):
        cfg = {"id": "webenv", "name": "Web", "tools": ["git", "node"]}
        env = self._write_and_load(cfg, "webenv")
        self.assertEqual(env["id"], "webenv")
        self.assertEqual(env["installers"], ["git", "node"])

    def test_v10_config_still_loads(self):
        cfg = {"schema": "1.0", "id": "webenv", "name": "Web", "installers": ["git"]}
        env = self._write_and_load(cfg, "webenv")
        self.assertEqual(env["installers"], ["git"])

    def test_invalid_config_raises_on_load(self):
        cfg = {"id": "bad-env!", "name": "Bad", "tools": ["git"]}
        with self.assertRaises(EnvironmentValidationError):
            self._write_and_load(cfg, "bad-env!")

    def test_duplicate_tools_raises_on_load(self):
        cfg = {"id": "dupenv", "name": "Dup", "tools": ["git", "git"]}
        with self.assertRaises(EnvironmentValidationError):
            self._write_and_load(cfg, "dupenv")


if __name__ == "__main__":
    unittest.main()
