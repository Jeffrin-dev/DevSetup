"""
devsetup.system.command_detector
----------------------------------
Centralized command detection utility.

Responsibilities:
  - Check whether a command exists on PATH
  - Verify a command executes successfully (exit code 0)
  - Provide a single reusable helper for all installer modules

No installation logic. No OS logic. Detection only.
"""

import shutil
import subprocess
from typing import Optional


def command_exists(command: str) -> bool:
    """
    Return True if the command is found on PATH.

    Uses shutil.which — fast, no subprocess required.

    Parameters
    ----------
    command : str
        The command name (e.g. 'git', 'node', 'code').

    Returns
    -------
    bool
    """
    return shutil.which(command) is not None


def command_runs(command: str, args: Optional[list] = None) -> bool:
    """
    Return True if the command is on PATH AND executes with exit code 0.

    More thorough than command_exists — catches corrupted or broken installs
    where the binary is present but non-functional (Phase 9 requirement).

    Parameters
    ----------
    command : str
        The command name (e.g. 'git').
    args : list, optional
        Arguments to pass (defaults to ['--version']).

    Returns
    -------
    bool
    """
    if not command_exists(command):
        return False

    if args is None:
        args = ["--version"]

    try:
        result = subprocess.run(
            [command] + args,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False
