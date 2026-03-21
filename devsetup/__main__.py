"""
Entry point for: python -m devsetup

Plugin loading is handled inside cli.main.main() so that both the
'devsetup' console-script entry point and 'python -m devsetup' execute
identical initialisation paths exactly once.

v1.9 (Rule 1 / Rule 7 fix):
  Previously this module called load_plugins() directly before invoking
  main(), which itself also calls load_plugins().  That caused every
  plugin to be loaded twice on 'python -m devsetup'.  The duplicate call
  has been removed — main() is now the single owner of plugin loading.
"""

import sys
from devsetup.cli.main import main

if __name__ == "__main__":
    sys.exit(main())
