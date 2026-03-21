# DevSetup

> Automated developer environment setup — one command to install everything.

DevSetup reads simple JSON configuration files and installs all the tools
your team needs, on any operating system, using native system package managers.

---

## Overview

DevSetup solves a common problem: setting up a new development machine by hand
is repetitive, error-prone, and undocumented. DevSetup replaces that process
with a single command that installs the right tools, in the right order, using
the system package manager already present on the machine.

Key properties:

- **Idempotent** — running it twice is safe; installed tools are skipped
- **Cross-platform** — works on Linux, macOS, and Windows
- **Configuration-driven** — environments are JSON files, no code changes needed
- **Extensible** — add tools or environments by dropping in a file
- **Non-interactive** — full CI/CD support via `--yes` flag
- **Observable** — `--verbose` and `--log-file` for detailed audit output

---

## Installation

```bash
pip install .
```

After installation the `devsetup` command is available globally.

Run without installing:

```bash
python -m devsetup --help
```

---

## Quick Start

```bash
# See what environments are available
devsetup list

# Install the web development environment
devsetup install web

# Install the Python development environment
devsetup install python

# Install a single tool
devsetup install --tool git

# Show details for a tool
devsetup info node

# Show details for an environment
devsetup info web --env
```

### CI/CD — Non-interactive mode

Use `--yes` to skip all confirmation prompts. Combine with `--log-file` for
a full audit trail:

```bash
devsetup install web --yes
devsetup install web --yes --log-file /var/log/devsetup.log
```

### Verbose and debug output

Use `--verbose` to see dependency resolution steps, version detection, and
internal decisions:

```bash
devsetup install web --verbose
devsetup install web --yes --verbose
devsetup install web --verbose --log-file install.log
```

Expected output for `devsetup install web`:

```
[HH:MM:SS] [INFO]    Installing environment: Web Development
[HH:MM:SS] [INFO]    Detected OS: linux
[HH:MM:SS] [INFO]    Detected package manager: apt
[HH:MM:SS] [DEPS]    Resolving dependencies...
[HH:MM:SS] [DEPS]    Computed install order:
[HH:MM:SS] [DEPS]      1. git
[HH:MM:SS] [DEPS]      2. node  (needs: git)
[HH:MM:SS] [DEPS]      3. vscode
[HH:MM:SS] [INFO]    [1/3] Installing git (linux / apt)
[HH:MM:SS] [CHECK]   git
[HH:MM:SS] [SKIP]    git already installed (git version 2.43.0)
[HH:MM:SS] [VERSION] 2.43.0
[HH:MM:SS] [INFO]    [2/3] Installing node (linux / apt)
[HH:MM:SS] [CHECK]   node
[HH:MM:SS] [INSTALL] node
[HH:MM:SS] [OK]      node installed successfully.
[HH:MM:SS] [VERSION] 20.11.1
...

[HH:MM:SS] [INFO]    Environment: Web Development

[HH:MM:SS] [INFO]    Installation Summary
[HH:MM:SS] [INFO]    --------------------
[HH:MM:SS] [INFO]    Installed (2):
[HH:MM:SS] [INFO]      node (20.11.1)
[HH:MM:SS] [INFO]      vscode (1.86.0)
[HH:MM:SS] [INFO]    Skipped (1):
[HH:MM:SS] [INFO]      git (2.43.0)
[HH:MM:SS] [INFO]    Failed:
[HH:MM:SS] [INFO]      none
[HH:MM:SS] [INFO]    Blocked:
[HH:MM:SS] [INFO]      none

[HH:MM:SS] [OK]      Environment setup complete.
```

---

## Supported Environments

| Environment | Tools |
|---|---|
| `web` | git, node, vscode |
| `python` | python, pip, vscode |
| `data-science` | python, pip, vscode |

---

## Supported Platforms

| OS | Package Managers |
|---|---|
| Linux | apt · dnf · pacman |
| macOS | brew |
| Windows | winget |

DevSetup automatically detects the OS and active package manager at runtime.

---

## CLI Commands

| Command | Description |
|---|---|
| `devsetup list` | List all available environments |
| `devsetup install <env>` | Install all tools for an environment |
| `devsetup install <env> --force` | Reinstall all tools even if present |
| `devsetup install <env> --yes` | Non-interactive install (no prompts) |
| `devsetup install <env> --verbose` | Verbose output with dep resolution detail |
| `devsetup install <env> --log-file <p>` | Tee all log output to a file |
| `devsetup install --tool <t>` | Install a single named tool |
| `devsetup info <tool>` | Show details for a specific tool |
| `devsetup info <env> --env` | Show details for an environment |
| `devsetup info <env> --summary` | Show compact one-line tool list |
| `devsetup info <env> --verbose` | Show per-tool dependency info |
| `devsetup --version` | Print the DevSetup version |
| `devsetup --help` | Show usage guide |

### Options

**`--force`** — Bypass the skip-if-installed check and reinstall every tool.

```bash
devsetup install web --force
devsetup install --tool git --force
```

**`--yes` / `-y`** — Non-interactive mode. Auto-accepts all prompts and logs
`[AUTO]` lines for every auto-accepted decision. Suitable for CI/CD pipelines
and automated provisioning scripts.

```bash
devsetup install web --yes
devsetup install python --yes --log-file /tmp/setup.log
```

**`--verbose`** — Detailed diagnostic output. Shows dependency resolution steps,
version detection, and internal decisions. Verbose lines carry a full
`YYYY-MM-DD HH:MM:SS` timestamp (all other lines use `HH:MM:SS`).

```bash
devsetup install web --verbose
devsetup install web --yes --verbose
```

**`--log-file <path>`** — Tee all log output to a file in addition to the
console. The file receives every log level including `[VERBOSE]` when
`--verbose` is active.

```bash
devsetup install web --log-file install.log
devsetup install web --yes --verbose --log-file /var/log/devsetup.log
```

**`--debug`** — Enable verbose internal debug output (sets `DEVSETUP_DEBUG=1`).
Prints `[DEBUG]` lines with low-level internal state.

```bash
DEVSETUP_DEBUG=1 devsetup install web
devsetup install web --debug
```

---

## Configuration Format

Environments are defined as JSON files in the `environments/` directory.

```json
{
  "schema": "1.0",
  "id": "web",
  "name": "Web Development",
  "description": "Full web development stack.",
  "installers": ["git", "node", "vscode"]
}
```

| Field | Required | Description |
|---|---|---|
| `schema` | No | Config schema version. If present must be `"1.0"`. |
| `id` | Yes | Unique identifier used in CLI commands. |
| `name` | Yes | Human-readable display name. |
| `description` | No | Optional description shown on `devsetup list`. |
| `installers` | Yes | Ordered list of tool IDs to install. |

The `tools` key is accepted as an alias for `installers` (v1.5+ format).

To add a new environment, create `environments/<id>.json` — no code changes needed.

---

## Installation Safety

DevSetup is idempotent by default.

- Tools already installed are detected and skipped automatically.
- Detection uses `command_runs()` — verifies both PATH presence and successful
  execution (exit code 0), catching corrupted installs where the binary exists
  but fails to run.
- If a tool installation fails, the pipeline stops immediately and reports the
  failure. Partially-installed environments are never silently completed.

### Force reinstall

```bash
devsetup install web --force
```

The `--force` flag bypasses skip logic and reinstalls all tools regardless of
current state.

---

## Dependency Ordering

DevSetup resolves tool dependencies automatically before installing.

```
git → node → vscode    (node requires git; vscode has no deps)
python → pip → vscode  (pip requires python; vscode has no deps)
```

The install order is always deterministic: dependencies install before their
dependents. If a dependency fails, all tools that depend on it are marked
`BLOCKED` and skipped; independent tools continue to run.

---

## Package Manager Architecture

```
devsetup install web
        │
        ▼
OS Detector          → linux | macos | windows
        │
        ▼
PM Detector          → apt | dnf | pacman | brew | winget
        │
        ▼
PackageManagerRunner → unified install(package) interface
        │
        ▼
Installer Modules    → git.py, node.py, ...
        │
        ▼
Package Name Mapping → packages/git.json → "git" (apt) / "Git.Git" (winget)
        │
        ▼
System Package Manager
```

---

## Troubleshooting

**`devsetup install web` fails with "sudo: command not found"**
Your system requires `sudo` for package manager commands. Install it or run
DevSetup as root.

**"Installer not registered: docker"**
`docker` has no installer module yet. See `CONTRIBUTING.md` to add one.

**"Environment not found: mobile"**
No `environments/mobile.json` exists. Run `devsetup list` to see available
environments, or create the file yourself.

**Tool detected as installed but version is wrong**
Use `--force` to reinstall: `devsetup install --tool git --force`

**`devsetup list` shows no environments**
Confirm that `environments/` contains `.json` files with valid `id`, `name`,
and `installers` fields.

**Enable debug output**

```bash
DEVSETUP_DEBUG=1 devsetup install web
# or
devsetup install web --debug
```

---

## License

MIT — see [LICENSE](LICENSE).
