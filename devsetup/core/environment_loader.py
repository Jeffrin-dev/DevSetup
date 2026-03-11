"""
devsetup.core.environment_loader
---------------------------------
Responsible for loading and returning environment objects from
JSON configuration files.

Responsibilities: read configs, parse JSON, return environment objects.
Validation is delegated to devsetup.system.environment_validator.

No OS-specific logic. No business/install logic.
"""

import json
import os
from typing import Dict, Any, List

from devsetup.utils.logger import error, debug
from devsetup.system.environment_validator import (
    validate,
    validate_no_duplicates,
    EnvironmentValidationError,
)


def _config_dir() -> str:
    """Return the canonical environments config directory."""
    pkg_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    return os.path.join(pkg_root, "environments")


def load(env_id: str) -> Dict[str, Any]:
    """
    Load an environment definition by ID.

    Parameters
    ----------
    env_id : str
        The environment ID (e.g. "web"). Matches ``<id>.json``.

    Returns
    -------
    dict
        Validated environment object.

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
                f"Failed to parse environments/{env_id}.json: {exc}"
            ) from exc

    debug(f"Loaded environment config: {env_id}.json")
    validate(data, f"{env_id}.json")
    return data


def list_available() -> List[str]:
    """
    Return a sorted list of all valid environment IDs.
    Scans the environments directory dynamically at runtime.
    Invalid or duplicate configs are skipped with a warning.
    """
    config_dir = _config_dir()

    if not os.path.isdir(config_dir):
        return []

    env_ids = []
    seen_ids: set = set()

    for filename in sorted(os.listdir(config_dir)):
        if not filename.endswith(".json"):
            continue

        filepath = os.path.join(config_dir, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (json.JSONDecodeError, OSError):
            error(f"Failed to parse {filename} — skipping.")
            continue

        env_id = data.get("id", os.path.splitext(filename)[0])

        try:
            validate_no_duplicates(env_id, seen_ids, filename)
            validate(data, filename)
        except EnvironmentValidationError as exc:
            error(f"{exc} — skipping.")
            continue

        seen_ids.add(env_id)
        env_ids.append(env_id)
        debug(f"Registered environment: {env_id}")

    return env_ids
