"""
Entry point for: python -m devsetup

Loads user plugins from ~/.devsetup/plugins/ before starting the CLI.
Plugin failures are sandboxed and will never crash DevSetup.
"""

import sys
from devsetup.core.plugin_loader import load_plugins
from devsetup.installers.manager import _REGISTRY
from devsetup.cli.main import main

if __name__ == "__main__":
    # Load user plugins before CLI execution (Architecture Rule 7)
    load_plugins(_REGISTRY)
    sys.exit(main())
