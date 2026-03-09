"""
devsetup.installers.pip
-----------------------
Isolated installer module for pip.

pip usually ships with Python but must be explicitly verified.
All OS-specific branching lives here (Architecture Rule 5).
Implements the standard BaseInstaller interface (Architecture Rule 4).
"""

import platform
import shutil
import subprocess
import sys

from devsetup.installers.base import BaseInstaller
from devsetup.utils.logger import info, error


class PipInstaller(BaseInstaller):
    tool_name = "pip"

    def detect(self) -> bool:
        """Return True if pip is available on PATH."""
        return shutil.which("pip3") is not None or shutil.which("pip") is not None

    def install(self) -> None:
        """Bootstrap pip using the OS-appropriate method."""
        os_name = platform.system().lower()

        if os_name == "linux":
            info("Installing pip via apt-get...")
            subprocess.run(
                ["sudo", "apt-get", "install", "-y", "python3-pip"],
                check=True,
            )

        elif os_name == "darwin":
            info("Bootstrapping pip via Python...")
            subprocess.run(
                [sys.executable, "-m", "ensurepip", "--upgrade"],
                check=True,
            )

        elif os_name == "windows":
            info("Bootstrapping pip via Python...")
            subprocess.run(
                [sys.executable, "-m", "ensurepip", "--upgrade"],
                check=True,
            )

        else:
            error(f"Unsupported OS: {os_name}. Please install pip manually.")
            raise RuntimeError(f"Cannot install pip on unsupported OS: {os_name}")

    def version(self) -> str:
        """Return the installed pip version string."""
        if not self.detect():
            return "not installed"
        result = subprocess.run(
            [sys.executable, "-m", "pip", "--version"],
            capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
