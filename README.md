# DevSetup

> Automated developer environment setup — one command to install everything.

DevSetup reads simple JSON configuration files and installs all the tools
your team needs, on any operating system, using native system package managers.

---

## Quick Start

```bash
devsetup list
devsetup install web
devsetup install python
devsetup install --tool git
devsetup info node
```

---

## Installation

```bash
pip install .
```

---

## Supported Platforms

| OS | Package Managers |
|---|---|
| Linux | apt · dnf · pacman |
| macOS | brew |
| Windows | winget |

DevSetup automatically detects the OS and active package manager at runtime.

---

## Supported Environments

| Environment | Tools |
|---|---|
| `web` | git, node, vscode |
| `python` | python, pip, vscode |
| `data-science` | python, pip, vscode |

---

## Creating a New Environment

No code changes required. Create a JSON file:

```json
{
  "schema": "1.0",
  "id": "go",
  "name": "Go Development",
  "description": "Go development environment.",
  "installers": ["git", "vscode"]
}
```

Then run it:

```bash
devsetup install go
```

---

## Package Manager Architecture

### Detection Pipeline

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

### Package Manager Commands

| Manager | Install command |
|---|---|
| apt | `sudo apt-get install -y <package>` |
| dnf | `sudo dnf install -y <package>` |
| pacman | `sudo pacman -S --noconfirm <package>` |
| brew | `brew install <package>` |
| winget | `winget install --id <package> -e` |

### Package Name Mapping

Some tools have different package names per manager. Mappings live in `packages/`:

```json
{
  "apt":    "git",
  "dnf":    "git",
  "pacman": "git",
  "brew":   "git",
  "winget": "Git.Git"
}
```

Add a new tool mapping by creating `packages/<toolname>.json` — no code changes needed.

### Example Install Log

```
[INFO]    Installing environment: Web Development
[INFO]    Detected OS: linux
[INFO]    Detected package manager: apt
[INFO]    [1/3] Installing git (linux / apt)
[CHECK]   git
[SKIP]    git already installed (git version 2.43.0)
[INFO]    [2/3] Installing node (linux / apt)
[CHECK]   node
[INSTALL] node
[INFO]    Installing nodejs using apt...
[OK]      node installed successfully.
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
Environment Registry          (environments/*.json)
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
└── plugins/
```

---

## CLI Commands

| Command | Description |
|---|---|
| `devsetup list` | List all available environments |
| `devsetup install <env>` | Install all tools for an environment |
| `devsetup install --tool <t>` | Install a single named tool |
| `devsetup info <tool>` | Show details for a specific tool |
| `devsetup --version` | Print the DevSetup version |
| `devsetup --help` | Show usage guide |

---

## License

MIT — see [LICENSE](LICENSE).
