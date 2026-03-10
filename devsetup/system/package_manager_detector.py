"""
devsetup.system.package_manager_detector
-----------------------------------------
Centralized package manager detection module.

Responsibilities:
  - Identify the available system package manager at runtime
  - Provide normalized package manager identifiers
  - Expose a clean API to all installer modules

Canonical PM identifiers:
  apt     — Debian / Ubuntu and derivatives
  dnf     — Fedora / RHEL and derivatives
  pacman  — Arch Linux and derivatives
  brew    — macOS Homebrew
  winget  — Windows Package Manager

No installation logic. No business logic. Detection only.
"""

import shutil

# Canonical package manager identifier constants
APT    = "apt"
DNF    = "dnf"
PACMAN = "pacman"
BREW   = "brew"
WINGET = "winget"

# Linux managers checked in priority order
_LINUX_MANAGERS = [APT, DNF, PACMAN]


def get_package_manager() -> str:
    """
    Detect and return the normalized package manager identifier.

    On Linux, checks for apt → dnf → pacman in priority order.
    On macOS, checks for brew.
    On Windows, checks for winget.

    Returns
    -------
    str
        One of: 'apt', 'dnf', 'pacman', 'brew', 'winget'

    Raises
    ------
    RuntimeError
        If no supported package manager is detected.
    """
    from devsetup.system.os_detector import get_os, LINUX, MACOS, WINDOWS

    os_name = get_os()

    if os_name == LINUX:
        for manager in _LINUX_MANAGERS:
            if shutil.which(manager) is not None:
                return manager
        raise RuntimeError(
            "No supported package manager found on Linux. "
            "DevSetup supports: apt, dnf, pacman."
        )

    elif os_name == MACOS:
        if shutil.which(BREW) is not None:
            return BREW
        raise RuntimeError(
            "Homebrew not installed. "
            "Install it from https://brew.sh before running DevSetup."
        )

    elif os_name == WINDOWS:
        if shutil.which(WINGET) is not None:
            return WINGET
        raise RuntimeError(
            "winget not found. "
            "Install it from the Microsoft Store before running DevSetup."
        )


def is_apt() -> bool:
    """Return True if apt is the active package manager."""
    try:
        return get_package_manager() == APT
    except RuntimeError:
        return False


def is_dnf() -> bool:
    """Return True if dnf is the active package manager."""
    try:
        return get_package_manager() == DNF
    except RuntimeError:
        return False


def is_pacman() -> bool:
    """Return True if pacman is the active package manager."""
    try:
        return get_package_manager() == PACMAN
    except RuntimeError:
        return False


def is_brew() -> bool:
    """Return True if brew is the active package manager."""
    try:
        return get_package_manager() == BREW
    except RuntimeError:
        return False


def is_winget() -> bool:
    """Return True if winget is the active package manager."""
    try:
        return get_package_manager() == WINGET
    except RuntimeError:
        return False
