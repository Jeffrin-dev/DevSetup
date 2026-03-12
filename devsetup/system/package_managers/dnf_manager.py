"""
devsetup.system.package_managers.dnf_manager
---------------------------------------------
Package manager wrapper for dnf (Fedora / RHEL).

Commands:
  update:  sudo dnf check-update
  install: sudo dnf install -y <package>
"""

import subprocess
from devsetup.system.package_managers.base import BasePackageManager, PackageManagerError
from devsetup.utils.logger import info


class DnfManager(BasePackageManager):
    manager_name = "dnf"

    def update(self) -> None:
        """Check for dnf updates (non-fatal if packages need updating)."""
        info("Checking dnf for updates...")
        self._run(["sudo", "dnf", "check-update"], allow_nonzero={100})

    def install(self, package_name: str) -> None:
        """Install a package using dnf."""
        info(f"Installing {package_name} using dnf...")
        self._run(["sudo", "dnf", "install", "-y", package_name])

    def _run(self, cmd: list, allow_nonzero: set = None) -> None:
        """Execute a command, translating errors to PackageManagerError."""
        try:
            result = subprocess.run(cmd, check=False)
            if result.returncode != 0:
                if allow_nonzero and result.returncode in allow_nonzero:
                    return
                raise PackageManagerError(
                    f"dnf command failed: {' '.join(cmd)}",
                    pm_exit_code=result.returncode,
                )
        except FileNotFoundError:
            raise PackageManagerError(
                f"dnf binary not found — is dnf installed?",
                pm_exit_code=-1,
            )
        except PermissionError:
            raise PackageManagerError(
                f"Permission denied running: {' '.join(cmd)}",
                pm_exit_code=-1,
            )
        except subprocess.CalledProcessError as exc:
            raise PackageManagerError(
                f"dnf command failed: {' '.join(cmd)}",
                pm_exit_code=exc.returncode,
            )
