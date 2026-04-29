# Engineering System Designer

A model-first, artifact-driven engineering tool for visual system modeling, equation extraction, simulation, and control design — inspired by Simscape and Modelica.

## Status

**Phase 1 (Visual Modeling Tier) — under active development.**

* component library and registry
* visual block-diagram canvas with drag/drop
* graph assembly and validation
* project package persistence (`.systemdesign/` directory format)
* configuration UI for controllers, I/O, simulation, and plots
* unified result panel with grouped plot type selection

Phase 2 (Equation Extraction, Simulation, Stability) and Phase 3 (Advanced Performance) are planned. See `specs/07_implementation_order.md` for the staged roadmap.

---

## Architecture Overview

The project is organized around a three-layer application structure:

1. **`application/`** — application shell, composition, routing, and orchestration.
2. **`features/`** — domain-oriented modules such as system modeling and controller design.
3. **`shared/`** — reusable components, types, and utilities shared across modules.

The target architecture follows two feature modules backed by a shared simulation engine:

- `features/SystemModelingModule`
- `features/ControllerDesignModule`
- `shared/engine` (Phase 2 only — Phase 1 raises `ImportError`)
- `shared/components`
- `shared/graph`
- `shared/probes`
- `shared/types`
- `shared/utils`
- `shared/registry`

For the full layered architecture, see `specs/06_data_flow_and_architecture.md` §2.

---

## Python Setup

Create and activate the local environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -r requirements-dev.txt
```

Install the project in **editable mode** so that the `application`,
`features`, and `shared` packages are importable from anywhere:

```bash
python -m pip install -e .
```

This is a one-time setup. After this step, the project layout under
`src/` is registered with the active Python environment.

Install pre-commit hooks (one-time setup):

```bash
pre-commit install
```

Run the desktop app:

```bash
python -m application.main
```

Or use the installed console script:

```bash
system-designer
```

To run with debug logging:

```bash
python -m application.main --debug
```

---

## Verifying the Development Environment

After setup, verify everything is wired correctly:

```bash
ruff check src tests
ruff format --check src tests
mypy --config-file pyproject.toml src
pytest -m architecture -v
```

If `pytest -m architecture` reports `PASSED` for all (or `SKIPPED` for
the logging-events test, which is expected before Stage S1), the
project is in a clean Stage S0 baseline.

---

## Running Tests

Tests are segmented by pytest markers:

```bash
# Architecture invariants (must pass at all times — runs first in CI)
pytest -m architecture

# Unit tests
pytest -m unit

# Integration tests
pytest -m integration

# GUI tests (requires display or Xvfb)
pytest -m gui

# All tests except slow
pytest -m "not slow"

# Coverage report
pytest -m unit --cov=src --cov-report=html
```

`pyproject.toml` already adds `src/` to the pytest path, so the
commands above work without manual `PYTHONPATH` configuration.

See `specs/12_ci_cd_pipeline.md` §6 for the full test segmentation policy.

---

## For AI Coding Agents

This project is designed to support AI-assisted development. Read the documents below **in order** before making changes.

### Required Reading (Authority Order)

The order below is the conflict-resolution authority order from `specs/08_codex_execution_rules.md` §3.1.

1. **`specs/08_codex_execution_rules.md`** — Execution contract for AI agents. Read this first.
2. **`specs/02_workspace_requirements.md`** — Visual modeling canvas, graph, identity model, persistence.
3. **`specs/03_configuration_requirements.md`** — Controller, I/O, simulation, plot layout configuration.
4. **`specs/04_model_equations_requirements.md`** — Equation extraction pipeline (Phase 2).
5. **`specs/05_simulation_and_results_requirements.md`** — Simulation engine, results, stability, plots.
6. **`specs/06_data_flow_and_architecture.md`** — Module ownership, project structure, ADR catalog.
7. **`specs/07_implementation_order.md`** — 8-stage roadmap (S0–S7) with dependencies and risks.
8. **`specs/01_library_requirements.md`** — Component library, registry, SVG, drag/drop.
9. **`specs/09_coding_standards.md`** — Python style, type hints, naming, PySide6 conventions.
10. **`specs/10_logging_conventions.md`** — Logger hierarchy, levels, structured logging.
11. **`specs/11_error_code_catalog.md`** — Stable error code catalog.
12. **`specs/12_ci_cd_pipeline.md`** — CI/CD pipeline definition.
13. **`decisions/ADR-001..017.md`** — Architecture Decision Records.

### Critical Rules

Before writing code, the AI agent must internalize these rules from `08`:

1. **Specs are contracts, not suggestions.** Do not "improve" architectural decisions captured in ADRs.
2. **Phase 1 must not import `shared.engine`.** This is enforced at startup with `ImportError` (ADR-001).
3. **`WorkspaceModel` is the source of truth.** UI components subscribe to its signals; they do not store independent state (ADR-003).
4. **Component instance IDs use ULID with `cmp_` prefix.** Do not use display names as references (ADR-002).
5. **Plot configuration uses `channel_selection.kind` schema.** Legacy `signals[]` arrays are forbidden (ADR-016).
6. **Stability artifact is separate from ODE artifact.** A/B/C/D matrices live in `StabilityAnalysisArtifact`, not `ODEArtifact` (ADR-010, ADR-013).
7. **Result panel is unified.** Both simulation results and stability analysis render in the same 4-slot panel (ADR-015).

### Forbidden Actions

See `specs/08_codex_execution_rules.md` §6 for the complete list. Highlights:

* **No fake simulation data** to make plots appear to work.
* **No silent equation linearization** without explicit user workflow.
* **No hardcoded quarter-car topology** in generic library components.
* **No A/B/C/D matrices in `ODEArtifact`** (they belong in `StabilityAnalysisArtifact`).
* **No skipping migration tests** for schema changes.

---

## Project Structure

```
Codex_Project/
├── README.md                              ← you are here
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
├── .gitignore
│
├── specs/                                 ← all specification documents
│   ├── 01_library_requirements.md
│   ├── 02_workspace_requirements.md
│   ├── 03_configuration_requirements.md
│   ├── 04_model_equations_requirements.md
│   ├── 05_simulation_and_results_requirements.md
│   ├── 06_data_flow_and_architecture.md
│   ├── 07_implementation_order.md
│   ├── 08_codex_execution_rules.md
│   ├── 09_coding_standards.md
│   ├── 10_logging_conventions.md
│   ├── 11_error_code_catalog.md
│   └── 12_ci_cd_pipeline.md
│
├── decisions/                             ← Architecture Decision Records
│   ├── README.md
│   ├── _template.md
│   └── ADR-001 ... ADR-017
│
├── .github/                               ← CI/CD pipeline
│   └── workflows/
│       └── ci.yml
│
├── tests/                                 ← test code
│   ├── __init__.py
│   └── architecture/
│       ├── __init__.py
│       └── test_*.py
│
├── assets/                                ← localization, license files
│   └── locales/
│       └── en.json
│
└── src/                                   ← source code
    ├── application/                       ← QApplication entry, shell, bootstrap
    │   ├── __init__.py
    │   ├── main.py                        ← entry point: python -m application.main
    │   └── SystemDesignerShell/
    │       ├── __init__.py
    │       └── main_window.py
    ├── features/
    │   ├── SystemModelingModule/          ← visual modeling, workspace, graph
    │   │   ├── model/                     ← WorkspaceModel, ComponentInstance
    │   │   ├── commands/                  ← QUndoCommand subclasses
    │   │   ├── panels/                    ← Library, Info, ModelEquations panels
    │   │   └── workspace/                 ← BlockDiagramWorkspace (UI)
    │   └── ControllerDesignModule/        ← configuration, controller design
    │       ├── model/                     ← ControllerSettings, IOSelection, PlotLayout
    │       ├── builders/                  ← Phase 2: TF/SS builders, linearization
    │       └── panels/
    │           ├── ConfigurationPanel/    ← 4-tab config panel
    │           └── ResultsPanel/          ← 4-slot unified result panel
    └── shared/
        ├── components/                    ← component schema dataclasses
        ├── registry/                      ← ComponentRegistry, DomainRegistry
        ├── graph/                         ← SystemGraph, GraphAssembler
        ├── types/                         ← domain enums, port kinds, plot types
        ├── probes/                        ← output observation
        ├── utils/                         ← helpers (ULID, JSON, units, logging)
        └── engine/                        ← PHASE 2 ONLY — Phase 1: ImportError
```

---

## Stages and Phases

The project distinguishes **product phases** (user-facing capability tiers) from **implementation stages** (build order).

### Product Phases

| Phase | Capability |
|---|---|
| Phase 1 | Visual modeling: canvas, graph, validation, persistence (active) |
| Phase 2 | Equation extraction, simulation, stability analysis, controller runtime |
| Phase 3 | Advanced performance, large-scale workflows, nonlinear systems, streaming |

### Implementation Stages

| Stage | Phase | Name | Output |
|---|---|---|---|
| **S0** | Pre-Phase 1 | Architecture Scaffold and ADR Gate | folder skeleton, import boundaries, ADR baseline |
| **S1** | Phase 1 | Workspace Foundation | `WorkspaceModel`, commands, graph |
| **S2** | Phase 1 | Configuration and Project Package | controller/config/plot placeholders, `.systemdesign/` |
| **S3** | Phase 2A | Equation System | `ODEArtifact` |
| **S4** | Phase 2B | Simulation Engine | `SimulationResultArtifact` |
| **S5** | Phase 2C | Stability and Control Analysis | `StabilityAnalysisArtifact` |
| **S6** | Phase 2D | Plot and Result Rendering | unified result panel |
| **S7** | Phase 2E | Controller Runtime Integration | closed-loop execution |

See `specs/07_implementation_order.md` for the full stage-by-stage execution plan with acceptance criteria.

---

## Development Workflow

### Daily Loop

1. Pull latest from `main`.
2. Create a feature branch: `git checkout -b feature/<short-description>`.
3. Make changes, following coding standards (`specs/09_coding_standards.md`).
4. Run linter and tests locally:
   ```bash
   ruff check src tests
   mypy --config-file pyproject.toml src
   pytest -m "architecture or unit"
   ```
5. Commit with a message matching the convention from `specs/08_codex_execution_rules.md` §13.2.
6. Push and open a pull request.
7. CI runs the full pipeline (see `specs/12_ci_cd_pipeline.md`).
8. Address review comments.
9. Squash merge once approved.

### Architecture Decisions

Significant architectural decisions are captured as ADRs under `decisions/`. Before introducing a new architectural pattern:

1. Check `specs/06_data_flow_and_architecture.md` §19 for existing ADRs.
2. If no ADR covers your decision, draft a new one using `decisions/_template.md`.
3. Have it reviewed before implementing.
4. Once accepted, the ADR becomes immutable (it can be superseded but not deleted).

### Schema Changes

If your change affects `project.json` or any saved data structure:

1. Bump the relevant `schema_version` in the schema definition.
2. Add a migration to `features/SystemModelingModule/model/migrations/`.
3. Add a round-trip migration test.
4. Update the relevant spec section.

See `specs/02_workspace_requirements.md` §29.3.1 for the full schema migration contract.

---

## Documentation Map

| Document | Purpose |
|---|---|
| `specs/01_library_requirements.md` | Component library and registry |
| `specs/02_workspace_requirements.md` | Visual canvas, identity, persistence |
| `specs/03_configuration_requirements.md` | Configuration panels |
| `specs/04_model_equations_requirements.md` | Equation extraction (Phase 2) |
| `specs/05_simulation_and_results_requirements.md` | Simulation engine and results (Phase 2) |
| `specs/06_data_flow_and_architecture.md` | Module ownership and architecture |
| `specs/07_implementation_order.md` | Stage-by-stage build plan |
| `specs/08_codex_execution_rules.md` | AI agent execution contract |
| `specs/09_coding_standards.md` | Python style and conventions |
| `specs/10_logging_conventions.md` | Logging hierarchy and format |
| `specs/11_error_code_catalog.md` | Stable error code catalog |
| `specs/12_ci_cd_pipeline.md` | CI/CD pipeline |
| `decisions/` | Architecture Decision Records |

---

## License

(To be determined.)

If SVG assets in this project are adapted from third-party sources (e.g., Modelica Standard Library), their original licenses are preserved under `assets/licenses/` and referenced from the SvgRegistry attribution metadata (see `specs/01_library_requirements.md` §10.4.1).

---

## Contact and Support

* For bug reports, open a GitHub issue.
* For architectural questions, check `decisions/` first; open a discussion if no ADR covers your case.
* For coding standards questions, see `specs/09_coding_standards.md`.
* For AI agent integration questions, see `specs/08_codex_execution_rules.md`.

---

## Acknowledgments

Inspired by:

* MathWorks Simscape (modeling philosophy)
* Modelica Association (Modelica Standard Library and Bond Graph approach)
* CasADi project (symbolic + numerical backend, planned for Phase 2)

These influences are referenced in the relevant ADRs and spec sections; the project does not depend on any of these tools at runtime in Phase 1.
