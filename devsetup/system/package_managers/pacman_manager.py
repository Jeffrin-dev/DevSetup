"""
devsetup.system.package_managers.pacman_manager
-------------------------------------------------
Package manager wrapper for pacman (Arch Linux).

v1.9 (Stability Pass):
  _run() removed — inherited from BasePackageManager.
"""

from devsetup.system.package_managers.base import BasePackageManager, PackageManagerError
from devsetup.utils.logger import info


class PacmanManager(BasePackageManager):
    manager_name = "pacman"

    def update(self) -> None:
        """Sync the pacman package database."""
        info("Syncing pacman package database...")
        self._run(["sudo", "pacman", "-Sy"])

    def install(self, package_name: str) -> None:
        """Install a package using pacman."""
        info(f"Installing {package_name} using pacman...")
        self._run(["sudo", "pacman", "-S", "--noconfirm", package_name])
