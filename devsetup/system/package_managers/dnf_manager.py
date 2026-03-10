"""
devsetup.system.package_managers.dnf_manager
---------------------------------------------
Package manager wrapper for dnf (Fedora / RHEL).

Commands:
  update:  sudo dnf check-update
  install: sudo dnf install -y <package>
"""

import subprocess
from devsetup.system.package_managers.base import BasePackageManager
from devsetup.utils.logger import info


class DnfManager(BasePackageManager):
    manager_name = "dnf"

    def update(self) -> None:
        """Check for dnf package updates."""
        info("Checking dnf package updates...")
        subprocess.run(["sudo", "dnf", "check-update"], check=False)

    def install(self, package_name: str) -> None:
        """Install a package using dnf."""
        info(f"Installing {package_name} using dnf...")
        subprocess.run(
            ["sudo", "dnf", "install", "-y", package_name],
            check=True,
        )
