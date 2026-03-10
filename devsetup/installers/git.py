"""
devsetup.installers.git
-----------------------
Isolated installer module for Git.

OS detection is delegated to devsetup.system.os_detector (Architecture Rule 5).
Implements the standard BaseInstaller interface (Architecture Rule 4).
"""

import shutil
import subprocess

from devsetup.installers.base import BaseInstaller
from devsetup.system.os_detector import get_os, LINUX, MACOS, WINDOWS
from devsetup.utils.logger import info, error


class GitInstaller(BaseInstaller):
    tool_name = "git"

    def detect(self) -> bool:
        """Return True if git is available on PATH."""
        return shutil.which("git") is not None

    def install(self) -> None:
        """Install git using the OS-appropriate package manager."""
        os_name = get_os()

        if os_name == LINUX:
            info("Installing git via apt-get...")
            subprocess.run(["sudo", "apt-get", "install", "-y", "git"], check=True)

        elif os_name == MACOS:
            info("Installing git via Homebrew...")
            subprocess.run(["brew", "install", "git"], check=True)

        elif os_name == WINDOWS:
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
