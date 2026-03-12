"""
devsetup.core.plugin_loader
-----------------------------
Loads user plugins from ~/.devsetup/plugins/ at startup.

Plugin rules (Architecture Rule 7):
  - Plugins may only register new tools or environments via register(registry)
  - Plugins cannot modify core DevSetup modules
  - Every plugin load is wrapped in try/except — failures never crash DevSetup
  - Each plugin must expose a register(registry) function

Usage
-----
    from devsetup.core.plugin_loader import load_plugins
    load_plugins(registry)

Where registry is a dict[str, Type[BaseInstaller]].
"""

import importlib.util
import os
from typing import Dict, Type, TYPE_CHECKING

if TYPE_CHECKING:
    from devsetup.installers.base import BaseInstaller

from devsetup.utils.logger import info, warn, debug


_PLUGIN_DIR = os.path.expanduser("~/.devsetup/plugins")


def load_plugins(registry: Dict[str, Type]) -> None:
    """
    Scan ~/.devsetup/plugins/ and load each .py file as a plugin.

    Each plugin must expose:
        def register(registry: dict) -> None

    Plugin failures are caught and logged — they never crash DevSetup.

    Parameters
    ----------
    registry : dict
        The live installer registry from manager.py.
        Plugins may only add new keys, never overwrite existing ones.
    """
    if not os.path.isdir(_PLUGIN_DIR):
        debug(f"Plugin directory not found: {_PLUGIN_DIR} — skipping plugin load")
        return

    plugin_files = sorted(
        f for f in os.listdir(_PLUGIN_DIR)
        if f.endswith(".py") and not f.startswith("_")
    )

    if not plugin_files:
        debug(f"No plugins found in {_PLUGIN_DIR}")
        return

    for filename in plugin_files:
        plugin_path = os.path.join(_PLUGIN_DIR, filename)
        plugin_name = filename[:-3]  # strip .py
        _load_one(plugin_name, plugin_path, registry)


def _load_one(name: str, path: str, registry: Dict[str, Type]) -> None:
    """
    Load a single plugin file.

    Sandboxed: any exception during import or registration is caught,
    logged as a warning, and execution continues.
    """
    try:
        spec = importlib.util.spec_from_file_location(
            f"devsetup_plugin_{name}", path
        )
        if spec is None or spec.loader is None:
            warn(f"Plugin '{name}': could not create module spec — skipped")
            return

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # type: ignore[attr-defined]

        if not hasattr(module, "register") or not callable(module.register):
            warn(f"Plugin '{name}': missing register(registry) function — skipped")
            return

        # Pass a guarded proxy so plugins cannot overwrite core tools
        guarded = _GuardedRegistry(registry, source=name)
        module.register(guarded)
        info(f"Plugin '{name}': loaded successfully")

    except Exception as exc:  # noqa: BLE001 — intentional broad catch (sandbox rule)
        warn(f"Plugin '{name}': failed to load — {exc} (skipped, DevSetup continues)")


class _GuardedRegistry(dict):
    """
    A dict proxy passed to plugin register() functions.

    Allows plugins to add new tool IDs only.
    Raises ValueError if a plugin tries to overwrite a core or already-registered tool.
    """

    # Core tools that can never be overwritten by a plugin
    _CORE_IDS = frozenset({"git", "node", "pip", "python", "vscode"})

    def __init__(self, real_registry: dict, source: str) -> None:
        super().__init__(real_registry)
        self._real = real_registry
        self._source = source

    def __setitem__(self, key: str, value) -> None:
        if key in self._CORE_IDS:
            raise ValueError(
                f"Plugin '{self._source}' tried to overwrite core tool '{key}' — blocked"
            )
        if key in self._real:
            raise ValueError(
                f"Plugin '{self._source}' tried to overwrite already-registered tool '{key}' — blocked"
            )
        self._real[key] = value
        super().__setitem__(key, value)
