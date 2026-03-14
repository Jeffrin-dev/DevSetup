"""
devsetup.core.environment_loader
---------------------------------
Responsible for loading, validating, and returning environment objects
from JSON configuration files.

Responsibilities: read configs, parse JSON, validate, return environment objects.
Validation is delegated to devsetup.system.environment_validator.

v1.5 additions:
  - Normalisation: after validation, 'tools' key is aliased to 'installers'
    so all downstream code continues to work with env["installers"] unchanged.
  - Validation logging: each environment is logged with [VALID] ✓ or
    [INVALID] ✗ during list_available() (Phase 13).

No OS-specific logic. No business/install logic.
"""

import json
import os
from typing import Any, Dict, List

from devsetup.utils.logger import error, debug, valid as log_valid, invalid as log_invalid
from devsetup.system.environment_validator import (
    validate,
    validate_structure,
    validate_no_duplicates,
    EnvironmentValidationError,
)


def _config_dir() -> str:
    """Return the canonical environments config directory."""
    pkg_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    return os.path.join(pkg_root, "environments")


def _normalize(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ensure the returned dict always has an 'installers' key.

    v1.5 environments may use 'tools' instead of 'installers'.
    Normalise here so all downstream code (cli/main.py, manager.py)
    continues to use env["installers"] without modification.
    """
    data = dict(data)
    if "tools" in data and "installers" not in data:
        data["installers"] = data["tools"]
    return data


def load(env_id: str) -> Dict[str, Any]:
    """
    Load and validate an environment definition by ID.

    Pipeline
    --------
    load file → parse JSON → validate schema → validate tools → normalise → return

    Parameters
    ----------
    env_id : str
        The environment ID (e.g. "web"). Matches ``<id>.json``.

    Returns
    -------
    dict
        Validated, normalised environment object.

    Raises
    ------
    FileNotFoundError
        If the configuration file does not exist.
    EnvironmentValidationError
        If the configuration fails validation.
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
    return _normalize(data)


def list_available() -> List[str]:
    """
    Return a sorted list of all valid environment IDs.

    Scans the environments directory dynamically at runtime.
    Each config is logged with [VALID] ✓ or [INVALID] ✗ (Phase 13).
    Invalid or duplicate configs are skipped and do not appear in the list.
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
        except EnvironmentValidationError as exc:
            log_invalid(f"✗ {env_id} — {exc}")
            continue

        seen_ids.add(env_id)
        env_ids.append(env_id)
        log_valid(f"✓ {env_id}")
        debug(f"Registered environment: {env_id}")

    return env_ids
