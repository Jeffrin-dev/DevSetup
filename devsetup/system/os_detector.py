"""
devsetup.system.os_detector
----------------------------
Centralized operating system detection module.

Responsibilities:
  - Identify the current operating system at runtime
  - Provide normalized OS identifiers
  - Expose a clean API to all installer modules

Canonical OS values returned:
  linux   — any Linux distribution
  macos   — Apple macOS (darwin)
  windows — Microsoft Windows

No installation logic. No business logic. Detection only.
"""

import platform

# Canonical OS identifier constants
LINUX = "linux"
MACOS = "macos"
WINDOWS = "windows"

# Internal mapping from platform.system() raw values
_PLATFORM_MAP = {
    "linux": LINUX,
    "darwin": MACOS,
    "windows": WINDOWS,
}


def get_os() -> str:
    """
    Return the normalized operating system identifier.

    Returns
    -------
    str
        One of: 'linux', 'macos', 'windows'

    Raises
    ------
    RuntimeError
        If the operating system is not supported.
    """
    raw = platform.system().lower()
    normalized = _PLATFORM_MAP.get(raw)

    if normalized is None:
        raise RuntimeError(
            f"Unsupported operating system: '{raw}'. "
            f"DevSetup supports: {list(_PLATFORM_MAP.values())}"
        )

    return normalized


def is_linux() -> bool:
    """Return True if the current OS is Linux."""
    try:
        return get_os() == LINUX
    except RuntimeError:
        return False


def is_macos() -> bool:
    """Return True if the current OS is macOS."""
    try:
        return get_os() == MACOS
    except RuntimeError:
        return False


def is_windows() -> bool:
    """Return True if the current OS is Windows."""
    try:
        return get_os() == WINDOWS
    except RuntimeError:
        return False
