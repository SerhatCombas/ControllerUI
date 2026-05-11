# Finding: Command-Layer QtGui Exemption (S1.7.1)

**Type:** Finding (non-ADR; codifies an architecture-test split)
**Date:** 2026-05-11
**Discovered during:** S1.7.1 implementation (`WorkspaceCommandStack` + `AddComponentCommand`)
**Status:** Resolved — `tests/architecture/test_no_ui_in_model.py` split into data-layer + command-layer rules at commit `c07870d`
**Related:** ADR-003 (Workspace UI/Data Separation), ADR-005 (Command Stack with QUndoStack)

This file follows the precedent set by
`decisions/2026-05-05_s3-s5-handoff-design.md` and
`decisions/2026-05-10_pyside6-signal-exception-dispatch.md`: a dated
lowercase filename for non-ADR design notes that live alongside the
formal ADR catalog. It is **not** an ADR — `decisions/README.md`
distinguishes ADRs (immutable decisions) from dated findings
(advisory follow-up notes). The decision codified here lives in code
(`tests/architecture/test_no_ui_in_model.py`) and in commit
`c07870d`; this note documents the rationale so a future reviewer
does not have to reconstruct the conflict from a commit message.

## Background

ADR-003 separates the workspace data layer from the UI layer: data
(`model/` subfolders, most of `shared/`) must not import Qt UI
modules. The original `tests/architecture/test_no_ui_in_model.py`
encoded this as a flat list of "data layer subdirectories" plus a
flat list of forbidden Qt modules (everything outside `PySide6.QtCore`).

The data-layer list included
`src/features/SystemModelingModule/commands` from inception, on the
theory that commands are data-layer-adjacent and should not touch
UI internals.

ADR-005 mandates that the command stack be implemented with
`QUndoStack` and `QUndoCommand`. In Qt5 these classes lived in
`PySide2.QtWidgets`; in Qt6+ they were moved to `PySide6.QtGui`.

## The Conflict

The two decisions taken together produce an impossible constraint
for Qt6+:

* ADR-003 → `commands/` may not import `PySide6.QtGui`.
* ADR-005 → `commands/` must subclass `QUndoCommand`, which lives in
  `PySide6.QtGui`.

The conflict was latent because S1.3–S1.B work did not touch
`commands/` — the directory existed with only an `__init__.py` and
its docstring listed planned future commands. S1.7.1 was the first
sub-commit to add real command code, which made the test fail.

This is a Type-3 case per `08 §3.4`: ADR-005's directive (commands
use `QUndoCommand`) is structural to the architecture, but the
architecture test had encoded an interpretation of ADR-003 that
went broader than ADR-003 actually requires. The conflict was
between ADR-005 and the test's interpretation, not between the two
ADRs themselves.

## Resolution

The architecture test was split into two rules:

1. **Data layer** (`model/` subfolders, `shared/components`,
   `shared/registry`, `shared/graph`, `shared/types`,
   `shared/probes`, `shared/utils`): the original full Qt UI ban
   applies. `PySide6.QtCore` is the only allowed Qt import.
2. **Command layer**
   (`features/SystemModelingModule/commands/`): `PySide6.QtCore`
   and `PySide6.QtGui` are allowed (the latter is what ADR-005
   actually mandates). All widget modules — `QtWidgets`,
   `QtMultimedia`, `QtQuick`, `QtQml`, `QtCharts`,
   `QtSvgWidgets` — remain forbidden so commands cannot drift into
   UI construction.

The split is two parametrized tests in
`tests/architecture/test_no_ui_in_model.py`:

* `test_data_layer_packages_have_no_ui_imports` — unchanged in
  intent.
* `test_command_layer_does_not_import_widget_modules` — new, catches
  the inverse violation that the original test could not.

Both tests share the scan / report helpers; the only difference is
the `(patterns, forbidden_modules)` pair each receives.

## Why Not an ADR

The decision is small and entirely a test-codification: no
production-code architecture changed, no new module boundary was
introduced, and no ADR claim was superseded. ADR-003 and ADR-005
both stand; this note records the intersection point. If a future
layer emerges with a similar "structural Qt dependency outside the
UI" requirement (e.g., a `shared/qml-bridge/` for property
forwarding, or a worker-thread layer that needs `QtConcurrent`),
that would justify promoting this to a formal ADR. Until then the
single-point exemption is appropriately captured here.

## Forward Path

* Conditions under which this should be promoted to an ADR:
  - A second feature module wants its own `commands/` directory
    (would imply a generalization across modules).
  - A second non-UI subdirectory legitimately needs `PySide6.QtGui`
    for non-command reasons.
  - The Qt API moves `QUndoCommand` again (Qt7+ uncertainty) and
    the import surface needs adjustment.
* Conditions under which this is safe to leave as a dated note:
  - Only `features/SystemModelingModule/commands/` ever needs the
    QtGui exemption; widget modules stay forbidden everywhere
    outside the UI layer.

## References

* ADR-003 (`decisions/ADR-003-workspace-ui-data-separation.md`)
* ADR-005 (`decisions/ADR-005-command-stack-qundostack.md`)
* `08 §3.4` Conflict Classification (Type-3 example)
* `tests/architecture/test_no_ui_in_model.py` (the split)
* Commit `c07870d` (S1.7.1 — the split landed here)
