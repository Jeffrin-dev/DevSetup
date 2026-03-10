"""
devsetup.installers.vscode
--------------------------
Isolated installer module for Visual Studio Code.

Uses PackageManagerRunner for installation where available.
On Linux with apt/dnf, VS Code is not in the standard package
index — uses snap as the installation path instead.
Implements the standard BaseInstaller interface (Architecture Rule 4).
"""

import shutil
import subprocess

from devsetup.installers.base import BaseInstaller
from devsetup.system.package_managers import PackageManagerRunner
from devsetup.system.package_manager_detector import APT, DNF
from devsetup.utils.package_loader import load_package_name
from devsetup.utils.logger import info


class VSCodeInstaller(BaseInstaller):
    tool_name = "vscode"

    def detect(self) -> bool:
        """Return True if the 'code' CLI is available on PATH."""
        return shutil.which("code") is not None

    def install(self) -> None:
        """
        Install VS Code using the active system package manager.
        On apt and dnf systems, VS Code is not in the standard
        package index — falls back to snap for reliable installation.
        """
        pm = PackageManagerRunner()
        package = load_package_name("vscode", pm.name)

        if package is None:
            # apt / dnf: VS Code is not in the standard repo — use snap
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
