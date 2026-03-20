"""
devsetup.utils.prompt
---------------------
Centralised confirmation utility for DevSetup v1.7.

Responsibilities (Phase 3 / Phase 12):
  - Provide a single point for all user confirmations.
  - In non-interactive mode (auto_yes=True): log the auto-accept and
    return True immediately — never blocks execution.
  - In interactive mode (auto_yes=False): print a y/n prompt and read
    stdin; return True only if the user confirms.

All callers pass the auto_yes flag derived from the CLI --yes / -y
argument. This keeps the flag decoupled from individual modules — only
the prompt utility needs to know about it.

Architecture compliance:
  - No OS logic, no installation logic (Rules 1 & 5).
  - Output routes through devsetup.utils.logger (Rule 9).
  - This module is purely a utility; it contains no business logic.
"""

import sys
from devsetup.utils.logger import auto as log_auto, info as log_info


def confirm(message: str, auto_yes: bool = False) -> bool:
    """
    Ask the user to confirm an action, or auto-accept in non-interactive mode.

    Parameters
    ----------
    message : str
        The question to display (e.g. "Install 3 tools into Web? (y/n)").
    auto_yes : bool
        When True (--yes flag active), skip the prompt, log an [AUTO] line,
        and return True immediately.  When False, read a response from stdin.

    Returns
    -------
    bool
        True  → confirmed (user typed y/Y, or auto_yes is True).
        False → declined (user typed anything else).

    Examples
    --------
    Interactive:
        Proceed with installation? (y/n): y   → True
        Proceed with installation? (y/n): n   → False

    Non-interactive (--yes):
        [HH:MM:SS] [AUTO]    Proceed with installation? → yes (non-interactive mode)
        → True
    """
    if auto_yes:
        log_auto(f"{message} → yes (non-interactive mode)")
        return True

    log_info(message)
    try:
        response = input().strip().lower()
    except (EOFError, KeyboardInterrupt):
        # Treat EOF (e.g. piped input with no data) as a decline so scripts
        # that accidentally omit --yes do not hang or proceed silently.
        return False

    return response in ("y", "yes")
