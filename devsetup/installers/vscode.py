"""
devsetup.installers.vscode
--------------------------
Isolated installer module for Visual Studio Code.

OS detection is delegated to devsetup.system.os_detector (Architecture Rule 5).
Implements the standard BaseInstaller interface (Architecture Rule 4).
"""

import shutil
import subprocess

from devsetup.installers.base import BaseInstaller
from devsetup.system.os_detector import get_os, LINUX, MACOS, WINDOWS
from devsetup.utils.logger import info, error


class VSCodeInstaller(BaseInstaller):
    tool_name = "vscode"

    def detect(self) -> bool:
        """Return True if the 'code' CLI is available on PATH."""
        return shutil.which("code") is not None

    def install(self) -> None:
        """Install VS Code using the OS-appropriate method."""
        os_name = get_os()

        if os_name == LINUX:
            info("Installing VS Code via snap...")
            subprocess.run(["sudo", "snap", "install", "--classic", "code"], check=True)

        elif os_name == MACOS:
            info("Installing VS Code via Homebrew cask...")
            subprocess.run(["brew", "install", "--cask", "visual-studio-code"], check=True)

        elif os_name == WINDOWS:
            info("Installing VS Code via winget...")
            subprocess.run(
                ["winget", "install", "--id", "Microsoft.VisualStudioCode", "-e"],
                check=True,
            )

        else:
            error(f"Unsupported OS: {os_name}. Please install VS Code manually.")
            raise RuntimeError(f"Cannot install vscode on unsupported OS: {os_name}")

    def version(self) -> str:
        """Return the installed VS Code version string."""
        if not self.detect():
            return "not installed"
        result = subprocess.run(
            ["code", "--version"], capture_output=True, text=True, check=True
        )
        return result.stdout.splitlines()[0].strip()
