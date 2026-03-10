"""
devsetup.utils.logger
---------------------
Centralised logging utility.  All CLI output must be routed through
these helpers instead of raw print() calls.
"""

import sys


def info(message: str) -> None:
    """Print an informational message to stdout."""
    print(f"[INFO]    {message}")


def error(message: str) -> None:
    """Print an error message to stderr."""
    print(f"[ERROR]   {message}", file=sys.stderr)


def success(message: str) -> None:
    """Print a success message to stdout."""
    print(f"[OK]      {message}")


def warn(message: str) -> None:
    """Print a warning message to stdout."""
    print(f"[WARN]    {message}")


def check(message: str) -> None:
    """Print a check/detection message to stdout."""
    print(f"[CHECK]   {message}")


def skip(message: str) -> None:
    """Print a skip message when tool is already installed."""
    print(f"[SKIP]    {message}")


def install(message: str) -> None:
    """Print an install action message to stdout."""
    print(f"[INSTALL] {message}")
