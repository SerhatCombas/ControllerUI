# ADR-005: Command Stack with QUndoStack

**Status:** Accepted  
**Date:** 2026-04-28  
**Deciders:** Serhat Combas  
**Stage:** S1  
**Supersedes:** —  
**Superseded by:** —

## Context

Every user action that mutates the workspace (add component, move, rotate, delete, connect, change parameter) must be undoable and redoable. The application also needs:

* command merging (e.g., consecutive small drags merged into one undo entry)
* command grouping (e.g., paste of multi-component selection as one undo)
* clean separation between user intent and model mutation

PySide6 provides `QUndoCommand` and `QUndoStack` natively. The alternatives are a custom command pattern, an immutable history snapshot, or no undo.

## Decision

The application uses **`QUndoStack`** with **`QUndoCommand`** subclasses for all user-initiated workspace mutations.

* every state-affecting user action is implemented as a `QUndoCommand` subclass
* commands live in `features/SystemModelingModule/commands/`
* command names end with `Command` (per `09 §7.2.4`)
* commands log on `redo()` (initial execution) and `undo()` at DEBUG level (per `10 §10.2`)
* the underlying `WorkspaceModel` methods do their own INFO logging; commands don't duplicate

UI input does **not** mutate `WorkspaceModel` directly. UI creates a command and pushes it to the undo stack:

```python
def on_drop(self, event):
    command = AddComponentCommand(
        self._workspace_model,
        definition_id=event.payload.definition_id,
        position=event.scene_pos,
    )
    self._undo_stack.push(command)
```

Command merging is allowed for sequential commands of the same type targeting the same entity (e.g., multi-frame drag becomes one undoable move). Merging is implemented via `QUndoCommand.mergeWith`.

## Alternatives Considered

### Alternative 1: Custom command pattern

Implement `Command` interface from scratch.

**Rejected because:**

* QUndoStack already provides merging, grouping, signals, command IDs, clean reset
* Reinventing duplicates well-tested Qt code

### Alternative 2: Immutable snapshot history

Save full model snapshots after every change.

**Rejected because:**

* Memory cost for large workspaces
* No native command merging
* Diffing for descriptive undo labels is complex

### Alternative 3: No undo

Defer undo/redo to Phase 2.

**Rejected because:**

* Undo is a baseline expectation in any visual editor
* Adding undo later requires retrofitting every mutation site

## Consequences

### Positive

* Native Qt support, no custom infrastructure
* Built-in command merging for drag/parameter-edit cases
* `QUndoView` available for debug/dev tooling
* Clear pattern for AI agents: "every mutation is a Command subclass"
* Tests can verify undo/redo round-trip per command class

### Negative

* Boilerplate: each mutation type needs a command class
* Merging logic must be written carefully to avoid silent state loss
* Commands hold references to model objects; lifecycle must be managed

### Risks

* Bypass risk: a contributor may mutate the model directly without a command
* Mitigation: `WorkspaceModel`'s public mutation methods are the only way to mutate; tests verify that direct mutations from UI tests through the model do not occur outside commands

## Related ADRs

- ADR-003 Workspace UI/Data Separation

## References

- `02_workspace_requirements.md` §25 (Commands)
- `06_data_flow_and_architecture.md` §4.2 (SystemModelingModule responsibilities)
- `09_coding_standards.md` §7.2.4 (Command naming)
- `10_logging_conventions.md` §10.2 (Command logging)
