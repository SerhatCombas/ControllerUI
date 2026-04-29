# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Authoritative Documents

This repository ships an explicit execution contract for AI agents. Read these before substantive changes — they outrank both the README and existing code:

1. `specs/08_codex_execution_rules.md` — execution contract (authority order, forbidden actions, stop conditions, schema-change protocol). **Read this first.**
2. `specs/06_data_flow_and_architecture.md` — module ownership and artifact flow.
3. `specs/07_implementation_order.md` — staged build plan (S0–S7) with acceptance gates.
4. `specs/09_coding_standards.md`, `specs/10_logging_conventions.md`, `specs/11_error_code_catalog.md` — style, logging, error codes.
5. `decisions/ADR-001..017` — architecture decisions (immutable once accepted; supersede rather than edit).

Per `08 §3.1`, the conflict-resolution authority order is: explicit user instruction → `08` → `07` → `06` → `04`/`05`/`03`/`02`/`01` → `README.md` → existing code. Existing code is the **lowest** authority — do not assume it reflects the target architecture.

## Plugin & External Skill Policy

### Authority Hierarchy

Any loaded Claude Code plugin or third-party skill holds LOWER authority than `README.md` and this `CLAUDE.md` file within the conflict-resolution chain (`08 §3.1`). Plugins sit above existing code (which remains the lowest authority) but below all repository documentation, specs, ADRs, and conventions.

### Core Rules

1. **Conflict Resolution:** If a plugin's instructions conflict with this repository's specs, ADRs, or the execution contract, the plugin MUST be ignored for that specific task. Do not reorganize, refactor, or migrate code simply to align with a plugin's preferred patterns.
2. **Advisory Role:** Plugins are advisory tools, not architectural authorities. They may inform decisions where the contract is silent, but they never override it.
3. **Silent Adoption Forbidden:** Do not silently adopt a plugin's pattern. If a plugin suggests a change that touches owned artifacts, schemas, or boundaries, surface the suggestion explicitly with a reference to the relevant spec/ADR before any code change.

### Specific Restrictions

- **Schema Formats:** Do not adopt a plugin's schema format if it conflicts with `02 §29.3.1` or ADR-012 (`.systemdesign/` bundle layout).
- **Documentation Templates:** Do not adopt a plugin's spec/PRD template if it conflicts with the `02`–`11` spec numbering system.
- **Migration Patterns:** Do not adopt a plugin's migration pattern if it conflicts with `08 §9.4` (schema-change report format) or `02 §29.3.1`.
- **Artifact Ownership:** Do not let a plugin propose moving artifacts (e.g., putting `A/B/C/D` in `ODEArtifact`) regardless of how it justifies the move — see ADR-010, ADR-013.
- **Boundary Crossings:** Do not let a plugin's "convenience import" suggestions break the boundary rules enforced by `tests/architecture/`.

## Common Commands

Setup (one-time, requires `.venv` activated):

```bash
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m pip install -e .          # editable install registers application/, features/, shared/
pre-commit install
```

Run the desktop app:

```bash
python -m application.main          # add --debug for DEBUG-level logging
system-designer                     # console script equivalent
```

Lint, type-check, test (the local equivalents of CI in `.github/workflows/ci.yml`):

```bash
ruff format --check src tests
ruff check src tests
mypy --config-file pyproject.toml src
pytest -m architecture -v           # always-green invariant suite
pytest -m unit
pytest -m integration
xvfb-run -a pytest -m gui           # GUI tests need a display
pytest -m "not slow"
pytest -m unit --cov=src --cov-report=html
```

Run a single test:

```bash
pytest tests/architecture/test_module_boundaries.py::test_shared_does_not_import_features -v
```

`pyproject.toml` puts `src/` on the pytest path, so no `PYTHONPATH` is required. Markers (`unit`, `integration`, `architecture`, `gui`, `slow`) are `--strict-markers` enforced — adding a new marker requires a `pyproject.toml` change.

## Architecture — What You Need to Know to Edit

The codebase uses a strict three-layer + two-feature module layout under `src/`:

- `application/` — `QApplication` entry, bootstrap, `SystemDesignerShell` (`QMainWindow`), menu wiring. Composes features; **must not** contain physics, graph, or simulation logic.
- `features/SystemModelingModule/` — workspace, components, ports, graph, DAE/ODE artifacts. Owns the "model side."
- `features/ControllerDesignModule/` — controller settings, I/O selection, plot layout, linearization, `A/B/C/D`, transfer functions, `StabilityAnalysisArtifact`. Owns the "control side."
- `shared/` — registries, components, graph, types, probes, utils, widgets.
- `shared/engine/` — **dormant in Phase 1**. Importing it raises `ImportError` (ADR-001, enforced by `tests/architecture/test_engine_isolation.py`). The barrier is removed at S4 entry, not before.

### Boundary Rules (Enforced by Tests)

`tests/architecture/` runs static-import checks that will fail PRs that:

- import `features.ControllerDesignModule` from `features.SystemModelingModule` (or vice versa) — features communicate through `shared/` types/artifacts only
- import `application.*` from `features/` or `shared/`
- import `features.*` from `shared/`
- import any submodule of `shared.engine` during Phase 1

Cross-feature data passes as method arguments or shared-type artifacts, never as module-to-module imports.

### Source-of-Truth Rules

- **`WorkspaceModel` is the only source of truth** for workspace state (ADR-003). UI subscribes to its signals; widgets never store canonical data. Edits must go through `QUndoCommand` subclasses in `features/SystemModelingModule/commands/` (ADR-005).
- **Component IDs are ULIDs prefixed `cmp_`** (ADR-002). Display labels and custom labels are user-facing only; never use them as references.
- **State references are semantic `(component_id, state_id)` tuples** (S3 rule). Index-only references are forbidden as canonical identity.

### Artifact Ownership (do not move these)

| Artifact | Owner | Forbidden Contents |
|---|---|---|
| `WorkspaceModel`, `SystemGraph`, `DAEArtifact`, `ODEArtifact` | `SystemModelingModule` | `A/B/C/D`, transfer functions, poles, simulation arrays, plot state |
| `StabilityAnalysisArtifact` | `ControllerDesignModule` | workspace state, full time-domain arrays |
| `SimulationRequest`, `SimulationResultArtifact` | `shared/engine` (Phase 2+) | UI references, design internals |
| `PlotSlotConfig` | `ControllerDesignModule` (`plot_layout`) | full arrays, legacy `signals[]` schema |

`A/B/C/D`, transfer functions, poles, zeros, and frequency response live **only** in `StabilityAnalysisArtifact` (ADR-010, ADR-013). Putting them in `ODEArtifact` is a hard violation.

### Plot/Result Panel

There is one unified result panel with four slots (ADR-015). No separate stability panel. Plot configuration uses the `channel_selection.kind` schema with values `channels` | `io_pair` | `system_wide` (ADR-016) — the legacy `signals[]` array is forbidden. Step response is the only plot type allowed to consume both `result_ref` and `analysis_ref`, with `result_ref` taking priority (`08 §16.4`).

### Persistence

Projects are saved as `.systemdesign/` directory bundles (ADR-012):

```
project.systemdesign/
  project.json     # metadata, references, schema version — JSON only
  results/         # *.h5 — full numeric arrays (HDF5)
  exports/
  recovery/
```

JSON holds metadata and references; full numeric/time-series data goes in HDF5. Storing arrays in JSON is a forbidden shortcut.

Schema changes require `schema_version` bump, a migration under `features/SystemModelingModule/model/migrations/`, a round-trip test, and an updated spec section (`02 §29.3.1`). Use the schema-change report format in `08 §9.4`.

## Conventions

- Python ≥ 3.11, < 3.14. Use modern syntax: `list[T]`, `T | None`, `from __future__ import annotations` at the top of every module.
- Ruff is the canonical formatter and linter (Black/isort/flake8/pyupgrade replaced). Line length 100.
- `mypy --strict` is on for `src`. New code must type-check.
- `print()` is forbidden in production code (Ruff `T201`). Use `logging.getLogger(__name__)` per `specs/10_logging_conventions.md`. The root logger is `system_designer`; `shared.engine` is pinned to `WARNING` in Phase 1.
- PySide6 signals use `lowerCamelCase` (the `N815` rule is disabled for `**/model/*.py` and `**/widgets/*.py`).
- Commit messages follow `S<stage>: <imperative summary>` per `08 §13.2`, with `Artifacts:`, `Tests:`, `Boundary checks:` trailers.

## Common Pitfalls (from `08 §6`)

- Do **not** make `shared/engine` importable in Phase 1 to "test something" — wrap or stub instead.
- Do **not** store workspace truth in widgets to avoid a command class.
- Do **not** invent fake simulation data, fallback curves, or empty-success artifacts to make plots/tests pass — surface a structured failure instead.
- Do **not** hardcode quarter-car (or any specific) topology into generic library/graph/equation code.
- Do **not** silently linearize a nonlinear ODE; the linearity flag and explicit workflow exist for a reason (ADR-010).
- Do **not** add `A/B/C/D` "temporarily" to `ODEArtifact`.
- Do **not** treat existing legacy code as the architecture — read the spec and migrate.

When ownership, schema, stage order, or artifact contracts are unclear, **stop and ask** using the escalation format in `08 §11.3` rather than guessing.
