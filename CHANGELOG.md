# Changelog

All notable changes to DevSetup are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.4.1] — 2026-03-14

Post-review patches. All 25/25 architecture and 25/25 dependency ordering audit
questions pass. 129/129 tests green.

### Fixed
- **CRITICAL** `result.py` — multi-failure summary loss: replaced single
  `failed_result` stored field with `_failed_ids: List[str]`. All failures are
  now retained. `failed_result` property returns the first (backward-compatible);
  new `failed_results` property returns all failures in execution order.
- **CRITICAL** `manager.py` — `_print_summary` and RuntimeError message now
  iterate `summary.failed_results` so every failure is reported, not just the last.
- **SIGNIFICANT** `cli/main.py` — `DependencyError` now caught explicitly before
  the broad `except Exception` handler, so cycle/config errors produce a clean
  `[ERROR]` line.
- **SIGNIFICANT** `dependency_resolver.py` — module docstring corrected:
  `get_blocked` return type was `-> bool`; actual is `-> Optional[str]`.
- **SIGNIFICANT** `dependency_resolver.py` — `_topological_sort` rewired from
  `list.pop(0) + list.sort()` (O(n²logn)) to `heapq` push/pop (O((n+e)logn)).
- **SIGNIFICANT** `dependency_resolver.py` — eliminated double graph build;
  `resolve_with_graph()` added, builds graph once and returns `(ordered, graph)`.
  `_build_graph` promoted to public `build_graph`. No-op wrapper removed.
- **SIGNIFICANT** `manager.py` — `import re` removed from inside `_print_summary`;
  uses module-level `_re` alias throughout.
- **MINOR** `logger.py` — `[BLOCKED]` and `[DEPS]` added to module docstring.
- **MINOR** `git.py`, `node.py`, `pip.py`, `python.py`, `vscode.py` — all five
  `dependencies` declarations now use `List[str]` type annotation consistently.
- **MINOR** `node.py` — comment corrected from factually wrong
  "git must be present for npm source operations" to
  "git is a common prerequisite for Node.js workflows (cloning, npm scripts)".

---

## [1.4.0] — 2026-03-13

Dependency ordering.

### Added
- **`devsetup/installers/dependency_resolver.py`** — full dependency resolution
  engine: `DependencyError`, `build_graph`, `resolve`, `resolve_with_graph`,
  `get_blocked`, `_validate`, `_topological_sort` (Kahn's + min-heap),
  `_find_cycle` (DFS coloring).
- **`BaseInstaller.dependencies`** — `List[str]` class attribute (default `[]`).
  All five installers declare their dependencies explicitly.
- **`InstallerStatus.BLOCKED`** — new outcome for tools whose dependency failed.
- **`ExitCode.DEPENDENCY_BLOCKED = 6`** and `ErrorCategory.DEPENDENCY_BLOCKED`.
- **`InstallerResult.block()`** — named constructor for BLOCKED results.
- **`InstallSummary.blocked`** — insertion-ordered list of blocked tool IDs.
- **`InstallSummary.has_blocked`** — True when any tools were blocked.
- **`logger.blocked()`** / **`logger.dep_order()`** — new `[BLOCKED]` and
  `[DEPS]` log levels.
- **`tests/test_dependency.py`** — 52 new tests covering all resolver behaviour.

### Changed
- `install_environment()` now runs a full dependency resolution pipeline before
  executing any installers; pipeline no longer stops on first failure — dependent
  tools are BLOCKED while independent tools continue.
- `_print_summary()` extended with a Blocked section.
- `tool_info()` returns a `dependencies` field.
- `__version__` bumped to 1.4.0.

### Declared dependencies
- `git`: none  
- `node`: `["git"]`  
- `python`: none  
- `pip`: `["python"]`  
- `vscode`: none

---

## [1.3.2] — 2026-03-12

Six design issue fixes.

### Fixed
- `InstallSummary` refactored to single source of truth (`result_map`).
- `_verify_version()` no-op wrapper removed from `manager.py`.
- `list_tools()` / `tool_info()` use `_get_version()` safety wrapper.
- Sentinel blacklist replaced with digit-presence check.
- `UnsupportedOSError` introduced; replaces fragile RuntimeError string matching.
- `test_installers.py` updated to reflect all fixes.

---

## [1.3.1] — 2026-03-12

OS error classification.

### Fixed
- Replaced fragile `RuntimeError` string matching with `UnsupportedOSError`.

---

## [1.3.0] — 2026-03-12

Tool version verification.

### Added
- Post-install version verification via `_get_version()`.
- `InstallerResult.version` field.
- `ExitCode.VERIFICATION_FAILURE = 5`, `ErrorCategory.VERIFICATION_FAILURE`.
- `[VERSION]` log level.
- `devsetup/utils/version_parser.py` — normalises raw version strings.
- `tests/test_version.py` — 40 tests.

---

## [1.2.0] — 2026-03-12

Install summary overhaul.

### Added
- `InstallSummary` accumulator with `installed`, `skipped`, `failed_result`
  buckets; `env_name` header; count prefixes.
- `_print_summary()` with Fixed section order and `none` placeholders.
- `tests/test_summary.py` — Phase 13 integration scenarios.

---

## [1.1.0] — 2026-03-11

Pre-stable improvements.

---

## [1.0.0] — 2026-03-11

First stable public release.

### Added
- Complete cross-platform install pipeline (Linux, macOS, Windows).
- `CHANGELOG.md`, `CONTRIBUTING.md`.

---

## [0.0.0] — 2026-03-11

Initial release.
