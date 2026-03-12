"""
devsetup.system.package_managers.brew_manager
----------------------------------------------
Package manager wrapper for Homebrew (macOS).

Commands:
  update:  brew update
  install: brew install <package>
"""

import subprocess
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

    def _run(self, cmd: list) -> None:
        """Execute a command, translating errors to PackageManagerError."""
        try:
            subprocess.run(cmd, check=True)
        except FileNotFoundError:
            raise PackageManagerError(
                f"brew binary not found — is Homebrew installed?",
                pm_exit_code=-1,
            )
        except PermissionError:
            raise PackageManagerError(
                f"Permission denied running: {' '.join(cmd)}",
                pm_exit_code=-1,
            )
        except subprocess.CalledProcessError as exc:
            raise PackageManagerError(
                f"brew command failed: {' '.join(cmd)}",
                pm_exit_code=exc.returncode,
            )
