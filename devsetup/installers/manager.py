"""
devsetup.installers.manager
----------------------------
Installer manager / registry.

The CLI calls this module — it never calls individual installers directly.
Contains no OS logic. Contains no environment loading logic.
"""

from typing import Dict, List, Type

from devsetup.installers.base import BaseInstaller
from devsetup.installers.git import GitInstaller
from devsetup.installers.node import NodeInstaller
from devsetup.installers.pip import PipInstaller
from devsetup.installers.python import PythonInstaller
from devsetup.installers.vscode import VSCodeInstaller
from devsetup.system.os_detector import get_os
from devsetup.system.package_manager_detector import get_package_manager
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


def install_tool(tool_name: str, force: bool = False) -> str:
    """
    Detect and, if necessary, install a single tool.

    Returns
    -------
    str
        One of: 'skipped', 'installed', 'failed'
    """
    installer = get_installer(tool_name)

    check(tool_name)
    debug(f"Running detect() for {tool_name}")

    if not force and installer.detect():
        ver = installer.version()
        skip(f"{tool_name} already installed ({ver})")
        return "skipped"

    if force and installer.detect():
        warn(f"--force enabled. Reinstalling {tool_name}.")

    install(tool_name)
    try:
        installer.install()
        success(f"{tool_name} installed successfully.")
        return "installed"
    except Exception as exc:
        fail(f"{tool_name} installation failed: {exc}")
        return "failed"


def install_environment(tools: List[str], force: bool = False) -> None:
    """
    Install all tools defined in an environment config.
    Stops the pipeline on first failure and prints a summary.

    Parameters
    ----------
    tools : list
        Ordered list of tool names to install.
    force : bool
        If True, reinstall all tools even if already present.
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

    # Track results for summary
    installed_tools: List[str] = []
    skipped_tools:   List[str] = []
    failed_tool:     str | None = None

    total = len(tools)
    for index, tool_name in enumerate(tools, start=1):
        info(f"[{index}/{total}] Installing {tool_name} ({current_os} / {current_pm})")
        result = install_tool(tool_name, force=force)

        if result == "skipped":
            skipped_tools.append(tool_name)
        elif result == "installed":
            installed_tools.append(tool_name)
        elif result == "failed":
            failed_tool = tool_name
            break  # Stop pipeline on failure (Phase 9)

    _print_summary(installed_tools, skipped_tools, failed_tool)

    if failed_tool:
        raise RuntimeError(f"Installation stopped: {failed_tool} failed.")

    success("Environment setup complete.")


def _print_summary(
    installed: List[str],
    skipped: List[str],
    failed: str | None,
) -> None:
    """Print the installation summary (Phase 10)."""
    info("")
    info("Installation Summary")
    info("--------------------")

    if installed:
        info("Installed:")
        for t in installed:
            info(f"  {t}")
    if skipped:
        info("Skipped:")
        for t in skipped:
            info(f"  {t}")
    info(f"Failed:    {'None' if failed is None else failed}")
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
