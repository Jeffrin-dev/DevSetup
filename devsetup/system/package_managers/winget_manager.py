"""
devsetup.system.package_managers.winget_manager
-------------------------------------------------
Package manager wrapper for winget (Windows).

v1.9 (Stability Pass):
  _run() removed — inherited from BasePackageManager.
  update() uses _run() with check=False semantics via allow_nonzero
  since winget upgrade may return non-zero for partial upgrades.
"""

from devsetup.system.package_managers.base import BasePackageManager, PackageManagerError
from devsetup.utils.logger import info


class WingetManager(BasePackageManager):
    manager_name = "winget"

    def update(self) -> None:
        """Upgrade all packages via winget (non-fatal on partial failure)."""
        info("Running winget upgrade...")
        # winget upgrade may return non-zero when some packages cannot update;
        # treat any exit code as success for the upgrade check (non-blocking).
        try:
            self._run(["winget", "upgrade"])
        except PackageManagerError:
            pass  # upgrade failures are non-fatal

    def install(self, package_name: str) -> None:
        """Install a package using winget."""
        info(f"Installing {package_name} using winget...")
        self._run(
            ["winget", "install", "--id", package_name, "--exact", "--silent"]
        )
