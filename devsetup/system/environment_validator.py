"""
devsetup.system.environment_validator
---------------------------------------
Dedicated environment configuration validator.

Responsibilities:
  - Validate required fields are present
  - Verify schema version is supported
  - Confirm installers array is non-empty and correctly typed
  - Confirm all installer IDs exist in the installer registry
  - Detect and reject duplicate environment IDs across config files

This module is separate from environment_loader (Architecture Rule 6).
The loader reads and parses. The validator checks correctness.

No installation logic. No OS logic. Validation only.
"""

import json
import os
from typing import Dict, Any, List

REQUIRED_FIELDS = {"schema", "id", "name", "installers"}
SUPPORTED_SCHEMAS = {"1.0"}


class EnvironmentValidationError(ValueError):
    """Raised when an environment configuration fails validation."""
    pass


def validate(data: Dict[str, Any], source: str) -> None:
    """
    Validate a parsed environment configuration dict.

    Parameters
    ----------
    data : dict
        Parsed JSON environment data.
    source : str
        Human-readable source identifier for error messages (e.g. 'web.json').

    Raises
    ------
    EnvironmentValidationError
        If any validation check fails.
    """
    _check_required_fields(data, source)
    _check_schema_version(data, source)
    _check_installers_field(data, source)
    _check_installer_ids(data, source)


def validate_no_duplicates(env_id: str, seen_ids: set, source: str) -> None:
    """
    Check that env_id has not already been registered.

    Parameters
    ----------
    env_id : str
        The environment ID to check.
    seen_ids : set
        Set of already-registered environment IDs.
    source : str
        Filename for error messages.

    Raises
    ------
    EnvironmentValidationError
        If a duplicate ID is detected.
    """
    if env_id in seen_ids:
        raise EnvironmentValidationError(
            f"Duplicate environment ID '{env_id}' found in {source}. "
            f"Each environment must have a unique id."
        )


def _check_required_fields(data: Dict[str, Any], source: str) -> None:
    missing = REQUIRED_FIELDS - data.keys()
    if missing:
        raise EnvironmentValidationError(
            f"Invalid environment config: {source} — "
            f"missing required fields: {sorted(missing)}"
        )


def _check_schema_version(data: Dict[str, Any], source: str) -> None:
    if data["schema"] not in SUPPORTED_SCHEMAS:
        raise EnvironmentValidationError(
            f"Invalid environment config: {source} — "
            f"unsupported schema version '{data['schema']}'. "
            f"Supported: {sorted(SUPPORTED_SCHEMAS)}"
        )


def _check_installers_field(data: Dict[str, Any], source: str) -> None:
    if not isinstance(data["installers"], list):
        raise EnvironmentValidationError(
            f"Invalid environment config: {source} — "
            f"'installers' must be a list, "
            f"got {type(data['installers']).__name__}."
        )
    if len(data["installers"]) == 0:
        raise EnvironmentValidationError(
            f"Invalid environment config: {source} — "
            f"'installers' must not be empty."
        )


def _check_installer_ids(data: Dict[str, Any], source: str) -> None:
    from devsetup.installers.manager import is_registered
    for installer_id in data["installers"]:
        if not is_registered(installer_id):
            raise EnvironmentValidationError(
                f"Invalid environment config: {source} — "
                f"unknown installer \"{installer_id}\". "
                f"Use 'devsetup list' to see available environments."
            )
