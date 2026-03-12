"""
devsetup.system.package_managers.winget_manager
-------------------------------------------------
Package manager wrapper for winget (Windows).

Commands:
  update:  winget upgrade
  install: winget install --id <package> --exact --silent
"""

import subprocess
from devsetup.system.package_managers.base import BasePackageManager, PackageManagerError
from devsetup.utils.logger import info


class WingetManager(BasePackageManager):
    manager_name = "winget"

    def update(self) -> None:
        """Upgrade all packages via winget (non-fatal on partial failure)."""
        info("Running winget upgrade...")
        try:
            subprocess.run(["winget", "upgrade"], check=False)
        except FileNotFoundError:
            raise PackageManagerError(
                "winget binary not found — is winget installed?",
                pm_exit_code=-1,
            )

    def install(self, package_name: str) -> None:
        """Install a package using winget."""
        info(f"Installing {package_name} using winget...")
        self._run(
            ["winget", "install", "--id", package_name, "--exact", "--silent"]
        )

    def _run(self, cmd: list) -> None:
        """Execute a command, translating errors to PackageManagerError."""
        try:
            subprocess.run(cmd, check=True)
        except FileNotFoundError:
            raise PackageManagerError(
                "winget binary not found — is winget installed?",
                pm_exit_code=-1,
            )
        except PermissionError:
            raise PackageManagerError(
                f"Permission denied running: {' '.join(cmd)}",
                pm_exit_code=-1,
            )
        except subprocess.CalledProcessError as exc:
            raise PackageManagerError(
                f"winget command failed: {' '.join(cmd)}",
                pm_exit_code=exc.returncode,
            )
