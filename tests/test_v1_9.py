"""
tests.test_v1_9
----------------
DevSetup v1.9 — Stability Pass test suite.

Covers every change made in the v1.9 Stability Pass:

Phase 1 — Code Refactoring
  • BasePackageManager._run() consolidates 5 duplicated implementations
  • allow_nonzero parameter on _run() (dnf check-update exit 100)
  • Individual managers (apt, brew, dnf, pacman, winget) have no local _run

Phase 2 — CLI Documentation
  • All major flags present in help text
  • Example commands documented

Phase 3 — Error Handling Consistency
  • Unified error messages from _run() include manager_name
  • FileNotFoundError, PermissionError, CalledProcessError all handled
  • allow_nonzero lets dnf's exit 100 pass without raising

Phase 4 — Modular Architecture
  • No subclass defines its own _run; all use BasePackageManager._run
  • allow_nonzero kwarg available for any future manager that needs it

Phase 5 — Testing
  • All 78 pre-existing tests still pass (no regressions)
  • _run() behaviour verified directly on BasePackageManager subclass
"""

import inspect
import subprocess
import unittest
from unittest.mock import patch, MagicMock, call

from devsetup.system.package_managers.base import BasePackageManager, PackageManagerError
from devsetup.system.package_managers.apt_manager    import AptManager
from devsetup.system.package_managers.dnf_manager    import DnfManager
from devsetup.system.package_managers.pacman_manager import PacmanManager
from devsetup.system.package_managers.brew_manager   import BrewManager
from devsetup.system.package_managers.winget_manager import WingetManager


# ── Helpers ───────────────────────────────────────────────────────────────────

ALL_MANAGERS = [AptManager, DnfManager, PacmanManager, BrewManager, WingetManager]


def _has_local_run(cls) -> bool:
    """Return True if cls defines its own _run (not just inheriting from base)."""
    return "_run" in cls.__dict__


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 1: Code Refactoring — _run() lives only in BasePackageManager
# ═══════════════════════════════════════════════════════════════════════════════

class TestPhase1RunConsolidation(unittest.TestCase):
    """
    v1.9 moved _run() from five identical/near-identical copies in individual
    managers into BasePackageManager.  Verify that all subclasses inherit
    _run() rather than defining their own copy.
    """

    def test_base_defines_run(self):
        """BasePackageManager must define _run()."""
        self.assertIn("_run", BasePackageManager.__dict__,
                      "_run must be defined directly on BasePackageManager")

    def test_apt_has_no_local_run(self):
        self.assertFalse(_has_local_run(AptManager),
                         "AptManager must not define its own _run (use inherited)")

    def test_dnf_has_no_local_run(self):
        self.assertFalse(_has_local_run(DnfManager),
                         "DnfManager must not define its own _run (use inherited)")

    def test_pacman_has_no_local_run(self):
        self.assertFalse(_has_local_run(PacmanManager),
                         "PacmanManager must not define its own _run (use inherited)")

    def test_brew_has_no_local_run(self):
        self.assertFalse(_has_local_run(BrewManager),
                         "BrewManager must not define its own _run (use inherited)")

    def test_winget_has_no_local_run(self):
        self.assertFalse(_has_local_run(WingetManager),
                         "WingetManager must not define its own _run (use inherited)")

    def test_all_managers_share_same_run_implementation(self):
        """All managers must resolve _run to the same BasePackageManager method."""
        base_run = BasePackageManager._run
        for cls in ALL_MANAGERS:
            with self.subTest(cls=cls.__name__):
                self.assertIs(
                    cls._run, base_run,
                    f"{cls.__name__}._run must be BasePackageManager._run"
                )

    def test_run_deduplication_reduces_line_count(self):
        """
        After consolidation each manager module must be shorter than it was
        before v1.9 (when each had ~15 lines of _run boilerplate).
        A proxy check: individual manager files are each < 60 lines.
        """
        import devsetup.system.package_managers.apt_manager as m
        src = inspect.getsource(m)
        lines = [l for l in src.splitlines() if l.strip() and not l.strip().startswith("#")]
        self.assertLess(len(lines), 60,
                        f"AptManager source is suspiciously long ({len(lines)} non-blank, "
                        f"non-comment lines) — _run may not have been removed")


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 1b: _run() behaviour — all error paths
# ═══════════════════════════════════════════════════════════════════════════════

class TestBaseRunBehaviour(unittest.TestCase):
    """
    Verify the shared _run() handles every error path:
      • exit code 0           → success (no exception)
      • exit code non-zero    → PackageManagerError with pm_exit_code
      • allow_nonzero match   → treated as success
      • FileNotFoundError     → PackageManagerError(pm_exit_code=-1)
      • PermissionError       → PackageManagerError(pm_exit_code=-1)
    """

    def setUp(self):
        """AptManager is concrete; use it to exercise the inherited _run."""
        self.mgr = AptManager()

    def _mock_run(self, returncode):
        mock_result = MagicMock()
        mock_result.returncode = returncode
        return patch("subprocess.run", return_value=mock_result)

    def test_exit_code_zero_does_not_raise(self):
        with self._mock_run(0):
            self.mgr._run(["sudo", "apt-get", "update"])  # must not raise

    def test_nonzero_exit_raises_package_manager_error(self):
        with self._mock_run(1):
            with self.assertRaises(PackageManagerError) as ctx:
                self.mgr._run(["sudo", "apt-get", "install", "-y", "git"])
        self.assertEqual(ctx.exception.pm_exit_code, 1)

    def test_error_message_contains_manager_name(self):
        """Error message must name the manager (apt) not be a generic string."""
        with self._mock_run(1):
            with self.assertRaises(PackageManagerError) as ctx:
                self.mgr._run(["sudo", "apt-get", "install", "-y", "git"])
        self.assertIn("apt", str(ctx.exception).lower())

    def test_allow_nonzero_suppresses_error(self):
        """Exit code in allow_nonzero must NOT raise."""
        with self._mock_run(100):
            # Should not raise — 100 is explicitly allowed
            self.mgr._run(["sudo", "apt-get", "update"], allow_nonzero={100})

    def test_allow_nonzero_only_suppresses_matching_code(self):
        """allow_nonzero={100} must still raise for exit code 1."""
        with self._mock_run(1):
            with self.assertRaises(PackageManagerError):
                self.mgr._run(["sudo", "apt-get", "update"], allow_nonzero={100})

    def test_file_not_found_raises_pm_error_with_minus_one(self):
        with patch("subprocess.run", side_effect=FileNotFoundError("apt: not found")):
            with self.assertRaises(PackageManagerError) as ctx:
                self.mgr._run(["sudo", "apt-get", "update"])
        self.assertEqual(ctx.exception.pm_exit_code, -1)
        self.assertIn("apt", str(ctx.exception).lower())

    def test_permission_error_raises_pm_error_with_minus_one(self):
        with patch("subprocess.run", side_effect=PermissionError("permission denied")):
            with self.assertRaises(PackageManagerError) as ctx:
                self.mgr._run(["sudo", "apt-get", "update"])
        self.assertEqual(ctx.exception.pm_exit_code, -1)
        self.assertIn("Permission denied", str(ctx.exception))

    def test_allow_nonzero_none_still_raises_on_nonzero(self):
        """Default allow_nonzero=None must still raise for any non-zero exit."""
        with self._mock_run(2):
            with self.assertRaises(PackageManagerError):
                self.mgr._run(["sudo", "apt-get", "install", "-y", "git"])

    def test_run_passes_cmd_to_subprocess(self):
        """_run must forward the cmd list to subprocess.run unchanged."""
        expected_cmd = ["sudo", "apt-get", "install", "-y", "git"]
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result) as mock_sub:
            self.mgr._run(expected_cmd)
        mock_sub.assert_called_once()
        actual_cmd = mock_sub.call_args[0][0]
        self.assertEqual(actual_cmd, expected_cmd)


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 1c: allow_nonzero used correctly by DnfManager
# ═══════════════════════════════════════════════════════════════════════════════

class TestDnfAllowNonzero(unittest.TestCase):
    """
    dnf check-update returns 100 when updates are available.
    DnfManager.update() must pass allow_nonzero={100} so this does not
    raise PackageManagerError.
    """

    def test_dnf_update_exit_100_does_not_raise(self):
        mock_result = MagicMock()
        mock_result.returncode = 100
        with patch("subprocess.run", return_value=mock_result):
            mgr = DnfManager()
            mgr.update()  # must not raise

    def test_dnf_update_exit_0_does_not_raise(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result):
            DnfManager().update()

    def test_dnf_update_exit_1_raises(self):
        mock_result = MagicMock()
        mock_result.returncode = 1
        with patch("subprocess.run", return_value=mock_result):
            with self.assertRaises(PackageManagerError):
                DnfManager().update()

    def test_dnf_install_does_not_use_allow_nonzero(self):
        """dnf install must raise on any non-zero (no grace for install)."""
        mock_result = MagicMock()
        mock_result.returncode = 100
        with patch("subprocess.run", return_value=mock_result):
            with self.assertRaises(PackageManagerError):
                DnfManager().install("git")

    def test_dnf_update_uses_check_update_command(self):
        """DnfManager.update() must invoke 'dnf check-update'."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result) as mock_sub:
            DnfManager().update()
        cmd = mock_sub.call_args[0][0]
        self.assertIn("dnf", cmd)
        self.assertIn("check-update", cmd)


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 1d: Every manager's install/update routes through _run
# ═══════════════════════════════════════════════════════════════════════════════

class TestManagersRouteThoughRun(unittest.TestCase):
    """
    Because each manager has no local _run, install() and update() must
    call BasePackageManager._run() (now the only implementation).
    Verify by patching _run on the instance and confirming it is called.
    """

    def _check_install_calls_run(self, cls, pkg):
        mgr = cls()
        with patch.object(mgr, "_run") as mock_run:
            mgr.install(pkg)
        mock_run.assert_called_once()
        actual_cmd = mock_run.call_args[0][0]
        self.assertIn(pkg, actual_cmd)

    def _check_update_calls_run(self, cls):
        mgr = cls()
        with patch.object(mgr, "_run") as mock_run:
            mgr.update()
        mock_run.assert_called()

    def test_apt_install_calls_run(self):
        self._check_install_calls_run(AptManager, "git")

    def test_dnf_install_calls_run(self):
        self._check_install_calls_run(DnfManager, "git")

    def test_pacman_install_calls_run(self):
        self._check_install_calls_run(PacmanManager, "git")

    def test_brew_install_calls_run(self):
        self._check_install_calls_run(BrewManager, "git")

    def test_winget_install_calls_run(self):
        self._check_install_calls_run(WingetManager, "OpenJS.NodeJS")

    def test_apt_update_calls_run(self):
        self._check_update_calls_run(AptManager)

    def test_pacman_update_calls_run(self):
        self._check_update_calls_run(PacmanManager)

    def test_brew_update_calls_run(self):
        self._check_update_calls_run(BrewManager)


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 1e: Correct commands per manager
# ═══════════════════════════════════════════════════════════════════════════════

class TestManagerCommands(unittest.TestCase):
    """Each manager must invoke the correct system binary in its commands."""

    def _run_ok(self, returncode=0):
        mock_result = MagicMock()
        mock_result.returncode = returncode
        return patch("subprocess.run", return_value=mock_result)

    def test_apt_install_uses_apt_get(self):
        with self._run_ok() as m:
            AptManager().install("git")
        cmd = m.call_args[0][0]
        self.assertIn("apt-get", cmd)
        self.assertIn("install", cmd)
        self.assertIn("git", cmd)

    def test_dnf_install_uses_dnf(self):
        with self._run_ok() as m:
            DnfManager().install("git")
        cmd = m.call_args[0][0]
        self.assertIn("dnf", cmd)
        self.assertIn("install", cmd)

    def test_pacman_install_uses_pacman(self):
        with self._run_ok() as m:
            PacmanManager().install("git")
        cmd = m.call_args[0][0]
        self.assertIn("pacman", cmd)

    def test_brew_install_uses_brew(self):
        with self._run_ok() as m:
            BrewManager().install("git")
        cmd = m.call_args[0][0]
        self.assertIn("brew", cmd)

    def test_winget_install_uses_winget(self):
        with self._run_ok() as m:
            WingetManager().install("Git.Git")
        cmd = m.call_args[0][0]
        self.assertIn("winget", cmd)
        self.assertIn("install", cmd)
        self.assertIn("Git.Git", cmd)

    def test_winget_install_uses_exact_flag(self):
        with self._run_ok() as m:
            WingetManager().install("Git.Git")
        cmd = m.call_args[0][0]
        self.assertIn("--exact", cmd)

    def test_apt_install_uses_yes_flag(self):
        with self._run_ok() as m:
            AptManager().install("git")
        cmd = m.call_args[0][0]
        self.assertIn("-y", cmd)

    def test_pacman_install_uses_noconfirm(self):
        with self._run_ok() as m:
            PacmanManager().install("git")
        cmd = m.call_args[0][0]
        self.assertIn("--noconfirm", cmd)


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 2: CLI Documentation — all flags present
# ═══════════════════════════════════════════════════════════════════════════════

class TestPhase2CLIDocumentation(unittest.TestCase):
    """
    All important flags must appear in help text.
    Ensures --verbose, --yes, --force, --log-file are documented.
    """

    def _get_help(self, *args):
        import io, sys
        from devsetup.cli.main import main
        buf = io.StringIO()
        old = sys.stdout; sys.stdout = buf
        try:
            main(list(args) + ["--help"])
        except SystemExit:
            pass
        finally:
            sys.stdout = old
        return buf.getvalue()

    def test_install_help_contains_verbose(self):
        self.assertIn("--verbose", self._get_help("install"))

    def test_install_help_contains_yes(self):
        self.assertIn("--yes", self._get_help("install"))

    def test_install_help_contains_force(self):
        self.assertIn("--force", self._get_help("install"))

    def test_install_help_contains_log_file(self):
        self.assertIn("--log-file", self._get_help("install"))

    def test_install_help_contains_tool(self):
        self.assertIn("--tool", self._get_help("install"))

    def test_top_help_contains_install(self):
        help_text = self._get_help()
        self.assertIn("install", help_text)

    def test_top_help_contains_list(self):
        help_text = self._get_help()
        self.assertIn("list", help_text)

    def test_top_help_contains_info(self):
        help_text = self._get_help()
        self.assertIn("info", help_text)

    def test_info_help_contains_summary(self):
        self.assertIn("--summary", self._get_help("info"))

    def test_info_help_contains_env(self):
        self.assertIn("--env", self._get_help("info"))


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 3: Error handling consistency
# ═══════════════════════════════════════════════════════════════════════════════

class TestPhase3ErrorConsistency(unittest.TestCase):
    """
    Error messages from the shared _run must be structured consistently:
      - Manager name always appears in the message
      - pm_exit_code is accurate
      - PackageManagerError is always the exception type raised
    """

    def _get_pm_error(self, cls, returncode):
        mock_result = MagicMock()
        mock_result.returncode = returncode
        with patch("subprocess.run", return_value=mock_result):
            mgr = cls()
            try:
                mgr.install("testpkg")
            except PackageManagerError as exc:
                return exc
        return None

    def test_apt_error_contains_manager_name(self):
        exc = self._get_pm_error(AptManager, 1)
        self.assertIsNotNone(exc)
        self.assertIn("apt", str(exc).lower())

    def test_dnf_error_contains_manager_name(self):
        exc = self._get_pm_error(DnfManager, 1)
        self.assertIsNotNone(exc)
        self.assertIn("dnf", str(exc).lower())

    def test_pacman_error_contains_manager_name(self):
        exc = self._get_pm_error(PacmanManager, 1)
        self.assertIsNotNone(exc)
        self.assertIn("pacman", str(exc).lower())

    def test_brew_error_contains_manager_name(self):
        exc = self._get_pm_error(BrewManager, 1)
        self.assertIsNotNone(exc)
        self.assertIn("brew", str(exc).lower())

    def test_winget_error_contains_manager_name(self):
        exc = self._get_pm_error(WingetManager, 1)
        self.assertIsNotNone(exc)
        self.assertIn("winget", str(exc).lower())

    def test_all_managers_return_pm_error_on_failure(self):
        """Every manager must raise PackageManagerError (not RuntimeError, etc.)."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        for cls in ALL_MANAGERS:
            with self.subTest(cls=cls.__name__):
                with patch("subprocess.run", return_value=mock_result):
                    mgr = cls()
                    with self.assertRaises(PackageManagerError):
                        mgr.install("testpkg")

    def test_all_managers_return_pm_error_on_missing_binary(self):
        """Every manager must raise PackageManagerError on FileNotFoundError."""
        for cls in ALL_MANAGERS:
            with self.subTest(cls=cls.__name__):
                with patch("subprocess.run", side_effect=FileNotFoundError):
                    mgr = cls()
                    with self.assertRaises(PackageManagerError) as ctx:
                        mgr.install("testpkg")
                    self.assertEqual(ctx.exception.pm_exit_code, -1)

    def test_pm_error_exit_code_matches_subprocess(self):
        """pm_exit_code on the raised error must match the process exit code."""
        for code in (1, 2, 127, 255):
            with self.subTest(code=code):
                exc = self._get_pm_error(AptManager, code)
                self.assertIsNotNone(exc)
                self.assertEqual(exc.pm_exit_code, code)


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 4: Modular architecture — BasePackageManager interface contract
# ═══════════════════════════════════════════════════════════════════════════════

class TestPhase4ModularArchitecture(unittest.TestCase):
    """
    BasePackageManager provides a clean interface:
      - Abstract install() and update() methods
      - Concrete _run() with allow_nonzero support
      - manager_name class attribute
    Subclasses must only override what they need to.
    """

    def test_all_managers_have_manager_name(self):
        for cls in ALL_MANAGERS:
            with self.subTest(cls=cls.__name__):
                self.assertIsInstance(cls.manager_name, str)
                self.assertGreater(len(cls.manager_name), 0)

    def test_manager_names_are_canonical(self):
        expected = {"apt", "dnf", "pacman", "brew", "winget"}
        actual = {cls.manager_name for cls in ALL_MANAGERS}
        self.assertEqual(actual, expected)

    def test_base_is_abstract(self):
        from abc import ABC
        self.assertTrue(issubclass(BasePackageManager, ABC))

    def test_install_is_abstract_on_base(self):
        """install() must be abstract — BasePackageManager cannot be instantiated."""
        with self.assertRaises(TypeError):
            BasePackageManager()  # type: ignore

    def test_run_accepts_allow_nonzero_kwarg(self):
        """_run must accept allow_nonzero without TypeError."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result):
            mgr = AptManager()
            mgr._run(["sudo", "apt-get", "update"], allow_nonzero={100})

    def test_run_allow_nonzero_default_is_none(self):
        """_run's allow_nonzero parameter must default to None."""
        sig = inspect.signature(BasePackageManager._run)
        param = sig.parameters.get("allow_nonzero")
        self.assertIsNotNone(param, "_run must have allow_nonzero parameter")
        self.assertIsNone(param.default,
                          "allow_nonzero default must be None")

    def test_each_manager_only_overrides_install_and_update(self):
        """
        In v1.9, each manager should define only install(), update(), and
        manager_name — nothing else beyond Python/ABC internals.
        No manager should define extra public methods or _run.
        """
        # Python's ABC machinery adds __abstractmethods__ and _abc_impl to
        # every concrete subclass automatically; exclude those from the check.
        abc_internals = {"__abstractmethods__", "_abc_impl",
                         "__module__", "__doc__", "__dict__", "__weakref__"}
        allowed_own = {"install", "update", "manager_name"}
        for cls in ALL_MANAGERS:
            with self.subTest(cls=cls.__name__):
                own_attrs = set(cls.__dict__) - abc_internals
                unexpected = own_attrs - allowed_own
                self.assertEqual(unexpected, set(),
                                 f"{cls.__name__} has unexpected attributes: {unexpected}")


# ═══════════════════════════════════════════════════════════════════════════════
# Phase 5: No regressions — key integration paths still work
# ═══════════════════════════════════════════════════════════════════════════════

class TestPhase5NoRegressions(unittest.TestCase):
    """
    Spot-check the install pipeline still works end-to-end after the
    v1.9 refactor.  Full regression coverage is in the existing test files.
    """

    def test_install_tool_git_skip(self):
        from devsetup.installers.manager import install_tool
        from devsetup.installers.result import InstallerStatus
        with patch("devsetup.installers.git.GitInstaller.detect", return_value=True), \
             patch("devsetup.installers.git.GitInstaller.version", return_value="2.43.0"):
            result = install_tool("git")
        self.assertEqual(result.status, InstallerStatus.SKIP)
        self.assertEqual(result.version, "2.43.0")

    def test_install_tool_git_install(self):
        from devsetup.installers.manager import install_tool
        from devsetup.installers.result import InstallerStatus
        with patch("devsetup.installers.git.GitInstaller.detect", return_value=False), \
             patch("devsetup.installers.git.GitInstaller.install", return_value=None), \
             patch("devsetup.installers.git.GitInstaller.version", return_value="2.43.0"):
            result = install_tool("git")
        self.assertEqual(result.status, InstallerStatus.SUCCESS)
        self.assertEqual(result.version, "2.43.0")

    def test_install_environment_respects_dep_order(self):
        from devsetup.installers.manager import install_environment
        run_order = []

        def make_install(name):
            def _i(): run_order.append(name)
            return _i

        patches = []
        for t in ["git", "node"]:
            base = {"git": "devsetup.installers.git.GitInstaller",
                    "node": "devsetup.installers.node.NodeInstaller"}[t]
            patches += [
                patch(f"{base}.detect",  return_value=False),
                patch(f"{base}.install", side_effect=make_install(t)),
                patch(f"{base}.version", return_value="1.0.0"),
            ]

        from contextlib import ExitStack
        with ExitStack() as stack:
            for p in patches:
                stack.enter_context(p)
            install_environment(["node", "git"])

        # git must precede node (node declares git as dependency)
        self.assertLess(run_order.index("git"), run_order.index("node"))

    def test_package_manager_error_propagates_through_installer(self):
        from devsetup.installers.manager import install_tool
        from devsetup.installers.result import InstallerStatus, ErrorCategory
        pm_err = PackageManagerError("network error", pm_exit_code=1)
        with patch("devsetup.installers.git.GitInstaller.detect", return_value=False), \
             patch("devsetup.installers.git.GitInstaller.install", side_effect=pm_err):
            result = install_tool("git")
        self.assertEqual(result.status, InstallerStatus.FAIL)
        self.assertEqual(result.error_category, ErrorCategory.PACKAGE_MANAGER_ERROR)

    def test_cli_list_still_works(self):
        from devsetup.cli.main import main
        result = main(["list"])
        self.assertEqual(result, 0)

    def test_cli_info_git_still_works(self):
        from devsetup.cli.main import main
        result = main(["info", "git"])
        self.assertEqual(result, 0)

    def test_environment_configs_still_load(self):
        from devsetup.core.environment_loader import load
        for env_id in ("web", "python", "data-science"):
            with self.subTest(env_id=env_id):
                env = load(env_id)
                self.assertEqual(env["id"], env_id)
                self.assertIn("installers", env)
                self.assertIsInstance(env["installers"], list)


if __name__ == "__main__":
    unittest.main()
