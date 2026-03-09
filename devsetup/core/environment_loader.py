"""
devsetup.core.environment_loader
---------------------------------
Responsible for loading, validating, and returning environment
objects from JSON configuration files.

No OS-specific logic.  No business/install logic.
"""

import json
import os
from typing import Dict, Any

from devsetup.utils.logger import error

REQUIRED_FIELDS = {"schema", "name", "tools"}
SUPPORTED_SCHEMAS = {"1.0"}


def _config_dir() -> str:
    """Return the canonical environments config directory."""
    # Resolved relative to this file's package root
    pkg_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    return os.path.join(pkg_root, "environments")


def load(name: str) -> Dict[str, Any]:
    """
    Load an environment definition by name.

    Parameters
    ----------
    name : str
        The environment name (e.g. "web").  Matches ``<name>.json``.

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
    config_path = os.path.join(_config_dir(), f"{name}.json")

    if not os.path.isfile(config_path):
        raise FileNotFoundError(
            f"Environment '{name}' not found. "
            f"Expected config at: {config_path}"
        )

    with open(config_path, "r", encoding="utf-8") as fh:
        try:
            data = json.load(fh)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON in '{config_path}': {exc}") from exc

    _validate(data, config_path)
    return data


def list_available() -> list:
    """Return a list of all available environment names."""
    config_dir = _config_dir()
    if not os.path.isdir(config_dir):
        return []
    return [
        os.path.splitext(f)[0]
        for f in os.listdir(config_dir)
        if f.endswith(".json")
    ]


def _validate(data: Dict[str, Any], source: str) -> None:
    """Raise ValueError if required fields are missing or schema is unsupported."""
    missing = REQUIRED_FIELDS - data.keys()
    if missing:
        raise ValueError(
            f"Environment config '{source}' is missing required fields: {missing}"
        )

    if data["schema"] not in SUPPORTED_SCHEMAS:
        raise ValueError(
            f"Unsupported schema version '{data['schema']}' in '{source}'. "
            f"Supported: {SUPPORTED_SCHEMAS}"
        )

    if not isinstance(data["tools"], list):
        raise ValueError(
            f"'tools' in '{source}' must be a list, got {type(data['tools']).__name__}."
        )
