"""
devsetup.system.package_managers.brew_manager
----------------------------------------------
Package manager wrapper for Homebrew (macOS).

Commands:
  update:  brew update
  install: brew install <package>
"""

import subprocess
from devsetup.system.package_managers.base import BasePackageManager
from devsetup.utils.logger import info


class BrewManager(BasePackageManager):
    manager_name = "brew"

    def update(self) -> None:
        """Update Homebrew and its formulae."""
        info("Updating Homebrew...")
        subprocess.run(["brew", "update"], check=True)

    def install(self, package_name: str) -> None:
        """Install a package using Homebrew."""
        info(f"Installing {package_name} using brew...")
        subprocess.run(["brew", "install", package_name], check=True)
