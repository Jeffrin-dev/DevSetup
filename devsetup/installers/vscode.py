"""
devsetup.installers.vscode
--------------------------
Isolated installer module for Visual Studio Code.

Patch (v1.3.2 — Issue 2): version() uses command_exists() not detect().
"""

import subprocess
from typing import List

from devsetup.installers.base import BaseInstaller
from devsetup.system.command_detector import command_exists, command_runs
from devsetup.system.package_managers import PackageManagerRunner
from devsetup.utils.package_loader import load_package_name
from devsetup.utils.version_parser import parse_version
from devsetup.utils.logger import info


class VSCodeInstaller(BaseInstaller):
    dependencies: List[str] = []  # no prerequisites — vscode appears in envs without node
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

        Uses command_exists() (shutil.which only) rather than detect()
        to avoid running 'code --version' twice (Issue 2 fix).
        parse_version() reads only the first line of multi-line output.
        Returns 'not installed' if code binary is not on PATH.
        """
        if not command_exists("code"):
            return "not installed"
        result = subprocess.run(
            ["code", "--version"],
            capture_output=True, text=True, check=True, timeout=5,
        )
        return parse_version(result.stdout)
