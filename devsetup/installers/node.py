"""
devsetup.installers.node
------------------------
Isolated installer module for Node.js.

Uses PackageManagerRunner for installation (Architecture Rule 5).
Uses command_detector for reliable tool detection (Phase 9).
Uses parse_version for clean version extraction (v1.3, Phase 3).
Implements the standard BaseInstaller interface (Architecture Rule 4).
"""

import subprocess

from devsetup.installers.base import BaseInstaller
from devsetup.system.command_detector import command_runs
from devsetup.system.package_managers import PackageManagerRunner
from devsetup.utils.package_loader import load_package_name
from devsetup.utils.version_parser import parse_version


class NodeInstaller(BaseInstaller):
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

        Runs 'node --version' with a 5-second timeout (v1.3, Phase 14).
        Parses 'v20.11.1' → '20.11.1' via parse_version (v1.3, Phase 9).
        Returns 'not installed' if node is not detected.
        """
        if not self.detect():
            return "not installed"
        result = subprocess.run(
            ["node", "--version"],
            capture_output=True, text=True, check=True, timeout=5,
        )
        return parse_version(result.stdout)
