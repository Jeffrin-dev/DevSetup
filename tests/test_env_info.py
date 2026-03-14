"""
tests.test_env_info
--------------------
Tests for the v1.6 environment info command (Phase 8).

Coverage:
  Phase 1  — command definition / registration
  Phase 2  — environment lookup (found / not found)
  Phase 3  — output content (ID, name, description, tools)
  Phase 4  — output formatting (order, empty description default)
  Phase 5  — error handling (unknown env, corrupt config, empty tools)
  Phase 6  — CLI parser integration
  Phase 7  — --summary flag
  Phase 8  — all scenarios from the roadmap
  Phase 9  — --verbose flag (dependency info)
  Phase 10 — read-only, uses v1.5 loader + validator
  Phase 11 — exit codes (0 success, 1 not found/invalid, 2 unexpected)
  Phase 13 — env_info module isolation from installer engine
"""

import io
import json
import os
import re
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from devsetup.cli.main import main
from devsetup.cli.env_info import print_env_info, print_env_summary, _get_dependencies
import devsetup.core.environment_loader as loader_mod


# ── Helpers ───────────────────────────────────────────────────────────────────

_LOG_PREFIX = re.compile(r"^\[\d{2}:\d{2}:\d{2}\] \[[A-Z]+\]\s*")


def _strip(line: str) -> str:
    return _LOG_PREFIX.sub("", line)


def _run_main(argv):
    """Run main(argv) capturing stdout + stderr. Returns (stdout, stderr, exit_code)."""
    buf_out = io.StringIO()
    buf_err = io.StringIO()
    old_out, old_err = sys.stdout, sys.stderr
    sys.stdout = buf_out
    sys.stderr = buf_err
    try:
        code = main(argv)
    finally:
        sys.stdout = old_out
        sys.stderr = old_err
    return buf_out.getvalue(), buf_err.getvalue(), code


def _content(output: str):
    """Return list of stripped non-blank lines."""
    return [_strip(l) for l in output.splitlines() if _strip(l).strip()]


def _env(overrides=None):
    """Return a minimal valid normalised env dict."""
    base = {
        "schema": "1.0",
        "id": "web",
        "name": "Web Development",
        "description": "Full web development stack.",
        "installers": ["git", "node", "vscode"],
    }
    if overrides:
        base.update(overrides)
    return base


# ── Phase 1: command definition ───────────────────────────────────────────────

class TestCommandDefinition(unittest.TestCase):

    def test_info_command_registered(self):
        """info must be a recognised top-level command."""
        try:
            main(["info", "--help"])
        except SystemExit as e:
            self.assertEqual(e.code, 0)
    def test_info_requires_target_argument(self):
        """Running 'devsetup info' without a target must produce non-zero."""
        with self.assertRaises(SystemExit) as ctx:
            main(["info"])
        self.assertNotEqual(ctx.exception.code, 0)

    def test_info_target_is_positional(self):
        """target must be accepted as a positional argument."""
        with patch("devsetup.cli.main._cmd_tool_info", return_value=0) as mock:
            main(["info", "git"])
            mock.assert_called_once_with("git")

    def test_info_help_exits_zero(self):
        with self.assertRaises(SystemExit) as ctx:
            main(["info", "--help"])
        self.assertEqual(ctx.exception.code, 0)


# ── Phase 2: environment lookup ───────────────────────────────────────────────

class TestEnvironmentLookup(unittest.TestCase):

    def test_known_environment_exits_zero(self):
        _, _, code = _run_main(["info", "web"])
        self.assertEqual(code, 0)

    def test_unknown_environment_exits_one(self):
        _, _, code = _run_main(["info", "nonexistent_xyz", "--env"])
        self.assertEqual(code, 1)

    def test_unknown_environment_error_message(self):
        _, stderr, _ = _run_main(["info", "nonexistent_xyz", "--env"])
        self.assertIn("nonexistent_xyz", stderr)

    def test_unknown_environment_suggests_list(self):
        _, stderr, _ = _run_main(["info", "nonexistent_xyz", "--env"])
        self.assertIn("devsetup list", stderr)

    def test_env_flag_forces_environment_lookup(self):
        """--env forces env lookup even for 'python' which is also a tool."""
        out, _, code = _run_main(["info", "python", "--env"])
        lines = _content(out)
        self.assertEqual(code, 0)
        # must show environment block, not tool block
        self.assertTrue(any("Environment" in l for l in lines))
        self.assertFalse(any(l.startswith("Tool  ") for l in lines))

    def test_tool_name_without_env_flag_shows_tool_info(self):
        """Without --env, a registered tool name shows tool info (backward compat)."""
        out, _, code = _run_main(["info", "git"])
        lines = _content(out)
        self.assertEqual(code, 0)
        self.assertTrue(any(l.startswith("Tool") for l in lines))

    def test_python_ambiguity_resolved_by_env_flag(self):
        """'python' is both a tool and an env — --env selects the environment."""
        out_tool, _, _ = _run_main(["info", "python"])
        out_env,  _, _ = _run_main(["info", "python", "--env"])
        tool_lines = _content(out_tool)
        env_lines  = _content(out_env)
        self.assertTrue(any(l.startswith("Tool") for l in tool_lines))
        self.assertTrue(any("Environment" in l for l in env_lines))


# ── Phase 3: output content ───────────────────────────────────────────────────

class TestOutputContent(unittest.TestCase):

    def _lines(self, env_dict, verbose=False):
        buf = io.StringIO()
        old = sys.stdout
        sys.stdout = buf
        try:
            print_env_info(env_dict, verbose=verbose)
        finally:
            sys.stdout = old
        return _content(buf.getvalue())

    def test_output_contains_environment_id(self):
        lines = self._lines(_env())
        self.assertTrue(any("web" in l for l in lines))

    def test_output_contains_name(self):
        lines = self._lines(_env())
        self.assertTrue(any("Web Development" in l for l in lines))

    def test_output_contains_description(self):
        lines = self._lines(_env())
        self.assertTrue(any("Full web development stack" in l for l in lines))

    def test_output_contains_all_tools(self):
        lines = self._lines(_env())
        for tool in ("git", "node", "vscode"):
            self.assertTrue(any(tool in l for l in lines), f"Missing: {tool}")

    def test_output_contains_tools_header(self):
        lines = self._lines(_env())
        self.assertTrue(any("Tools" in l for l in lines))

    def test_output_shows_environment_label(self):
        lines = self._lines(_env())
        self.assertTrue(any(l.startswith("Environment") for l in lines))

    def test_output_shows_name_label(self):
        lines = self._lines(_env())
        self.assertTrue(any(l.startswith("Name") for l in lines))

    def test_output_shows_description_label(self):
        lines = self._lines(_env())
        self.assertTrue(any(l.startswith("Description") for l in lines))


# ── Phase 4: output formatting ────────────────────────────────────────────────

class TestOutputFormatting(unittest.TestCase):

    def _lines(self, env_dict, verbose=False):
        buf = io.StringIO()
        old = sys.stdout
        sys.stdout = buf
        try:
            print_env_info(env_dict, verbose=verbose)
        finally:
            sys.stdout = old
        return _content(buf.getvalue())

    def test_tools_shown_in_config_order(self):
        """Tools must appear in the order defined in the config, not alphabetical."""
        env = _env({"installers": ["vscode", "git", "node"]})
        lines = self._lines(env)
        tool_lines = [l.strip() for l in lines if l.strip().startswith("- ")]
        self.assertEqual(tool_lines, ["- vscode", "- git", "- node"])

    def test_each_tool_prefixed_with_dash(self):
        lines = self._lines(_env())
        tool_lines = [l.strip() for l in lines if any(
            t in l for t in ("git", "node", "vscode")
        )]
        for tl in tool_lines:
            self.assertTrue(tl.startswith("- "), f"Expected '- ' prefix: {tl!r}")

    def test_empty_description_shows_default(self):
        env = _env({"description": ""})
        lines = self._lines(env)
        self.assertTrue(any("No description provided" in l for l in lines))

    def test_absent_description_shows_default(self):
        env = {k: v for k, v in _env().items() if k != "description"}
        lines = self._lines(env)
        self.assertTrue(any("No description provided" in l for l in lines))

    def test_whitespace_only_description_shows_default(self):
        env = _env({"description": "   "})
        lines = self._lines(env)
        self.assertTrue(any("No description provided" in l for l in lines))

    def test_tools_indented(self):
        buf = io.StringIO()
        old = sys.stdout; sys.stdout = buf
        try:
            print_env_info(_env())
        finally:
            sys.stdout = old
        # After stripping the logger prefix ([HH:MM:SS] [INFO]    ),
        # the raw content before stripping still carries our 2-space indent.
        # Check the raw logger output directly for the "  - " pattern.
        raw_lines = buf.getvalue().splitlines()
        tool_raw = [l for l in raw_lines if "- git" in l or "- node" in l or "- vscode" in l]
        for l in tool_raw:
            # Remove the log prefix to get the content portion
            content = re.sub(r'^\[\d{2}:\d{2}:\d{2}\] \[[A-Z]+\]\s{0,4}', '', l)
            self.assertTrue(content.startswith("  "), f"Expected 2-space indent: {content!r}")


# ── Phase 5: error handling ───────────────────────────────────────────────────

class TestErrorHandling(unittest.TestCase):

    def test_unknown_env_returns_exit_1(self):
        _, _, code = _run_main(["info", "unknown_env_xyz", "--env"])
        self.assertEqual(code, 1)

    def test_corrupt_json_returns_exit_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "bad.json"), "w") as f:
                f.write("{bad json}")
            with patch.object(loader_mod, "_config_dir", return_value=tmp):
                _, stderr, code = _run_main(["info", "bad", "--env"])
        self.assertEqual(code, 1)
        self.assertTrue(len(stderr) > 0)

    def test_empty_tools_shows_message(self):
        """env_info must not crash on empty tools list."""
        buf = io.StringIO()
        old = sys.stdout; sys.stdout = buf
        try:
            print_env_info(_env({"installers": []}))
        finally:
            sys.stdout = old
        lines = _content(buf.getvalue())
        self.assertTrue(any("No tools" in l for l in lines))

    def test_missing_env_error_is_actionable(self):
        _, stderr, _ = _run_main(["info", "missing_xyz", "--env"])
        self.assertTrue(len(stderr) > 0)

    def test_invalid_config_shows_error(self):
        """A config that passes JSON parse but fails validation shows an error."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg = {"id": "bad env!", "name": "Bad", "installers": ["git"]}
            with open(os.path.join(tmp, "bad-env-.json"), "w") as f:
                json.dump(cfg, f)
            with patch.object(loader_mod, "_config_dir", return_value=tmp):
                _, stderr, code = _run_main(["info", "bad-env-", "--env"])
        self.assertEqual(code, 1)
        self.assertTrue(len(stderr) > 0)


# ── Phase 6: CLI parser integration ──────────────────────────────────────────

class TestCLIParserIntegration(unittest.TestCase):

    def test_info_in_command_handlers(self):
        from devsetup.cli.main import _COMMAND_HANDLERS
        self.assertIn("info", _COMMAND_HANDLERS)

    def test_install_still_works(self):
        with patch("devsetup.installers.manager.install_environment", return_value=None), \
             patch("devsetup.core.environment_loader.load",
                   return_value={"id": "web", "name": "Web", "installers": ["git"]}):
            _, _, code = _run_main(["install", "web"])
        self.assertEqual(code, 0)

    def test_list_still_works(self):
        _, _, code = _run_main(["list"])
        self.assertEqual(code, 0)

    def test_info_tool_backward_compat(self):
        """devsetup info git (tool) must still work exactly as before."""
        out, _, code = _run_main(["info", "git"])
        lines = _content(out)
        self.assertEqual(code, 0)
        self.assertTrue(any("Tool" in l for l in lines))
        self.assertTrue(any("Installed" in l for l in lines))
        self.assertTrue(any("Version" in l for l in lines))
        self.assertTrue(any("Dependencies" in l for l in lines))

    def test_no_command_prints_help(self):
        out, _, code = _run_main([])
        self.assertEqual(code, 0)


# ── Phase 7: --summary flag ───────────────────────────────────────────────────

class TestSummaryFlag(unittest.TestCase):

    def test_summary_exits_zero(self):
        _, _, code = _run_main(["info", "web", "--summary"])
        self.assertEqual(code, 0)

    def test_summary_shows_all_tools_on_one_line(self):
        out, _, _ = _run_main(["info", "web", "--summary"])
        lines = _content(out)
        self.assertEqual(len(lines), 1, f"Expected 1 line, got: {lines}")

    def test_summary_contains_all_tool_names(self):
        out, _, _ = _run_main(["info", "web", "--summary"])
        for tool in ("git", "node", "vscode"):
            self.assertIn(tool, out)

    def test_summary_contains_env_id(self):
        out, _, _ = _run_main(["info", "web", "--summary"])
        self.assertIn("web", out)

    def test_summary_format(self):
        """Output must match: Tools in '<id>': t1, t2, t3"""
        out, _, _ = _run_main(["info", "web", "--summary"])
        line = _content(out)[0]
        self.assertRegex(line, r"Tools in 'web':")

    def test_summary_unit_function(self):
        buf = io.StringIO()
        old = sys.stdout; sys.stdout = buf
        try:
            print_env_summary(_env())
        finally:
            sys.stdout = old
        line = _content(buf.getvalue())[0]
        self.assertIn("git", line)
        self.assertIn("node", line)
        self.assertIn("vscode", line)

    def test_summary_empty_tools(self):
        buf = io.StringIO()
        old = sys.stdout; sys.stdout = buf
        try:
            print_env_summary(_env({"installers": []}))
        finally:
            sys.stdout = old
        line = _content(buf.getvalue())[0]
        self.assertIn("none", line)


# ── Phase 9: --verbose flag ───────────────────────────────────────────────────

class TestVerboseFlag(unittest.TestCase):

    def test_verbose_exits_zero(self):
        _, _, code = _run_main(["info", "web", "--verbose"])
        self.assertEqual(code, 0)

    def test_verbose_shows_tool_with_dependency(self):
        """node declares git as dependency — verbose must show it."""
        out, _, _ = _run_main(["info", "web", "--verbose"])
        lines = _content(out)
        node_lines = [l for l in lines if "node" in l]
        self.assertTrue(
            any("git" in l for l in node_lines),
            f"Expected 'git' in node verbose line. Lines: {node_lines}"
        )

    def test_verbose_shows_depends_on_label(self):
        out, _, _ = _run_main(["info", "web", "--verbose"])
        self.assertIn("depends on", out)

    def test_verbose_no_dep_tool_shows_no_dep_suffix(self):
        """git has no dependencies — verbose line must not include 'depends on'."""
        out, _, _ = _run_main(["info", "web", "--verbose"])
        lines = _content(out)
        git_lines = [l for l in lines if l.strip().startswith("- git")]
        self.assertTrue(
            all("depends on" not in l for l in git_lines),
            f"git should show no dep suffix: {git_lines}"
        )

    def test_verbose_unit_function_with_deps(self):
        buf = io.StringIO()
        old = sys.stdout; sys.stdout = buf
        try:
            print_env_info(_env(), verbose=True)
        finally:
            sys.stdout = old
        lines = _content(buf.getvalue())
        node_lines = [l for l in lines if "node" in l]
        self.assertTrue(any("git" in l for l in node_lines))

    def test_verbose_unit_function_no_dep_no_suffix(self):
        buf = io.StringIO()
        old = sys.stdout; sys.stdout = buf
        try:
            print_env_info(_env(), verbose=True)
        finally:
            sys.stdout = old
        lines = _content(buf.getvalue())
        git_lines = [l for l in lines if l.strip().startswith("- git")]
        self.assertTrue(all("depends" not in l for l in git_lines))


# ── Phase 10: read-only, no installation ──────────────────────────────────────

class TestReadOnly(unittest.TestCase):

    def test_env_info_does_not_call_install_tool(self):
        with patch("devsetup.installers.manager.install_tool") as mock_install:
            _run_main(["info", "web"])
            mock_install.assert_not_called()

    def test_env_info_does_not_call_install_environment(self):
        with patch("devsetup.installers.manager.install_environment") as mock_env:
            _run_main(["info", "web"])
            mock_env.assert_not_called()

    def test_env_info_module_has_no_install_imports(self):
        """env_info.py must not import install_tool or install_environment."""
        import devsetup.cli.env_info as ei
        import inspect
        src = inspect.getsource(ei)
        self.assertNotIn("install_tool", src)
        self.assertNotIn("install_environment", src)

    def test_get_dependencies_is_read_only(self):
        """_get_dependencies must not call detect() or install()."""
        with patch("devsetup.installers.git.GitInstaller.detect") as mock_d, \
             patch("devsetup.installers.git.GitInstaller.install") as mock_i:
            _get_dependencies("git")
            mock_d.assert_not_called()
            mock_i.assert_not_called()


# ── Phase 11: exit codes ──────────────────────────────────────────────────────

class TestExitCodes(unittest.TestCase):

    def test_valid_env_exits_0(self):
        _, _, code = _run_main(["info", "web", "--env"])
        self.assertEqual(code, 0)

    def test_valid_env_summary_exits_0(self):
        _, _, code = _run_main(["info", "web", "--summary"])
        self.assertEqual(code, 0)

    def test_valid_env_verbose_exits_0(self):
        _, _, code = _run_main(["info", "web", "--verbose"])
        self.assertEqual(code, 0)

    def test_unknown_env_exits_1(self):
        _, _, code = _run_main(["info", "unknown_xyz", "--env"])
        self.assertEqual(code, 1)

    def test_corrupt_json_exits_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "corrupt.json"), "w") as f:
                f.write("{not valid json}")
            with patch.object(loader_mod, "_config_dir", return_value=tmp):
                _, _, code = _run_main(["info", "corrupt", "--env"])
        self.assertEqual(code, 1)

    def test_valid_tool_exits_0(self):
        _, _, code = _run_main(["info", "git"])
        self.assertEqual(code, 0)

    def test_unknown_tool_exits_1(self):
        _, _, code = _run_main(["info", "unknowntoolxyz"])
        self.assertEqual(code, 1)


# ── Phase 13: env_info module isolation ───────────────────────────────────────

class TestEnvInfoModuleIsolation(unittest.TestCase):

    def test_print_env_info_is_importable(self):
        from devsetup.cli.env_info import print_env_info
        self.assertTrue(callable(print_env_info))

    def test_print_env_summary_is_importable(self):
        from devsetup.cli.env_info import print_env_summary
        self.assertTrue(callable(print_env_summary))

    def test_env_info_does_not_import_os_detector(self):
        import devsetup.cli.env_info as ei
        import inspect
        src = inspect.getsource(ei)
        self.assertNotIn("os_detector", src)
        self.assertNotIn("get_os", src)

    def test_env_info_does_not_import_package_manager(self):
        import devsetup.cli.env_info as ei
        import inspect
        src = inspect.getsource(ei)
        self.assertNotIn("PackageManager", src)
        self.assertNotIn("package_manager", src)

    def test_print_env_info_accepts_normalised_dict(self):
        """print_env_info must work with any valid normalised env dict."""
        buf = io.StringIO()
        old = sys.stdout; sys.stdout = buf
        try:
            print_env_info({
                "id": "test",
                "name": "Test",
                "description": "A test env",
                "installers": ["git"],
            })
        finally:
            sys.stdout = old
        out = _content(buf.getvalue())
        self.assertTrue(any("test" in l for l in out))
        self.assertTrue(any("git" in l for l in out))


# ── Phase 8: roadmap scenarios ────────────────────────────────────────────────

class TestRoadmapScenarios(unittest.TestCase):
    """Explicit coverage of the 5 test scenarios defined in the roadmap."""

    def test_scenario_1_valid_env_with_description(self):
        """Scenario 1: valid environment with description → outputs correctly."""
        out, _, code = _run_main(["info", "web", "--env"])
        self.assertEqual(code, 0)
        lines = _content(out)
        self.assertTrue(any("web" in l for l in lines))
        self.assertTrue(any("Web Development" in l for l in lines))
        self.assertTrue(any("Full web" in l for l in lines))
        for tool in ("git", "node", "vscode"):
            self.assertTrue(any(tool in l for l in lines))

    def test_scenario_2_valid_env_without_description(self):
        """Scenario 2: valid environment without description → default message."""
        with tempfile.TemporaryDirectory() as tmp:
            cfg = {"id": "nodesc", "name": "No Desc Env", "installers": ["git"]}
            with open(os.path.join(tmp, "nodesc.json"), "w") as f:
                json.dump(cfg, f)
            with patch.object(loader_mod, "_config_dir", return_value=tmp):
                out, _, code = _run_main(["info", "nodesc", "--env"])
        self.assertEqual(code, 0)
        self.assertIn("No description provided", out)

    def test_scenario_3_env_with_no_tools(self):
        """Scenario 3: environment with no tools → shows empty tools message."""
        buf = io.StringIO()
        old = sys.stdout; sys.stdout = buf
        try:
            print_env_info({"id": "empty", "name": "Empty", "installers": []})
        finally:
            sys.stdout = old
        lines = _content(buf.getvalue())
        self.assertTrue(any("No tools" in l for l in lines))

    def test_scenario_4_invalid_environment_id(self):
        """Scenario 4: invalid environment ID → error and exit 1."""
        _, stderr, code = _run_main(["info", "does_not_exist", "--env"])
        self.assertEqual(code, 1)
        self.assertIn("does_not_exist", stderr)

    def test_scenario_5_corrupt_config(self):
        """Scenario 5: corrupt config → error handling works, exit 1."""
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "broken.json"), "w") as f:
                f.write("{{{{invalid")
            with patch.object(loader_mod, "_config_dir", return_value=tmp):
                _, stderr, code = _run_main(["info", "broken", "--env"])
        self.assertEqual(code, 1)
        self.assertTrue(len(stderr) > 0)


if __name__ == "__main__":
    unittest.main()
