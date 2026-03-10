"""
devsetup.installers.manager
----------------------------
Installer manager / registry.

The CLI calls this module — it never calls individual installers directly.
Contains no OS logic.  Contains no environment loading logic.
"""

from typing import Dict, Type

from devsetup.installers.base import BaseInstaller
from devsetup.installers.git import GitInstaller
from devsetup.installers.node import NodeInstaller
from devsetup.installers.pip import PipInstaller
from devsetup.installers.python import PythonInstaller
from devsetup.installers.vscode import VSCodeInstaller
from devsetup.system.os_detector import get_os
from devsetup.utils.logger import info, error, success, warn, check, skip, install

# Registry: tool name → installer class
_REGISTRY: Dict[str, Type[BaseInstaller]] = {
    "git": GitInstaller,
    "node": NodeInstaller,
    "pip": PipInstaller,
    "python": PythonInstaller,
    "vscode": VSCodeInstaller,
}


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
            f"Installer '{tool_name}' not found. "
            f"Available installers: {list(_REGISTRY.keys())}"
        )
    return _REGISTRY[tool_name]()


def install_tool(tool_name: str) -> None:
    """Detect and, if necessary, install a single tool."""
    installer = get_installer(tool_name)

    check(tool_name)

    if installer.detect():
        ver = installer.version()
        skip(f"{tool_name} already installed ({ver})")
        return

    install(tool_name)
    installer.install()
    success(f"{tool_name} installed successfully.")


def install_environment(tools: list) -> None:
    """Install all tools defined in an environment config."""
    try:
        current_os = get_os()
        info(f"Detected OS: {current_os}")
    except RuntimeError as exc:
        error(str(exc))
        raise

    total = len(tools)
    for index, tool_name in enumerate(tools, start=1):
        info(f"[{index}/{total}] Installing {tool_name} ({current_os})")
        install_tool(tool_name)
    success("Environment setup complete.")


def list_tools() -> Dict[str, str]:
    """
    Return a dict of tool → version for all registered tools.
    Version is 'not installed' if the tool is absent.
    """
    result = {}
    for name, cls in _REGISTRY.items():
        installer = cls()
        result[name] = installer.version() if installer.detect() else "not installed"
    return result


def tool_info(tool_name: str) -> Dict[str, str]:
    """Return detection status and version for a single tool."""
    installer = get_installer(tool_name)
    return {
        "tool": tool_name,
        "installed": str(installer.detect()),
        "version": installer.version(),
    }
