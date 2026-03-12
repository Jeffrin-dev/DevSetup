"""
devsetup.system.package_managers.apt_manager
---------------------------------------------
Package manager wrapper for apt (Debian / Ubuntu).

Commands:
  update:  sudo apt-get update
  install: sudo apt-get install -y <package>
"""

import subprocess
from devsetup.system.package_managers.base import BasePackageManager, PackageManagerError
from devsetup.utils.logger import info


class AptManager(BasePackageManager):
    manager_name = "apt"

    def update(self) -> None:
        """Refresh the apt package index."""
        info("Updating apt package index...")
        self._run(["sudo", "apt-get", "update"])

    def install(self, package_name: str) -> None:
        """Install a package using apt-get."""
        info(f"Installing {package_name} using apt...")
        self._run(["sudo", "apt-get", "install", "-y", package_name])

    def _run(self, cmd: list) -> None:
        """Execute a command, translating errors to PackageManagerError."""
        try:
            subprocess.run(cmd, check=True)
        except FileNotFoundError:
            raise PackageManagerError(
                f"apt-get binary not found — is apt installed?",
                pm_exit_code=-1,
            )
        except PermissionError:
            raise PackageManagerError(
                f"Permission denied running: {' '.join(cmd)}",
                pm_exit_code=-1,
            )
        except subprocess.CalledProcessError as exc:
            raise PackageManagerError(
                f"apt command failed: {' '.join(cmd)}",
                pm_exit_code=exc.returncode,
            )
