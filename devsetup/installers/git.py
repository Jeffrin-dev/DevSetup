"""
devsetup.installers.git
-----------------------
Isolated installer module for Git.

Uses PackageManagerRunner for installation (Architecture Rule 5).
Implements the standard BaseInstaller interface (Architecture Rule 4).
"""

import shutil
import subprocess

from devsetup.installers.base import BaseInstaller
from devsetup.system.package_managers import PackageManagerRunner
from devsetup.utils.package_loader import load_package_name


class GitInstaller(BaseInstaller):
    tool_name = "git"

    def detect(self) -> bool:
        """Return True if git is available on PATH."""
        return shutil.which("git") is not None

    def install(self) -> None:
        """Install git using the active system package manager."""
        pm = PackageManagerRunner()
        package = load_package_name("git", pm.name)
        pm.install(package)

    def version(self) -> str:
        """Return the installed git version string."""
        if not self.detect():
            return "not installed"
        result = subprocess.run(
            ["git", "--version"], capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
