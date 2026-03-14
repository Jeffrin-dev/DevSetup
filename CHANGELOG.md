# Changelog

All notable changes to DevSetup are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.5.0] — 2026-03-14

Environment Configuration Validation.
236/236 tests green. All 15 roadmap phases implemented.

### Added
- **`_check_id_format()`** (Phase 7) — environment IDs must be lowercase,
  start with a letter, and contain only letters, digits, and hyphens.
  Valid: `web`, `data-science`, `python3`. Invalid: `Web Dev`, `web_env`.
- **`_check_duplicate_tools()`** (Phase 6) — duplicate tool IDs within a
  single environment config now raise `EnvironmentValidationError`.
- **`_check_field_types()`** (Phase 3) — `id` and `name` must be non-empty
  strings; `description`, if present, must be a string.
- **`get_tools_list()`** (Phase 1) — public helper accepting both `tools`
  (v1.5 format) and `installers` (v1.0 backward-compatible format).
- **`logger.valid()`** / **`logger.invalid()`** (Phase 13) — new `[VALID]`
  and `[INVALID]` log levels emitted per environment during `list_available()`.
- **`tests/test_validation.py`** (Phase 15) — 84 new tests covering all
  validation rules: required fields, field types, tools list, installer
  references, duplicate tools, ID format, duplicate environments, JSON
  structure, error message quality, and validation logging.

### Changed
- **`schema` field is now optional** (Phase 2) — v1.5 environment configs
  do not require a `schema` key. If present, it must be `"1.0"`.
- **`environment_loader.py`** — `_normalize()` added: after validation,
  the `tools` key is aliased to `installers` so all downstream code
  (`cli/main.py`, `manager.py`) continues to use `env["installers"]`
  unchanged.
- **`environment_loader.py`** — `list_available()` now logs `[VALID] ✓`
  or `[INVALID] ✗` per config (Phase 13) and guards against non-dict
  JSON roots.
- **`environment_validator.py`** — all error messages now include the
  environment id and source filename (Phase 12).
- **`tests/test_config.py`** — `test_missing_schema_raises` removed;
  replaced with `test_schema_is_optional`. New tests for duplicate tools,
  ID format rules, field type checks, and `tools`/`installers` alias.
- **`utils/__init__.py`** — `valid` and `invalid` exported.
- **`__version__`** bumped to `1.5.0`.

---

## [1.4.1] — 2026-03-14

Post-review patches. 25/25 dependency ordering audit. 152/152 tests.

### Fixed
- Multi-failure summary loss (`result.py` — `_failed_ids` list).
- All failures printed in summary and RuntimeError message.
- `DependencyError` caught explicitly in CLI before broad handler.
- `get_blocked` docstring return type corrected.
- `_topological_sort` rewired to `heapq` (O((n+e)logn)).
- Double graph build eliminated (`resolve_with_graph`).
- `import re` removed from inside `_print_summary`.
- `dependencies: List[str]` annotations on all 5 installers.
- `node.py` dependency comment corrected.

---

## [1.4.0] — 2026-03-13

Dependency ordering. 129/129 tests.

### Added
- `dependency_resolver.py` — DependencyError, build_graph, resolve,
  get_blocked, topological sort (Kahn's + min-heap), cycle detection (DFS).
- `BaseInstaller.dependencies: List[str]`.
- `InstallerStatus.BLOCKED`, `ExitCode.DEPENDENCY_BLOCKED`.
- `InstallerResult.block()` named constructor.
- `InstallSummary.blocked`, `has_blocked` properties.
- `logger.blocked()`, `logger.dep_order()`.
- `tests/test_dependency.py` — 52 tests.

---

## [1.3.2] — 2026-03-12

Six design issue fixes.

---

## [1.3.0] — 2026-03-12

Tool version verification. 40 tests added.

---

## [1.2.0] — 2026-03-12

Install summary overhaul.

---

## [1.0.0] — 2026-03-11

First stable public release.

---

## [0.0.0] — 2026-03-11

Initial release.
