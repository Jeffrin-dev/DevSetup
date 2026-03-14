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
  - Confirm all tool IDs exist in the installer registry
  - Detect and reject duplicate environment IDs across config files

Field name compatibility (v1.5):
  The tools list may be supplied under either the 'tools' key (v1.5 format)
  or the 'installers' key (v1.0 backward-compatible format). Both are
  accepted. 'tools' takes precedence when both are present.
  Downstream code (environment_loader) normalises to 'installers' after
  validation so the rest of the system is unchanged.

This module is separate from environment_loader (Architecture Rule 6).
The loader reads and parses. The validator checks correctness.

No installation logic. No OS logic. Validation only.

v1.5 additions over v1.4:
  - schema field is now optional (not required)
  - 'tools' accepted as field name alongside 'installers'
  - _check_id_format()     — Phase 7
  - _check_field_types()   — Phase 3
  - _check_duplicate_tools() — Phase 6
  - Improved error messages include environment id — Phase 12
"""

import re
from typing import Any, Dict, List, Optional

# ── Constants ─────────────────────────────────────────────────────────────────

# Required fields regardless of schema version.
# 'schema' is intentionally absent — it is optional in v1.5.
# The tools list may appear as 'tools' OR 'installers'; checked separately.
REQUIRED_BASE_FIELDS: frozenset = frozenset({"id", "name"})

SUPPORTED_SCHEMAS: frozenset = frozenset({"1.0"})

# Environment ID must be lowercase, start with a letter, contain only
# lowercase letters, digits, and hyphens.
# Valid:   web, python, data-science, python3
# Invalid: Web Dev, _web, 123env, web_env
_ID_PATTERN = re.compile(r"^[a-z][a-z0-9-]*$")


# ── Public exception ──────────────────────────────────────────────────────────

class EnvironmentValidationError(ValueError):
    """
    Raised when an environment configuration fails validation.

    The message always identifies the source file and the specific
    problem so the user knows exactly what to fix.
    """
    pass


# ── Public validation functions ───────────────────────────────────────────────

def validate_structure(data: Any, source: str) -> None:
    """
    Verify the parsed JSON root value is a dict (Phase 9 / Rule 6).

    Must be called by the loader before validate(), because validate()
    accepts Dict[str, Any] and would raise an AttributeError rather than
    a clean EnvironmentValidationError if passed a list or scalar.

    Keeping this check here (not inline in the loader) preserves the
    principle that all structural validation lives in the validator module.

    Parameters
    ----------
    data : Any
        The raw value returned by json.load().
    source : str
        Filename for error messages (e.g. 'web.json').

    Raises
    ------
    EnvironmentValidationError
        If the root JSON value is not a dict.
    """
    if not isinstance(data, dict):
        raise EnvironmentValidationError(
            f"CONFIG ERROR: {source} — root JSON value must be an object "
            f"(got {type(data).__name__}). "
            f"Environment configs must be a JSON object, not an array or scalar."
        )


# ── Public helpers ────────────────────────────────────────────────────────────

def get_tools_list(data: Dict[str, Any]) -> Optional[List]:
    """
    Return the tools list from a config dict, accepting both 'tools'
    (v1.5) and 'installers' (v1.0) as field names.

    'tools' takes precedence when both keys are present.

    Returns None if neither key exists.
    """
    if "tools" in data:
        return data["tools"]
    if "installers" in data:
        return data["installers"]
    return None


# ── Primary validation entry point ────────────────────────────────────────────

def validate(data: Dict[str, Any], source: str) -> None:
    """
    Validate a parsed environment configuration dict.

    Runs all checks in order. Raises on the first failure encountered
    so the error message is precise rather than listing every problem.

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
    env_id = data.get("id", source)   # best-effort for error messages

    _check_required_base_fields(data, source, env_id)
    _check_tools_present(data, source, env_id)
    _check_schema_version(data, source, env_id)
    _check_id_format(data, source, env_id)
    _check_field_types(data, source, env_id)
    _check_tools_field(data, source, env_id)
    _check_duplicate_tools(data, source, env_id)
    _check_installer_ids(data, source, env_id)


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
            f"CONFIG ERROR: duplicate environment id '{env_id}' "
            f"found in {source}. "
            f"Each environment must have a unique id."
        )


# ── Internal checks ───────────────────────────────────────────────────────────

def _check_required_base_fields(
    data: Dict[str, Any], source: str, env_id: str
) -> None:
    """Verify 'id' and 'name' are present."""
    missing = REQUIRED_BASE_FIELDS - data.keys()
    if missing:
        raise EnvironmentValidationError(
            f"CONFIG ERROR: Environment '{env_id}' ({source}) — "
            f"missing required field(s): {sorted(missing)}"
        )


def _check_tools_present(
    data: Dict[str, Any], source: str, env_id: str
) -> None:
    """Verify either 'tools' or 'installers' is present."""
    if get_tools_list(data) is None:
        raise EnvironmentValidationError(
            f"CONFIG ERROR: Environment '{env_id}' ({source}) — "
            f"missing required field 'tools' (or 'installers' for v1.0 configs)."
        )


def _check_schema_version(
    data: Dict[str, Any], source: str, env_id: str
) -> None:
    """If 'schema' is present, verify it is a supported version."""
    if "schema" not in data:
        return   # schema is optional in v1.5
    if data["schema"] not in SUPPORTED_SCHEMAS:
        raise EnvironmentValidationError(
            f"CONFIG ERROR: Environment '{env_id}' ({source}) — "
            f"unsupported schema version '{data['schema']}'. "
            f"Supported: {sorted(SUPPORTED_SCHEMAS)}"
        )


def _check_id_format(
    data: Dict[str, Any], source: str, env_id: str
) -> None:
    """
    Verify the environment ID conforms to the allowed format.

    Rules (Phase 7):
      - lowercase letters only
      - digits and hyphens allowed after the first character
      - must start with a lowercase letter
      - no spaces, underscores, or uppercase letters

    Valid:   web, python, data-science, python3
    Invalid: Web, web dev, web_dev, 123env
    """
    raw_id = data.get("id", "")
    if not isinstance(raw_id, str) or not _ID_PATTERN.match(raw_id):
        raise EnvironmentValidationError(
            f"CONFIG ERROR: Environment '{env_id}' ({source}) — "
            f"invalid id format: '{raw_id}'. "
            f"IDs must be lowercase, start with a letter, and contain "
            f"only letters, digits, and hyphens (e.g. web, data-science)."
        )


def _check_field_types(
    data: Dict[str, Any], source: str, env_id: str
) -> None:
    """
    Verify string fields contain strings (Phase 3).

    'id' and 'name' must be non-empty strings.
    'description', if present, must be a string.
    """
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


def _check_tools_field(
    data: Dict[str, Any], source: str, env_id: str
) -> None:
    """
    Verify the tools list is a non-empty list (Phase 4).
    Accepts both 'tools' and 'installers' field names.
    """
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


def _check_duplicate_tools(
    data: Dict[str, Any], source: str, env_id: str
) -> None:
    """
    Detect duplicate tool entries within a single environment (Phase 6).

    Example invalid: tools: ["git", "node", "git"]
    """
    tools = get_tools_list(data)
    if not isinstance(tools, list):
        return   # already caught by _check_tools_field

    seen: set = set()
    for tool_id in tools:
        if tool_id in seen:
            raise EnvironmentValidationError(
                f"CONFIG ERROR: Environment '{env_id}' ({source}) — "
                f"duplicate tool '{tool_id}'. "
                f"Each tool may only appear once in the tools list."
            )
        seen.add(tool_id)


def _check_installer_ids(
    data: Dict[str, Any], source: str, env_id: str
) -> None:
    """Verify every tool ID in the list is registered (Phase 5)."""
    from devsetup.installers.manager import is_registered
    tools = get_tools_list(data)
    if not isinstance(tools, list):
        return   # already caught

    for tool_id in tools:
        if not is_registered(tool_id):
            raise EnvironmentValidationError(
                f"CONFIG ERROR: installer '{tool_id}' not found in "
                f"environment '{env_id}' ({source}). "
                f"Use 'devsetup list' to see available environments."
            )
