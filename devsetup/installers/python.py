"""
devsetup.installers.python
--------------------------
Isolated installer module for Python 3.

Uses PackageManagerRunner for installation (Architecture Rule 5).
Uses command_detector for reliable tool detection (Phase 9).
Implements the standard BaseInstaller interface (Architecture Rule 4).
"""

import subprocess
import sys

from devsetup.installers.base import BaseInstaller
from devsetup.system.command_detector import command_runs
from devsetup.system.package_managers import PackageManagerRunner
from devsetup.utils.package_loader import load_package_name


class PythonInstaller(BaseInstaller):
    tool_name = "python"

    def detect(self) -> bool:
        """Return True if python3 or python is on PATH and executes successfully."""
        return command_runs("python3") or command_runs("python")

    def install(self) -> None:
        """Install Python 3 using the active system package manager."""
        pm = PackageManagerRunner()
        package = load_package_name("python", pm.name)
        pm.install(package)

    def version(self) -> str:
        """Return the installed Python version string."""
        if not self.detect():
            return "not installed"
        result = subprocess.run(
            [sys.executable, "--version"], capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
