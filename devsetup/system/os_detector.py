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

Patch (v1.3.1):
  - Introduced UnsupportedOSError(RuntimeError) so callers can catch
    OS errors precisely without string matching.
"""

import platform

# Canonical OS identifier constants
LINUX = "linux"
MACOS = "macos"
WINDOWS = "windows"

# Internal mapping from platform.system() raw values
_PLATFORM_MAP = {
    "linux":   LINUX,
    "darwin":  MACOS,
    "windows": WINDOWS,
}


class UnsupportedOSError(RuntimeError):
    """
    Raised when the current operating system is not supported by DevSetup.

    Replaces the plain RuntimeError previously raised by get_os(), allowing
    callers to catch OS errors precisely without fragile string matching.

    Attributes
    ----------
    os_name : str
        The raw platform string that was not recognised (e.g. 'freebsd').
    """

    def __init__(self, os_name: str) -> None:
        super().__init__(
            f"Unsupported operating system: '{os_name}'. "
            f"DevSetup supports: {list(_PLATFORM_MAP.values())}"
        )
        self.os_name = os_name


def get_os() -> str:
    """
    Return the normalized operating system identifier.

    Returns
    -------
    str
        One of: 'linux', 'macos', 'windows'

    Raises
    ------
    UnsupportedOSError
        If the operating system is not supported.
    """
    raw = platform.system().lower()
    normalized = _PLATFORM_MAP.get(raw)

    if normalized is None:
        raise UnsupportedOSError(raw)

    return normalized


def is_linux() -> bool:
    """Return True if the current OS is Linux."""
    try:
        return get_os() == LINUX
    except UnsupportedOSError:
        return False


def is_macos() -> bool:
    """Return True if the current OS is macOS."""
    try:
        return get_os() == MACOS
    except UnsupportedOSError:
        return False


def is_windows() -> bool:
    """Return True if the current OS is Windows."""
    try:
        return get_os() == WINDOWS
    except UnsupportedOSError:
        return False
