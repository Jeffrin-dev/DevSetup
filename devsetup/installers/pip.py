"""
devsetup.installers.pip
-----------------------
Isolated installer module for pip.

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
from devsetup.utils.logger import info


class PipInstaller(BaseInstaller):
    dependencies: List[str] = ["python"]  # pip is a Python package manager, python required
    tool_name = "pip"

    def detect(self) -> bool:
        """Return True if pip3 or pip is on PATH and executes successfully."""
        return command_runs("pip3") or command_runs("pip")

    def install(self) -> None:
        """
        Install pip using the active system package manager.
        On brew and winget systems, pip ships bundled with Python —
        use ensurepip to bootstrap it.
        """
        pm = PackageManagerRunner()
        package = load_package_name("pip", pm.name)
        if package is None:
            info("Bootstrapping pip via Python ensurepip...")
            subprocess.run(
                [sys.executable, "-m", "ensurepip", "--upgrade"],
                check=True,
            )
        else:
            pm.install(package)

    def version(self) -> str:
        """
        Return the installed pip version string.

        Uses command_exists() (shutil.which only) rather than detect()
        to avoid running the version command twice (Issue 2 fix).
        Parses 'pip 23.0.1 from /usr/...' → '23.0.1' via parse_version.
        Returns 'not installed' if neither pip3 nor pip is on PATH.
        """
        if not (command_exists("pip3") or command_exists("pip")):
            return "not installed"
        result = subprocess.run(
            [sys.executable, "-m", "pip", "--version"],
            capture_output=True, text=True, check=True, timeout=5,
        )
        return parse_version(result.stdout)
