# DevSetup

> Automated developer environment setup — one command to install everything.

DevSetup reads simple JSON configuration files and installs all the tools
your team needs, on any operating system, with a single command.

---

## Quick Start

```bash
# List all available environments
devsetup list

# Install the web development environment
devsetup install web

# Install the Python development environment
devsetup install python

# Install a single tool
devsetup install --tool git

# Show info for a specific tool
devsetup info node
```

---

## Installation

```bash
pip install .
```

After installation the `devsetup` command is available globally.

You can also run without installing:

```bash
python -m devsetup --help
```

---

## Supported Platforms

| OS | Status |
|---|---|
| Linux | ✅ Supported |
| macOS | ✅ Supported |
| Windows | ✅ Supported |

DevSetup automatically detects the operating system at runtime and runs
the correct installation path for each tool.

---

## Supported Environments

### Web
```bash
devsetup install web
```
Tools installed: Git, Node.js, VS Code

### Python
```bash
devsetup install python
```
Tools installed: Python 3, pip, VS Code

### Data Science
```bash
devsetup install data-science
```
Tools installed: Python 3, pip, VS Code

---

## Creating a New Environment

Adding a new environment requires **no code changes** — just create a JSON file.

1. Create a new file in `environments/`:

```json
{
  "schema": "1.0",
  "id": "go",
  "name": "Go Development",
  "description": "Go development environment.",
  "installers": ["git", "vscode"]
}
```

2. Run it immediately:

```bash
devsetup install go
devsetup list
```

---

## Cross-Platform Architecture

DevSetup uses a centralized OS detection module that provides a clean,
normalized API to all installer modules.

### OS Detection

```
devsetup install web
        │
        ▼
OS Detector (system/os_detector.py)
        │
        ▼
Normalized OS: linux | macos | windows
        │
        ▼
Installer OS Branch
```

### Normalized OS identifiers

| Raw platform value | Normalized |
|---|---|
| `linux` | `linux` |
| `darwin` | `macos` |
| `win32` / `windows` | `windows` |

### Installer OS branching

Each installer contains OS branches internally:

```
install()
   │
   ├─ linux   → apt-get
   ├─ macos   → brew
   └─ windows → winget
```

All OS detection is centralized in `devsetup/system/os_detector.py`.
No installer calls `platform.system()` directly.

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
Installer IDs                 (["python", "pip", "vscode"])
 │
 ▼
Installer Registry            (installers/manager.py)
 │
 ▼
OS Detector                   (system/os_detector.py)
 │
 ▼
Installer Modules             (installers/git.py, node.py, ...)
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
│   │   └── os_detector.py        ← centralized OS detection
│   ├── installers/
│   │   ├── base.py
│   │   ├── manager.py
│   │   ├── git.py
│   │   ├── node.py
│   │   ├── pip.py
│   │   ├── python.py
│   │   └── vscode.py
│   └── utils/
│       └── logger.py
├── environments/
│   ├── web.json
│   ├── python.json
│   └── data-science.json
├── plugins/
├── pyproject.toml
├── LICENSE
└── README.md
```

---

## CLI Commands

| Command                       | Description                              |
|-------------------------------|------------------------------------------|
| `devsetup list`               | List all available environments          |
| `devsetup install <env>`      | Install all tools for an environment     |
| `devsetup install --tool <t>` | Install a single named tool              |
| `devsetup info <tool>`        | Show details for a specific tool         |
| `devsetup --version`          | Print the DevSetup version               |
| `devsetup --help`             | Show usage guide                         |

---

## Environment Configuration Schema

```json
{
  "schema": "1.0",
  "id": "web",
  "name": "Web Development",
  "description": "Full web development stack.",
  "installers": ["git", "node", "vscode"]
}
```

---

## Plugin System

Drop a Python module into `~/.devsetup/plugins/` to register custom tools.
See `plugins/README.md` for the plugin API.

---

## License

MIT — see [LICENSE](LICENSE).
