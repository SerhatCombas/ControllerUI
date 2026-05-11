# Architecture Decision Records (ADRs)

This folder contains the canonical Architecture Decision Records for the Engineering System Designer project.

## What is an ADR?

An ADR captures a single architectural decision: what was decided, why, what alternatives were considered, and what the consequences are. ADRs are **immutable** once accepted — they may be superseded but never edited or deleted.

ADRs serve three audiences:

* **future contributors** who need to understand why the architecture is the way it is
* **AI coding agents** who must respect existing decisions when making changes
* **the team** when revisiting a decision (the alternatives section makes the original tradeoff explicit)

## Authority

ADRs sit at priority 5 in the conflict-resolution authority order defined in `08_codex_execution_rules.md` §3.1:

```
1. Hard safety rules
2. ADR catalog (06 §19)
3. Spec documents (01-07)
4. Implementation order (07)
5. ADR files (this folder)         ← here
6. Existing architectural code patterns
7. Existing test patterns
8. README and onboarding docs
9. Style guides (09)
10. Code comments and docstrings
```

When a spec document conflicts with an ADR file, the spec wins. ADR files are the **detailed expansion** of decisions referenced in `06 §19`.

## Index

The 21 canonical ADRs (per `06_data_flow_and_architecture.md` §19):

| # | Title | Stage | Status |
|---|---|---|---|
| 001 | Phase 1 Engine Isolation | S0 | Accepted |
| 002 | Hybrid ULID Identity Model | S1 | Accepted |
| 003 | Workspace UI/Data Separation | S1 | Accepted |
| 004 | Equation Builder Ownership | S3 | Accepted |
| 005 | Command Stack with QUndoStack | S1 | Accepted |
| 006 | Controller Owns Transfer-Function and State-Space Builders | S5 | Accepted |
| 007 | Symbolic Backend — CasADi | S4 | Accepted |
| 008 | Bond Graph Causality | S3 | Accepted |
| 009 | DAE Reduction Strategy | S3 | Accepted |
| 010 | Linearization Ownership | S5 | Accepted |
| 011 | Dimensional Analysis Policy | S2 | Accepted |
| 012 | Project Package Directory Format | S2 | Accepted |
| 013 | StabilityAnalysisArtifact | S5 | Accepted |
| 014 | Controller Runtime Wrapper in shared/engine | S7 | Accepted |
| 015 | Result Panel Unified With Grouped Dropdown | S6 | Accepted |
| 016 | channel_selection.kind Schema | S2 | Accepted |
| 017 | Mirror Sync Plot Dropdowns | S2 | Accepted |
| 018 | WorkspaceModel Signal Payload Contracts | S1 | Accepted |
| 019 | Batch Mutation Mode and WorkspaceChangeSet | S1 | Accepted |
| 020 | Dirty Tracking Semantics | S1 | Accepted |
| 021 | Built-in Component Definitions as Python Dataclasses | S1 | Accepted |

## Adding a New ADR

1. Copy `_template.md` to `ADR-NNN-<short-slug>.md`.
2. Fill in all sections.
3. Status starts as `Proposed`.
4. Discuss with the team or open a PR.
5. When accepted, change Status to `Accepted` and the ADR becomes immutable.
6. Add the new entry to the index above.
7. Update `06 §19` if appropriate.

## Superseding an ADR

ADRs are immutable but can be superseded:

1. Create a new ADR explaining the new decision.
2. In the new ADR, reference the old one in the `Supersedes:` field.
3. Edit the old ADR's metadata to set `Superseded by: ADR-NNN` and `Status: Superseded by ADR-NNN`.
4. Do not delete the old ADR.

The "edit metadata" step is the **only** allowed change to an accepted ADR.

## Non-ADR Documents in This Folder

This folder may contain dated design documents that are **not** ADRs:

* **Naming**: `YYYY-MM-DD_slug.md` (dated lowercase, distinct from
  `ADR-NNN-slug.md`).
* **Purpose**: findings, handoff notes, or pre-ADR exploration that
  may evolve into formal ADRs but are not yet architectural decisions.
* **Authority**: below ADRs in `08 §3.1`; informational and advisory.
* **Promotion**: if a dated note matures into a formal decision,
  `git mv` it to `ADR-NNN-slug.md`, convert to the ADR template
  (`_template.md`), and reference the original in the new ADR's
  `Context` section.

The `tests/architecture/test_adr_files_present.py` test does **not**
gate on these files; it counts only the canonical `ADR-NNN-*.md`
filenames, so dated notes can come and go without architecture-test
churn.

Current non-ADR documents in this folder:

| File | Subject |
|---|---|
| `2026-05-05_s3-s5-handoff-design.md` | S3 to S5 handoff design (architecture test invariants) |
| `2026-05-10_pyside6-signal-exception-dispatch.md` | PySide6 signal exception dispatch finding (S1.3d follow-up) |
| `2026-05-11_command-layer-qtgui-exemption.md` | Command-layer QtGui exemption finding (S1.7.1 follow-up) |

## Naming Convention

ADR files follow this pattern:

```
ADR-<3-digit-number>-<lowercase-slug-with-hyphens>.md
```

Examples:

* `ADR-001-phase1-engine-isolation.md`
* `ADR-007-symbolic-backend-casadi.md`
* `ADR-015-result-panel-unified-with-grouped-dropdown.md`

The number is permanent; the slug should match the canonical title.

## Tests

The CI architecture wave includes a test (`tests/architecture/test_adr_files_present.py`) that verifies all 21 canonical ADRs exist as files in this folder. Adding new ADRs requires updating that test list.
