"""
devsetup.installers.pip
-----------------------
Isolated installer module for pip.

OS detection is delegated to devsetup.system.os_detector (Architecture Rule 5).
Implements the standard BaseInstaller interface (Architecture Rule 4).
"""

import shutil
import subprocess
import sys

from devsetup.installers.base import BaseInstaller
from devsetup.system.os_detector import get_os, LINUX, MACOS, WINDOWS
from devsetup.utils.logger import info, error


class PipInstaller(BaseInstaller):
    tool_name = "pip"

    def detect(self) -> bool:
        """Return True if pip is available on PATH."""
        return shutil.which("pip3") is not None or shutil.which("pip") is not None

    def install(self) -> None:
        """Bootstrap pip using the OS-appropriate method."""
        os_name = get_os()

        if os_name == LINUX:
            info("Installing pip via apt-get...")
            subprocess.run(
                ["sudo", "apt-get", "install", "-y", "python3-pip"],
                check=True,
            )

        elif os_name == MACOS:
            info("Bootstrapping pip via Python...")
            subprocess.run(
                [sys.executable, "-m", "ensurepip", "--upgrade"],
                check=True,
            )

        elif os_name == WINDOWS:
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
