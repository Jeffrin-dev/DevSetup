"""
devsetup.installers.manager
----------------------------
Installer manager / registry and install engine.

The CLI calls this module — it never calls individual installers directly.
Contains no OS logic. Contains no environment loading logic.

Returns InstallerResult objects for every install_tool() call so that
the engine and CLI have a typed, structured view of every outcome.
"""

from typing import Dict, List, Type

from devsetup.installers.base import BaseInstaller
from devsetup.installers.git import GitInstaller
from devsetup.installers.node import NodeInstaller
from devsetup.installers.pip import PipInstaller
from devsetup.installers.python import PythonInstaller
from devsetup.installers.vscode import VSCodeInstaller
from devsetup.installers.result import (
    InstallerResult,
    InstallerStatus,
    InstallSummary,
    ExitCode,
    ErrorCategory,
)
from devsetup.system.os_detector import get_os
from devsetup.system.package_manager_detector import get_package_manager
from devsetup.system.package_managers.base import PackageManagerError
from devsetup.utils.logger import info, error, success, warn, check, skip, install, fail, debug

# Registry: tool name → installer class
_REGISTRY: Dict[str, Type[BaseInstaller]] = {
    "git":    GitInstaller,
    "node":   NodeInstaller,
    "pip":    PipInstaller,
    "python": PythonInstaller,
    "vscode": VSCodeInstaller,
}


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


def install_tool(tool_name: str, force: bool = False) -> InstallerResult:
    """
    Detect and, if necessary, install a single tool.

    Parameters
    ----------
    tool_name : str
        Registered tool name.
    force : bool
        If True, reinstall even if the tool is already present.

    Returns
    -------
    InstallerResult
        Typed result with status, exit code, message, and error category.
    """
    installer = get_installer(tool_name)

    check(tool_name)
    debug(f"Running detect() for {tool_name}")

    # ── Detection ──────────────────────────────────────────────────────────
    try:
        already_installed = installer.detect()
    except Exception as exc:
        msg = f"{tool_name} detection failed: {exc}"
        fail(f"{msg} | exit_code={ExitCode.DETECTION_ERROR} | category={ErrorCategory.INSTALLER_FAILURE}")
        return InstallerResult.fail(
            tool_name, msg,
            exit_code=ExitCode.DETECTION_ERROR,
            error_category=ErrorCategory.INSTALLER_FAILURE,
        )

    # ── Skip ───────────────────────────────────────────────────────────────
    if not force and already_installed:
        ver = installer.version()
        skip_msg = f"{tool_name} already installed ({ver})"
        skip(skip_msg)
        return InstallerResult.skip(tool_name, skip_msg)

    if force and already_installed:
        warn(f"--force enabled. Reinstalling {tool_name}.")

    # ── Install ────────────────────────────────────────────────────────────
    install(tool_name)
    try:
        installer.install()
        ok_msg = f"{tool_name} installed successfully."
        success(ok_msg)
        return InstallerResult.success(tool_name, ok_msg)

    except PackageManagerError as exc:
        exit_code = ExitCode.PACKAGE_MANAGER_FAILURE
        category  = ErrorCategory.PACKAGE_MANAGER_ERROR
        msg = (
            f"{tool_name} installation failed: package manager error — {exc} "
            f"| exit_code={exit_code} | category={category}"
        )
        fail(msg)
        return InstallerResult.fail(tool_name, str(exc), exit_code=exit_code, error_category=category)

    except FileNotFoundError as exc:
        exit_code = ExitCode.INSTALLATION_FAILURE
        category  = ErrorCategory.COMMAND_NOT_FOUND
        msg = (
            f"{tool_name} installation failed: command not found — {exc} "
            f"| exit_code={exit_code} | category={category}"
        )
        fail(msg)
        return InstallerResult.fail(tool_name, str(exc), exit_code=exit_code, error_category=category)

    except RuntimeError as exc:
        src = str(exc).lower()
        if "unsupported os" in src or "cannot install" in src:
            exit_code = ExitCode.UNSUPPORTED_OS
            category  = ErrorCategory.OS_NOT_SUPPORTED
        else:
            exit_code = ExitCode.INSTALLATION_FAILURE
            category  = ErrorCategory.INSTALLER_FAILURE
        msg = (
            f"{tool_name} installation failed: {exc} "
            f"| exit_code={exit_code} | category={category}"
        )
        fail(msg)
        return InstallerResult.fail(tool_name, str(exc), exit_code=exit_code, error_category=category)

    except Exception as exc:
        # Safety guard: convert any unexpected crash to a FAIL result
        exit_code = ExitCode.INSTALLATION_FAILURE
        category  = ErrorCategory.INSTALLER_FAILURE
        msg = (
            f"{tool_name} installation failed: {exc} "
            f"| exit_code={exit_code} | category={category}"
        )
        fail(msg)
        return InstallerResult.fail(tool_name, str(exc), exit_code=exit_code, error_category=category)


def install_environment(
    tools: List[str],
    force: bool = False,
    env_name: str | None = None,
) -> None:
    """
    Install all tools defined in an environment config.
    Stops the pipeline on first FAIL result and prints a summary.

    Parameters
    ----------
    tools : list
        Ordered list of tool names to install.
    force : bool
        If True, reinstall all tools even if already present.
    env_name : str | None
        Human-readable environment name shown in the summary header.
        Pass the ``name`` field from the environment JSON config.

    Raises
    ------
    RuntimeError
        If any tool installation fails (after summary is printed).
    """
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

    summary = InstallSummary(env_name=env_name)

    total = len(tools)
    for index, tool_name in enumerate(tools, start=1):
        info(f"[{index}/{total}] Installing {tool_name} ({current_os} / {current_pm})")
        result = install_tool(tool_name, force=force)
        summary.record(result)

        if result.status == InstallerStatus.FAIL:
            break  # Stop pipeline on failure

    _print_summary(summary)

    if summary.has_failure:
        fr = summary.failed_result
        raise RuntimeError(
            f"Installation stopped: {fr.installer_id} failed "
            f"(exit_code={fr.exit_code}, "
            f"category={fr.error_category})."
        )

    success("Environment setup complete.")


def _print_summary(summary: InstallSummary) -> None:
    """
    Print the installation report.

    Format
    ------
    If an environment name is available it appears as a header.
    Each section uses a count prefix when non-empty so large environments
    are easy to scan at a glance.  Empty sections display 'none'.

    Example (non-empty installed, one skip, one failure):

        Environment: Web

        Installation Summary
        --------------------
        Installed (2):
          git
          python

        Skipped (1):
          vscode

        Failed:
          node  (exit_code=4, category=PACKAGE_MANAGER_ERROR)
    """
    info("")

    # Phase 11 — environment name header
    if summary.env_name:
        info(f"Environment: {summary.env_name}")
        info("")

    info("Installation Summary")
    info("--------------------")

    # Phase 12 — count prefix when non-empty
    n_installed = len(summary.installed)
    if n_installed:
        info(f"Installed ({n_installed}):")
        for t in summary.installed:
            info(f"  {t}")
    else:
        info("Installed:")
        info("  none")

    info("")

    n_skipped = len(summary.skipped)
    if n_skipped:
        info(f"Skipped ({n_skipped}):")
        for t in summary.skipped:
            info(f"  {t}")
    else:
        info("Skipped:")
        info("  none")

    info("")

    if summary.failed_result:
        fr = summary.failed_result
        info(f"Failed:")
        info(f"  {fr.installer_id}  "
             f"(exit_code={fr.exit_code}, category={fr.error_category})")
    else:
        info("Failed:")
        info("  none")

    info("")


def list_tools() -> Dict[str, str]:
    """Return a dict of tool → version for all registered tools."""
    result = {}
    for name, cls in _REGISTRY.items():
        installer = cls()
        result[name] = installer.version() if installer.detect() else "not installed"
    return result


def tool_info(tool_name: str) -> Dict[str, str]:
    """Return detection status and version for a single tool."""
    installer = get_installer(tool_name)
    return {
        "tool":      tool_name,
        "installed": str(installer.detect()),
        "version":   installer.version(),
    }
