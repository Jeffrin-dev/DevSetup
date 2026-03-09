"""
devsetup.installers.git
-----------------------
Isolated installer module for Git.

All OS-specific branching lives here (Architecture Rule 5).
Implements the standard BaseInstaller interface (Architecture Rule 4).
"""

import platform
import shutil
import subprocess

from devsetup.installers.base import BaseInstaller
from devsetup.utils.logger import info, error


class GitInstaller(BaseInstaller):
    tool_name = "git"

    def detect(self) -> bool:
        """Return True if git is available on PATH."""
        return shutil.which("git") is not None

    def install(self) -> None:
        """Install git using the OS-appropriate package manager."""
        os_name = platform.system().lower()

        if os_name == "linux":
            info("Installing git via apt-get...")
            subprocess.run(["sudo", "apt-get", "install", "-y", "git"], check=True)

        elif os_name == "darwin":
            info("Installing git via Homebrew...")
            subprocess.run(["brew", "install", "git"], check=True)

        elif os_name == "windows":
            info("Installing git via winget...")
            subprocess.run(
                ["winget", "install", "--id", "Git.Git", "-e", "--source", "winget"],
                check=True,
            )

        else:
            error(f"Unsupported OS: {os_name}. Please install git manually.")
            raise RuntimeError(f"Cannot install git on unsupported OS: {os_name}")

    def version(self) -> str:
        """Return the installed git version string."""
        if not self.detect():
            return "not installed"
        result = subprocess.run(
            ["git", "--version"], capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
