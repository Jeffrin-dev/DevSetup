"""
devsetup.system.environment_validator
---------------------------------------
Dedicated environment configuration validator for DevSetup v1.5.

Responsibilities:
  - Validate required fields are present
  - Validate field types (id, name, description must be strings)
  - Verify schema version is supported (if present — schema is optional in v1.5)
  - Confirm tools array is non-empty, correctly typed, and duplicate-free
  - Validate environment ID format (lowercase, alphanumeric + hyphens)
  - Detect and reject duplicate environment IDs across config files

Architecture note (v1.9 — Rule 6 / circular-dependency fix):
  _check_installer_ids() was previously here via a deferred import of
  installers/manager.py.  That created an upward dependency:
    system/ → installers/  while  installers/manager.py → system/
  The check is now in environment_loader.py, which legitimately sits
  above both layers.  This module contains structural/format validation
  only — zero imports from installers/.

No installation logic. No OS logic. No installer-registry imports.
Validation only.
"""

import re
from typing import Any, Dict, List, Optional

REQUIRED_BASE_FIELDS: frozenset = frozenset({"id", "name"})
SUPPORTED_SCHEMAS: frozenset = frozenset({"1.0"})
_ID_PATTERN = re.compile(r"^[a-z][a-z0-9-]*$")


class EnvironmentValidationError(ValueError):
    """
    Raised when an environment configuration fails validation.

    The message always identifies the source file and the specific
    problem so the user knows exactly what to fix.
    """
    pass


def validate_structure(data: Any, source: str) -> None:
    """Verify the parsed JSON root value is a dict."""
    if not isinstance(data, dict):
        raise EnvironmentValidationError(
            f"CONFIG ERROR: {source} — root JSON value must be an object "
            f"(got {type(data).__name__}). "
            f"Environment configs must be a JSON object, not an array or scalar."
        )


def get_tools_list(data: Dict[str, Any]) -> Optional[List]:
    """
    Return the tools list, accepting both 'tools' (v1.5) and
    'installers' (v1.0) as field names. Returns None if neither exists.
    """
    if "tools" in data:
        return data["tools"]
    if "installers" in data:
        return data["installers"]
    return None


def validate(data: Dict[str, Any], source: str) -> None:
    """
    Validate a parsed environment configuration dict.

    Performs structural and format checks only.  Installer-ID existence
    checking is intentionally absent here — it belongs in
    environment_loader, which sits above both this module and the
    installer registry (see environment_loader._check_installer_ids).

    Raises EnvironmentValidationError on the first failure encountered.
    """
    env_id = data.get("id", source)

    _check_required_base_fields(data, source, env_id)
    _check_tools_present(data, source, env_id)
    _check_schema_version(data, source, env_id)
    _check_id_format(data, source, env_id)
    _check_field_types(data, source, env_id)
    _check_tools_field(data, source, env_id)
    _check_tool_entry_types(data, source, env_id)
    _check_duplicate_tools(data, source, env_id)


def validate_no_duplicates(env_id: str, seen_ids: set, source: str) -> None:
    """Check that env_id has not already been registered."""
    if env_id in seen_ids:
        raise EnvironmentValidationError(
            f"CONFIG ERROR: duplicate environment id '{env_id}' "
            f"found in {source}. "
            f"Each environment must have a unique id."
        )


# ── Internal checks ───────────────────────────────────────────────────────────

def _check_required_base_fields(data, source, env_id):
    missing = REQUIRED_BASE_FIELDS - data.keys()
    if missing:
        raise EnvironmentValidationError(
            f"CONFIG ERROR: Environment '{env_id}' ({source}) — "
            f"missing required field(s): {sorted(missing)}"
        )


def _check_tools_present(data, source, env_id):
    if get_tools_list(data) is None:
        raise EnvironmentValidationError(
            f"CONFIG ERROR: Environment '{env_id}' ({source}) — "
            f"missing required field 'tools' (or 'installers' for v1.0 configs)."
        )


def _check_schema_version(data, source, env_id):
    if "schema" not in data:
        return
    if data["schema"] not in SUPPORTED_SCHEMAS:
        raise EnvironmentValidationError(
            f"CONFIG ERROR: Environment '{env_id}' ({source}) — "
            f"unsupported schema version '{data['schema']}'. "
            f"Supported: {sorted(SUPPORTED_SCHEMAS)}"
        )


def _check_id_format(data, source, env_id):
    raw_id = data.get("id", "")
    if not isinstance(raw_id, str) or not _ID_PATTERN.match(raw_id):
        raise EnvironmentValidationError(
            f"CONFIG ERROR: Environment '{env_id}' ({source}) — "
            f"invalid id format: '{raw_id}'. "
            f"IDs must be lowercase, start with a letter, and contain "
            f"only letters, digits, and hyphens (e.g. web, data-science)."
        )


def _check_field_types(data, source, env_id):
    for field in ("id", "name"):
        value = data.get(field)
        if not isinstance(value, str) or not value.strip():
            raise EnvironmentValidationError(
                f"CONFIG ERROR: Environment '{env_id}' ({source}) — "
                f"field '{field}' must be a non-empty string, "
                f"got {type(value).__name__}."
            )
    if "description" in data and not isinstance(data["description"], str):
        raise EnvironmentValidationError(
            f"CONFIG ERROR: Environment '{env_id}' ({source}) — "
            f"field 'description' must be a string, "
            f"got {type(data['description']).__name__}."
        )


def _check_tools_field(data, source, env_id):
    tools = get_tools_list(data)
    field_name = "tools" if "tools" in data else "installers"
    if not isinstance(tools, list):
        raise EnvironmentValidationError(
            f"CONFIG ERROR: Environment '{env_id}' ({source}) — "
            f"'{field_name}' must be a list, "
            f"got {type(tools).__name__}."
        )
    if len(tools) == 0:
        raise EnvironmentValidationError(
            f"CONFIG ERROR: Environment '{env_id}' ({source}) — "
            f"'{field_name}' must not be empty. "
            f"Environment must define at least one tool."
        )


def _check_tool_entry_types(data, source, env_id):
    tools = get_tools_list(data)
    if not isinstance(tools, list):
        return
    for index, tool_id in enumerate(tools):
        if not isinstance(tool_id, str):
            raise EnvironmentValidationError(
                f"CONFIG ERROR: Environment '{env_id}' ({source}) — "
                f"tools list entry at index {index} must be a string "
                f"(installer ID), got {type(tool_id).__name__}: {tool_id!r}."
            )


def _check_duplicate_tools(data, source, env_id):
    tools = get_tools_list(data)
    if not isinstance(tools, list):
        return
    seen: set = set()
    for tool_id in tools:
        if tool_id in seen:
            raise EnvironmentValidationError(
                f"CONFIG ERROR: Environment '{env_id}' ({source}) — "
                f"duplicate tool '{tool_id}'. "
                f"Each tool may only appear once in the tools list."
            )
        seen.add(tool_id)
