"""
devsetup.system.package_managers.apt_manager
---------------------------------------------
Package manager wrapper for apt (Debian / Ubuntu).

v1.9 (Stability Pass):
  _run() removed — inherited from BasePackageManager.
"""

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
