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

```bash
environments/go.json
```

2. Define the environment:

```json
{
  "schema": "1.0",
  "id": "go",
  "name": "Go Development",
  "description": "Go development environment.",
  "installers": ["git", "vscode"]
}
```

3. Run it immediately:

```bash
devsetup install go
devsetup list
```

The environment is automatically discovered — no restarts, no code edits.

---

## Architecture

```
CLI
 │
 ▼
Environment Loader            (core/environment_loader.py)
 │  scans environments/ dynamically
 ▼
Environment Registry          (environments/*.json)
 │  id, name, description, installers list
 ▼
Installer IDs                 (["python", "pip", "vscode"])
 │
 ▼
Installer Registry            (installers/manager.py)
 │  maps IDs to installer classes
 ▼
Installer Modules             (installers/git.py, node.py, ...)
```

Each layer has a single responsibility:

- **CLI** — parses commands, no business logic
- **Environment Loader** — scans directory, parses JSON, validates schema
- **Environment Registry** — JSON config files, one per environment
- **Installer Registry** — maps tool names to installer classes
- **Installer Modules** — isolated per tool, OS-specific logic contained inside

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

| Field | Purpose |
|---|---|
| `schema` | Config schema version for backward compatibility |
| `id` | Unique identifier used in CLI commands |
| `name` | Human-readable display name |
| `description` | Short description of the environment |
| `installers` | Ordered list of installer IDs to execute |

---

## Project Structure

```
DevSetup/
├── devsetup/
│   ├── __version__.py        ← single version source of truth
│   ├── __main__.py           ← python -m devsetup entry point
│   ├── cli/
│   │   └── main.py           ← argument parsing only, no business logic
│   ├── core/
│   │   └── environment_loader.py  ← dynamic loader, validates & registers envs
│   ├── installers/
│   │   ├── base.py           ← standard installer interface
│   │   ├── manager.py        ← installer registry & dispatch
│   │   ├── git.py
│   │   ├── node.py
│   │   ├── pip.py
│   │   ├── python.py
│   │   └── vscode.py
│   └── utils/
│       └── logger.py         ← all output routed through here
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

## Adding a Tool Installer

1. Create `devsetup/installers/<toolname>.py`
2. Subclass `BaseInstaller` and implement `detect()`, `install()`, `version()`
3. Register it in `devsetup/installers/manager.py`

All OS-specific logic must stay inside the installer module.

---

## Plugin System

Drop a Python module into `~/.devsetup/plugins/` to register custom tools.
See `plugins/README.md` for the plugin API.

Plugin failures are sandboxed and will never crash DevSetup.

---

## License

MIT — see [LICENSE](LICENSE).
