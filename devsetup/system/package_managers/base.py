"""
devsetup.system.package_managers.base
---------------------------------------
Abstract base class for package manager wrappers.

v1.9 (Stability Pass):
  - _run() moved from individual manager subclasses to BasePackageManager.
    All five managers previously duplicated identical error-handling logic;
    it now lives in one place.
  - allow_nonzero parameter supports dnf check-update exit code 100.
  - Subclasses that previously defined _run() have had their local copy
    removed; they delegate to super() via the inherited implementation.
"""

import subprocess
from abc import ABC, abstractmethod
from typing import Optional, Set


class PackageManagerError(RuntimeError):
    """
    Raised when a package manager command fails.

    Attributes
    ----------
    pm_exit_code : int
        The exit code returned by the process, or -1 if the binary was
        not found.
    """

    def __init__(self, message: str, pm_exit_code: int = -1) -> None:
        super().__init__(message)
        self.pm_exit_code = pm_exit_code

    def __str__(self) -> str:
        suffix = f" (exit code: {self.pm_exit_code})" if self.pm_exit_code >= 0 else ""
        return f"{super().__str__()}{suffix}"


class BasePackageManager(ABC):
    """Standard interface for all package manager wrappers."""

    # Canonical identifier — override in subclasses (e.g. "apt", "brew")
    manager_name: str = ""

    @abstractmethod
    def install(self, package_name: str) -> None:
        """Install the named package."""

    @abstractmethod
    def update(self) -> None:
        """Update the package manager index / cache."""

    # ── Shared execution helper (v1.9) ────────────────────────────────────────

    def _run(self, cmd: list, allow_nonzero: Optional[Set[int]] = None) -> None:
        """
        Execute a shell command and translate errors into PackageManagerError.

        Previously each subclass (apt, brew, pacman, winget, dnf) defined an
        identical or near-identical version of this method.  The v1.9 Stability
        Pass consolidates them here so there is a single implementation to
        maintain.

        Parameters
        ----------
        cmd : list
            Command and arguments (e.g. ["sudo", "apt-get", "install", "-y", "git"]).
        allow_nonzero : set of int, optional
            Exit codes that should be treated as success.  Used by DnfManager
            where ``dnf check-update`` returns 100 when updates are available.

        Raises
        ------
        PackageManagerError
            On non-zero exit code (unless in allow_nonzero), missing binary,
            or permission error.
        """
        try:
            result = subprocess.run(cmd, check=False)
            if result.returncode != 0:
                if allow_nonzero and result.returncode in allow_nonzero:
                    return
                raise PackageManagerError(
                    f"{self.manager_name} command failed: {' '.join(cmd)}",
                    pm_exit_code=result.returncode,
                )
        except FileNotFoundError:
            raise PackageManagerError(
                f"{self.manager_name} binary not found — "
                f"is {self.manager_name} installed?",
                pm_exit_code=-1,
            )
        except PermissionError:
            raise PackageManagerError(
                f"Permission denied running: {' '.join(cmd)}",
                pm_exit_code=-1,
            )
