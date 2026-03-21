"""
devsetup.installers.manager
----------------------------
Installer manager / registry and install engine.

The CLI calls this module — it never calls individual installers directly.
Contains no OS logic. Contains no environment loading logic.

v1.3: _get_version(), version logging, InstallerResult.version.
v1.3.1: UnsupportedOSError replaces fragile string matching.
v1.3.2: list_tools/tool_info use _get_version(); sentinel blacklist
        replaced with digit-presence check.
v1.4: Dependency resolution pipeline; BLOCKED results; independent tools
      continue after a peer failure.
v1.9 (DRY — Q2/Q3/Q4 fix):
  The five except-handler blocks in install_tool() each previously
  repeated the same three lines:
      exit_code = ExitCode.<CODE>
      category  = ErrorCategory.<CATEGORY>
      fail(f"... | exit_code={exit_code} | category={category}")
      return InstallerResult.fail(tool_name, str(exc), ...)
  That pattern is now captured in a single private helper:
      _handle_install_error(tool_name, exc, exit_code, category)
  The five blocks are reduced to one-liner calls, eliminating ~40 lines
  of duplication while keeping each except clause handling its specific
  exception type.
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
    auto as log_auto, verbose as log_verbose,
)

# ── Registry ──────────────────────────────────────────────────────────────────

_REGISTRY: Dict[str, Type[BaseInstaller]] = {
    "git":    GitInstaller,
    "node":   NodeInstaller,
    "pip":    PipInstaller,
    "python": PythonInstaller,
    "vscode": VSCodeInstaller,
}


# ── Private helpers ───────────────────────────────────────────────────────────

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
            log_verbose(f"Version detected: {tool_name} {ver}")
            debug(f"parsed version for {tool_name}: {ver}")
            return ver
        debug(f"version() returned non-version string for {tool_name}: {repr(ver)}")
        return None
    except Exception as exc:
        debug(f"version() raised for {tool_name}: {exc}")
        return None


def _handle_install_error(
    tool_name: str,
    exc: Exception,
    exit_code: int,
    category: str,
) -> InstallerResult:
    """
    Log an installation failure and return a structured FAIL result.

    v1.9 (DRY fix): Previously each of the five except-handler blocks in
    install_tool() repeated these identical three lines before returning:

        fail(f"{tool_name} installation failed | exit_code=... | category=...")
        return InstallerResult.fail(tool_name, str(exc), exit_code=..., error_category=...)

    This helper captures that repeated pattern once so each except clause
    becomes a single call, keeping all failure paths uniformly structured.

    Parameters
    ----------
    tool_name : str
    exc : Exception
        The caught exception; str(exc) becomes the result message.
    exit_code : int
        One of the ExitCode constants.
    category : str
        One of the ErrorCategory constants.

    Returns
    -------
    InstallerResult with status FAIL.
    """
    fail(
        f"{tool_name} installation failed "
        f"| exit_code={exit_code} | category={category}"
    )
    return InstallerResult.fail(
        tool_name, str(exc), exit_code=exit_code, error_category=category,
    )


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

    Pipeline
    --------
    check → detect → [skip | install] → version verify → result

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
    log_verbose(f"Running detect() for {tool_name}")

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
        return _handle_install_error(
            tool_name, exc,
            ExitCode.PACKAGE_MANAGER_FAILURE,
            ErrorCategory.PACKAGE_MANAGER_ERROR,
        )

    except FileNotFoundError as exc:
        return _handle_install_error(
            tool_name, exc,
            ExitCode.INSTALLATION_FAILURE,
            ErrorCategory.COMMAND_NOT_FOUND,
        )

    except UnsupportedOSError as exc:
        return _handle_install_error(
            tool_name, exc,
            ExitCode.UNSUPPORTED_OS,
            ErrorCategory.OS_NOT_SUPPORTED,
        )

    except RuntimeError as exc:
        return _handle_install_error(
            tool_name, exc,
            ExitCode.INSTALLATION_FAILURE,
            ErrorCategory.INSTALLER_FAILURE,
        )

    except Exception as exc:
        return _handle_install_error(
            tool_name, exc,
            ExitCode.INSTALLATION_FAILURE,
            ErrorCategory.INSTALLER_FAILURE,
        )

    # ── Post-install version verification ──────────────────────────────────
    ver = _get_version(installer, tool_name)
    if ver is None:
        fail(
            f"[VERSION CHECK FAILED] {tool_name} "
            f"| exit_code={ExitCode.VERIFICATION_FAILURE} "
            f"| category={ErrorCategory.VERIFICATION_FAILURE}"
        )
        return InstallerResult.fail(
            tool_name,
            f"{tool_name} version verification failed after installation.",
            exit_code=ExitCode.VERIFICATION_FAILURE,
            error_category=ErrorCategory.VERIFICATION_FAILURE,
        )

    version_log(ver)
    return InstallerResult.success(
        tool_name, f"{tool_name} installed successfully.", version=ver,
    )


def install_environment(
    tools: List[str],
    force: bool = False,
    env_name: Optional[str] = None,
    yes_mode: bool = False,
) -> None:
    """
    Install all tools in an environment, respecting dependency order.

    Pipeline
    --------
    1. Detect OS and package manager
    2. Resolve dependency order (topological sort)
    3. Execute installers; block dependents of failed tools
    4. Print summary
    5. Raise RuntimeError if any failures or blocked tools exist

    Parameters
    ----------
    tools : List[str]
    force : bool
    env_name : str | None
    yes_mode : bool
        When True, suppress confirmation prompts (--yes flag).
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

    if yes_mode:
        log_auto("Non-interactive mode active (--yes). All prompts auto-accepted.")

    # ── 2. Dependency resolution ───────────────────────────────────────────
    dep_order("Resolving dependencies...")
    log_verbose("DependencyResolver: starting resolution")
    try:
        ordered_tools, graph = resolve_with_graph(tools, _REGISTRY)
    except DependencyError as exc:
        error(str(exc))
        raise

    if ordered_tools:
        dep_order("Computed install order:")
        for i, t in enumerate(ordered_tools, 1):
            deps = graph.get(t, [])
            dep_hint = f"  (needs: {', '.join(deps)})" if deps else ""
            dep_order(f"  {i}. {t}{dep_hint}")
            if deps:
                log_verbose(f"DependencyResolver: {t} depends on {', '.join(deps)}")
    else:
        dep_order("No tools to install.")

    # ── 3. Execute in resolved order ───────────────────────────────────────
    summary = InstallSummary(env_name=env_name)
    failed_or_blocked: Set[str] = set()
    total = len(ordered_tools)

    for index, tool_name in enumerate(ordered_tools, start=1):
        info(f"[{index}/{total}] Installing {tool_name} ({current_os} / {current_pm})")

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
            continue

        result = install_tool(tool_name, force=force)
        summary.record(result)

        if result.failed:
            failed_or_blocked.add(tool_name)

    # ── 4. Print summary ───────────────────────────────────────────────────
    _print_summary(summary)

    # ── 5. Raise on failure ────────────────────────────────────────────────
    if summary.has_failure or summary.has_blocked:
        parts = []
        if summary.has_failure:
            for fr in summary.failed_results:
                parts.append(
                    f"{fr.installer_id} failed "
                    f"(exit_code={fr.exit_code}, category={fr.error_category})"
                )
        if summary.has_blocked:
            parts.append(
                f"{len(summary.blocked)} tool(s) blocked: "
                f"{', '.join(summary.blocked)}"
            )
        raise RuntimeError(
            "Installation incomplete: " + "; ".join(parts) + "."
        )

    success("Environment setup complete.")


def _print_summary(summary: InstallSummary) -> None:
    """Print the installation report to stdout via the logger."""
    info("")

    if summary.env_name:
        info(f"Environment: {summary.env_name}")
        info("")

    info("Installation Summary")
    info("--------------------")

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

    all_failures = summary.failed_results
    if all_failures:
        label = f"Failed ({len(all_failures)}):" if len(all_failures) > 1 else "Failed:"
        info(label)
        for fr in all_failures:
            info(
                f"  {fr.installer_id}  "
                f"(exit_code={fr.exit_code}, category={fr.error_category})"
            )
    else:
        info("Failed:")
        info("  none")
    info("")

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
    """Return a dict of tool → version for all registered tools."""
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
    """Return detection status, version, and dependencies for a single tool."""
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
