"""
devsetup.installers.pip
-----------------------
Isolated installer module for pip.

Uses PackageManagerRunner for installation where available.
Falls back to ensurepip on macOS and Windows where pip is
not a standalone package manager package (Architecture Rule 5).
Implements the standard BaseInstaller interface (Architecture Rule 4).
"""

import shutil
import subprocess
import sys

from devsetup.installers.base import BaseInstaller
from devsetup.system.package_managers import PackageManagerRunner
from devsetup.system.package_manager_detector import BREW, WINGET
from devsetup.utils.package_loader import load_package_name
from devsetup.utils.logger import info


class PipInstaller(BaseInstaller):
    tool_name = "pip"

    def detect(self) -> bool:
        """Return True if pip is available on PATH."""
        return shutil.which("pip3") is not None or shutil.which("pip") is not None

    def install(self) -> None:
        """
        Install pip using the active system package manager.
        On macOS (brew) and Windows (winget), pip ships bundled
        with Python — use ensurepip to bootstrap it instead.
        """
        pm = PackageManagerRunner()
        package = load_package_name("pip", pm.name)

        if package is None:
            # brew and winget: pip is bundled with Python
            info("Bootstrapping pip via Python ensurepip...")
            subprocess.run(
                [sys.executable, "-m", "ensurepip", "--upgrade"],
                check=True,
            )
        else:
            pm.install(package)

    def version(self) -> str:
        """Return the installed pip version string."""
        if not self.detect():
            return "not installed"
        result = subprocess.run(
            [sys.executable, "-m", "pip", "--version"],
            capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
