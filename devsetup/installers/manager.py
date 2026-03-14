"""
devsetup.installers.manager
----------------------------
Installer manager / registry and install engine.

The CLI calls this module — it never calls individual installers directly.
Contains no OS logic. Contains no environment loading logic.

v1.3 additions (Tool Version Verification):
  - _get_version()  : safely retrieves version from installer
  - Version logged via [VERSION] after every install or skip
  - InstallerResult carries .version field
  - Summary displays version next to each tool name

v1.3.1:
  - Replaced fragile RuntimeError string matching with UnsupportedOSError.

v1.3.2:
  - Removed _verify_version() no-op wrapper
  - list_tools() / tool_info() use _get_version() safety wrapper
  - Sentinel blacklist replaced with digit-presence check

v1.4 (Dependency Ordering — Phases 8–12):
  - install_environment() now runs a full dependency resolution pipeline
    before executing any installers:

      load tools
        ↓
      build dependency graph       (dependency_resolver.build_graph)
        ↓
      validate dependency refs     (dependency_resolver._validate)
        ↓
      topological sort             (dependency_resolver.resolve)
        ↓
      log computed order           ([DEPS] log lines)
        ↓
      execute in resolved order
        ↓
      block tools whose deps failed (InstallerResult.block)
        ↓
      print summary (with Blocked section)

  - Pipeline no longer stops on first failure; instead, tools whose
    dependency failed are marked BLOCKED and skipped. Independent tools
    continue to run. RuntimeError is raised at the end if any FAIL or
    BLOCKED results were recorded.

  - _print_summary() extended with Blocked section (Phase 11).
"""

import re as _re
from typing import Dict, List, Optional, Set, Type

from devsetup.installers.base import BaseInstaller
from devsetup.installers.git import GitInstaller
from devsetup.installers.node import NodeInstaller
from devsetup.installers.pip import PipInstaller
from devsetup.installers.python import PythonInstaller
from devsetup.installers.vscode import VSCodeInstaller
from devsetup.installers.dependency_resolver import (
    DependencyError,
    resolve_with_graph,
    get_blocked,
)
from devsetup.installers.result import (
    InstallerResult,
    InstallerStatus,
    InstallSummary,
    ExitCode,
    ErrorCategory,
)
from devsetup.system.os_detector import get_os, UnsupportedOSError
from devsetup.system.package_manager_detector import get_package_manager
from devsetup.system.package_managers.base import PackageManagerError
from devsetup.utils.logger import (
    info, error, success, warn, check, skip, install, fail,
    debug, version_log, blocked as log_blocked, dep_order,
)

# ── Registry ──────────────────────────────────────────────────────────────────

_REGISTRY: Dict[str, Type[BaseInstaller]] = {
    "git":    GitInstaller,
    "node":   NodeInstaller,
    "pip":    PipInstaller,
    "python": PythonInstaller,
    "vscode": VSCodeInstaller,
}


# ── Version helpers ───────────────────────────────────────────────────────────

def _get_version(installer: BaseInstaller, tool_name: str) -> Optional[str]:
    """
    Safely retrieve the installed version from an installer.

    Any exception, timeout, or non-version string returns None.
    A 'version string' is defined as any string containing at least
    one digit (rejects 'not installed', 'unknown', 'N/A', etc.).
    """
    try:
        ver = installer.version()
        if ver and _re.search(r"\d", ver):
            debug(f"parsed version for {tool_name}: {ver}")
            return ver
        debug(f"version() returned non-version string for {tool_name}: {repr(ver)}")
        return None
    except Exception as exc:
        debug(f"version() raised for {tool_name}: {exc}")
        return None


# ── Registry helpers ──────────────────────────────────────────────────────────

def is_registered(tool_name: str) -> bool:
    """Return True if tool_name exists in the installer registry."""
    return tool_name in _REGISTRY


def get_installer(tool_name: str) -> BaseInstaller:
    """
    Return an installer instance for the given tool name.

    Raises
    ------
    KeyError
        If the tool name is not registered.
    """
    if tool_name not in _REGISTRY:
        raise KeyError(
            f"Installer '{tool_name}' not registered. "
            f"Available installers: {list(_REGISTRY.keys())}"
        )
    return _REGISTRY[tool_name]()


# ── Core install engine ───────────────────────────────────────────────────────

def install_tool(tool_name: str, force: bool = False) -> InstallerResult:
    """
    Detect and, if necessary, install a single tool.

    Pipeline:
        check → [skip | install] → version verification → result

    Parameters
    ----------
    tool_name : str
    force : bool
        If True, reinstall even if already present.

    Returns
    -------
    InstallerResult
    """
    installer = get_installer(tool_name)

    check(tool_name)
    debug(f"Running detect() for {tool_name}")

    # ── Detection ──────────────────────────────────────────────────────────
    try:
        already_installed = installer.detect()
    except Exception as exc:
        msg = f"{tool_name} detection failed: {exc}"
        fail(
            f"{msg} | exit_code={ExitCode.DETECTION_ERROR} "
            f"| category={ErrorCategory.INSTALLER_FAILURE}"
        )
        return InstallerResult.fail(
            tool_name, msg,
            exit_code=ExitCode.DETECTION_ERROR,
            error_category=ErrorCategory.INSTALLER_FAILURE,
        )

    # ── Skip path ──────────────────────────────────────────────────────────
    if not force and already_installed:
        ver = _get_version(installer, tool_name)
        ver_display = ver or "unknown"
        skip_msg = f"{tool_name} already installed ({ver_display})"
        skip(skip_msg)
        version_log(ver_display)
        return InstallerResult.skip(tool_name, skip_msg, version=ver)

    if force and already_installed:
        warn(f"--force enabled. Reinstalling {tool_name}.")

    # ── Install ────────────────────────────────────────────────────────────
    install(tool_name)
    try:
        installer.install()
        success(f"{tool_name} installed successfully.")

    except PackageManagerError as exc:
        exit_code = ExitCode.PACKAGE_MANAGER_FAILURE
        category  = ErrorCategory.PACKAGE_MANAGER_ERROR
        msg = (
            f"{tool_name} installation failed: package manager error — {exc} "
            f"| exit_code={exit_code} | category={category}"
        )
        fail(msg)
        return InstallerResult.fail(
            tool_name, str(exc), exit_code=exit_code, error_category=category,
        )

    except FileNotFoundError as exc:
        exit_code = ExitCode.INSTALLATION_FAILURE
        category  = ErrorCategory.COMMAND_NOT_FOUND
        msg = (
            f"{tool_name} installation failed: command not found — {exc} "
            f"| exit_code={exit_code} | category={category}"
        )
        fail(msg)
        return InstallerResult.fail(
            tool_name, str(exc), exit_code=exit_code, error_category=category,
        )

    except UnsupportedOSError as exc:
        exit_code = ExitCode.UNSUPPORTED_OS
        category  = ErrorCategory.OS_NOT_SUPPORTED
        msg = (
            f"{tool_name} installation failed: unsupported OS — {exc} "
            f"| exit_code={exit_code} | category={category}"
        )
        fail(msg)
        return InstallerResult.fail(
            tool_name, str(exc), exit_code=exit_code, error_category=category,
        )

    except RuntimeError as exc:
        exit_code = ExitCode.INSTALLATION_FAILURE
        category  = ErrorCategory.INSTALLER_FAILURE
        msg = (
            f"{tool_name} installation failed: {exc} "
            f"| exit_code={exit_code} | category={category}"
        )
        fail(msg)
        return InstallerResult.fail(
            tool_name, str(exc), exit_code=exit_code, error_category=category,
        )

    except Exception as exc:
        exit_code = ExitCode.INSTALLATION_FAILURE
        category  = ErrorCategory.INSTALLER_FAILURE
        msg = (
            f"{tool_name} installation failed: {exc} "
            f"| exit_code={exit_code} | category={category}"
        )
        fail(msg)
        return InstallerResult.fail(
            tool_name, str(exc), exit_code=exit_code, error_category=category,
        )

    # ── Post-install version verification ──────────────────────────────────
    ver = _get_version(installer, tool_name)
    if ver is None:
        vfail_msg = (
            f"{tool_name} version verification failed after installation. "
            f"The tool may not have installed correctly."
        )
        fail(
            f"[VERSION CHECK FAILED] {tool_name} "
            f"| exit_code={ExitCode.VERIFICATION_FAILURE} "
            f"| category={ErrorCategory.VERIFICATION_FAILURE}"
        )
        return InstallerResult.fail(
            tool_name,
            vfail_msg,
            exit_code=ExitCode.VERIFICATION_FAILURE,
            error_category=ErrorCategory.VERIFICATION_FAILURE,
        )

    version_log(ver)
    ok_msg = f"{tool_name} installed successfully."
    return InstallerResult.success(tool_name, ok_msg, version=ver)


def install_environment(
    tools: List[str],
    force: bool = False,
    env_name: Optional[str] = None,
) -> None:
    """
    Install all tools in an environment, respecting dependency order.

    v1.4 Pipeline
    -------------
    1. Detect OS and package manager
    2. Build dependency graph from installer declarations
    3. Validate all dependency references (Phase 7)
    4. Topological sort → deterministic install order (Phase 5)
    5. Log computed order (Phase 12)
    6. Execute installers in resolved order
       - If a tool's dependency failed/was blocked → mark BLOCKED, skip it
       - Independent tools continue even after a failure (Phase 10)
    7. Print summary (with Blocked section — Phase 11)
    8. Raise RuntimeError if any failures or blocked tools exist

    Parameters
    ----------
    tools : List[str]
    force : bool
    env_name : str | None

    Raises
    ------
    DependencyError
        If dependency validation or cycle detection fails.
    RuntimeError
        If any tool installation failed or was blocked.
    """
    # ── 1. OS / PM detection ───────────────────────────────────────────────
    try:
        current_os = get_os()
        current_pm = get_package_manager()
        info(f"Detected OS: {current_os}")
        info(f"Detected package manager: {current_pm}")
    except RuntimeError as exc:
        error(str(exc))
        raise

    if force:
        warn("--force enabled. All tools will be reinstalled.")

    # ── 2–4. Dependency resolution (Phases 4–6) ────────────────────────────
    dep_order("Resolving dependencies...")
    try:
        ordered_tools, graph = resolve_with_graph(tools, _REGISTRY)
    except DependencyError as exc:
        error(str(exc))
        raise

    # ── 5. Log computed install order (Phase 12) ───────────────────────────
    if ordered_tools:
        dep_order("Computed install order:")
        for i, t in enumerate(ordered_tools, 1):
            deps = graph.get(t, [])
            dep_hint = f"  (needs: {', '.join(deps)})" if deps else ""
            dep_order(f"  {i}. {t}{dep_hint}")
    else:
        dep_order("No tools to install.")

    # ── 6. Execute in resolved order (Phases 8–10) ────────────────────────
    summary = InstallSummary(env_name=env_name)
    failed_or_blocked: Set[str] = set()
    total = len(ordered_tools)

    for index, tool_name in enumerate(ordered_tools, start=1):
        info(f"[{index}/{total}] Installing {tool_name} ({current_os} / {current_pm})")

        # Check if any dependency failed or was blocked (Phase 10)
        blocking_dep = get_blocked(tool_name, graph, failed_or_blocked)
        if blocking_dep is not None:
            block_result = InstallerResult.block(tool_name, blocking_dep)
            summary.record(block_result)
            failed_or_blocked.add(tool_name)
            log_blocked(
                f"{tool_name} — dependency '{blocking_dep}' failed "
                f"| exit_code={ExitCode.DEPENDENCY_BLOCKED} "
                f"| category={ErrorCategory.DEPENDENCY_BLOCKED}"
            )
            continue  # Don't stop; independent tools continue

        result = install_tool(tool_name, force=force)
        summary.record(result)

        if result.failed:
            failed_or_blocked.add(tool_name)
            # Do NOT break — let independent tools run (v1.4 behaviour)

    # ── 7. Print summary (Phase 11) ────────────────────────────────────────
    _print_summary(summary)

    # ── 8. Raise if anything went wrong ───────────────────────────────────
    if summary.has_failure or summary.has_blocked:
        parts = []
        if summary.has_failure:
            for fr in summary.failed_results:
                parts.append(
                    f"{fr.installer_id} failed "
                    f"(exit_code={fr.exit_code}, category={fr.error_category})"
                )
        if summary.has_blocked:
            parts.append(f"{len(summary.blocked)} tool(s) blocked: {', '.join(summary.blocked)}")
        raise RuntimeError(
            "Installation incomplete: " + "; ".join(parts) + "."
        )

    success("Environment setup complete.")


def _print_summary(summary: InstallSummary) -> None:
    """
    Print the installation report.

    v1.3 — version strings displayed next to each tool name.
    v1.4 — Blocked section added (Phase 11).

    Format
    ------
        Environment: Web

        Installation Summary
        --------------------
        Installed (2):
          git (2.43.0)
          node (20.11.1)

        Skipped (1):
          vscode (1.86.0)

        Failed:
          python  (exit_code=5, category=VERIFICATION_FAILURE)

        Blocked (1):
          vscode  (blocked by: node)
    """
    info("")

    if summary.env_name:
        info(f"Environment: {summary.env_name}")
        info("")

    info("Installation Summary")
    info("--------------------")

    # Installed
    n_installed = len(summary.installed)
    if n_installed:
        info(f"Installed ({n_installed}):")
        for t in summary.installed:
            res = summary.result_map.get(t)
            ver_suffix = f" ({res.version})" if res and res.version else ""
            info(f"  {t}{ver_suffix}")
    else:
        info("Installed:")
        info("  none")

    info("")

    # Skipped
    n_skipped = len(summary.skipped)
    if n_skipped:
        info(f"Skipped ({n_skipped}):")
        for t in summary.skipped:
            res = summary.result_map.get(t)
            ver_suffix = f" ({res.version})" if res and res.version else ""
            info(f"  {t}{ver_suffix}")
    else:
        info("Skipped:")
        info("  none")

    info("")

    # Failed
    all_failures = summary.failed_results
    if all_failures:
        info(f"Failed ({len(all_failures)}):" if len(all_failures) > 1 else "Failed:")
        for fr in all_failures:
            info(
                f"  {fr.installer_id}  "
                f"(exit_code={fr.exit_code}, category={fr.error_category})"
            )
    else:
        info("Failed:")
        info("  none")

    info("")

    # Blocked (v1.4 — Phase 11)
    blocked_list = summary.blocked
    if blocked_list:
        info(f"Blocked ({len(blocked_list)}):")
        for t in blocked_list:
            res = summary.result_map.get(t)
            reason = ""
            if res and res.message:
                m = _re.search(r"dependency '([^']+)'", res.message)
                reason = f"  (blocked by: {m.group(1)})" if m else ""
            info(f"  {t}{reason}")
    else:
        info("Blocked:")
        info("  none")

    info("")


# ── Utility functions ─────────────────────────────────────────────────────────

def list_tools() -> Dict[str, str]:
    """
    Return a dict of tool → version for all registered tools.
    Uses _get_version() so exceptions cannot crash the command.
    """
    result = {}
    for name, cls in _REGISTRY.items():
        installer = cls()
        ver = _get_version(installer, name)
        result[name] = ver if ver is not None else "not installed"
    return result


def tool_dependencies(tool_name: str) -> List[str]:
    """
    Return the declared dependency list for a registered tool.

    Read-only — never instantiates the installer or calls detect().
    Returns an empty list if the tool has no dependencies.

    Raises
    ------
    KeyError
        If tool_name is not registered.
    """
    if tool_name not in _REGISTRY:
        raise KeyError(
            f"Installer '{tool_name}' not registered. "
            f"Available installers: {list(_REGISTRY.keys())}"
        )
    cls = _REGISTRY[tool_name]
    return list(getattr(cls, "dependencies", []))


def tool_info(tool_name: str) -> Dict[str, str]:
    """
    Return detection status, version, and dependencies for a single tool.
    Uses _get_version() so exceptions cannot crash the command.
    """
    installer = get_installer(tool_name)
    detected  = installer.detect()
    ver       = _get_version(installer, tool_name) if detected else None
    deps      = getattr(installer.__class__, "dependencies", [])
    return {
        "tool":         tool_name,
        "installed":    str(detected),
        "version":      ver if ver is not None else "not installed",
        "dependencies": ", ".join(deps) if deps else "none",
    }
