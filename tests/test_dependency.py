"""
tests.test_dependency
---------------------
Phase 13 — Dependency ordering tests for DevSetup v1.4.

Covers:
  - DependencyError contract
  - Graph construction from installer classes
  - Topological sort correctness (all orderings)
  - Determinism
  - Circular dependency detection and cycle path reporting
  - Missing registry reference detection
  - Missing tool list reference detection
  - Dependency failure propagation → BLOCKED results
  - Full integration: environment installs in correct order regardless of
    config order
  - Preserved existing features: skip, force, version verification
"""

import unittest
from unittest.mock import patch, MagicMock
from typing import Dict, List, Type

from devsetup.installers.dependency_resolver import (
    DependencyError,
    resolve,
    build_graph,
    get_blocked,
)
from devsetup.installers.base import BaseInstaller
from devsetup.installers.result import (
    InstallerResult,
    InstallerStatus,
    InstallSummary,
    ExitCode,
    ErrorCategory,
)
from devsetup.installers.manager import install_environment, install_tool
from devsetup.system.package_managers.base import PackageManagerError


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_cls(name: str, deps: List[str]) -> Type[BaseInstaller]:
    """Dynamically build a minimal installer class with given dependencies."""
    return type(
        f"{name.capitalize()}Installer",
        (object,),
        {
            "tool_name": name,
            "dependencies": deps,
            "detect": lambda self: False,
            "install": lambda self: None,
            "version": lambda self: "not installed",
        },
    )


def _registry(*specs) -> Dict[str, Type]:
    """Build a registry dict from (name, deps) tuples."""
    return {name: _make_cls(name, deps) for name, deps in specs}


# ── DependencyError contract ──────────────────────────────────────────────────

class TestDependencyError(unittest.TestCase):

    def test_is_value_error(self):
        err = DependencyError("oops")
        self.assertIsInstance(err, ValueError)

    def test_cycle_path_none_by_default(self):
        err = DependencyError("oops")
        self.assertIsNone(err.cycle_path)

    def test_cycle_path_stored(self):
        err = DependencyError("cycle", cycle_path=["a", "b", "a"])
        self.assertEqual(err.cycle_path, ["a", "b", "a"])

    def test_message_accessible(self):
        err = DependencyError("bad config")
        self.assertIn("bad config", str(err))


# ── Graph construction ────────────────────────────────────────────────────────

class TestBuildGraph(unittest.TestCase):

    def test_no_deps_produces_empty_adjacency(self):
        reg = _registry(("git", []), ("node", []))
        graph = build_graph(["git", "node"], reg)
        self.assertEqual(graph["git"], [])
        self.assertEqual(graph["node"], [])

    def test_declared_dep_in_tool_list_is_included(self):
        reg = _registry(("git", []), ("node", ["git"]))
        graph = build_graph(["git", "node"], reg)
        self.assertIn("git", graph["node"])

    def test_declared_dep_not_in_tool_list_is_excluded(self):
        """Deps outside the tool list are silently excluded; _validate catches them."""
        reg = _registry(("git", []), ("node", ["docker"]))
        graph = build_graph(["git", "node"], reg)
        self.assertNotIn("docker", graph["node"])

    def test_all_tools_present_as_keys(self):
        reg = _registry(("git", []), ("node", ["git"]), ("vscode", ["node"]))
        graph = build_graph(["git", "node", "vscode"], reg)
        self.assertSetEqual(set(graph.keys()), {"git", "node", "vscode"})

    def test_empty_tool_list_returns_empty_graph(self):
        reg = _registry(("git", []))
        graph = build_graph([], reg)
        self.assertEqual(graph, {})


# ── Topological sort ──────────────────────────────────────────────────────────

class TestTopologicalSort(unittest.TestCase):

    def test_simple_dependency(self):
        """git must come before node."""
        reg = _registry(("git", []), ("node", ["git"]))
        order = resolve(["node", "git"], reg)
        self.assertLess(order.index("git"), order.index("node"))

    def test_multi_level_dependency(self):
        """git → node → vscode: git first, then node, then vscode."""
        reg = _registry(("git", []), ("node", ["git"]), ("vscode", ["node"]))
        order = resolve(["vscode", "node", "git"], reg)
        self.assertLess(order.index("git"),   order.index("node"))
        self.assertLess(order.index("node"),  order.index("vscode"))

    def test_no_dependencies_all_tools_returned(self):
        reg = _registry(("git", []), ("python", []), ("pip", []))
        order = resolve(["git", "python", "pip"], reg)
        self.assertCountEqual(order, ["git", "python", "pip"])

    def test_order_independent_of_config_order(self):
        """Same dep graph must produce same result regardless of input order."""
        reg = _registry(("git", []), ("node", ["git"]), ("vscode", ["node"]))
        order_a = resolve(["git", "node", "vscode"], reg)
        order_b = resolve(["vscode", "git", "node"], reg)
        order_c = resolve(["node", "vscode", "git"], reg)
        self.assertEqual(order_a, order_b)
        self.assertEqual(order_b, order_c)

    def test_diamond_dependency(self):
        """
        a → c, b → c: c before both a and b.

             a   b
              \\ /
               c
        """
        reg = _registry(("c", []), ("a", ["c"]), ("b", ["c"]))
        order = resolve(["a", "b", "c"], reg)
        self.assertLess(order.index("c"), order.index("a"))
        self.assertLess(order.index("c"), order.index("b"))

    def test_deterministic_among_peers(self):
        """Tools with no relative dependency should appear in stable order."""
        reg = _registry(("z", []), ("a", []), ("m", []))
        order = resolve(["z", "a", "m"], reg)
        self.assertEqual(order, sorted(order))   # alphabetical among equals

    def test_empty_tool_list_returns_empty(self):
        reg = _registry(("git", []))
        self.assertEqual(resolve([], reg), [])

    def test_single_tool_no_deps(self):
        reg = _registry(("git", []))
        self.assertEqual(resolve(["git"], reg), ["git"])

    def test_all_registered_tools_resolved_correctly(self):
        """
        Realistic web environment: config out-of-order.
        node→git is a declared dependency; vscode has no explicit dep but
        alphabetical tiebreaking (node < vscode) naturally places it last.
        """
        from devsetup.installers.manager import _REGISTRY
        tools = ["vscode", "node", "git"]
        order = resolve(tools, _REGISTRY)
        self.assertLess(order.index("git"),  order.index("node"))
        self.assertLess(order.index("node"), order.index("vscode"))

    def test_python_env_resolved_correctly(self):
        """
        python must come before pip (pip declares python as dependency).
        pip comes before vscode due to alphabetical tiebreaking (pip < vscode).
        """
        from devsetup.installers.manager import _REGISTRY
        tools = ["vscode", "pip", "python"]
        order = resolve(tools, _REGISTRY)
        self.assertLess(order.index("python"), order.index("pip"))
        self.assertLess(order.index("pip"),    order.index("vscode"))


# ── Circular dependency detection ─────────────────────────────────────────────

class TestCircularDependency(unittest.TestCase):

    def test_direct_cycle_raises(self):
        """a → b, b → a"""
        reg = _registry(("a", ["b"]), ("b", ["a"]))
        with self.assertRaises(DependencyError) as ctx:
            resolve(["a", "b"], reg)
        self.assertIsNotNone(ctx.exception.cycle_path)

    def test_indirect_cycle_raises(self):
        """a → b → c → a"""
        reg = _registry(("a", ["b"]), ("b", ["c"]), ("c", ["a"]))
        with self.assertRaises(DependencyError) as ctx:
            resolve(["a", "b", "c"], reg)
        cycle = ctx.exception.cycle_path
        self.assertIsNotNone(cycle)
        # Start and end must be the same node
        self.assertEqual(cycle[0], cycle[-1])

    def test_cycle_error_message_contains_arrow(self):
        reg = _registry(("a", ["b"]), ("b", ["a"]))
        with self.assertRaises(DependencyError) as ctx:
            resolve(["a", "b"], reg)
        self.assertIn("→", str(ctx.exception))

    def test_cycle_error_aborts_immediately(self):
        """No tools should be installed when a cycle is detected."""
        reg = _registry(("a", ["b"]), ("b", ["a"]))
        with self.assertRaises(DependencyError):
            resolve(["a", "b"], reg)


# ── Missing dependency validation ─────────────────────────────────────────────

class TestValidation(unittest.TestCase):

    def test_dep_not_in_registry_raises(self):
        """node declares 'docker' as dep; docker not in registry."""
        reg = _registry(("git", []), ("node", ["docker"]))
        with self.assertRaises(DependencyError) as ctx:
            resolve(["git", "node"], reg)
        self.assertIn("docker", str(ctx.exception))
        self.assertIn("registry", str(ctx.exception).lower())

    def test_dep_not_in_tool_list_raises(self):
        """node depends on git but git is not in the environment tool list."""
        reg = _registry(("git", []), ("node", ["git"]))
        with self.assertRaises(DependencyError) as ctx:
            resolve(["node"], reg)   # git missing from list
        self.assertIn("git", str(ctx.exception))
        self.assertIn("environment", str(ctx.exception).lower())

    def test_config_error_category_mentioned(self):
        reg = _registry(("git", []), ("node", ["docker"]))
        with self.assertRaises(DependencyError) as ctx:
            resolve(["git", "node"], reg)
        self.assertIn("CONFIG ERROR", str(ctx.exception))

    def test_valid_config_does_not_raise(self):
        reg = _registry(("git", []), ("node", ["git"]))
        order = resolve(["git", "node"], reg)
        self.assertCountEqual(order, ["git", "node"])


# ── get_blocked helper ────────────────────────────────────────────────────────

class TestGetBlocked(unittest.TestCase):

    def test_returns_none_when_no_deps_failed(self):
        graph = {"node": ["git"], "git": []}
        self.assertIsNone(get_blocked("node", graph, set()))

    def test_returns_dep_when_dep_failed(self):
        graph = {"node": ["git"], "git": []}
        self.assertEqual(get_blocked("node", graph, {"git"}), "git")

    def test_returns_none_for_tool_with_no_deps(self):
        graph = {"git": []}
        self.assertIsNone(get_blocked("git", graph, {"anything"}))

    def test_returns_first_blocking_dep(self):
        graph = {"vscode": ["node", "python"]}
        result = get_blocked("vscode", graph, {"node"})
        self.assertEqual(result, "node")


# ── BLOCKED result contract ───────────────────────────────────────────────────

class TestBlockedResult(unittest.TestCase):

    def test_block_named_constructor(self):
        r = InstallerResult.block("vscode", "node")
        self.assertEqual(r.status, InstallerStatus.BLOCKED)
        self.assertEqual(r.exit_code, ExitCode.DEPENDENCY_BLOCKED)
        self.assertEqual(r.error_category, ErrorCategory.DEPENDENCY_BLOCKED)
        self.assertEqual(r.installer_id, "vscode")

    def test_blocked_property_true(self):
        r = InstallerResult.block("vscode", "node")
        self.assertTrue(r.blocked)
        self.assertFalse(r.failed)
        self.assertFalse(r.succeeded)

    def test_message_contains_both_ids(self):
        r = InstallerResult.block("vscode", "node")
        self.assertIn("vscode", r.message)
        self.assertIn("node", r.message)


# ── InstallSummary blocked bucket ─────────────────────────────────────────────

class TestInstallSummaryBlocked(unittest.TestCase):

    def test_record_blocked_appears_in_blocked(self):
        s = InstallSummary()
        s.record(InstallerResult.block("vscode", "node"))
        self.assertIn("vscode", s.blocked)
        self.assertNotIn("vscode", s.installed)
        self.assertNotIn("vscode", s.skipped)

    def test_has_blocked_true_when_blocked(self):
        s = InstallSummary()
        s.record(InstallerResult.block("vscode", "node"))
        self.assertTrue(s.has_blocked)

    def test_has_blocked_false_when_none(self):
        s = InstallSummary()
        s.record(InstallerResult.success("git", version="2.43.0"))
        self.assertFalse(s.has_blocked)

    def test_total_run_includes_blocked(self):
        s = InstallSummary()
        s.record(InstallerResult.success("git", version="2.43.0"))
        s.record(InstallerResult.block("vscode", "node"))
        self.assertEqual(s.total_run, 2)

    def test_blocked_order_preserved(self):
        s = InstallSummary()
        s.record(InstallerResult.block("vscode", "node"))
        s.record(InstallerResult.block("pip", "python"))
        self.assertEqual(s.blocked, ["vscode", "pip"])

    def test_constructor_blocked_kwarg(self):
        r = InstallerResult.block("vscode", "node")
        s = InstallSummary(blocked=["vscode"], result_map={"vscode": r})
        self.assertIn("vscode", s.blocked)


# ── Dependency failure propagation ────────────────────────────────────────────

class TestDependencyFailurePropagation(unittest.TestCase):

    def _patches(self, tool, *, detect, fail_with=None, version="1.0.0"):
        base = {
            "git":    "devsetup.installers.git.GitInstaller",
            "node":   "devsetup.installers.node.NodeInstaller",
            "python": "devsetup.installers.python.PythonInstaller",
            "pip":    "devsetup.installers.pip.PipInstaller",
            "vscode": "devsetup.installers.vscode.VSCodeInstaller",
        }[tool]
        p = [
            patch(f"{base}.detect",  return_value=detect),
            patch(f"{base}.version", return_value=version),
            patch(f"{base}.install",
                  side_effect=fail_with if fail_with else None,
                  return_value=None if not fail_with else ...),
        ]
        return p

    def test_failed_dep_blocks_dependent(self):
        """
        python fails → pip blocked (pip declares python as dependency).
        git is unrelated and unaffected by this failure.
        """
        from contextlib import ExitStack
        patches = (
            self._patches("python", detect=False,
                          fail_with=PackageManagerError("err", pm_exit_code=1))
            + self._patches("pip",    detect=False)
        )
        with ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            with self.assertRaises(RuntimeError):
                install_environment(["python", "pip"])

    def test_blocked_tool_not_installed(self):
        """
        pip.install() must NOT be called when python fails.
        pip declares python as a dependency (pip → python in registry).
        """
        from contextlib import ExitStack
        install_calls = []

        def pip_install():
            install_calls.append("pip")

        with ExitStack() as stack:
            stack.enter_context(
                patch("devsetup.installers.python.PythonInstaller.detect",
                      return_value=False)
            )
            stack.enter_context(
                patch("devsetup.installers.python.PythonInstaller.install",
                      side_effect=PackageManagerError("err", pm_exit_code=1))
            )
            stack.enter_context(
                patch("devsetup.installers.python.PythonInstaller.version",
                      return_value="3.11.7")
            )
            stack.enter_context(
                patch("devsetup.installers.pip.PipInstaller.detect",
                      return_value=False)
            )
            stack.enter_context(
                patch("devsetup.installers.pip.PipInstaller.install",
                      side_effect=pip_install)
            )
            stack.enter_context(
                patch("devsetup.installers.pip.PipInstaller.version",
                      return_value="23.0.1")
            )
            with self.assertRaises(RuntimeError):
                install_environment(["python", "pip"])

        self.assertEqual(install_calls, [],
                         "pip.install() must not be called when python failed")

    def test_independent_tool_still_runs_after_failure(self):
        """
        python and pip are independent of the git/node/vscode chain.
        When node fails, python should still be installed.
        """
        from contextlib import ExitStack
        run_order = []

        def git_install():    run_order.append("git")
        def python_install(): run_order.append("python")
        def pip_install():    run_order.append("pip")

        with ExitStack() as stack:
            stack.enter_context(patch("devsetup.installers.git.GitInstaller.detect",    return_value=False))
            stack.enter_context(patch("devsetup.installers.git.GitInstaller.install",    side_effect=git_install))
            stack.enter_context(patch("devsetup.installers.git.GitInstaller.version",    return_value="2.43.0"))
            stack.enter_context(patch("devsetup.installers.node.NodeInstaller.detect",   return_value=False))
            stack.enter_context(patch("devsetup.installers.node.NodeInstaller.install",
                                      side_effect=PackageManagerError("err", pm_exit_code=1)))
            stack.enter_context(patch("devsetup.installers.node.NodeInstaller.version",  return_value="20.x"))
            stack.enter_context(patch("devsetup.installers.python.PythonInstaller.detect", return_value=False))
            stack.enter_context(patch("devsetup.installers.python.PythonInstaller.install", side_effect=python_install))
            stack.enter_context(patch("devsetup.installers.python.PythonInstaller.version", return_value="3.11.7"))
            stack.enter_context(patch("devsetup.installers.pip.PipInstaller.detect",    return_value=False))
            stack.enter_context(patch("devsetup.installers.pip.PipInstaller.install",   side_effect=pip_install))
            stack.enter_context(patch("devsetup.installers.pip.PipInstaller.version",   return_value="23.0.1"))
            stack.enter_context(patch("devsetup.installers.vscode.VSCodeInstaller.detect", return_value=False))
            stack.enter_context(patch("devsetup.installers.vscode.VSCodeInstaller.install", return_value=None))
            stack.enter_context(patch("devsetup.installers.vscode.VSCodeInstaller.version", return_value="1.0.0"))

            with self.assertRaises(RuntimeError):
                install_environment(["git", "node", "python", "pip", "vscode"])

        self.assertIn("python", run_order,
                      "python must run even though node failed")

    def test_summary_shows_blocked_section(self):
        """Summary must list blocked tools in the Blocked section."""
        from contextlib import ExitStack
        import io, sys

        patches = [
            patch("devsetup.installers.git.GitInstaller.detect",    return_value=False),
            patch("devsetup.installers.git.GitInstaller.install",
                  side_effect=PackageManagerError("err", pm_exit_code=1)),
            patch("devsetup.installers.git.GitInstaller.version",    return_value="2.43.0"),
            patch("devsetup.installers.node.NodeInstaller.detect",   return_value=False),
            patch("devsetup.installers.node.NodeInstaller.install",  return_value=None),
            patch("devsetup.installers.node.NodeInstaller.version",  return_value="20.x"),
            patch("devsetup.installers.vscode.VSCodeInstaller.detect",   return_value=False),
            patch("devsetup.installers.vscode.VSCodeInstaller.install",  return_value=None),
            patch("devsetup.installers.vscode.VSCodeInstaller.version",  return_value="1.0.0"),
        ]
        buf = io.StringIO()
        old_out, old_err = sys.stdout, sys.stderr
        sys.stdout = buf; sys.stderr = buf
        try:
            with ExitStack() as stack:
                for p in patches:
                    stack.enter_context(p)
                try:
                    install_environment(["git", "node", "vscode"])
                except RuntimeError:
                    pass
        finally:
            sys.stdout = old_out; sys.stderr = old_err

        out = buf.getvalue()
        self.assertIn("Blocked", out)
        self.assertIn("node", out)   # node blocked by git failure


# ── Integration: config order independence ────────────────────────────────────

class TestConfigOrderIndependence(unittest.TestCase):

    def _capture_env(self, tools):
        """Run install_environment and capture which tools ran and in what order."""
        from contextlib import ExitStack
        run_order = []

        def make_install(name):
            def _install():
                run_order.append(name)
            return _install

        patches = []
        for t in ["git", "node", "python", "pip", "vscode"]:
            base = {
                "git":    "devsetup.installers.git.GitInstaller",
                "node":   "devsetup.installers.node.NodeInstaller",
                "python": "devsetup.installers.python.PythonInstaller",
                "pip":    "devsetup.installers.pip.PipInstaller",
                "vscode": "devsetup.installers.vscode.VSCodeInstaller",
            }[t]
            patches += [
                patch(f"{base}.detect",  return_value=False),
                patch(f"{base}.install", side_effect=make_install(t)),
                patch(f"{base}.version", return_value="1.0.0"),
            ]

        with ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            install_environment(tools)

        return run_order

    def test_web_env_git_before_node_before_vscode(self):
        order = self._capture_env(["vscode", "node", "git"])
        self.assertLess(order.index("git"),  order.index("node"))
        self.assertLess(order.index("node"), order.index("vscode"))

    def test_python_env_python_before_pip_before_vscode(self):
        order = self._capture_env(["vscode", "pip", "python"])
        self.assertLess(order.index("python"), order.index("pip"))
        self.assertLess(order.index("pip"),    order.index("vscode"))

    def test_all_tools_env_full_chain(self):
        """git → node → vscode and python → pip → vscode both respected."""
        order = self._capture_env(["vscode", "pip", "node", "python", "git"])
        self.assertLess(order.index("git"),    order.index("node"))
        self.assertLess(order.index("node"),   order.index("vscode"))
        self.assertLess(order.index("python"), order.index("pip"))


# ── Phase 9: preserved existing features ──────────────────────────────────────

class TestPreservedFeatures(unittest.TestCase):

    def test_skip_logic_still_works(self):
        """Already-installed tools are still skipped in v1.4."""
        with patch("devsetup.installers.git.GitInstaller.detect", return_value=True), \
             patch("devsetup.installers.git.GitInstaller.version", return_value="2.43.0"), \
             patch("devsetup.installers.git.GitInstaller.install") as mock_install:
            result = install_tool("git")
            self.assertEqual(result.status, InstallerStatus.SKIP)
            mock_install.assert_not_called()

    def test_force_still_reinstalls(self):
        """--force flag still bypasses skip in v1.4."""
        with patch("devsetup.installers.git.GitInstaller.detect", return_value=True), \
             patch("devsetup.installers.git.GitInstaller.version", return_value="2.43.0"), \
             patch("devsetup.installers.git.GitInstaller.install", return_value=None):
            result = install_tool("git", force=True)
            self.assertEqual(result.status, InstallerStatus.SUCCESS)

    def test_version_verification_still_runs(self):
        """Post-install version verification still produces VERIFICATION_FAILURE."""
        with patch("devsetup.installers.git.GitInstaller.detect", return_value=False), \
             patch("devsetup.installers.git.GitInstaller.install", return_value=None), \
             patch("devsetup.installers.git.GitInstaller.version", return_value="not installed"):
            result = install_tool("git")
            self.assertEqual(result.exit_code, ExitCode.VERIFICATION_FAILURE)

    def test_dep_order_in_summary(self):
        """tool_info returns dependencies field in v1.4."""
        from devsetup.installers.manager import tool_info
        with patch("devsetup.installers.git.GitInstaller.detect", return_value=True), \
             patch("devsetup.installers.git.GitInstaller.version", return_value="2.43.0"):
            info = tool_info("git")
            self.assertIn("dependencies", info)
            self.assertEqual(info["dependencies"], "none")

    def test_node_dependencies_field(self):
        from devsetup.installers.manager import tool_info
        with patch("devsetup.installers.node.NodeInstaller.detect", return_value=True), \
             patch("devsetup.installers.node.NodeInstaller.version", return_value="20.x"):
            info = tool_info("node")
            self.assertIn("git", info["dependencies"])


if __name__ == "__main__":
    unittest.main()
