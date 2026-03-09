# DevSetup

> Automated developer environment setup — one command to install everything.

DevSetup reads a simple JSON configuration file and installs all the tools
your team needs, on any operating system, with a single command.

---

## Quick Start

```bash
# Install the web development environment
devsetup install web

# Install a single tool
devsetup install --tool git

# List all tools and their versions
devsetup list

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

## Project Structure

```
DevSetup/
├── devsetup/
│   ├── __version__.py        ← single version source of truth
│   ├── __main__.py           ← python -m devsetup entry point
│   ├── cli/
│   │   └── main.py           ← argument parsing only, no business logic
│   ├── core/
│   │   └── environment_loader.py  ← reads & validates JSON configs
│   ├── installers/
│   │   ├── base.py           ← standard installer interface
│   │   ├── manager.py        ← registry & dispatch
│   │   ├── git.py
│   │   ├── node.py
│   │   ├── python.py
│   │   └── vscode.py
│   └── utils/
│       └── logger.py         ← all output routed through here
├── environments/
│   ├── web.json
│   └── data-science.json
├── plugins/                  ← user plugins loaded from ~/.devsetup/plugins/
├── pyproject.toml
├── LICENSE
└── README.md
```

---

## CLI Commands

| Command                       | Description                              |
|-------------------------------|------------------------------------------|
| `devsetup install <env>`      | Install all tools for an environment     |
| `devsetup install --tool <t>` | Install a single named tool              |
| `devsetup list`               | List all tools and installed versions    |
| `devsetup info <tool>`        | Show details for a specific tool         |
| `devsetup --version`          | Print the DevSetup version               |
| `devsetup --help`             | Show usage guide                         |

---

## Environment Configuration

Environments are defined as versioned JSON files in `environments/`.

```json
{
  "schema": "1.0",
  "name": "web",
  "tools": ["git", "node", "vscode"]
}
```

To add a new environment, create a new `.json` file — no source code changes needed.

---

## Adding a Tool Installer

1. Create `devsetup/installers/<toolname>.py`
2. Subclass `BaseInstaller` and implement `detect()`, `install()`, `version()`
3. Register it in `devsetup/installers/manager.py`

All OS-specific logic must stay inside the installer module.

---

## Plugin System

Drop a Python module into `~/.devsetup/plugins/` to register custom tools or
environments. See `plugins/README.md` for the plugin API.

Plugin failures are sandboxed and will never crash DevSetup.

---

## Architecture Rules

This project enforces 10 architecture rules documented in `ARCHITECTURE.md`
(or the project wiki). Key principles:

- CLI contains **no business logic**
- Every tool has its **own isolated installer**
- Environments are **configuration-driven** (JSON only)
- All installers implement a **standard interface**
- OS-specific logic is **contained inside installers**

---

## License

MIT — see [LICENSE](LICENSE).
