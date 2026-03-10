"""
devsetup.utils.package_loader
------------------------------
Utility for loading package name mappings from packages/*.json.

Installer modules call load_package_name(tool, manager) to retrieve
the correct package identifier for the active package manager without
hardcoding names inside installer modules.
"""

import json
import os
from typing import Optional


def _packages_dir() -> str:
    """Return the canonical packages directory path."""
    pkg_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    return os.path.join(pkg_root, "packages")


def load_package_name(tool_name: str, manager_name: str) -> Optional[str]:
    """
    Return the package identifier for tool_name under manager_name.

    Parameters
    ----------
    tool_name : str
        The DevSetup tool name (e.g. 'git', 'node').
    manager_name : str
        The canonical package manager identifier (e.g. 'apt', 'brew').

    Returns
    -------
    str or None
        The package name string, or None if this tool requires a
        special install path for this manager.

    Raises
    ------
    FileNotFoundError
        If no mapping file exists for the given tool.
    KeyError
        If the manager is not present in the mapping file.
    """
    path = os.path.join(_packages_dir(), f"{tool_name}.json")

    if not os.path.isfile(path):
        raise FileNotFoundError(
            f"Package mapping not found for tool '{tool_name}'. "
            f"Expected: {path}"
        )

    with open(path, "r", encoding="utf-8") as fh:
        mapping = json.load(fh)

    if manager_name not in mapping:
        raise KeyError(
            f"Package manager '{manager_name}' not defined "
            f"in packages/{tool_name}.json."
        )

    return mapping[manager_name]
