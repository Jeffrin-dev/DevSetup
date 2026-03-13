"""
devsetup.installers.python
--------------------------
Isolated installer module for Python 3.

Patch (v1.3.2 — Issue 2): version() uses command_exists() not detect().
"""

import subprocess
import sys
from typing import List

from devsetup.installers.base import BaseInstaller
from devsetup.system.command_detector import command_exists, command_runs
from devsetup.system.package_managers import PackageManagerRunner
from devsetup.utils.package_loader import load_package_name
from devsetup.utils.version_parser import parse_version


class PythonInstaller(BaseInstaller):
    dependencies: List[str] = []  # no prerequisites
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

        Uses command_exists() (shutil.which only) rather than detect()
        to avoid running the version command twice (Issue 2 fix).
        Parses 'Python 3.11.7' → '3.11.7' via parse_version.
        Returns 'not installed' if neither python3 nor python is on PATH.
        """
        cmd = "python3" if command_exists("python3") else (
              "python"  if command_exists("python")  else None)
        if cmd is None:
            return "not installed"
        result = subprocess.run(
            [sys.executable, "--version"],
            capture_output=True, text=True, check=True, timeout=5,
        )
        return parse_version(result.stdout)
