"""
devsetup.system.package_managers.winget_manager
-------------------------------------------------
Package manager wrapper for winget (Windows).

Commands:
  update:  winget upgrade
  install: winget install --id <package> -e
"""

import subprocess
from devsetup.system.package_managers.base import BasePackageManager
from devsetup.utils.logger import info


class WingetManager(BasePackageManager):
    manager_name = "winget"

    def update(self) -> None:
        """Check for winget package upgrades."""
        info("Checking winget upgrades...")
        subprocess.run(["winget", "upgrade"], check=False)

    def install(self, package_name: str) -> None:
        """Install a package using winget."""
        info(f"Installing {package_name} using winget...")
        subprocess.run(
            ["winget", "install", "--id", package_name, "-e"],
            check=True,
        )
