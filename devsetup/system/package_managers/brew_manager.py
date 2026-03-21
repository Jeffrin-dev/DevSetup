"""
devsetup.system.package_managers.brew_manager
----------------------------------------------
Package manager wrapper for Homebrew (macOS).

v1.9 (Stability Pass):
  _run() removed — inherited from BasePackageManager.
"""

from devsetup.system.package_managers.base import BasePackageManager, PackageManagerError
from devsetup.utils.logger import info


class BrewManager(BasePackageManager):
    manager_name = "brew"

    def update(self) -> None:
        """Update Homebrew and its formulae."""
        info("Updating Homebrew...")
        self._run(["brew", "update"])

    def install(self, package_name: str) -> None:
        """Install a package using Homebrew."""
        info(f"Installing {package_name} using brew...")
        self._run(["brew", "install", package_name])
