"""
devsetup.cli.env_info
----------------------
Output formatter for the environment info command (v1.6).

Responsibilities (Phase 13 — Info Command Module / Output Formatter):
  - Format a validated environment config dict for human-readable display
  - Support three output modes:
      default  — ID, name, description, ordered tools list
      summary  — compact one-line tool list  (--summary, Phase 7)
      verbose  — default + per-tool dependency info  (--verbose, Phase 9)

Rules:
  - No file I/O, no JSON loading, no validation (Architecture Rule 6)
  - No installation, no OS detection (Architecture Rules 1 & 5)
  - All output routes through devsetup.utils.logger (Architecture Rule 9)
  - Accepts only a pre-validated, normalised env dict from environment_loader

v1.6 output modes
-----------------
Default
    Environment : web
    Name        : Web Development
    Description : Full web development stack with Git, Node.js, and VS Code.
    Tools:
      - git
      - node
      - vscode

Summary  (--summary)
    Tools in 'web': git, node, vscode

Verbose  (--verbose)
    Environment : web
    Name        : Web Development
    Description : Full web development stack with Git, Node.js, and VS Code.
    Tools:
      - git
      - node  (depends on: git)
      - vscode
"""

from typing import Any, Dict, List

from devsetup.utils.logger import info


# ── Public entry points ───────────────────────────────────────────────────────

def print_env_info(env: Dict[str, Any], verbose: bool = False) -> None:
    """
    Print full environment details to stdout (default and verbose modes).

    Parameters
    ----------
    env : dict
        Validated, normalised environment dict from environment_loader.load().
    verbose : bool
        When True, append per-tool dependency lines after each tool entry.
    """
    env_id      = env.get("id", "")
    name        = env.get("name", "")
    description = env.get("description", "").strip()
    tools: List[str] = env.get("installers", [])

    info(f"Environment : {env_id}")
    info(f"Name        : {name}")
    info(f"Description : {description if description else 'No description provided'}")

    if not tools:
        info("Tools       : No tools defined")
        return

    info("Tools:")
    for tool_id in tools:
        deps = _get_dependencies(tool_id)
        if verbose and deps:
            info(f"  - {tool_id}  (depends on: {', '.join(deps)})")
        else:
            info(f"  - {tool_id}")


def print_env_summary(env: Dict[str, Any]) -> None:
    """
    Print a compact one-line tool list for scripting / automation (--summary).

    Output format:
        Tools in '<id>': git, node, vscode

    Parameters
    ----------
    env : dict
        Validated, normalised environment dict from environment_loader.load().
    """
    env_id = env.get("id", "")
    tools: List[str] = env.get("installers", [])

    if not tools:
        info(f"Tools in '{env_id}': (none)")
    else:
        info(f"Tools in '{env_id}': {', '.join(tools)}")


# ── Internal helpers ──────────────────────────────────────────────────────────

def _get_dependencies(tool_id: str) -> List[str]:
    """
    Return the declared dependency list for tool_id via the public
    tool_dependencies() API on the installer manager.

    Uses the public API rather than accessing _REGISTRY directly, keeping
    the CLI layer decoupled from installer internals (Architecture Rule 1).

    Read-only — never instantiates or runs the installer.
    Returns an empty list if the tool is not registered or has no dependencies.
    """
    try:
        from devsetup.installers.manager import tool_dependencies
        return tool_dependencies(tool_id)
    except KeyError:
        return []   # tool not registered — not an error in display context
    except Exception:
        return []
