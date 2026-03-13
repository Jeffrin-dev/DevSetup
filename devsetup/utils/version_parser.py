"""
devsetup.utils.version_parser
------------------------------
Shared utility for extracting clean version strings from raw
command output.

Responsibilities:
  - Accept raw stdout from version commands
  - Extract the first semver-like version number
  - Strip leading 'v' prefix for consistency
  - Return a clean, human-readable version string
  - Gracefully handle empty or unrecognised output

Supported input patterns (Phase 9):
  git version 2.43.0         → 2.43.0
  v20.11.1                   → 20.11.1
  Python 3.11.7              → 3.11.7
  pip 23.0.1 from /usr/...   → 23.0.1
  code 1.86.0                → 1.86.0
  java version "21.0.2"      → 21.0.2

No subprocess calls. No OS logic. Parsing only.
"""

import re

# Matches an optional leading 'v' then MAJOR.MINOR with optional additional
# dot-separated components (e.g. 2.43.0, 20.11.1, 3.11.7, 1.86.0.24388.0)
_VERSION_RE = re.compile(r'v?(\d+\.\d+(?:\.\d+)*)')


def parse_version(raw_output: str) -> str:
    """
    Extract a clean version string from raw command output.

    Only the first line of output is examined — tools like VS Code
    emit multi-line output where the version is always on line 1.

    Parameters
    ----------
    raw_output : str
        Raw stdout (or stderr) from a version command.

    Returns
    -------
    str
        The extracted version string (e.g. '2.43.0'), or 'unknown'
        if no version-like pattern is found.

    Examples
    --------
    >>> parse_version("git version 2.43.0")
    '2.43.0'
    >>> parse_version("v20.11.1")
    '20.11.1'
    >>> parse_version("Python 3.11.7")
    '3.11.7'
    >>> parse_version("pip 23.0.1 from /usr/lib/python3/dist-packages/pip (python 3.11)")
    '23.0.1'
    """
    if not raw_output or not raw_output.strip():
        return "unknown"

    # Only inspect the first non-empty line
    first_line = raw_output.strip().splitlines()[0]

    match = _VERSION_RE.search(first_line)
    if match:
        return match.group(1)

    # No version-like pattern found — never leak raw command output
    # (e.g. "error: command failed") as a version string.
    return "unknown"
