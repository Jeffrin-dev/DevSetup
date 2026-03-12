"""
devsetup.cli.main
-----------------
CLI entry point.

Responsibilities (Architecture Rule 1):
  - Parse commands and arguments
  - Validate arguments
  - Call internal modules

Must NOT contain:
  - Installation logic
  - OS detection
  - Environment loading
  - Business logic of any kind
"""

import argparse
import os
import sys

from devsetup.__version__ import __version__
from devsetup.utils.logger import info, error
from devsetup.installers import manager as installer_manager
from devsetup.core import environment_loader
from devsetup.core.plugin_loader import load_plugins


def build_parser() -> argparse.ArgumentParser:
    """Construct and return the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="devsetup",
        description="DevSetup — automated developer environment setup tool.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Commands:\n"
            "  install <environment>    Install a development environment\n"
            "  install --tool <n>       Install a single tool\n"
            "  list                     List available environments\n"
            "  info <tool>              Show details for a specific tool\n\n"
            "Options:\n"
            "  --force                  Reinstall tools even if already installed\n"
            "  --debug                  Enable verbose diagnostic output\n"
            "  --version                Show CLI version\n"
            "  --help                   Show this help message\n\n"
            "Examples:\n"
            "  devsetup install web\n"
            "  devsetup install web --force\n"
            "  devsetup install web --debug\n"
            "  devsetup install --tool git\n"
            "  devsetup list\n"
            "  devsetup info node\n"
        ),
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"devsetup {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", metavar="<command>")

    # ── devsetup install ──────────────────────────────────────────────────────
    install_parser = subparsers.add_parser(
        "install",
        help="Install an environment or a single tool.",
    )
    install_group = install_parser.add_mutually_exclusive_group(required=True)
    install_group.add_argument(
        "environment",
        nargs="?",
        help="ID of the environment to install (e.g. web, python).",
    )
    install_group.add_argument(
        "--tool",
        metavar="TOOL",
        help="Install a single tool by name (e.g. git).",
    )
    install_parser.add_argument(
        "--force",
        action="store_true",
        default=False,
        help="Force reinstall even if the tool is already installed.",
    )
    install_parser.add_argument(
        "--debug",
        action="store_true",
        default=False,
        help="Enable verbose diagnostic output (sets DEVSETUP_DEBUG=1).",
    )

    # ── devsetup list ─────────────────────────────────────────────────────────
    subparsers.add_parser(
        "list",
        help="List all available environments.",
    )

    # ── devsetup info ─────────────────────────────────────────────────────────
    info_parser = subparsers.add_parser(
        "info",
        help="Show installation details for a specific tool.",
    )
    info_parser.add_argument("tool", help="Tool name (e.g. git, node, vscode).")

    return parser


def cmd_install(args: argparse.Namespace) -> int:
    """Handle: devsetup install"""
    # Activate debug mode if --debug flag is set
    if getattr(args, "debug", False):
        os.environ["DEVSETUP_DEBUG"] = "1"

    force = getattr(args, "force", False)

    if args.tool:
        try:
            result = installer_manager.install_tool(args.tool, force=force)
            return 1 if result.failed else 0
        except KeyError as exc:
            error(str(exc))
            error("Use 'devsetup list' to see available environments.")
            return 1
        except Exception as exc:
            error(f"Installation failed: {exc}")
            return 1

    else:
        env_id = args.environment
        try:
            env = environment_loader.load(env_id)
        except FileNotFoundError as exc:
            error(str(exc))
            return 1
        except ValueError as exc:
            error(str(exc))
            return 1

        info(f"Installing environment: {env['name']}")
        try:
            installer_manager.install_environment(env["installers"], force=force)
        except RuntimeError as exc:
            error(str(exc))
            return 1
        except Exception as exc:
            error(f"Environment installation failed: {exc}")
            return 1

    return 0


def cmd_list(_args: argparse.Namespace) -> int:
    """Handle: devsetup list"""
    try:
        environments = environment_loader.list_available()
    except Exception as exc:
        error(f"Failed to load environments: {exc}")
        return 1

    if not environments:
        info("No environments available.")
        return 0

    info("Available environments:\n")
    for env_id in environments:
        info(f"  {env_id}")
    return 0


def cmd_info(args: argparse.Namespace) -> int:
    """Handle: devsetup info <tool>"""
    try:
        data = installer_manager.tool_info(args.tool)
    except KeyError as exc:
        error(str(exc))
        error("Use 'devsetup list' to see available environments.")
        return 1

    info(f"Tool      : {data['tool']}")
    info(f"Installed : {data['installed']}")
    info(f"Version   : {data['version']}")
    return 0


_COMMAND_HANDLERS = {
    "install": cmd_install,
    "list":    cmd_list,
    "info":    cmd_info,
}


def main(argv=None) -> int:
    """
    Primary CLI entry point.

    Returns
    -------
    int
        Exit code (0 = success, non-zero = failure).
    """
    # Load user plugins before any command runs (Architecture Rule 7)
    load_plugins(installer_manager._REGISTRY)

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    handler = _COMMAND_HANDLERS.get(args.command)
    if handler is None:
        error(f"Unknown command: {args.command}")
        error("Run 'devsetup --help' for usage.")
        parser.print_help()
        return 1

    return handler(args)
