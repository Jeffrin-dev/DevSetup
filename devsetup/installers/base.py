"""
devsetup.installers.base
------------------------
Abstract base class that defines the standard interface every
tool installer must implement.

Rules (Architecture Rule 4):
  - detect()       → bool        : is the tool already present?
  - install()      → None        : perform the installation
  - version()      → str         : return the installed version string

v1.4 additions (Dependency Ordering):
  - dependencies   → List[str]   : installer IDs this tool requires first.
                                   Default is an empty list (no dependencies).
                                   Subclasses override this class attribute to
                                   declare explicit dependencies.
"""

from abc import ABC, abstractmethod
from typing import List


class BaseInstaller(ABC):
    """Standard interface for all DevSetup tool installers."""

    # Human-readable name of the tool (override in subclasses)
    tool_name: str = ""

    # Ordered list of installer IDs that must be installed before this tool.
    # Default = empty (no dependencies). Subclasses declare explicitly.
    # Example: dependencies = ["git"]
    dependencies: List[str] = []

    @abstractmethod
    def detect(self) -> bool:
        """Return True if the tool is already installed, False otherwise."""

    @abstractmethod
    def install(self) -> None:
        """Install the tool on the current operating system."""

    @abstractmethod
    def version(self) -> str:
        """Return the installed tool version as a string."""
