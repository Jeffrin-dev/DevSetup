"""
devsetup.utils.logger
---------------------
Centralised logging utility. All CLI output must be routed through
these helpers instead of raw print() calls.

Log levels supported:
  [INFO]    — general information
  [WARN]    — non-fatal warning
  [ERROR]   — error, written to stderr
  [DEBUG]   — verbose diagnostics (enabled via DEVSETUP_DEBUG=1)
  [CHECK]   — tool detection in progress
  [SKIP]    — tool already installed, skipping
  [INSTALL] — tool installation starting
  [OK]      — success confirmation
  [FAIL]    — installation failure
  [VERSION] — confirmed installed version (v1.3)
  [BLOCKED] — tool skipped because a dependency failed (v1.4, stderr)
  [DEPS]    — dependency resolution progress messages (v1.4, stdout)
  [VALID]   — environment config passed validation (v1.5, stdout)
  [INVALID] — environment config failed validation (v1.5, stderr)

All messages include a timestamp for debugging.
"""

import os
import sys
from datetime import datetime


def _timestamp() -> str:
    """Return current time formatted as HH:MM:SS."""
    return datetime.now().strftime("%H:%M:%S")


def _is_debug() -> bool:
    """Return True if debug output is enabled via environment variable."""
    return os.environ.get("DEVSETUP_DEBUG", "").strip() == "1"


def info(message: str) -> None:
    """Print an informational message to stdout."""
    print(f"[{_timestamp()}] [INFO]    {message}")


def error(message: str) -> None:
    """Print an error message to stderr."""
    print(f"[{_timestamp()}] [ERROR]   {message}", file=sys.stderr)


def success(message: str) -> None:
    """Print a success message to stdout."""
    print(f"[{_timestamp()}] [OK]      {message}")


def warn(message: str) -> None:
    """Print a warning message to stdout."""
    print(f"[{_timestamp()}] [WARN]    {message}")


def check(message: str) -> None:
    """Print a check/detection message to stdout."""
    print(f"[{_timestamp()}] [CHECK]   {message}")


def skip(message: str) -> None:
    """Print a skip message when tool is already installed."""
    print(f"[{_timestamp()}] [SKIP]    {message}")


def install(message: str) -> None:
    """Print an install action message to stdout."""
    print(f"[{_timestamp()}] [INSTALL] {message}")


def fail(message: str) -> None:
    """Print a failure message to stderr."""
    print(f"[{_timestamp()}] [FAIL]    {message}", file=sys.stderr)


def version_log(message: str) -> None:
    """
    Print a confirmed version string to stdout.

    Used after installation or skip to confirm the tool is present
    and working (v1.3 — Phase 5).

    Example output:
        [HH:MM:SS] [VERSION] 2.43.0
    """
    print(f"[{_timestamp()}] [VERSION] {message}")


def debug(message: str) -> None:
    """Print a debug message to stdout (only when DEVSETUP_DEBUG=1)."""
    if _is_debug():
        print(f"[{_timestamp()}] [DEBUG]   {message}")


def blocked(message: str) -> None:
    """
    Print a blocked tool message to stderr (v1.4).

    Used when a tool is not installed because a dependency failed.

    Example output:
        [HH:MM:SS] [BLOCKED] vscode (dependency 'node' failed)
    """
    print(f"[{_timestamp()}] [BLOCKED] {message}", file=sys.stderr)


def dep_order(message: str) -> None:
    """
    Print a dependency resolution message to stdout (v1.4).

    Used to log the computed install order before execution begins.

    Example output:
        [HH:MM:SS] [DEPS]    Computed install order: git → node → vscode
    """
    print(f"[{_timestamp()}] [DEPS]    {message}")


def valid(message: str) -> None:
    """
    Print a validation-passed message to stdout (v1.5).

    Used during environment loading to confirm a config passed all checks.

    Example output:
        [HH:MM:SS] [VALID]   ✓ web
    """
    print(f"[{_timestamp()}] [VALID]   {message}")


def invalid(message: str) -> None:
    """
    Print a validation-failed message to stderr (v1.5).

    Used during environment loading when a config fails any check.

    Example output:
        [HH:MM:SS] [INVALID] ✗ web — duplicate tool 'git'
    """
    print(f"[{_timestamp()}] [INVALID] {message}", file=sys.stderr)
