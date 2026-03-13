"""
devsetup.installers.result
---------------------------
Structured result contract for the installer engine.

v1.3 additions:
  - InstallerResult.version       — stores the verified installed version
  - ExitCode.VERIFICATION_FAILURE — version command failed post-install
  - ErrorCategory.VERIFICATION_FAILURE

Patch (v1.3.2 — Issue 5):
  - InstallSummary refactored so result_map is the single source of
    truth. Previously installed and skipped were List[str] fields that
    existed in parallel to result_map, creating two representations of
    the same data that could drift if record() was bypassed.

    New design:
      - _ordered_ids : List[str]  — private, records insertion order
      - _records     : Dict[str, InstallerResult]  — single source
      - installed    : property — computed from _records/_ordered_ids
      - skipped      : property — computed from _records/_ordered_ids
      - result_map   : property — read-only view of _records

    __init__ accepts the same keyword arguments as before for backward
    compatibility with direct construction in tests and callers.

Exit Code Contract
------------------
  0  → success
  1  → installation failure (generic)
  2  → detection error
  3  → unsupported OS
  4  → package manager failure
  5  → version verification failure (v1.3)

Error Categories
----------------
  INSTALLER_FAILURE      — installer module raised an unexpected exception
  PACKAGE_MANAGER_ERROR  — package manager returned non-zero exit code
  OS_NOT_SUPPORTED       — OS not in supported set
  COMMAND_NOT_FOUND      — required binary absent from PATH
  CONFIG_ERROR           — environment or package config invalid
  VERIFICATION_FAILURE   — version command failed or timed out (v1.3)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional


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
    """
    SUCCESS                 = 0
    INSTALLATION_FAILURE    = 1
    DETECTION_ERROR         = 2
    UNSUPPORTED_OS          = 3
    PACKAGE_MANAGER_FAILURE = 4
    VERIFICATION_FAILURE    = 5   # v1.3


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
    VERIFICATION_FAILURE  = "VERIFICATION_FAILURE"   # v1.3


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
    version : str | None
        Confirmed installed version string (e.g. '2.43.0'), or None if
        version verification was not performed or failed (v1.3).
    """
    installer_id:   str
    status:         InstallerStatus
    exit_code:      int
    message:        str
    error_category: Optional[str] = None
    version:        Optional[str] = None

    @classmethod
    def success(
        cls,
        installer_id: str,
        message: str = "",
        version: Optional[str] = None,
    ) -> InstallerResult:
        """Build a SUCCESS result, optionally carrying a verified version."""
        return cls(
            installer_id=installer_id,
            status=InstallerStatus.SUCCESS,
            exit_code=ExitCode.SUCCESS,
            message=message or f"{installer_id} installed successfully.",
            version=version,
        )

    @classmethod
    def skip(
        cls,
        installer_id: str,
        message: str = "",
        version: Optional[str] = None,
    ) -> InstallerResult:
        """Build a SKIP result, optionally carrying the existing version."""
        return cls(
            installer_id=installer_id,
            status=InstallerStatus.SKIP,
            exit_code=ExitCode.SUCCESS,
            message=message or f"{installer_id} already installed.",
            version=version,
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

    @property
    def succeeded(self) -> bool:
        """True for SUCCESS and SKIP — anything that does not stop the pipeline."""
        return self.status in (InstallerStatus.SUCCESS, InstallerStatus.SKIP)

    @property
    def failed(self) -> bool:
        """True only for FAIL."""
        return self.status == InstallerStatus.FAIL


# ── Install Summary ───────────────────────────────────────────────────────────

class InstallSummary:
    """
    Accumulates installer results and produces the final installation report.

    Design (v1.3.2 — single source of truth):
      _records     : Dict[str, InstallerResult]  — every result, keyed by tool ID
      _ordered_ids : List[str]                   — insertion order for SUCCESS/SKIP
      failed_result: Optional[InstallerResult]   — fast access to the single failure

    installed and skipped are computed properties derived from _records and
    _ordered_ids. There is no separate list that could drift out of sync.

    result_map is a read-only property returning _records directly, preserving
    the v1.3 API used by _print_summary() and tests.

    Backward-compatible constructor:
      InstallSummary() — empty
      InstallSummary(env_name="Web")
      InstallSummary(installed=["git"], result_map={"git": result})
      InstallSummary(installed=["git"], skipped=["node"])
      InstallSummary(failed_result=result)
    When installed/skipped lists are passed without a matching result_map
    entry, synthetic InstallerResult objects are created so that
    _records is always the authoritative store.
    """

    def __init__(
        self,
        env_name: Optional[str] = None,
        installed: Optional[List[str]] = None,
        skipped: Optional[List[str]] = None,
        failed_result: Optional[InstallerResult] = None,
        result_map: Optional[Dict[str, InstallerResult]] = None,
    ) -> None:
        self.env_name      = env_name
        self.failed_result = failed_result
        self._ordered_ids: List[str] = []
        self._records: Dict[str, InstallerResult] = {}

        # Seed _records from result_map if provided
        if result_map:
            self._records.update(result_map)

        # Populate ordering from installed list; create synthetic result if absent
        for tool_id in (installed or []):
            if tool_id not in self._records:
                self._records[tool_id] = InstallerResult.success(tool_id)
            self._ordered_ids.append(tool_id)

        # Populate ordering from skipped list; create synthetic result if absent
        for tool_id in (skipped or []):
            if tool_id not in self._records:
                self._records[tool_id] = InstallerResult.skip(tool_id)
            self._ordered_ids.append(tool_id)

        # Ensure failed result is in _records
        if failed_result and failed_result.installer_id not in self._records:
            self._records[failed_result.installer_id] = failed_result

    # ── Computed properties (single source of truth) ──────────────────────────

    @property
    def installed(self) -> List[str]:
        """Installer IDs with SUCCESS status, in execution order."""
        return [
            t for t in self._ordered_ids
            if self._records.get(t, None) is not None
            and self._records[t].status == InstallerStatus.SUCCESS
        ]

    @property
    def skipped(self) -> List[str]:
        """Installer IDs with SKIP status, in execution order."""
        return [
            t for t in self._ordered_ids
            if self._records.get(t, None) is not None
            and self._records[t].status == InstallerStatus.SKIP
        ]

    @property
    def result_map(self) -> Dict[str, InstallerResult]:
        """Read-only view of all results keyed by installer_id."""
        return self._records

    # ── Mutation ──────────────────────────────────────────────────────────────

    def record(self, result: InstallerResult) -> None:
        """
        Record an installer result.

        Each installer ID is accepted exactly once — duplicate calls are
        silently ignored. _records is updated atomically so installed and
        skipped properties always reflect the true state.

        Parameters
        ----------
        result : InstallerResult
        """
        tool = result.installer_id

        # Duplicate guard — _records is the single source of truth
        if tool in self._records:
            return
        # Also guard against a tool that previously failed
        if self.failed_result and tool == self.failed_result.installer_id:
            return

        self._records[tool] = result

        if result.status == InstallerStatus.FAIL:
            self.failed_result = result
        else:
            self._ordered_ids.append(tool)

    # ── Summary properties ────────────────────────────────────────────────────

    @property
    def has_failure(self) -> bool:
        """True when at least one installer failed."""
        return self.failed_result is not None

    @property
    def total_run(self) -> int:
        """Total number of installers that produced a result."""
        return len(self.installed) + len(self.skipped) + (1 if self.failed_result else 0)
