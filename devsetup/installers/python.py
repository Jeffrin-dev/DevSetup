"""
devsetup.installers.python
--------------------------
Isolated installer module for Python 3.

Uses PackageManagerRunner for installation (Architecture Rule 5).
Uses command_detector for reliable tool detection (Phase 9).
Uses parse_version for clean version extraction (v1.3, Phase 3).
Implements the standard BaseInstaller interface (Architecture Rule 4).
"""

import subprocess
import sys

from devsetup.installers.base import BaseInstaller
from devsetup.system.command_detector import command_runs
from devsetup.system.package_managers import PackageManagerRunner
from devsetup.utils.package_loader import load_package_name
from devsetup.utils.version_parser import parse_version


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
        """
        Return the installed Python version string.

        Runs 'python --version' with a 5-second timeout (v1.3, Phase 14).
        Parses 'Python 3.11.7' → '3.11.7' via parse_version (v1.3, Phase 9).
        Returns 'not installed' if Python is not detected.
        """
        if not self.detect():
            return "not installed"
        result = subprocess.run(
            [sys.executable, "--version"],
            capture_output=True, text=True, check=True, timeout=5,
        )
        return parse_version(result.stdout)
