"""
devsetup.installers.node
------------------------
Isolated installer module for Node.js.

All OS-specific branching lives here (Architecture Rule 5).
Implements the standard BaseInstaller interface (Architecture Rule 4).
"""

import platform
import shutil
import subprocess

from devsetup.installers.base import BaseInstaller
from devsetup.utils.logger import info, error


class NodeInstaller(BaseInstaller):
    tool_name = "node"

    def detect(self) -> bool:
        """Return True if node is available on PATH."""
        return shutil.which("node") is not None

    def install(self) -> None:
        """Install Node.js using the OS-appropriate method."""
        os_name = platform.system().lower()

        if os_name == "linux":
            info("Installing Node.js via apt-get...")
            subprocess.run(["sudo", "apt-get", "install", "-y", "nodejs", "npm"], check=True)

        elif os_name == "darwin":
            info("Installing Node.js via Homebrew...")
            subprocess.run(["brew", "install", "node"], check=True)

        elif os_name == "windows":
            info("Installing Node.js via winget...")
            subprocess.run(
                ["winget", "install", "--id", "OpenJS.NodeJS", "-e"],
                check=True,
            )

        else:
            error(f"Unsupported OS: {os_name}. Please install Node.js manually.")
            raise RuntimeError(f"Cannot install node on unsupported OS: {os_name}")

    def version(self) -> str:
        """Return the installed node version string."""
        if not self.detect():
            return "not installed"
        result = subprocess.run(
            ["node", "--version"], capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
