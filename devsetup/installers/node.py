"""
devsetup.installers.node
------------------------
Isolated installer module for Node.js.

Patch (v1.3.2 — Issue 2): version() uses command_exists() not detect().
"""

import subprocess
from typing import List

from devsetup.installers.base import BaseInstaller
from devsetup.system.command_detector import command_exists, command_runs
from devsetup.system.package_managers import PackageManagerRunner
from devsetup.utils.package_loader import load_package_name
from devsetup.utils.version_parser import parse_version


class NodeInstaller(BaseInstaller):
    dependencies: List[str] = ["git"]  # git is a common prerequisite for Node.js workflows (cloning, npm scripts)
    tool_name = "node"

    def detect(self) -> bool:
        """Return True if node is on PATH and executes successfully."""
        return command_runs("node")

    def install(self) -> None:
        """Install Node.js using the active system package manager."""
        pm = PackageManagerRunner()
        package = load_package_name("node", pm.name)
        pm.install(package)

    def version(self) -> str:
        """
        Return the installed Node.js version string.

        Uses command_exists() (shutil.which only) rather than detect()
        to avoid running 'node --version' twice (Issue 2 fix).
        Parses 'v20.11.1' → '20.11.1' via parse_version.
        Returns 'not installed' if node binary is not on PATH.
        """
        if not command_exists("node"):
            return "not installed"
        result = subprocess.run(
            ["node", "--version"],
            capture_output=True, text=True, check=True, timeout=5,
        )
        return parse_version(result.stdout)
