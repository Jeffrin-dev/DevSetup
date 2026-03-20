"""
devsetup.utils.logger
---------------------
Centralised logging utility for DevSetup v1.8.

All CLI output must be routed through these helpers — never raw print().

Log levels:
  [INFO]    — general information
  [WARN]    — non-fatal warning
  [ERROR]   — error, written to stderr
  [OK]      — success confirmation
  [CHECK]   — tool detection in progress
  [SKIP]    — tool already installed, skipping
  [INSTALL] — tool installation starting
  [FAIL]    — installation failure, written to stderr
  [VERSION] — confirmed installed version (v1.3)
  [BLOCKED] — tool skipped because a dependency failed (v1.4, stderr)
  [DEPS]    — dependency resolution progress (v1.4)
  [VALID]   — environment config passed validation (v1.5)
  [INVALID] — environment config failed validation (v1.5, stderr)
  [AUTO]    — prompt auto-accepted in non-interactive mode (v1.7)
  [VERBOSE] — detailed diagnostics, gated on DEVSETUP_VERBOSE=1 (v1.8)
  [DEBUG]   — internal debug output, gated on DEVSETUP_DEBUG=1

Timestamp format (v1.8):
  [VERBOSE] lines : YYYY-MM-DD HH:MM:SS  (full, for traceability — Phase 7)
  All other lines : HH:MM:SS             (short — deterministic contract)

Log file (v1.8, Phase 12):
  Set DEVSETUP_LOG_FILE=<path> or call set_log_file(path) to tee all
  output to a file in addition to stdout/stderr.

Verbosity (v1.8):
  set_verbose(True)  — equivalent to DEVSETUP_VERBOSE=1
  set_log_file(path) — equivalent to DEVSETUP_LOG_FILE=path
"""

import os
import sys
from datetime import datetime
from typing import Optional

# ── Module-level state (overridden by set_* helpers or env vars) ──────────────
_verbose_override: Optional[bool] = None
_log_file_path:    Optional[str]  = None


# ── Configuration helpers (Phase 2 / Phase 12) ────────────────────────────────

def set_verbose(flag: bool) -> None:
    """
    Enable or disable verbose mode programmatically (v1.8).

    Equivalent to setting DEVSETUP_VERBOSE=1 in the environment.
    Used by cmd_install when --verbose is parsed from CLI args.
    """
    global _verbose_override
    _verbose_override = flag


def set_log_file(path: Optional[str]) -> None:
    """
    Set an optional log file path (v1.8, Phase 12).

    When set, all log output is tee'd to this file in addition to
    stdout/stderr. Pass None to disable file logging.
    """
    global _log_file_path
    _log_file_path = path


# ── Internal helpers ──────────────────────────────────────────────────────────

def _is_verbose() -> bool:
    """Return True if verbose mode is active (v1.8)."""
    if _verbose_override is not None:
        return _verbose_override
    return os.environ.get("DEVSETUP_VERBOSE", "").strip() == "1"


def _is_debug() -> bool:
    """Return True if debug output is enabled via environment variable."""
    return os.environ.get("DEVSETUP_DEBUG", "").strip() == "1"


def _timestamp() -> str:
    """
    Return a short timestamp: HH:MM:SS.

    Used by all log levels except [VERBOSE].
    This format is the established output contract — always deterministic
    regardless of verbose mode (Architecture Rule 9).
    """
    return datetime.now().strftime("%H:%M:%S")


def _timestamp_full() -> str:
    """
    Return a full timestamp: YYYY-MM-DD HH:MM:SS (v1.8, Phase 7).

    Used exclusively by verbose() so that [VERBOSE] lines carry full
    date+time context for traceability in CI/CD logs, while all other
    log levels keep the established short HH:MM:SS format.
    """
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _emit(message: str, file=None) -> None:
    """
    Write a formatted log line to the target stream and optionally to file.

    Centralises the tee-to-file logic so every log function benefits
    from --log-file without any per-function boilerplate (Phase 12).
    """
    stream = file if file is not None else sys.stdout
    print(message, file=stream)

    path = _log_file_path or os.environ.get("DEVSETUP_LOG_FILE", "").strip()
    if path:
        try:
            with open(path, "a", encoding="utf-8") as fh:
                print(message, file=fh)
        except OSError:
            pass   # never let file I/O errors crash the install pipeline


# ── Public log functions ──────────────────────────────────────────────────────

def info(message: str) -> None:
    """Print an informational message to stdout."""
    _emit(f"[{_timestamp()}] [INFO]    {message}")


def error(message: str) -> None:
    """Print an error message to stderr."""
    _emit(f"[{_timestamp()}] [ERROR]   {message}", file=sys.stderr)


def success(message: str) -> None:
    """Print a success message to stdout."""
    _emit(f"[{_timestamp()}] [OK]      {message}")


def warn(message: str) -> None:
    """Print a warning message to stdout."""
    _emit(f"[{_timestamp()}] [WARN]    {message}")


def check(message: str) -> None:
    """Print a check/detection message to stdout."""
    _emit(f"[{_timestamp()}] [CHECK]   {message}")


def skip(message: str) -> None:
    """Print a skip message when tool is already installed."""
    _emit(f"[{_timestamp()}] [SKIP]    {message}")


def install(message: str) -> None:
    """Print an install action message to stdout."""
    _emit(f"[{_timestamp()}] [INSTALL] {message}")


def fail(message: str) -> None:
    """Print a failure message to stderr."""
    _emit(f"[{_timestamp()}] [FAIL]    {message}", file=sys.stderr)


def version_log(message: str) -> None:
    """
    Print a confirmed version string to stdout (v1.3).

    Example output:
        [HH:MM:SS] [VERSION] 2.43.0
    """
    _emit(f"[{_timestamp()}] [VERSION] {message}")


def debug(message: str) -> None:
    """Print a debug message to stdout (only when DEVSETUP_DEBUG=1)."""
    if _is_debug():
        _emit(f"[{_timestamp()}] [DEBUG]   {message}")


def verbose(message: str) -> None:
    """
    Print a verbose diagnostic message to stdout (v1.8, Phase 4/11).

    Shown only when --verbose is active (DEVSETUP_VERBOSE=1).
    Uses a full YYYY-MM-DD HH:MM:SS timestamp for traceability (Phase 7),
    while all other log levels keep the short HH:MM:SS format so the
    established output contract is never altered (Architecture Rule 9).

    Example output:
        [2026-03-20 16:00:03] [VERBOSE] DependencyResolver: git -> node
        [2026-03-20 16:00:04] [VERBOSE] Version detected: Node.js 20.2.0
    """
    if _is_verbose():
        _emit(f"[{_timestamp_full()}] [VERBOSE] {message}")


def blocked(message: str) -> None:
    """
    Print a blocked tool message to stderr (v1.4).

    Example output:
        [HH:MM:SS] [BLOCKED] vscode (dependency 'node' failed)
    """
    _emit(f"[{_timestamp()}] [BLOCKED] {message}", file=sys.stderr)


def dep_order(message: str) -> None:
    """
    Print a dependency resolution message to stdout (v1.4).

    In v1.8: when verbose mode is active these lines are also mirrored
    as [VERBOSE] to provide full resolution detail.

    Example output:
        [HH:MM:SS] [DEPS]    Computed install order: git → node → vscode
    """
    _emit(f"[{_timestamp()}] [DEPS]    {message}")


def valid(message: str) -> None:
    """
    Print a validation-passed message to stdout (v1.5).

    Example output:
        [HH:MM:SS] [VALID]   ✓ web
    """
    _emit(f"[{_timestamp()}] [VALID]   {message}")


def invalid(message: str) -> None:
    """
    Print a validation-failed message to stderr (v1.5).

    Example output:
        [HH:MM:SS] [INVALID] ✗ web — duplicate tool 'git'
    """
    _emit(f"[{_timestamp()}] [INVALID] {message}", file=sys.stderr)


def auto(message: str) -> None:
    """
    Print an auto-accepted prompt message to stdout (v1.7).

    Example output:
        [HH:MM:SS] [AUTO]    Proceed with installation? → yes (non-interactive mode)
    """
    _emit(f"[{_timestamp()}] [AUTO]    {message}")
