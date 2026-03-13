"""
devsetup.installers.pip
-----------------------
Isolated installer module for pip.

Uses PackageManagerRunner where available, ensurepip on brew/winget.
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
from devsetup.utils.logger import info


class PipInstaller(BaseInstaller):
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

        Runs 'pip --version' with a 5-second timeout (v1.3, Phase 14).
        Parses 'pip 23.0.1 from /usr/...' → '23.0.1' via parse_version
        (v1.3, Phase 9).
        Returns 'not installed' if pip is not detected.
        """
        if not self.detect():
            return "not installed"
        result = subprocess.run(
            [sys.executable, "-m", "pip", "--version"],
            capture_output=True, text=True, check=True, timeout=5,
        )
        return parse_version(result.stdout)
