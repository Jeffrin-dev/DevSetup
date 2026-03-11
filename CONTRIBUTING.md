# Contributing to DevSetup

This document describes how DevSetup is structured, how to extend it, and the
standards expected for all contributions.

---

## Project Architecture

DevSetup enforces a strict layered architecture. Each layer has exactly one
responsibility. Mixing responsibilities across layers is a violation.

```
CLI  (devsetup/cli/main.py)
 │   Parse arguments. Call internal modules. No business logic.
 ▼
Environment Loader  (devsetup/core/environment_loader.py)
 │   Read JSON configs from environments/. Return environment objects.
 ▼
Environment Validator  (devsetup/system/environment_validator.py)
 │   Validate required fields. Reject unknown installers. Detect duplicates.
 ▼
Installer Registry / Engine  (devsetup/installers/manager.py)
 │   Resolve tool names. Run detect/install/skip logic. Print summary.
 ▼
OS Detector  (devsetup/system/os_detector.py)
 │   Return canonical OS name: linux | macos | windows.
 ▼
Package Manager Detector  (devsetup/system/package_manager_detector.py)
 │   Return active package manager: apt | dnf | pacman | brew | winget.
 ▼
Command Detector  (devsetup/system/command_detector.py)
 │   command_exists(): PATH check. command_runs(): PATH + exit code 0.
 ▼
Installer Modules  (devsetup/installers/git.py, node.py, ...)
 │   Implement detect() / install() / version() per tool.
 ▼
Package Manager Interface  (devsetup/system/package_managers/)
     Five manager modules. PackageManagerRunner unifies them.
```

### 10 Architecture Rules

1. **CLI contains no business logic** — only argument parsing and module calls.
2. **Every tool has its own isolated installer** — one file per tool.
3. **Environments are configuration-driven** — JSON files only, no hardcoded lists.
4. **All installers implement a standard interface** — `detect()`, `install()`, `version()`.
5. **OS-specific logic stays inside installers** — never in CLI or loader.
6. **Environment loader is separate** — delegates validation to `environment_validator`.
7. **Plugin system is sandboxed** — plugins cannot modify core modules.
8. **CLI commands remain minimal** — `install`, `list`, `info` only.
9. **All output is deterministic** — routed through `devsetup/utils/logger.py`.
10. **Configuration schema is versioned** — every JSON file carries `"schema": "1.0"`.

---

## How to Add a New Tool Installer

### Step 1 — Create the installer module

Create `devsetup/installers/<toolname>.py`:

```python
"""
devsetup.installers.<toolname>
------------------------------
Isolated installer module for <ToolName>.
"""

from devsetup.installers.base import BaseInstaller
from devsetup.system.command_detector import command_runs
from devsetup.system.package_managers import PackageManagerRunner
from devsetup.utils.package_loader import load_package_name
import subprocess


class <ToolName>Installer(BaseInstaller):
    tool_name = "<toolname>"

    def detect(self) -> bool:
        return command_runs("<toolname>")

    def install(self) -> None:
        pm = PackageManagerRunner()
        package = load_package_name("<toolname>", pm.name)
        pm.install(package)

    def version(self) -> str:
        if not self.detect():
            return "not installed"
        result = subprocess.run(
            ["<toolname>", "--version"], capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
```

### Step 2 — Create the package name mapping

Create `packages/<toolname>.json`:

```json
{
  "apt":    "<apt-package-name>",
  "dnf":    "<dnf-package-name>",
  "pacman": "<pacman-package-name>",
  "brew":   "<brew-formula>",
  "winget": "<WingetID>"
}
```

Use `null` for any package manager that does not support the tool.

### Step 3 — Register the installer

Add one line to `devsetup/installers/manager.py`:

```python
from devsetup.installers.<toolname> import <ToolName>Installer

_REGISTRY: Dict[str, Type[BaseInstaller]] = {
    ...
    "<toolname>": <ToolName>Installer,
}
```

That is the complete change required. No other files need modification.

---

## How to Add a New Environment

No Python code changes are required.

Create `environments/<id>.json`:

```json
{
  "schema": "1.0",
  "id": "<id>",
  "name": "<Human Readable Name>",
  "description": "Optional description.",
  "installers": ["git", "node", "vscode"]
}
```

Rules:

- `id` must be unique across all environment files.
- Every entry in `installers` must be a registered tool name.
- `schema` must be `"1.0"`.

Run `devsetup list` to confirm the environment appears.

---

## Coding Style

- **Python 3.9+** — no syntax from later versions in core code.
- **Type hints** — all public functions must have type annotations.
- **Docstrings** — every module and every public function needs a docstring.
- **No raw `print()` calls** — all output must go through `devsetup/utils/logger.py`.
- **No OS branching outside installers** — `platform.system()` and direct OS checks
  are forbidden outside `devsetup/system/` and `devsetup/installers/`.
- **Installer modules are self-contained** — no cross-installer imports.
- **`check=True` on all subprocess calls** — let exceptions propagate; the install
  engine catches and reports them.

---

## Testing Procedure

Tests use Python's built-in `unittest` library — no external dependencies required.

### Run all tests

```bash
python3 -m unittest discover -s tests -p "test_*.py" -v
```

### Test structure

```
tests/
├── test_cli.py        — CLI argument parsing, exit codes, error messages
├── test_installers.py — BaseInstaller interface, registry, skip/install/force/fail logic
└── test_config.py     — environment loading, validation, duplicate detection, bad JSON
```

### Expectations for new contributions

- New installers must have at least: detect returns bool, version returns string,
  install does not crash when mocked.
- New environments must have: valid JSON, all installer IDs registered, schema 1.0.
- All 41 existing tests must continue to pass after your change.

### Writing a test

```python
import unittest
from unittest.mock import patch

class TestMyInstaller(unittest.TestCase):

    def test_detect_returns_bool(self):
        from devsetup.installers.mytool import MyToolInstaller
        result = MyToolInstaller().detect()
        self.assertIsInstance(result, bool)

    def test_install_called_when_not_detected(self):
        from devsetup.installers.manager import install_tool
        with patch("devsetup.installers.mytool.MyToolInstaller.detect", return_value=False), \
             patch("devsetup.installers.mytool.MyToolInstaller.install") as mock_install:
            mock_install.return_value = None
            result = install_tool("mytool")
            self.assertEqual(result, "installed")
            mock_install.assert_called_once()
```

---

## Plugin System

Custom tools and environments can be registered without modifying core files.
Drop a Python module into `~/.devsetup/plugins/`. See `plugins/README.md` for
the plugin API.

Plugin rules:
- Plugins cannot modify core DevSetup modules.
- Plugins can only register new tools or environments.
- Plugin failures must not crash DevSetup.

---

## Commit Messages

Use the conventional format:

```
feat: add docker installer
fix: vscode detect() returns false on corrupted install
docs: add troubleshooting section to README
test: add force-reinstall test for node installer
refactor: extract package name resolution into package_loader
```

---

## Release Process

Versions follow `MAJOR.MINOR.PATCH`:

- `PATCH` — bug fixes, no API changes
- `MINOR` — new environments or new tool installers
- `MAJOR` — breaking changes to CLI interface or architecture

Update `devsetup/__version__.py` and add a section to `CHANGELOG.md` before tagging.
