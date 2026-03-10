from devsetup.system.os_detector import get_os, is_linux, is_macos, is_windows
from devsetup.system.package_manager_detector import (
    get_package_manager,
    is_apt, is_dnf, is_pacman, is_brew, is_winget,
)

__all__ = [
    "get_os", "is_linux", "is_macos", "is_windows",
    "get_package_manager", "is_apt", "is_dnf", "is_pacman", "is_brew", "is_winget",
]
