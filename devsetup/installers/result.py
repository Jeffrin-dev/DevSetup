"""
devsetup.installers.result
---------------------------
Structured result contract for the installer engine.

v1.3 additions:
  - InstallerResult.version       — stores the verified installed version
  - ExitCode.VERIFICATION_FAILURE — version command failed post-install
  - ErrorCategory.VERIFICATION_FAILURE

v1.3.2 — Issue 5:
  - InstallSummary refactored to single source of truth (result_map).

v1.4 additions (Dependency Ordering):
  - InstallerStatus.BLOCKED       — tool not run because a dependency failed
  - ExitCode.DEPENDENCY_BLOCKED   — exit code 6 for blocked tools
  - ErrorCategory.DEPENDENCY_BLOCKED
  - InstallerResult.block()       — named constructor for blocked results
  - InstallSummary.blocked        — computed property (list of blocked IDs)
  - InstallSummary._blocked_ids   — private insertion-ordered list
  - InstallSummary.total_run      — now includes blocked count
  - InstallSummary.record()       — handles BLOCKED status bucket

Exit Code Contract
------------------
  0  → success
  1  → installation failure (generic)
  2  → detection error
  3  → unsupported OS
  4  → package manager failure
  5  → version verification failure
  6  → dependency blocked (v1.4)

Error Categories
----------------
  INSTALLER_FAILURE      — installer module raised an unexpected exception
  PACKAGE_MANAGER_ERROR  — package manager returned non-zero exit code
  OS_NOT_SUPPORTED       — OS not in supported set
  COMMAND_NOT_FOUND      — required binary absent from PATH
  CONFIG_ERROR           — environment or package config invalid
  VERIFICATION_FAILURE   — version command failed or timed out
  DEPENDENCY_BLOCKED     — tool skipped because a dependency failed (v1.4)
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
    BLOCKED = "BLOCKED"   # v1.4 — dependency failed, tool not attempted


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
    VERIFICATION_FAILURE    = 5
    DEPENDENCY_BLOCKED      = 6   # v1.4


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
    VERIFICATION_FAILURE  = "VERIFICATION_FAILURE"
    DEPENDENCY_BLOCKED    = "DEPENDENCY_BLOCKED"   # v1.4


# ── Result object ─────────────────────────────────────────────────────────────

@dataclass
class InstallerResult:
    """
    Structured result returned by install_tool() or produced for blocked tools.

    Attributes
    ----------
    installer_id : str
    status : InstallerStatus  — SUCCESS | SKIP | FAIL | BLOCKED
    exit_code : int
    message : str
    error_category : str | None
    version : str | None
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

    @classmethod
    def block(
        cls,
        installer_id: str,
        blocking_dep: str,
    ) -> InstallerResult:
        """
        Build a BLOCKED result (v1.4).

        Parameters
        ----------
        installer_id : str
            The tool that was not run.
        blocking_dep : str
            The dependency whose failure caused this tool to be blocked.
        """
        return cls(
            installer_id=installer_id,
            status=InstallerStatus.BLOCKED,
            exit_code=ExitCode.DEPENDENCY_BLOCKED,
            message=(
                f"{installer_id} was not installed because its dependency "
                f"'{blocking_dep}' failed or was blocked."
            ),
            error_category=ErrorCategory.DEPENDENCY_BLOCKED,
        )

    @property
    def succeeded(self) -> bool:
        """True for SUCCESS and SKIP — does not stop the pipeline."""
        return self.status in (InstallerStatus.SUCCESS, InstallerStatus.SKIP)

    @property
    def failed(self) -> bool:
        """True only for FAIL."""
        return self.status == InstallerStatus.FAIL

    @property
    def blocked(self) -> bool:
        """True only for BLOCKED (v1.4)."""
        return self.status == InstallerStatus.BLOCKED


# ── Install Summary ───────────────────────────────────────────────────────────

class InstallSummary:
    """
    Accumulates installer results and produces the final installation report.

    Design (single source of truth — v1.3.2):
      _records     : Dict[str, InstallerResult]  — authoritative store
      _ordered_ids : List[str]                   — SUCCESS/SKIP insertion order
      _blocked_ids : List[str]                   — BLOCKED insertion order (v1.4)
      failed_result: Optional[InstallerResult]   — fast access to the failure

    Computed properties:
      installed  → SUCCESS tools in order
      skipped    → SKIP tools in order
      blocked    → BLOCKED tools in order (v1.4)
      result_map → read-only view of _records

    Backward-compatible constructor accepts installed=, skipped=,
    failed_result=, result_map= keyword arguments.
    """

    def __init__(
        self,
        env_name: Optional[str] = None,
        installed: Optional[List[str]] = None,
        skipped: Optional[List[str]] = None,
        failed_result: Optional[InstallerResult] = None,
        result_map: Optional[Dict[str, InstallerResult]] = None,
        blocked: Optional[List[str]] = None,
    ) -> None:
        self.env_name      = env_name
        self.failed_result = failed_result
        self._ordered_ids: List[str] = []
        self._blocked_ids: List[str] = []
        self._records: Dict[str, InstallerResult] = {}

        if result_map:
            self._records.update(result_map)

        for tool_id in (installed or []):
            if tool_id not in self._records:
                self._records[tool_id] = InstallerResult.success(tool_id)
            self._ordered_ids.append(tool_id)

        for tool_id in (skipped or []):
            if tool_id not in self._records:
                self._records[tool_id] = InstallerResult.skip(tool_id)
            self._ordered_ids.append(tool_id)

        for tool_id in (blocked or []):
            if tool_id not in self._records:
                self._records[tool_id] = InstallerResult.block(tool_id, "unknown")
            self._blocked_ids.append(tool_id)

        if failed_result and failed_result.installer_id not in self._records:
            self._records[failed_result.installer_id] = failed_result

    # ── Computed properties ───────────────────────────────────────────────────

    @property
    def installed(self) -> List[str]:
        """Installer IDs with SUCCESS status, in execution order."""
        return [
            t for t in self._ordered_ids
            if self._records.get(t) is not None
            and self._records[t].status == InstallerStatus.SUCCESS
        ]

    @property
    def skipped(self) -> List[str]:
        """Installer IDs with SKIP status, in execution order."""
        return [
            t for t in self._ordered_ids
            if self._records.get(t) is not None
            and self._records[t].status == InstallerStatus.SKIP
        ]

    @property
    def blocked(self) -> List[str]:
        """Installer IDs with BLOCKED status, in blocked order (v1.4)."""
        return list(self._blocked_ids)

    @property
    def result_map(self) -> Dict[str, InstallerResult]:
        """Read-only view of all results keyed by installer_id."""
        return self._records

    # ── Mutation ──────────────────────────────────────────────────────────────

    def record(self, result: InstallerResult) -> None:
        """
        Record an installer result into the correct bucket.

        Duplicate tool IDs are silently ignored (Phase 6 guard).
        """
        tool = result.installer_id

        if tool in self._records:
            return
        if self.failed_result and tool == self.failed_result.installer_id:
            return

        self._records[tool] = result

        if result.status == InstallerStatus.FAIL:
            self.failed_result = result
        elif result.status == InstallerStatus.BLOCKED:
            self._blocked_ids.append(tool)
        else:
            self._ordered_ids.append(tool)

    # ── Summary properties ────────────────────────────────────────────────────

    @property
    def has_failure(self) -> bool:
        """True when at least one installer failed."""
        return self.failed_result is not None

    @property
    def has_blocked(self) -> bool:
        """True when at least one tool was blocked by a dependency failure (v1.4)."""
        return len(self._blocked_ids) > 0

    @property
    def total_run(self) -> int:
        """Total number of results recorded (includes blocked)."""
        return (
            len(self.installed)
            + len(self.skipped)
            + len(self.blocked)
            + (1 if self.failed_result else 0)
        )
