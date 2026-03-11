"""
devsetup.installers.vscode
--------------------------
Isolated installer module for Visual Studio Code.

Uses PackageManagerRunner where available, snap on apt/dnf.
Uses command_detector for reliable tool detection (Phase 9).
Implements the standard BaseInstaller interface (Architecture Rule 4).
"""

import subprocess

from devsetup.installers.base import BaseInstaller
from devsetup.system.command_detector import command_runs
from devsetup.system.package_managers import PackageManagerRunner
from devsetup.utils.package_loader import load_package_name
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
        """Return the installed VS Code version string."""
        if not self.detect():
            return "not installed"
        result = subprocess.run(
            ["code", "--version"], capture_output=True, text=True, check=True
        )
        return result.stdout.splitlines()[0].strip()
