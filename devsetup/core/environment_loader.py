"""
devsetup.core.environment_loader
---------------------------------
Responsible for loading, validating, and returning environment
objects from JSON configuration files.

No OS-specific logic.  No business/install logic.
"""

import json
import os
from typing import Dict, Any, List

from devsetup.utils.logger import error

REQUIRED_FIELDS = {"schema", "id", "name", "installers"}
SUPPORTED_SCHEMAS = {"1.0"}


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
    ValueError
        If the configuration fails schema validation.
    """
    config_path = os.path.join(_config_dir(), f"{env_id}.json")

    if not os.path.isfile(config_path):
        raise FileNotFoundError(
            f"Environment '{env_id}' not found. "
            f"Expected config at: {config_path}"
        )

    with open(config_path, "r", encoding="utf-8") as fh:
        try:
            data = json.load(fh)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Failed to parse environments/{env_id}.json: {exc}"
            ) from exc

    _validate(data, env_id)
    return data


def list_available() -> List[str]:
    """
    Return a sorted list of all available environment IDs.
    Scans the environments directory dynamically —
    no code changes required when new files are added.
    """
    config_dir = _config_dir()

    if not os.path.isdir(config_dir):
        return []

    env_ids = []
    seen_ids = set()

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

        # Duplicate ID protection
        if env_id in seen_ids:
            error(
                f"Duplicate environment ID '{env_id}' in {filename} — skipping."
            )
            continue

        seen_ids.add(env_id)
        env_ids.append(env_id)

    return env_ids


def _validate(data: Dict[str, Any], source: str) -> None:
    """
    Raise ValueError if required fields are missing,
    schema is unsupported, or installer list is invalid.
    """
    missing = REQUIRED_FIELDS - data.keys()
    if missing:
        raise ValueError(
            f"Invalid environment configuration: {source}.json — "
            f"missing required fields: {missing}"
        )

    if data["schema"] not in SUPPORTED_SCHEMAS:
        raise ValueError(
            f"Unsupported schema version '{data['schema']}' in {source}.json. "
            f"Supported: {SUPPORTED_SCHEMAS}"
        )

    if not isinstance(data["installers"], list):
        raise ValueError(
            f"'installers' in {source}.json must be a list, "
            f"got {type(data['installers']).__name__}."
        )

    if len(data["installers"]) == 0:
        raise ValueError(
            f"'installers' in {source}.json must not be empty."
        )

    # Validate all installer IDs exist in the installer registry
    from devsetup.installers.manager import _REGISTRY
    for installer_id in data["installers"]:
        if installer_id not in _REGISTRY:
            raise ValueError(
                f"Installer '{installer_id}' not found in registry. "
                f"Referenced in {source}.json."
            )
