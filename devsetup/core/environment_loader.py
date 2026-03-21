"""
devsetup.core.environment_loader
---------------------------------
Responsible for loading, validating, and returning environment objects
from JSON configuration files.

Responsibilities: read configs, parse JSON, validate, return environment objects.
Structural validation is delegated to devsetup.system.environment_validator.
Installer-ID existence is checked here (v1.9 architecture fix — see below).

Architecture note (v1.9 — Rule 6 / circular-dependency fix):
  _check_installer_ids() was previously called from
  system/environment_validator.py via a deferred import of
  installers/manager.py.  That created an upward dependency:
    system/ → installers/  while  installers/manager.py → system/
  The check now lives here.  The loader sits above both the system/ and
  installers/ layers, so importing is_registered from installers.manager
  is a legitimate downward dependency — no cycle is introduced.

No OS-specific logic. No business/install logic.
"""

import json
import os
from typing import Any, Dict, List

from devsetup.utils.logger import debug, valid as log_valid, invalid as log_invalid
from devsetup.system.environment_validator import (
    validate,
    validate_structure,
    validate_no_duplicates,
    EnvironmentValidationError,
    get_tools_list,
)


def _config_dir() -> str:
    """Return the canonical environments config directory."""
    pkg_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    return os.path.join(pkg_root, "environments")


def _normalize(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ensure the returned dict always has an 'installers' key.

    v1.5 environments may use 'tools' instead of 'installers'.
    Normalise here so all downstream code uses env["installers"].
    """
    data = dict(data)
    if "tools" in data and "installers" not in data:
        data["installers"] = data["tools"]
    return data


def _check_installer_ids(data: Dict[str, Any], source: str) -> None:
    """
    Verify every tool ID in the config exists in the installer registry.

    Moved here from system/environment_validator.py in v1.9 to fix a
    circular dependency.  The loader legitimately sits above both the
    system/ layer and the installers/ layer, making this the correct
    home for cross-layer semantic checks.

    Parameters
    ----------
    data : dict
        Parsed, structurally-valid environment config.
    source : str
        Filename for error messages (e.g. 'web.json').

    Raises
    ------
    EnvironmentValidationError
        If any tool ID is not registered in the installer registry.
    """
    # Import is at function scope rather than module scope to mirror the
    # previous deferred-import pattern, keeping import-time behaviour
    # identical while making the dependency explicit and one-directional.
    from devsetup.installers.manager import is_registered

    env_id = data.get("id", source)
    tools = get_tools_list(data)
    if not isinstance(tools, list):
        return  # structural issues already caught by validate()

    for tool_id in tools:
        if not isinstance(tool_id, str):
            continue  # non-string entries caught by validate()
        if not is_registered(tool_id):
            raise EnvironmentValidationError(
                f"CONFIG ERROR: installer '{tool_id}' not found in "
                f"environment '{env_id}' ({source}). "
                f"Use 'devsetup list' to see available environments."
            )


def load(env_id: str) -> Dict[str, Any]:
    """
    Load and validate an environment definition by ID.

    Pipeline
    --------
    load file → parse JSON → structural validate → installer-ID check
    → normalise → return

    Raises
    ------
    FileNotFoundError
        If the configuration file does not exist.
    EnvironmentValidationError
        If the configuration fails structural or installer-ID validation.
    """
    config_path = os.path.join(_config_dir(), f"{env_id}.json")

    if not os.path.isfile(config_path):
        raise FileNotFoundError(
            f"Environment '{env_id}' not found. "
            f"Use 'devsetup list' to see available environments."
        )

    with open(config_path, "r", encoding="utf-8") as fh:
        try:
            data = json.load(fh)
        except json.JSONDecodeError as exc:
            raise EnvironmentValidationError(
                f"Invalid JSON in environment config '{env_id}.json': {exc}"
            ) from exc

    debug(f"Loaded environment config: {env_id}.json")
    validate(data, f"{env_id}.json")
    _check_installer_ids(data, f"{env_id}.json")
    return _normalize(data)


def list_available() -> List[str]:
    """
    Return a sorted list of all valid environment IDs.

    Scans the environments directory dynamically at runtime.
    Each config is logged with [VALID] or [INVALID] (Phase 13).
    Invalid or duplicate configs are skipped silently.
    """
    config_dir = _config_dir()

    if not os.path.isdir(config_dir):
        return []

    env_ids: List[str] = []
    seen_ids: set = set()

    for filename in sorted(os.listdir(config_dir)):
        if not filename.endswith(".json"):
            continue

        filepath = os.path.join(config_dir, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (json.JSONDecodeError, OSError) as exc:
            log_invalid(f"✗ {filename} — invalid JSON: {exc}")
            continue

        try:
            validate_structure(data, filename)
        except EnvironmentValidationError as exc:
            log_invalid(f"✗ {filename} — {exc}")
            continue

        env_id = data.get("id", os.path.splitext(filename)[0])

        try:
            validate_no_duplicates(env_id, seen_ids, filename)
            validate(data, filename)
            _check_installer_ids(data, filename)
        except EnvironmentValidationError as exc:
            log_invalid(f"✗ {env_id} — {exc}")
            continue

        seen_ids.add(env_id)
        env_ids.append(env_id)
        log_valid(f"✓ {env_id}")
        debug(f"Registered environment: {env_id}")

    return env_ids
