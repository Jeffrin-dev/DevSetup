"""
devsetup.system.package_managers.apt_manager
---------------------------------------------
Package manager wrapper for apt (Debian / Ubuntu).

Commands:
  update:  sudo apt-get update
  install: sudo apt-get install -y <package>
"""

import subprocess
from devsetup.system.package_managers.base import BasePackageManager
from devsetup.utils.logger import info


class AptManager(BasePackageManager):
    manager_name = "apt"

    def update(self) -> None:
        """Refresh the apt package index."""
        info("Updating apt package index...")
        subprocess.run(["sudo", "apt-get", "update"], check=True)

    def install(self, package_name: str) -> None:
        """Install a package using apt-get."""
        info(f"Installing {package_name} using apt...")
        subprocess.run(
            ["sudo", "apt-get", "install", "-y", package_name],
            check=True,
        )
