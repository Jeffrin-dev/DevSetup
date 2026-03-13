"""
devsetup.installers.vscode
--------------------------
Isolated installer module for Visual Studio Code.

Uses PackageManagerRunner where available, snap on apt/dnf.
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
from devsetup.utils.logger import info


class VSCodeInstaller(BaseInstaller):
    tool_name = "vscode"

    def detect(self) -> bool:
        """Return True if the 'code' CLI is on PATH and executes successfully."""
        return command_runs("code")

    def install(self) -> None:
        """
        Install VS Code using the active system package manager.
        On apt/dnf systems, VS Code is not in the standard repo — uses snap.
        """
        pm = PackageManagerRunner()
        package = load_package_name("vscode", pm.name)

        if package is None:
            info("Installing VS Code via snap...")
            subprocess.run(
                ["sudo", "snap", "install", "--classic", "code"],
                check=True,
            )
        else:
            pm.install(package)

    def version(self) -> str:
        """
        Return the installed VS Code version string.

        Runs 'code --version' with a 5-second timeout (v1.3, Phase 14).
        'code --version' emits multiple lines; parse_version reads only
        the first line and extracts the version number (e.g. '1.86.0').
        Returns 'not installed' if VS Code is not detected.
        """
        if not self.detect():
            return "not installed"
        result = subprocess.run(
            ["code", "--version"],
            capture_output=True, text=True, check=True, timeout=5,
        )
        return parse_version(result.stdout)
