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

Phase 2 (Equation Extraction, Simulation, Stability) and Phase 3 (Advanced Performance) are planned. See `07_implementation_order.md` for the staged roadmap.

---

## Quick Start (for human contributors)

### Prerequisites

* Python 3.11 or 3.12
* Git
* (optional) Make or just for shortcut commands

### Installation

```bash
# Clone the repository
git clone <repo-url>
cd Codex_Project

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # on Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Install pre-commit hooks
pre-commit install

# Verify setup
ruff check src tests
mypy --config-file pyproject.toml src
pytest -m architecture
```

### Running the Application

```bash
python -m application.main
```

### Running Tests

```bash
# Architecture invariants (must pass at all times)
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

---

## For AI Coding Agents

This project is designed to support AI-assisted development. Read the documents below **in order** before making changes.

### Required Reading (Authority Order)

The order below is the conflict-resolution authority order from `08_codex_execution_rules.md` §3.1.

1. **`08_codex_execution_rules.md`** — Execution contract for AI agents. Read this first.
2. **`02_workspace_requirements.md`** — Visual modeling canvas, graph, identity model, persistence.
3. **`03_configuration_requirements.md`** — Controller, I/O, simulation, plot layout configuration.
4. **`04_model_equations_requirements.md`** — Equation extraction pipeline (Phase 2).
5. **`05_simulation_and_results_requirements.md`** — Simulation engine, results, stability, plots.
6. **`06_data_flow_and_architecture.md`** — Module ownership, project structure, ADR catalog.
7. **`07_implementation_order.md`** — 8-stage roadmap (S0–S7) with dependencies and risks.
8. **`01_library_requirements.md`** — Component library, registry, SVG, drag/drop.
9. **`09_coding_standards.md`** — Python style, type hints, naming, PySide6 conventions.
10. **`10_logging_conventions.md`** — Logger hierarchy, levels, structured logging.
11. **`11_error_code_catalog.md`** — Stable error code catalog.
12. **`12_ci_cd_pipeline.md`** — CI/CD pipeline definition.
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

See `08_codex_execution_rules.md` §6 for the complete list. Highlights:

* **No fake simulation data** to make plots appear to work.
* **No silent equation linearization** without explicit user workflow.
* **No hardcoded quarter-car topology** in generic library components.
* **No A/B/C/D matrices in `ODEArtifact`** (they belong in `StabilityAnalysisArtifact`).
* **No skipping migration tests** for schema changes.

---

## Project Structure

```
src/
  application/                    # QApplication entry, shell, bootstrap
  features/
    SystemModelingModule/         # Visual modeling, workspace, graph
      model/                      # WorkspaceModel, ComponentInstance, Connection
      commands/                   # QUndoCommand subclasses
      panels/                     # ModelLibraryPanel, ComponentInfoPanel, ModelEquationsPanel
      workspace/                  # BlockDiagramWorkspace (UI)
    ControllerDesignModule/       # Configuration, controller design, results
      model/                      # ControllerSettings, IOSelection, PlotLayout, StabilityAnalysisArtifact
      builders/                   # Phase 2: TF/SS builders, linearization
      panels/                     # ConfigurationPanel, ResultsPanel
  shared/
    components/                   # Component schema dataclasses
    registry/                     # ComponentRegistry, DomainRegistry, ParameterSchemaRegistry, SvgRegistry
    graph/                        # SystemGraph, GraphAssembler, GraphValidator
    types/                        # Domain enums, port kinds, plot types
    probes/                       # Output observation
    utils/                        # Helpers (ULID, JSON, units, logging)
    engine/                       # PHASE 2 ONLY — Phase 1: ImportError

tests/
  architecture/                   # Import-boundary and invariant tests
  features/                       # Per-module tests mirroring src/features
  integration/                    # Cross-module integration tests

decisions/                        # ADR-001 ... ADR-017 + README + _template.md

assets/
  locales/                        # Localization tables (en.json default)
  licenses/                       # Third-party SVG license files

.github/
  workflows/                      # CI/CD pipeline (see 12_ci_cd_pipeline.md)
```

For the full layered architecture, see `06_data_flow_and_architecture.md` §2.

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

See `07_implementation_order.md` for the full stage-by-stage execution plan with acceptance criteria.

---

## Development Workflow

### Daily Loop

1. Pull latest from `main`.
2. Create a feature branch: `git checkout -b feature/<short-description>`.
3. Make changes, following coding standards (`09`).
4. Run linter and tests locally: `ruff check src tests && mypy src && pytest -m "architecture or unit"`.
5. Commit with a message matching the convention from `08 §13.2`.
6. Push and open a pull request.
7. CI runs the full pipeline (see `12`).
8. Address review comments.
9. Squash merge once approved.

### Architecture Decisions

Significant architectural decisions are captured as ADRs under `decisions/`. Before introducing a new architectural pattern:

1. Check `06 §19` for existing ADRs.
2. If no ADR covers your decision, draft a new one using `decisions/_template.md`.
3. Have it reviewed before implementing.
4. Once accepted, the ADR becomes immutable (it can be superseded but not deleted).

### Schema Changes

If your change affects `project.json` or any saved data structure:

1. Bump the relevant `schema_version` in the schema definition.
2. Add a migration to `features/SystemModelingModule/model/migrations/`.
3. Add a round-trip migration test.
4. Update the relevant spec section.

See `02 §29.3.1` for the full schema migration contract.

---

## Documentation Map

| Document | Purpose |
|---|---|
| `01_library_requirements.md` | Component library and registry |
| `02_workspace_requirements.md` | Visual canvas, identity, persistence |
| `03_configuration_requirements.md` | Configuration panels |
| `04_model_equations_requirements.md` | Equation extraction (Phase 2) |
| `05_simulation_and_results_requirements.md` | Simulation engine and results (Phase 2) |
| `06_data_flow_and_architecture.md` | Module ownership and architecture |
| `07_implementation_order.md` | Stage-by-stage build plan |
| `08_codex_execution_rules.md` | AI agent execution contract |
| `09_coding_standards.md` | Python style and conventions |
| `10_logging_conventions.md` | Logging hierarchy and format |
| `11_error_code_catalog.md` | Stable error code catalog |
| `12_ci_cd_pipeline.md` | CI/CD pipeline |
| `decisions/` | Architecture Decision Records |

---

## License

(To be determined.)

If SVG assets in this project are adapted from third-party sources (e.g., Modelica Standard Library), their original licenses are preserved under `assets/licenses/` and referenced from the SvgRegistry attribution metadata (see `01 §10.4.1`).

---

## Contact and Support

* For bug reports, open a GitHub issue.
* For architectural questions, check `decisions/` first; open a discussion if no ADR covers your case.
* For coding standards questions, see `09_coding_standards.md`.
* For AI agent integration questions, see `08_codex_execution_rules.md`.

---

## Acknowledgments

Inspired by:

* MathWorks Simscape (modeling philosophy)
* Modelica Association (Modelica Standard Library and Bond Graph approach)
* CasADi project (symbolic + numerical backend, planned for Phase 2)

These influences are referenced in the relevant ADRs and spec sections; the project does not depend on any of these tools at runtime in Phase 1.
