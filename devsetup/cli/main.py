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

v1.4.1: DependencyError caught explicitly in cmd_install.
v1.6:   info command extended with --env, --summary, --verbose.
v1.7:   --yes / -y non-interactive mode.
v1.8:   --verbose on install command (Phase 4/10).
        --log-file <path> optional file output (Phase 12).
        Sets DEVSETUP_VERBOSE / DEVSETUP_LOG_FILE env vars which
        logger.py reads, keeping flag propagation to a single line
        in the CLI layer.
"""

import argparse
import os
import sys

from devsetup.__version__ import __version__
from devsetup.utils.logger import info, error, set_verbose, set_log_file
from devsetup.installers import manager as installer_manager
from devsetup.core import environment_loader
from devsetup.core.plugin_loader import load_plugins
from devsetup.installers.dependency_resolver import DependencyError
from devsetup.cli.env_info import print_env_info, print_env_summary


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
            "  info <tool>              Show details for a specific tool\n"
            "  info <environment>       Show details for an environment\n"
            "  info <n> --env           Force environment lookup\n\n"
            "Options:\n"
            "  --force                  Reinstall tools even if already installed\n"
            "  --yes, -y                Non-interactive mode, auto-accept all prompts\n"
            "  --verbose                Show detailed log output for debugging\n"
            "  --log-file <path>        Save all log output to a file\n"
            "  --debug                  Enable internal debug output\n"
            "  --summary                Show compact tool list (info command)\n"
            "  --version                Show CLI version\n"
            "  --help                   Show this help message\n\n"
            "Examples:\n"
            "  devsetup install web\n"
            "  devsetup install web --yes\n"
            "  devsetup install web --verbose\n"
            "  devsetup install web --yes --verbose\n"
            "  devsetup install web --log-file install.log\n"
            "  devsetup install web --force\n"
            "  devsetup install --tool git\n"
            "  devsetup list\n"
            "  devsetup info git\n"
            "  devsetup info web\n"
            "  devsetup info python --env\n"
            "  devsetup info web --summary\n"
            "  devsetup info web --verbose\n"
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
        "--yes", "-y",
        action="store_true",
        default=False,
        dest="yes",
        help=(
            "Non-interactive mode: automatically accept all prompts. "
            "Suitable for CI/CD pipelines and automated scripts."
        ),
    )
    install_parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help=(
            "Show detailed log output for debugging: dependency resolution "
            "steps, version detection, and internal decisions."
        ),
    )
    install_parser.add_argument(
        "--log-file",
        metavar="PATH",
        default=None,
        dest="log_file",
        help="Save all log output to PATH in addition to the console.",
    )
    install_parser.add_argument(
        "--debug",
        action="store_true",
        default=False,
        help="Enable internal debug output (sets DEVSETUP_DEBUG=1).",
    )

    # ── devsetup list ─────────────────────────────────────────────────────────
    subparsers.add_parser(
        "list",
        help="List all available environments.",
    )

    # ── devsetup info ─────────────────────────────────────────────────────────
    info_parser = subparsers.add_parser(
        "info",
        help=(
            "Show details for a tool or environment. "
            "If the name matches a registered tool, tool info is shown. "
            "Otherwise, environment info is shown. "
            "Use --env to force environment lookup."
        ),
    )
    info_parser.add_argument(
        "target",
        help="Tool name (e.g. git) or environment ID (e.g. web).",
    )
    info_parser.add_argument(
        "--env",
        action="store_true",
        default=False,
        help=(
            "Force environment lookup. Useful when a name is both a tool "
            "and an environment ID (e.g. 'python')."
        ),
    )
    info_parser.add_argument(
        "--summary",
        action="store_true",
        default=False,
        help="Show a compact one-line tool list (environment mode only).",
    )
    info_parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Show per-tool dependency information (environment mode only).",
    )

    return parser


def cmd_install(args: argparse.Namespace) -> int:
    """Handle: devsetup install"""
    # ── Apply logging configuration before anything runs ──────────────────
    if getattr(args, "debug", False):
        os.environ["DEVSETUP_DEBUG"] = "1"

    if getattr(args, "verbose", False):
        set_verbose(True)        # logger reads this via _is_verbose()

    log_file = getattr(args, "log_file", None)
    if log_file:
        set_log_file(log_file)   # logger tees all output to this path

    force    = getattr(args, "force", False)
    yes_mode = getattr(args, "yes",   False)

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
            installer_manager.install_environment(
                env["installers"],
                force=force,
                env_name=env["name"],
                yes_mode=yes_mode,
            )
        except DependencyError as exc:
            error(str(exc))
            return 1
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
    """
    Handle: devsetup info <target> [--env] [--summary] [--verbose]

    Dispatch logic:
      1. If --env is set → always look up as environment.
      2. If target is a registered tool AND --env is not set → show tool info.
      3. Otherwise → try as environment ID.

    Exit codes:
      0 → success
      1 → not found or config invalid
      2 → unexpected error
    """
    target    = args.target
    force_env = getattr(args, "env",     False)
    summary   = getattr(args, "summary", False)
    verbose   = getattr(args, "verbose", False)

    if not force_env and installer_manager.is_registered(target):
        return _cmd_tool_info(target)

    return _cmd_env_info(target, summary=summary, verbose=verbose)


def _cmd_tool_info(tool_name: str) -> int:
    """Print tool installation details (existing behaviour, unchanged)."""
    try:
        data = installer_manager.tool_info(tool_name)
    except KeyError as exc:
        error(str(exc))
        error("Use 'devsetup list' to see available environments.")
        return 1
    except Exception as exc:
        error(f"Unexpected error retrieving tool info: {exc}")
        return 2

    info(f"Tool         : {data['tool']}")
    info(f"Installed    : {data['installed']}")
    info(f"Version      : {data['version']}")
    info(f"Dependencies : {data['dependencies']}")
    return 0


def _cmd_env_info(env_id: str, summary: bool = False, verbose: bool = False) -> int:
    """Print environment details using env_info formatter."""
    try:
        env = environment_loader.load(env_id)
    except FileNotFoundError:
        error(f"Environment '{env_id}' not found.")
        error("Use 'devsetup list' to see available environments.")
        return 1
    except ValueError as exc:
        error(str(exc))
        return 1
    except Exception as exc:
        error(f"Unexpected error loading environment '{env_id}': {exc}")
        return 2

    if summary:
        print_env_summary(env)
    else:
        print_env_info(env, verbose=verbose)

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
