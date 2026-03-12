"""
devsetup.system.package_managers.base
---------------------------------------
Abstract base class for package manager wrappers.
Also defines PackageManagerError — the standard exception raised
when a package manager command fails.
"""

from abc import ABC, abstractmethod


class PackageManagerError(RuntimeError):
    """
    Raised when a package manager command fails.

    Attributes
    ----------
    message : str
        Human-readable description (what failed and why).
    pm_exit_code : int
        The exit code returned by the package manager process,
        or -1 if the binary was not found.
    """

    def __init__(self, message: str, pm_exit_code: int = -1) -> None:
        super().__init__(message)
        self.pm_exit_code = pm_exit_code

    def __str__(self) -> str:
        suffix = f" (exit code: {self.pm_exit_code})" if self.pm_exit_code >= 0 else ""
        return f"{super().__str__()}{suffix}"


class BasePackageManager(ABC):
    """Standard interface for all package manager wrappers."""

    # Canonical identifier — override in subclasses
    manager_name: str = ""

    @abstractmethod
    def install(self, package_name: str) -> None:
        """
        Install the named package.

        Raises
        ------
        PackageManagerError
            If the package manager returns a non-zero exit code,
            the binary is not found, or a permission error occurs.
        """

    @abstractmethod
    def update(self) -> None:
        """
        Update the package manager index / cache.

        Raises
        ------
        PackageManagerError
            If the update command fails.
        """
