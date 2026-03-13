"""
devsetup.installers.git
-----------------------
Isolated installer module for Git.

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


class GitInstaller(BaseInstaller):
    tool_name = "git"

    def detect(self) -> bool:
        """Return True if git is on PATH and executes successfully."""
        return command_runs("git")

    def install(self) -> None:
        """Install git using the active system package manager."""
        pm = PackageManagerRunner()
        package = load_package_name("git", pm.name)
        pm.install(package)

    def version(self) -> str:
        """
        Return the installed git version string.

        Runs 'git --version' with a 5-second timeout (v1.3, Phase 14).
        Parses the output to return a clean version number (e.g. '2.43.0').
        Returns 'not installed' if git is not detected.
        """
        if not self.detect():
            return "not installed"
        result = subprocess.run(
            ["git", "--version"],
            capture_output=True, text=True, check=True, timeout=5,
        )
        return parse_version(result.stdout)
