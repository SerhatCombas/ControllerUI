# Post-Phase-1 Polish Backlog

Items deliberately deferred from Phase 1 closure. Each entry is
a concrete piece of work with its source commit / discussion
context, the rationale for deferral, and the scope estimate.

This file is a polish backlog, not an ADR catalog. Formal
architectural decisions belong in `decisions/ADR-NNN-*.md`;
this file collects "would be nice, not on the critical path"
work surfaced during Phase 1 implementation.

---

## S1.11 — Workspace UI polish (deferred from S1.9 / S1.10)

**Source:** S1.10 manual smoke report (commit `bb12ba5` "S1.10.1:
surface connection rejection in status bar" — cosmetic findings
C1–C4 catalogued).

**Rationale for deferral:** Each item is feedback-quality (delay
or visual nicety), not feedback-presence (B1 was the latter).
S1.10.1 closed B1; the rest can ride a single polish pass.

**Items:**

* **C1 — Parameter-edit transient status message.**
  `ChangeParameterCommand` push currently fires only
  `componentChanged` + `dirtyChanged(*)`; no transient
  "parameter X updated" string lands in the status bar. Wire
  a `componentChanged` slot in `SystemDesignerShell._wire_status_bar_signals`
  that pulls the changed parameter via the model and renders
  e.g. `"Parameter 'kp' = 2.5 on 'Main PID'"`. ~10 LOC + 1 gui
  test.

* **C2 — Validator debounce tuning (250 ms → 100 ms or "validating…"
  interim message).**
  Current `WorkspaceValidatorController` debounce is 250 ms
  (`DEFAULT_DEBOUNCE_MS`). Live UX feels slightly laggy on
  duplicate-connection-drop scenarios. Either drop to 100 ms or
  surface a transient "Validating…" status bar message during
  the debounce window. UX call — try both via `--debug` smoke.

* **C3 — Drag-time port hover highlight (spec §15).**
  Spec calls for green/red port tint during connection-draw
  drag to telegraph compatible/incompatible targets. Currently
  `port_graphics_item.py` carries no hover state. Add a
  `setBrush(QColor(...))` toggle on the port item, drive it
  from `WorkspaceScene.update_connection_draw` based on a
  candidate-domain check against the pending source.
  ~40 LOC + 2 gui tests.

* **C4 — Stale "added" status message after rejected operations.**
  Mostly subsumed by S1.10.1 (B1 fix) — rejected connection
  emits "Connection rejected:" which overwrites the previous
  message. Remaining sliver: same pattern for rejected
  duplicates of `add_component`. Likely zero-LOC if the scene
  already routes through `connectionRejected`; verify during
  the polish pass.

---

## S2.F — Autosave + recovery (deferred from S2 closure)

**Source:** S2.E pre-scan discussion. Spec §30 (Autosave and
Recovery) reads "the workspace should support autosave" — not
"must support". Deferred to keep the critical path (shell
integration → smoke v2 → Phase 1 declaration) unblocked.

**Rationale for deferral:**

1. Spec §30 uses "should", not "must". Phase 1 shipping without
   autosave is defensible.
2. Phase-1 manual smoke v2 does not exercise the autosave path
   (no scenario depends on it).
3. Autosave is purely additive on top of S2.E: a `QTimer`, a
   dirty check, a call to the existing `save_project()`. No
   refactor to S2.E API needed — it can land later in one
   short commit without disturbing anything around it.

**Items (one S2.F sub-commit when picked up):**

* `QTimer` (default 600 s, configurable via project settings or
  application preferences).
* Dirty-only check: skip the write if both
  `workspace_model.is_dirty` and `configuration_model.is_dirty`
  are `False`.
* Write target: `bundle/recovery/autosave.json` (per ADR-012
  bundle layout). The existing `save_project()` orchestrator
  composes the payload; redirect the atomic write target to
  `recovery/autosave.json` instead of `project.json`.
* Rotating snapshot policy: keep last N files (spec mentions
  "rotating, capped at 50 MB"). Phase 1.5 default N = 5.
* Load-time recovery detection + user dialog (further
  deferred — Phase 2 UX work). At Phase 1.5 the file is
  written but not auto-restored; the user can copy it to
  `project.json` manually if needed.

**Scope estimate:** ~50 LOC source + ~10 unit test + 5 LOC
shell wiring. Single sub-commit, fits in one session.

---

## Validation type consolidation (deferred from S2.B.2)

**Source:** Pre-S2.B.2 refactor commit (`302a146` "refactor:
relocate ValidationReport to shared/types"). The relocation
kept the original module path
(`features/SystemModelingModule/model/validation_report.py`)
as a 12-line re-export shim so the 30+ existing imports inside
`SystemModelingModule` kept working without churn.

**Rationale for deferral:** Migrating ~30 import sites mid-S2
would have inflated S2.B.2's commit with unrelated churn and
muddied the architectural narrative of the actual S2.B.2
change (cross-feature validator landing). The shim is harmless;
the consolidation is mechanical.

**Items:**

* Find/replace `from features.SystemModelingModule.model.validation_report import ...`
  → `from shared.types.validation_report import ...` (or
  `from shared.types import ...`).
* Touches ~30 source files + their test files.
* Delete `features/SystemModelingModule/model/validation_report.py`
  (the shim).

**Scope estimate:** Mechanical refactor; one commit, ~30 file
touches, no behavior change, all existing tests stay green.

---

## ADR-016 root_locus row alignment (deferred from S2.C)

**Source:** S2.C scaffold (commit `21cf9c0` "S2.C: PlotLayout +
PlotSlotConfig + ChannelSelection scaffold"). The
`PLOT_TYPE_KIND_MAP` table in `plot_layout.py` follows spec/03
§8.6 (root_locus → system_wide); ADR-016's table reads
"root locus → io_pair". The two tables diverged at some point;
spec/03 §8.6 is the authority used in source.

**Rationale for deferral:** Phase 1 does not use root_locus (it
is a Phase-2 plot type). The contradiction has no production
impact; cleanup is documentation hygiene only.

**Items:**

* `docs(decisions): align ADR-016 root_locus row with spec/03 §8.6`
  — edit ADR-016's table to read `root locus → system_wide`,
  matching the description column "+ gain parameter".

**Scope estimate:** 1-line ADR edit; trivial commit.

---

## Maintenance protocol for this file

* Items move from this file to a real commit when picked up; do
  not delete entries — replace them with a one-line "Landed in
  commit `<sha>`" pointer so the historical context survives.
* New items added during Phase 1 work go here, not into
  `decisions/`.
* When Phase 1 closes, the file is renamed `post-phase-1-DONE.md`
  (or similar archival treatment); new deferrals start a fresh
  `post-phase-2.md`.
