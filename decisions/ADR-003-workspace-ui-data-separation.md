# ADR-003: Workspace UI/Data Separation

**Status:** Accepted  
**Date:** 2026-04-28  
**Deciders:** Serhat Combas  
**Stage:** S1  
**Supersedes:** —  
**Superseded by:** —

## Context

The visual workspace involves two responsibilities:

1. **Data**: what components and connections exist, their parameters, validation state
2. **UI**: how those components are rendered as `QGraphicsItem` instances on a `QGraphicsScene`

A common (and tempting) anti-pattern is to make `QGraphicsItem` instances the source of truth, storing component data inside graphics objects and serializing them directly. This couples data to UI in ways that:

* require Qt running for any non-UI operation (tests, batch processing, headless validation)
* tie persistence format to graphics-item attributes
* make undo/redo difficult because state lives in mutable scene items
* prevent multiple views of the same data
* make testing slow and brittle

## Decision

The workspace has a **strict separation** between data and UI:

* **`WorkspaceModel`** (data, in `features/SystemModelingModule/model/workspace_model.py`) is the **single source of truth** for components, connections, selection, validation state, and dirty status. It inherits from `QObject` for signal emission but its API does not require a running event loop.
* **UI components** (`BlockDiagramWorkspaceScene`, `ComponentGraphicsItem`, `ConnectionGraphicsItem`, panels) **subscribe to model signals** and render derived visuals. They do not store independent data state.

User actions follow this flow:

```
User input  →  Command (QUndoCommand)  →  WorkspaceModel mutation  →  signal emitted  →  UI updates
```

UI never mutates the model directly except through commands. UI never holds authoritative state.

The `model/` subfolder must not import `PySide6.QtWidgets` or `PySide6.QtGui`. It may use `PySide6.QtCore` for `QObject` and `Signal`.

## Alternatives Considered

### Alternative 1: Graphics items as source of truth

Store component data directly on `QGraphicsItem` subclasses; serialize the scene.

**Rejected because:**

* Requires `QApplication` for tests
* Couples persistence to graphics-item attributes
* Makes undo/redo and validation harder
* Prevents headless usage

### Alternative 2: MVC with passive view

Use a strict Model-View-Controller pattern with a passive `QGraphicsView` and explicit Controller classes.

**Rejected because:**

* Qt's signal/slot mechanism already provides the reactive layer
* Adding explicit Controller classes is overhead without obvious benefit in this domain
* The chosen pattern (Model emits signals, View reacts) is essentially a thin MVC

### Alternative 3: Reactive store (Redux-style)

Use an external state-management library.

**Rejected because:**

* Adds a third-party dependency for a problem Qt's signal system already solves
* Python ecosystem reactive stores are less mature than JavaScript counterparts
* Unnecessary complexity for a desktop application

## Consequences

### Positive

* `WorkspaceModel` is testable without a running Qt application
* Persistence (`to_dict`/`from_dict`) is straightforward
* Multiple UI views can subscribe to the same model
* Undo/redo via QUndoCommand operates on the model, not on graphics items
* Headless validation, batch processing, and CLI tools become feasible later

### Negative

* Two layers of state to keep in sync (model + UI)
* Slot wiring boilerplate
* AI agents must consciously route mutations through commands, not direct UI manipulation

### Risks

* UI may drift out of sync with model if signals are missed
* Mitigation: model emits signals on every mutation; UI is a pure consumer; tests cover both layers

## Related ADRs

- ADR-002 Hybrid ULID Identity Model
- ADR-005 Command Stack with QUndoStack

## References

- `02_workspace_requirements.md` §3 (Source of Truth Rule), §4 (Signals), §25 (Commands)
- `06_data_flow_and_architecture.md` §4.2, §13
- `09_coding_standards.md` §10 (PySide6 Conventions)
