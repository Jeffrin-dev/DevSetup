# Changelog

All notable changes to DevSetup are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.9.0] — 2026-03-21

Stability Pass. 25/25 audit checks passing. 198 new tests added.

### Added

- **`BasePackageManager._run(cmd, allow_nonzero)`** (`system/package_managers/base.py`) —
  The five package manager modules (`apt_manager`, `dnf_manager`, `pacman_manager`,
  `brew_manager`, `winget_manager`) each previously contained an identical or
  near-identical `_run()` method (~15 lines of error-handling boilerplate each,
  ~75 lines total). That implementation now lives exclusively in
  `BasePackageManager._run()`. All five subclasses inherit it; none defines a
  local copy. The `allow_nonzero: Optional[Set[int]] = None` parameter supports
  `DnfManager.update()`, where `dnf check-update` exits 100 when updates are
  available — previously handled by a hand-rolled `check=False` comparison.
- **`_handle_install_error(tool_name, exc, exit_code, category)`** (`installers/manager.py`) —
  The five `except`-handler blocks in `install_tool()` each repeated the same
  three lines: assign `exit_code`, assign `category`, call `fail(...)`, return
  `InstallerResult.fail(...)`. This helper captures that repeated pattern once.
  All five blocks are now single-line calls, eliminating ~40 lines of duplication.
- **`_check_installer_ids(data, source)`** (`core/environment_loader.py`) —
  Installer-ID existence checking moved here from `system/environment_validator.py`
  (see Architecture Fixes). Called after `validate()` in both `load()` and
  `list_available()`.
- **`README.md`** — created at project root. Documents all flags introduced across
  v1.6–v1.9: `--yes`, `--verbose`, `--log-file`, `--debug`, `--summary`, `--env`.
  Includes CI/CD pipeline examples, expected output block, dependency ordering
  explanation, and full troubleshooting guide.
- **`tests/test_v1_9.py`** — 70 tests across 6 classes verifying every v1.9 change:
  `TestPhase1RunConsolidation`, `TestBaseRunBehaviour`, `TestDnfAllowNonzero`,
  `TestManagersRouteThoughRun`, `TestManagerCommands`, `TestPhase2CLIDocumentation`,
  `TestPhase3ErrorConsistency`, `TestPhase4ModularArchitecture`, `TestPhase5NoRegressions`.
- **`tests/test_noninteractive.py`** — 49 tests across 12 classes covering all
  `--yes` / `-y` scenarios: flag definition, no-blocking-input guarantee,
  `confirm()` all paths, skip/install behaviour unchanged, `yes_mode` threading,
  error handling, full pipeline, help text, scriptable exit codes, all 5 roadmap
  scenarios, log visibility, and `confirm()` centralisation.
- **`tests/test_logging.py`** — 79 tests across 11 classes covering the full logging
  system: `set_verbose`/`set_log_file` API, structured format verification,
  `--verbose` on install, no raw `print()` outside `logger.py`, error/warn stream
  routing, timestamp format (short vs full), per-tool log levels, verbose+yes
  combination, log file tee, help text, log level gating, and all 5 roadmap scenarios.

### Changed

- **`system/package_managers/apt_manager.py`** — local `_run()` removed; inherited
  from `BasePackageManager`.
- **`system/package_managers/dnf_manager.py`** — local `_run()` removed; `update()`
  calls `self._run([...], allow_nonzero={100})` for `dnf check-update` exit 100.
- **`system/package_managers/pacman_manager.py`** — local `_run()` removed.
- **`system/package_managers/brew_manager.py`** — local `_run()` removed.
- **`system/package_managers/winget_manager.py`** — local `_run()` removed;
  `update()` wraps `self._run()` in `try/except PackageManagerError: pass`,
  making the non-fatal upgrade intent explicit rather than implicit via `check=False`.
- **`cli/main.py`** — `--force` and `--debug` now have full description text in
  argparse (previously bare flag names with no description). `install` subcommand
  epilog and top-level epilog both gain an `Examples:` section with concrete
  commands including a CI/CD non-interactive example.
- **Error messages from `_run()`** — all `PackageManagerError` messages now include
  `self.manager_name` (e.g. `"apt command failed"`, `"brew command failed"`).
  Previously some managers hardcoded partial or inconsistent strings.
- **`packages/git.json`**, **`node.json`**, **`python.json`**, **`pip.json`**,
  **`vscode.json`** — `"schema": "1.0"` added as the first key to all five files
  (Rule 10 compliance; `package_loader.py` is unaffected).
- **`__version__`** bumped to `1.9.0`.

### Architecture Fixes

Three violations found and patched during the v1.9 code review:

- **Rule 6 + circular dependency** (`system/environment_validator.py`):
  `_check_installer_ids()` was calling
  `from devsetup.installers.manager import is_registered` via a deferred import.
  The `system/` layer is a foundation layer that `installers/manager.py` already
  imports from (`get_os`, `get_package_manager`, `PackageManagerError`).
  Having `system/` reach back up into `installers/` created a circular dependency.
  The check now lives in `core/environment_loader.py`, which legitimately sits
  above both layers. `environment_validator.py` now contains zero imports from
  `installers/`.

- **Rule 1 + Rule 7** (`devsetup/__main__.py`):
  `__main__.py` called `load_plugins(_REGISTRY)` before invoking `main()`, while
  `main()` itself also called `load_plugins()`. Every `python -m devsetup`
  invocation loaded every plugin twice. `__main__.py` now delegates entirely to
  `main()`, which remains the single owner of plugin loading.

- **Rule 10** (`packages/*.json`):
  All five package name-mapping files lacked `"schema": "1.0"`. Rule 10 requires
  every JSON configuration file to carry a schema version field.

---

## [1.8.0] — 2026-03-14

Logging Improvements.
434/434 tests green. All 15 roadmap phases implemented.

### Added
- **`verbose()`** log function → `[VERBOSE]` level, gated on `DEVSETUP_VERBOSE=1`.
  Used for dependency resolution steps, version detection, and internal decisions.
- **`_is_verbose()`** — reads `_verbose_override` first, then `DEVSETUP_VERBOSE` env var.
- **`_timestamp_full()`** — returns `YYYY-MM-DD HH:MM:SS`. Used exclusively by
  `verbose()` so `[VERBOSE]` lines carry full date+time context for CI/CD traceability.
- **`set_verbose(flag)`** / **`set_log_file(path)`** — programmatic configuration API
  called by the CLI layer after arg parsing. One call configures all downstream output.
- **`_emit(message, file)`** — centralized output function. All log functions call
  `_emit` instead of `print` directly. Handles tee-to-file logic once for all levels.
- **`--verbose`** flag on `install` command. Calls `set_verbose(True)` before
  anything runs. Shows `[VERBOSE]` dep resolution and version detection lines.
- **`--log-file <path>`** flag on `install` command. Tees all output to a file
  in addition to the console. Safe — bad paths never crash the install pipeline.
- **`[VERBOSE]` lines in `manager.py`** for version detection
  (`"Version detected: git 2.43.0"`) and dependency resolution
  (`"DependencyResolver: node depends on git"`).
- **`tests/test_logging.py`** — 61 tests across 11 classes covering all 14 roadmap phases.

### Changed
- `_timestamp()` always returns `HH:MM:SS` — deterministic, never changes format
  based on state (architecture review fix for Rule 9).
- `utils/__init__.py` exports `verbose`, `set_verbose`, `set_log_file`.
- `__version__` bumped to `1.8.0`.

### Architecture review fix (Rule 9)
- `_timestamp()` previously returned either `HH:MM:SS` or `YYYY-MM-DD HH:MM:SS`
  depending on `_is_verbose()`. The same `info("msg")` call could produce different
  output formats depending on mutable state — a Rule 9 (deterministic output) violation.
  Fixed: `_timestamp()` always returns `HH:MM:SS`. `_timestamp_full()` is used
  only by `verbose()`, keeping the full timestamp exclusively on `[VERBOSE]` lines.

---

## [1.7.0] — 2026-03-14

Non-Interactive Mode.
373/373 tests green. All 13 roadmap phases implemented.

### Added
- **`devsetup/utils/prompt.py`** — new centralised confirmation utility.
  `confirm(message, auto_yes)` is the single entry point for all confirmations.
  `auto_yes=True`: emits `[AUTO]` via logger, returns True without touching stdin.
  `auto_yes=False`: logs the question, reads stdin; `EOFError`/`KeyboardInterrupt`
  return False so piped scripts without `--yes` never hang silently.
- **`[AUTO]` log level** in `logger.py` → stdout. Emitted once per install when
  `yes_mode=True`, providing an audit trail in CI/CD logs.
- **`--yes` / `-y` flag** on `install` command. Passes `yes_mode=True` to
  `install_environment()`.
- **`tests/test_noninteractive.py`** — 48 tests across 12 classes covering all
  13 roadmap phases.

### Changed
- `install_environment()` gains `yes_mode: bool = False` parameter. When True:
  emits one `[AUTO]` line and proceeds without any stdin interaction.
  Default `False` preserves all existing behaviour exactly.
- `utils/__init__.py` exports `auto`.
- `__version__` bumped to `1.7.0`.

### Architecture review fix (Rule 9)
- Removed `confirm()` call from inside `install_environment()`. The installer
  engine must not call CLI/UI utilities. The engine logs `[AUTO]` directly;
  `confirm()` is reserved for future interactive prompts in the CLI layer.
  This also eliminated a duplicate second `[AUTO]` line that was being emitted.
- Removed unused `import sys` from `prompt.py`.

---

## [1.6.0] — 2026-03-14

Environment Info Command.
325/325 tests green. All 14 roadmap phases implemented.

### Added
- **`devsetup/cli/env_info.py`** — new dedicated output formatter module.
  `print_env_info(env, verbose)`, `print_env_summary(env)`,
  `_get_dependencies(tool_id)` using the public `tool_dependencies()` API.
  Zero installation logic, zero OS logic, zero file I/O.
- **`info <environment>` routing** — `devsetup info web` shows full environment
  details (ID, name, description, ordered tools list).
- **`--env` flag** — forces environment lookup on the `info` command, resolving
  the ambiguity where a name is both a registered tool and an environment ID
  (e.g. `devsetup info python --env`).
- **`--summary` flag** — compact one-line output: `Tools in 'web': git, node, vscode`
- **`--verbose` flag** on `info` command — shows per-tool dependency info:
  `- node  (depends on: git)`
- **`tool_dependencies(tool_name)`** — new public read-only function in
  `manager.py`. Returns declared deps without instantiating or running the installer.
  Exported from `installers/__init__.py`.
- **`tests/test_env_info.py`** — 69 tests across 12 test classes covering all
  14 roadmap phases.

### Changed
- `info` command parser: positional argument renamed `tool` → `target`;
  `--env`, `--summary`, `--verbose` flags added.
- Dispatch logic in `cmd_info`: registered tool → existing tool info (backward
  compatible); unregistered name or `--env` set → env info.
- `installers/__init__.py` exports `tool_dependencies`.
- `__version__` bumped to `1.6.0`.

### Architecture review fix (Rule 1)
- `_get_dependencies()` in `env_info.py` was importing and reading `_REGISTRY`
  directly — a private dict inside `manager.py`. Fixed to call the public
  `tool_dependencies()` API, keeping the CLI layer decoupled from installer internals.

### Exit codes
  0 → success, 1 → not found or config invalid, 2 → unexpected error

### Backward compatibility
  `devsetup info git`            → tool info (unchanged)
  `devsetup info web`            → environment info (new)
  `devsetup info python`         → tool info (unchanged, backward compat)
  `devsetup info python --env`   → environment info (new)

---

## [1.5.0] — 2026-03-14

Environment Configuration Validation.
256/256 tests green. All 15 roadmap phases implemented.

### Added
- **`_check_id_format()`** — environment IDs must be lowercase, start with a
  letter, and contain only letters, digits, and hyphens.
  Valid: `web`, `data-science`, `python3`. Invalid: `Web Dev`, `web_env`.
- **`_check_duplicate_tools()`** — duplicate tool IDs within a single environment
  config now raise `EnvironmentValidationError`.
- **`_check_field_types()`** — `id` and `name` must be non-empty strings;
  `description`, if present, must be a string.
- **`_check_tool_entry_types()`** — non-string entries in the tools list
  (integers, booleans, lists, dicts, None) raise `EnvironmentValidationError`
  with the offending index and type, never a bare `TypeError`.
- **`get_tools_list()`** — public helper accepting both `tools` (v1.5 format)
  and `installers` (v1.0 backward-compatible format).
- **`validate_structure()`** — root JSON type check moved from loader into
  validator (Architecture Rule 6 compliance).
- **`logger.valid()`** / **`logger.invalid()`** — new `[VALID]` and `[INVALID]`
  log levels emitted per environment during `list_available()`.
- **`tests/test_validation.py`** — 84 new tests covering all validation rules.

### Changed
- **`schema` field is now optional** — v1.5 environment configs do not require
  a `schema` key. If present, it must be `"1.0"`.
- **`tools` field alias** — `tools` accepted alongside `installers`; `_normalize()`
  in loader aliases to `installers` so all downstream code is unchanged.
- **`list_available()`** now logs `[VALID] ✓` or `[INVALID] ✗` per config and
  guards against non-dict JSON roots.
- All error messages include the environment id and source filename.
- `__version__` bumped to `1.5.0`.

### Architecture review fixes
- **Rule 6**: `validate_structure()` root-type check moved from `environment_loader`
  inline check into `environment_validator` — all validation logic lives in one place.
- **Rule 7**: `_GuardedRegistry._CORE_IDS` hardcoded list replaced with
  `_initial_ids = frozenset(real_registry.keys())` dynamic snapshot — protection
  automatically covers every registered tool without manual maintenance.

---

## [1.4.1] — 2026-03-14

Post-review patches.
152/152 tests green.

### Fixed
- Multi-failure summary loss (`result.py` — `_failed_ids` list replaces single
  `failed_result` field; all failures retained in execution order).
- `failed_results` property returns all FAIL results in order (v1.4.1).
- `DependencyError` caught explicitly in CLI before broad `except` handler.
- `_topological_sort` rewired to `heapq` — O((n+e)logn), eliminates the previous
  O(n² logn) list.pop(0) + list.sort() approach.
- Double graph build eliminated — `resolve_with_graph()` returns `(ordered, graph)`
  in a single call; manager no longer calls `build_graph()` separately.
- `dependencies: List[str]` type annotations added to all 5 installer classes.

---

## [1.4.0] — 2026-03-13

Dependency Ordering.
129/129 tests green.

### Added
- **`devsetup/installers/dependency_resolver.py`** — full dependency resolution engine:
  - `DependencyError` — raised on cycle, missing registry reference, missing tool reference.
  - `build_graph()` — O(n+e) adjacency map construction.
  - `resolve()` / `resolve_with_graph()` — single public entry points.
  - `_topological_sort()` — Kahn's algorithm with min-heap for deterministic ordering.
  - `_find_cycle()` — DFS coloring for cycle path reporting.
  - `get_blocked()` — returns the first failing dependency of a tool, or None.
- **`InstallerStatus.BLOCKED`** — tool not run because a dependency failed.
- **`ExitCode.DEPENDENCY_BLOCKED = 6`**.
- **`InstallerResult.block()`** — named constructor for blocked results.
- **`InstallSummary.blocked`** / **`has_blocked`** — blocked tools bucket.
- **`logger.blocked()`** / **`logger.dep_order()`** — new log levels.
- **`tests/test_dependency.py`** — 52 tests.

### Changed
- `install_environment()` now runs full dependency resolution before executing
  any installers. Tools whose dependency failed are marked BLOCKED and skipped;
  independent tools continue running. RuntimeError raised at end if any failures.
- Declared dependencies: `node → git`, `pip → python`.
- `BaseInstaller.dependencies: List[str] = []` class attribute added.

---

## [1.3.2] — 2026-03-12

Six design issue fixes.

### Fixed
- **Issue 2**: `version()` in all 5 installers used `detect()` as a presence guard,
  causing `--version` to run the version subprocess twice. Fixed to use
  `command_exists()` (shutil.which only, no subprocess).
- **Issue 5**: `InstallSummary` refactored to single source of truth (`result_map`).
  `installed` and `skipped` computed as properties from `_records`.
- `list_tools()` / `tool_info()` use `_get_version()` safety wrapper.
- `UnsupportedOSError` caught explicitly in `install_tool()` — replaces fragile
  string matching on RuntimeError messages.

---

## [1.3.0] — 2026-03-12

Tool Version Verification.
40 new tests added.

### Added
- **`devsetup/utils/version_parser.py`** — `parse_version(raw_output)` extracts
  clean version strings from raw command output. Strips leading `v`, reads first
  line only, returns `"unknown"` on no match.
- **`_get_version(installer, tool_name)`** — safety wrapper in manager. Any
  exception, timeout, or non-version string returns None.
- **`InstallerResult.version`** field — carries the verified installed version.
- **`ExitCode.VERIFICATION_FAILURE = 5`** / **`ErrorCategory.VERIFICATION_FAILURE`**.
- **`InstallerResult.block()`** wait — post-install verification: if `version()`
  returns nothing after install, status is FAIL with VERIFICATION_FAILURE.
- **`[VERSION]`** log level — emitted after every install or skip.
- **`tests/test_version.py`** — version parser, skip path reporting, post-install
  verification, summary version display, `_get_version` safety.

### Changed
- `install_tool()` — after successful install, calls `_get_version()`; if None
  returned, result is FAIL (VERIFICATION_FAILURE) not SUCCESS.
- Skip path — calls `_get_version()` and carries version in SKIP result.
- Summary — displays version next to each tool: `git (2.43.0)`.

---

## [1.2.0] — 2026-03-12

Install Summary Overhaul.

### Added
- `InstallSummary` — accumulates installer results and produces the final report.
- `InstallerResult` — structured result object with named constructors:
  `success()`, `skip()`, `fail()`.
- `InstallerStatus` enum: SUCCESS, SKIP, FAIL.
- `ExitCode` constants: SUCCESS=0, INSTALLATION_FAILURE=1, DETECTION_ERROR=2,
  UNSUPPORTED_OS=3, PACKAGE_MANAGER_FAILURE=4.
- `ErrorCategory` constants: INSTALLER_FAILURE, PACKAGE_MANAGER_ERROR,
  OS_NOT_SUPPORTED, COMMAND_NOT_FOUND, CONFIG_ERROR.
- `_print_summary()` — prints Installed / Skipped / Failed sections after
  every environment install.
- Duplicate-entry guard in `InstallSummary.record()` — same tool recorded twice
  is silently ignored.
- Execution-order preservation — installed list reflects the order tools ran.
- Summary shows environment name above the report.
- Count prefix on non-empty sections: `Installed (2):`, `Skipped (1):`.
- `tests/test_summary.py` — integration tests for all 14 Phase 13 scenarios.

---

## [1.1.0] — 2026-03-11

Failure Simulation & Error Classification.

### Added
- `UnsupportedOSError(RuntimeError)` — raised by `get_os()` when platform is
  not supported. Allows precise catch without string matching.
- `PackageManagerError(RuntimeError)` — raised by all PM wrappers on non-zero
  exit code, binary-not-found, or permission error. Carries `pm_exit_code`.
- `install_tool()` — distinct except clauses for PackageManagerError,
  FileNotFoundError, UnsupportedOSError, RuntimeError, generic Exception.
  Each maps to the correct ExitCode and ErrorCategory.
- `detect()` exception handling — OSError during detection returns
  FAIL with DETECTION_ERROR exit code.
- Pipeline stops immediately on first FAIL; subsequent tools are not run.
- RuntimeError raised from `install_environment()` includes exit_code and category.
- `tests/test_installers.py` — 9 failure simulation tests.

---

## [1.0.0] — 2026-03-11

First stable public release.

### Added
- `devsetup install <env>` — installs all tools for an environment.
- `devsetup install --tool <name>` — installs a single tool.
- `devsetup list` — lists all available environments.
- `devsetup info <tool>` — shows tool installation status and version.
- `devsetup --version` — prints version string.
- `devsetup --force` — reinstalls tools even if already present.
- Environment JSON configs: `web`, `python`, `data-science`.
- Package name mappings for apt, dnf, pacman, brew, winget.
- Five installer modules: git, node, pip, python, vscode.
- `BaseInstaller` abstract base class: `detect()`, `install()`, `version()`.
- `PackageManagerRunner` — unified install interface over all 5 PM wrappers.
- `command_exists()` / `command_runs()` — PATH and execution detection.
- `environment_loader.load()` / `list_available()` — reads and validates JSON configs.
- `EnvironmentValidationError` — raised on bad schema, missing fields, unknown tools.
- Plugin system: `~/.devsetup/plugins/` loaded at startup; failures sandboxed.
- `_GuardedRegistry` — prevents plugins overwriting core installers.
- All output routed through `devsetup/utils/logger.py` — no raw `print()`.

---

## [0.0.0] — 2026-03-11

Initial development release.
