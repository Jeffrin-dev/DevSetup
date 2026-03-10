"""
devsetup.system.package_managers.pacman_manager
-------------------------------------------------
Package manager wrapper for pacman (Arch Linux).

Commands:
  update:  sudo pacman -Sy
  install: sudo pacman -S --noconfirm <package>
"""

import subprocess
from devsetup.system.package_managers.base import BasePackageManager
from devsetup.utils.logger import info


class PacmanManager(BasePackageManager):
    manager_name = "pacman"

    def update(self) -> None:
        """Sync the pacman package database."""
        info("Syncing pacman package database...")
        subprocess.run(["sudo", "pacman", "-Sy"], check=True)

    def install(self, package_name: str) -> None:
        """Install a package using pacman."""
        info(f"Installing {package_name} using pacman...")
        subprocess.run(
            ["sudo", "pacman", "-S", "--noconfirm", package_name],
            check=True,
        )
