"""
devsetup.installers.result
---------------------------
Structured result contract for the installer engine.

Replaces loose string return values with a typed object that carries:
  - installer_id    : which tool was being processed
  - status          : SUCCESS | SKIP | FAIL
  - exit_code       : numeric code from the global ExitCode contract
  - message         : human-readable description
  - error_category  : optional error classification (None on success/skip)

Exit Code Contract
------------------
  0  → success
  1  → installation failure (generic)
  2  → detection error
  3  → unsupported OS
  4  → package manager failure

Error Categories
----------------
  INSTALLER_FAILURE      — installer module raised an unexpected exception
  PACKAGE_MANAGER_ERROR  — package manager returned non-zero exit code
  OS_NOT_SUPPORTED       — OS not in supported set
  COMMAND_NOT_FOUND      — required binary absent from PATH
  CONFIG_ERROR           — environment or package config invalid
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


# ── Status ────────────────────────────────────────────────────────────────────

class InstallerStatus(Enum):
    """Outcome of a single installer execution."""
    SUCCESS = "SUCCESS"
    SKIP    = "SKIP"
    FAIL    = "FAIL"


# ── Exit codes ────────────────────────────────────────────────────────────────

class ExitCode:
    """
    Global exit code contract.
    All installer results and CLI exit codes use these values.
    Unknown codes are treated as fatal errors by the engine.
    """
    SUCCESS              = 0
    INSTALLATION_FAILURE = 1
    DETECTION_ERROR      = 2
    UNSUPPORTED_OS       = 3
    PACKAGE_MANAGER_FAILURE = 4


# ── Error categories ──────────────────────────────────────────────────────────

class ErrorCategory:
    """
    Internal error classification for diagnostics and debug output.
    Used in InstallerResult.error_category and logged at [FAIL] level.
    """
    INSTALLER_FAILURE     = "INSTALLER_FAILURE"
    PACKAGE_MANAGER_ERROR = "PACKAGE_MANAGER_ERROR"
    OS_NOT_SUPPORTED      = "OS_NOT_SUPPORTED"
    COMMAND_NOT_FOUND     = "COMMAND_NOT_FOUND"
    CONFIG_ERROR          = "CONFIG_ERROR"


# ── Result object ─────────────────────────────────────────────────────────────

@dataclass
class InstallerResult:
    """
    Structured result returned by install_tool().

    Attributes
    ----------
    installer_id : str
        Registered tool name (e.g. "git").
    status : InstallerStatus
        SUCCESS | SKIP | FAIL.
    exit_code : int
        Numeric code from the ExitCode contract.
    message : str
        Human-readable description of the outcome.
    error_category : str | None
        Error classification string from ErrorCategory, or None on success/skip.
    """
    installer_id:   str
    status:         InstallerStatus
    exit_code:      int
    message:        str
    error_category: Optional[str] = None

    # ── Named constructors ────────────────────────────────────────────────────

    @classmethod
    def success(cls, installer_id: str, message: str = "") -> InstallerResult:
        """Build a SUCCESS result."""
        return cls(
            installer_id=installer_id,
            status=InstallerStatus.SUCCESS,
            exit_code=ExitCode.SUCCESS,
            message=message or f"{installer_id} installed successfully.",
        )

    @classmethod
    def skip(cls, installer_id: str, message: str = "") -> InstallerResult:
        """Build a SKIP result (tool already present)."""
        return cls(
            installer_id=installer_id,
            status=InstallerStatus.SKIP,
            exit_code=ExitCode.SUCCESS,
            message=message or f"{installer_id} already installed.",
        )

    @classmethod
    def fail(
        cls,
        installer_id: str,
        message: str,
        exit_code: int = ExitCode.INSTALLATION_FAILURE,
        error_category: str = ErrorCategory.INSTALLER_FAILURE,
    ) -> InstallerResult:
        """Build a FAIL result with exit code and category."""
        return cls(
            installer_id=installer_id,
            status=InstallerStatus.FAIL,
            exit_code=exit_code,
            message=message,
            error_category=error_category,
        )

    # ── Convenience properties ────────────────────────────────────────────────

    @property
    def succeeded(self) -> bool:
        """True for SUCCESS and SKIP — anything that does not stop the pipeline."""
        return self.status in (InstallerStatus.SUCCESS, InstallerStatus.SKIP)

    @property
    def failed(self) -> bool:
        """True only for FAIL."""
        return self.status == InstallerStatus.FAIL
