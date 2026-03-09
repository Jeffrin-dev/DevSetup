"""
devsetup.installers.base
------------------------
Abstract base class that defines the standard interface every
tool installer must implement.

Rules (Architecture Rule 4):
  - detect()   → bool   : is the tool already present?
  - install()  → None   : perform the installation
  - version()  → str    : return the installed version string
"""

from abc import ABC, abstractmethod


class BaseInstaller(ABC):
    """Standard interface for all DevSetup tool installers."""

    # Human-readable name of the tool (override in subclasses)
    tool_name: str = ""

    @abstractmethod
    def detect(self) -> bool:
        """Return True if the tool is already installed, False otherwise."""

    @abstractmethod
    def install(self) -> None:
        """Install the tool on the current operating system."""

    @abstractmethod
    def version(self) -> str:
        """Return the installed tool version as a string."""
