# Changelog

All notable changes to DevSetup are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] — 2026-03-11

First stable release.

### Added
- First stable public release of DevSetup
- Complete cross-platform install pipeline (Linux, macOS, Windows)
- `CHANGELOG.md` — this file
- `CONTRIBUTING.md` — contributor guide covering architecture, installers, environments, and testing

### Changed
- Installation summary now always displays all three sections (Installed, Skipped, Failed), showing `None` when a section is empty
- README restructured for v1.0 with Overview, Troubleshooting, and Configuration Format sections
- Version bumped to 1.0.0

---

## [0.9.0] — 2026-03-11

Pre-release stabilization.

### Added
- **Timestamped logging** — all log lines now include `[HH:MM:SS]` prefix
- **`fail()` and `debug()` log levels** — `debug()` gated behind `DEVSETUP_DEBUG=1`
- **`devsetup/system/environment_validator.py`** — dedicated validator module with `EnvironmentValidationError`, separated from environment loader
- **Duplicate environment ID detection** — `list_available()` skips duplicates with a warning
- **Functional test suite** — 41 tests across `test_cli.py`, `test_installers.py`, `test_config.py` using stdlib `unittest`

### Changed
- `environment_loader.py` now delegates all validation to `environment_validator.py`
- Error messages include actionable hints (`devsetup list`, `devsetup --help`)
- CLI help text restructured with Commands / Options / Examples sections

---

## [0.8.0] — 2026-03-11

Installation safety.

### Added
- **`devsetup/system/command_detector.py`** — `command_exists()` (PATH check) and `command_runs()` (PATH + exit code 0)
- **`--force` flag** — bypasses skip logic, reinstalls tools even if already present

### Changed
- All installers: `detect()` now uses `command_runs()` instead of `shutil.which`, catching corrupted installs
- `install_tool()` returns a result string (`"skipped"` / `"installed"` / `"failed"`)

---

## [0.7.0] — 2026-03-11

Package manager abstraction.

### Added
- **`devsetup/system/package_manager_detector.py`** — detects apt, dnf, pacman, brew, winget
- **`devsetup/system/package_managers/`** — five manager modules, each with `install()` and `update()`
- **`PackageManagerRunner`** — unified interface wrapping the active manager
- **`packages/*.json`** — per-tool package name mappings (git, node, python, pip, vscode)
- **`devsetup/utils/package_loader.py`** — loads package name from JSON for a given manager
- Public `is_registered()` API on `manager.py` — removes need for `environment_loader` to access private `_REGISTRY`

### Changed
- All five installers refactored to use `PackageManagerRunner` + `load_package_name()`
- Manager logs detected OS and package manager before each environment install

---

## [0.6.0] — 2026-03-11

OS detection.

### Added
- **`devsetup/system/os_detector.py`** — `get_os()`, `is_linux()`, `is_macos()`, `is_windows()`
- Canonical OS values: `linux`, `macos`, `windows` (`darwin` mapped to `macos`)

### Changed
- All five installers refactored to use `os_detector` instead of `platform.system()` directly

---

## [0.5.0] — 2026-03-11

Configuration-based environments.

### Added
- `id` and `description` fields in environment JSON schema
- `installers` key replaces `tools` key
- Validator confirms all referenced installer IDs exist in the registry

### Changed
- Environment JSON schema updated; `tools` → `installers`

---

## [0.4.0] — 2026-03-11

Installer modularization and logging.

### Added
- `check()`, `skip()`, `install()` log levels in `logger.py`
- `PipInstaller` (`installers/pip.py`)
- `environments/python.json`

---

## [0.3.0] — 2026-03-11

Python environment.

### Added
- `PipInstaller` and `environments/python.json`

---

## [0.2.0] — 2026-03-11

Environment discovery.

### Added
- `devsetup list` now shows environments instead of tools
- `environments/data-science.json`

---

## [0.1.0] — 2026-03-11

Numbered progress.

### Added
- `[1/3]`, `[2/3]`, `[3/3]` progress indicators during environment install

---

## [0.0.0] — 2026-03-11

Initial release.

### Added
- Full project structure
- CLI with `install`, `list`, `info`, `--help`, `--version`
- Installers: git, node, python, vscode
- Environment loader with JSON validation
- Centralised logger
