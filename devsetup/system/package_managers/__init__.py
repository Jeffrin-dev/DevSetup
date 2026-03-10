"""
devsetup.system.package_managers
----------------------------------
Package manager execution layer.

Each submodule wraps a single system package manager and
exposes a standard interface: install(package_name) and update().
The correct module is selected by PackageManagerRunner.
"""

from devsetup.system.package_managers.runner import PackageManagerRunner

__all__ = ["PackageManagerRunner"]
