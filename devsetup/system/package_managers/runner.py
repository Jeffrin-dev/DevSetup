"""
devsetup.system.package_managers.runner
-----------------------------------------
Package manager runner — selects the correct package manager
module based on the detected system and exposes a unified
install(package_name) / update() interface to installer modules.

Installers call this instead of invoking package managers directly.
"""

from devsetup.system.package_manager_detector import (
    get_package_manager,
    APT, DNF, PACMAN, BREW, WINGET,
)
from devsetup.system.package_managers.apt_manager    import AptManager
from devsetup.system.package_managers.dnf_manager    import DnfManager
from devsetup.system.package_managers.pacman_manager import PacmanManager
from devsetup.system.package_managers.brew_manager   import BrewManager
from devsetup.system.package_managers.winget_manager import WingetManager
from devsetup.system.package_managers.base           import BasePackageManager

_MANAGER_MAP = {
    APT:    AptManager,
    DNF:    DnfManager,
    PACMAN: PacmanManager,
    BREW:   BrewManager,
    WINGET: WingetManager,
}


class PackageManagerRunner:
    """
    Unified interface to the active system package manager.

    Usage
    -----
        pm = PackageManagerRunner()
        pm.install("git")
        pm.update()

    The correct manager is resolved once on construction.
    """

    def __init__(self) -> None:
        manager_id = get_package_manager()
        self._manager: BasePackageManager = _MANAGER_MAP[manager_id]()
        self.name: str = manager_id

    def install(self, package_name: str) -> None:
        """Install a package using the active package manager."""
        self._manager.install(package_name)

    def update(self) -> None:
        """Update the package index using the active package manager."""
        self._manager.update()
