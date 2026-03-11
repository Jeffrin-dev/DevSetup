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
```

Expected output for `devsetup install web`:

```
[HH:MM:SS] [INFO]    Installing environment: Web Development
[HH:MM:SS] [INFO]    Detected OS: linux
[HH:MM:SS] [INFO]    Detected package manager: apt
[HH:MM:SS] [INFO]    [1/3] Installing git (linux / apt)
[HH:MM:SS] [CHECK]   git
[HH:MM:SS] [SKIP]    git already installed (git version 2.43.0)
[HH:MM:SS] [INFO]    [2/3] Installing node (linux / apt)
[HH:MM:SS] [CHECK]   node
[HH:MM:SS] [INSTALL] node
[HH:MM:SS] [OK]      node installed successfully.
...

[HH:MM:SS] [INFO]    Installation Summary
[HH:MM:SS] [INFO]    --------------------
[HH:MM:SS] [INFO]    Installed:
[HH:MM:SS] [INFO]      node
[HH:MM:SS] [INFO]      vscode
[HH:MM:SS] [INFO]    Skipped:
[HH:MM:SS] [INFO]      git
[HH:MM:SS] [INFO]    Failed:    None

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
| `devsetup install --tool <t>` | Install a single named tool |
| `devsetup info <tool>` | Show details for a specific tool |
| `devsetup --version` | Print the DevSetup version |
| `devsetup --help` | Show usage guide |

### Options

**`--force`** — Bypass the skip-if-installed check and reinstall every tool.

```bash
devsetup install web --force
devsetup install --tool git --force
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
| `schema` | Yes | Config schema version. Must be `"1.0"`. |
| `id` | Yes | Unique identifier used in CLI commands. |
| `name` | Yes | Human-readable display name. |
| `description` | No | Optional description shown on `devsetup list`. |
| `installers` | Yes | Ordered list of tool IDs to install. |

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
current state. Useful for CI environments, recovering from corrupted installs,
or upgrading to latest versions.

---

## Package Manager Architecture

DevSetup maps tools to the correct system package manager automatically.

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

Package name mappings live in `packages/<toolname>.json`:

```json
{
  "apt":    "git",
  "dnf":    "git",
  "pacman": "git",
  "brew":   "git",
  "winget": "Git.Git"
}
```

---

## Full Architecture

```
CLI
 │
 ▼
Environment Loader            (core/environment_loader.py)
 │
 ▼
Environment Validator         (system/environment_validator.py)
 │
 ▼
Installer Registry            (installers/manager.py)
 │
 ▼
OS Detector                   (system/os_detector.py)
 │
 ▼
Package Manager Detector      (system/package_manager_detector.py)
 │
 ▼
Package Manager Runner        (system/package_managers/runner.py)
 │
 ▼
Installer Modules             (installers/git.py, node.py, ...)
 │
 ▼
Package Name Mapping          (packages/*.json)
 │
 ▼
System Package Manager
```

---

## Project Structure

```
DevSetup/
├── devsetup/
│   ├── __version__.py
│   ├── __main__.py
│   ├── cli/
│   │   └── main.py
│   ├── core/
│   │   └── environment_loader.py
│   ├── system/
│   │   ├── os_detector.py
│   │   ├── command_detector.py
│   │   ├── environment_validator.py
│   │   ├── package_manager_detector.py
│   │   └── package_managers/
│   │       ├── runner.py
│   │       ├── apt_manager.py
│   │       ├── dnf_manager.py
│   │       ├── pacman_manager.py
│   │       ├── brew_manager.py
│   │       └── winget_manager.py
│   ├── installers/
│   │   ├── base.py
│   │   ├── manager.py
│   │   ├── git.py
│   │   ├── node.py
│   │   ├── pip.py
│   │   ├── python.py
│   │   └── vscode.py
│   └── utils/
│       ├── logger.py
│       └── package_loader.py
├── environments/
│   ├── web.json
│   ├── python.json
│   └── data-science.json
├── packages/
│   ├── git.json
│   ├── node.json
│   ├── pip.json
│   ├── python.json
│   └── vscode.json
├── tests/
│   ├── test_cli.py
│   ├── test_installers.py
│   └── test_config.py
└── plugins/
    └── README.md
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
Confirm that `environments/` contains `.json` files with valid `schema`, `id`,
`name`, and `installers` fields.

**Enable debug output**
Set `DEVSETUP_DEBUG=1` for verbose diagnostics:

```bash
DEVSETUP_DEBUG=1 devsetup install web
```

---

## License

MIT — see [LICENSE](LICENSE).
