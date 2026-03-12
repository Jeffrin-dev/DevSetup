"""
devsetup.system.package_managers.pacman_manager
-------------------------------------------------
Package manager wrapper for pacman (Arch Linux).

Commands:
  update:  sudo pacman -Sy
  install: sudo pacman -S --noconfirm <package>
"""

import subprocess
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

    def _run(self, cmd: list) -> None:
        """Execute a command, translating errors to PackageManagerError."""
        try:
            subprocess.run(cmd, check=True)
        except FileNotFoundError:
            raise PackageManagerError(
                f"pacman binary not found — is pacman installed?",
                pm_exit_code=-1,
            )
        except PermissionError:
            raise PackageManagerError(
                f"Permission denied running: {' '.join(cmd)}",
                pm_exit_code=-1,
            )
        except subprocess.CalledProcessError as exc:
            raise PackageManagerError(
                f"pacman command failed: {' '.join(cmd)}",
                pm_exit_code=exc.returncode,
            )
