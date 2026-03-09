"""
devsetup.installers.python
--------------------------
Isolated installer module for Python 3.

All OS-specific branching lives here (Architecture Rule 5).
Implements the standard BaseInstaller interface (Architecture Rule 4).
"""

import platform
import shutil
import subprocess
import sys

from devsetup.installers.base import BaseInstaller
from devsetup.utils.logger import info, error


class PythonInstaller(BaseInstaller):
    tool_name = "python"

    def detect(self) -> bool:
        """Return True if python3 is available on PATH."""
        return shutil.which("python3") is not None or shutil.which("python") is not None

    def install(self) -> None:
        """Install Python 3 using the OS-appropriate method."""
        os_name = platform.system().lower()

        if os_name == "linux":
            info("Installing Python 3 via apt-get...")
            subprocess.run(
                ["sudo", "apt-get", "install", "-y", "python3", "python3-pip"],
                check=True,
            )

        elif os_name == "darwin":
            info("Installing Python 3 via Homebrew...")
            subprocess.run(["brew", "install", "python3"], check=True)

        elif os_name == "windows":
            info("Installing Python 3 via winget...")
            subprocess.run(
                ["winget", "install", "--id", "Python.Python.3", "-e"],
                check=True,
            )

        else:
            error(f"Unsupported OS: {os_name}. Please install Python 3 manually.")
            raise RuntimeError(f"Cannot install python on unsupported OS: {os_name}")

    def version(self) -> str:
        """Return the installed Python version string."""
        if not self.detect():
            return "not installed"
        result = subprocess.run(
            [sys.executable, "--version"], capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
