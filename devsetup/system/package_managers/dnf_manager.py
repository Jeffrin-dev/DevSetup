"""
devsetup.system.package_managers.dnf_manager
---------------------------------------------
Package manager wrapper for dnf (Fedora / RHEL).

v1.9 (Stability Pass):
  _run() removed — inherited from BasePackageManager.
  allow_nonzero={100} passed directly to _run() for check-update.
"""

from devsetup.system.package_managers.base import BasePackageManager, PackageManagerError
from devsetup.utils.logger import info


class DnfManager(BasePackageManager):
    manager_name = "dnf"

    def update(self) -> None:
        """Check for dnf updates (exit 100 = updates available, treated as success)."""
        info("Checking dnf for updates...")
        self._run(["sudo", "dnf", "check-update"], allow_nonzero={100})

    def install(self, package_name: str) -> None:
        """Install a package using dnf."""
        info(f"Installing {package_name} using dnf...")
        self._run(["sudo", "dnf", "install", "-y", package_name])
