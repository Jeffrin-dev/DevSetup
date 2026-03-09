"""
devsetup.utils.logger
---------------------
Centralised logging utility.  All CLI output must be routed through
these helpers instead of raw print() calls.
"""

import sys


def info(message: str) -> None:
    """Print an informational message to stdout."""
    print(f"[INFO]  {message}")


def error(message: str) -> None:
    """Print an error message to stderr."""
    print(f"[ERROR] {message}", file=sys.stderr)


def success(message: str) -> None:
    """Print a success message to stdout."""
    print(f"[OK]    {message}")


def warn(message: str) -> None:
    """Print a warning message to stdout."""
    print(f"[WARN]  {message}")
