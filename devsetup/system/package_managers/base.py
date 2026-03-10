"""
devsetup.system.package_managers.base
---------------------------------------
Abstract base class that defines the standard interface every
package manager module must implement.
"""

from abc import ABC, abstractmethod


class BasePackageManager(ABC):
    """Standard interface for all package manager wrappers."""

    # Canonical identifier — override in subclasses
    manager_name: str = ""

    @abstractmethod
    def install(self, package_name: str) -> None:
        """Install the named package using this package manager."""

    @abstractmethod
    def update(self) -> None:
        """Update the package manager index / cache."""
