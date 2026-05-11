"""QUndoCommand subclasses for workspace editing.

Every user action that mutates `WorkspaceModel` must go through a
command in this package. UI code creates commands and pushes them to
`WorkspaceCommandStack` (the per-document wrapper around
`QUndoStack`); commands call `WorkspaceModel` methods.

Stack placement (decision B from the S1.7 planning thread): the
`QUndoStack` lives on `WorkspaceCommandStack`, NOT on
`WorkspaceModel`. The model stays Qt-undo-agnostic — same separation
of concerns rationale as ADR-003.

Dirty-bit binding (decision A2; S1.7.5): the stack's
`cleanChanged` signal is wired to `WorkspaceModel._set_dirty` /
`_clear_dirty` per ADR-020 §"QUndoStack integration". The binding
is additive — direct-mutation calls into the model still drive
the dirty bit via the mutation-path branch, and the
transition-only rule in the helpers keeps redundant fires
idempotent.

Phase 1 commands (all S1.7 sub-commits complete):

* `AddComponentCommand` — S1.7.1 ✓ (captured-instance pattern;
  registry-required)
* `MoveComponentCommand` — S1.7.2 ✓
* `RotateComponentCommand` — S1.7.2 ✓ (Phase-1 grid validation
  at `__init__`)
* `ChangeParameterCommand` — S1.7.2 ✓ (two-branch undo handles
  the "param was absent before" case via `unset_parameter`)
* `DeleteComponentCommand` — S1.7.3 ✓ (with connection cascade
  inside a single `model.batch()`)
* `AddConnectionCommand` — S1.7.4 ✓ (calls `GraphValidator`;
  raises `ConnectionValidationError` on error severity; exposes
  warning issues via `command.warnings`)
* `DeleteConnectionCommand` — S1.7.4 ✓
* `ModifyConnectionCommand` — S1.7.4 ✓ (all-None invocation
  raises `ValueError`)
* `PasteSelectionCommand` — S1.7.5 ✓ (multi-entity compound;
  fresh ids on first redo, restore-verbatim on replay; silent
  half-orphan skip with `skipped_connection_count` exposed)

Merge-defer note: S1.7.x commands do not yet override
`QUndoCommand.mergeWith()` / `id()`; consecutive same-target
edits stack as N separate entries. Merge implementation is
parked behind a `TODO(S1.7.future)` in the affected command
files (Move, Rotate, ChangeParameter) and is expected to land
alongside the S1.9 UI drag handlers where intermediate edits
start appearing.

Custom exceptions:

* `ConnectionValidationError(ValueError)` — raised by
  `AddConnectionCommand.__init__` when `GraphValidator` flags
  error-severity issues. Carries the full `ValidationReport`
  on `.report` for granular UI handling; subclasses `ValueError`
  for generic catch.

References:
----------
* ADR-005: Command Stack with QUndoStack
  (`decisions/ADR-005-command-stack-qundostack.md`)
* ADR-003: Workspace UI / data separation
* ADR-020: Dirty-tracking semantics (cleanChanged binding)
* `specs/02_workspace_requirements.md` §25 (Command Stack)
* `specs/07_implementation_order.md` §7.12
* `specs/09_coding_standards.md` §7.2.4 (Command naming)
"""

from .add_component_command import AddComponentCommand
from .add_connection_command import AddConnectionCommand, ConnectionValidationError
from .change_parameter_command import ChangeParameterCommand
from .delete_component_command import DeleteComponentCommand
from .delete_connection_command import DeleteConnectionCommand
from .modify_connection_command import ModifyConnectionCommand
from .move_component_command import MoveComponentCommand
from .paste_selection_command import PasteSelectionCommand
from .rotate_component_command import RotateComponentCommand
from .workspace_command_stack import WorkspaceCommand, WorkspaceCommandStack

__all__ = [
    "AddComponentCommand",
    "AddConnectionCommand",
    "ChangeParameterCommand",
    "ConnectionValidationError",
    "DeleteComponentCommand",
    "DeleteConnectionCommand",
    "ModifyConnectionCommand",
    "MoveComponentCommand",
    "PasteSelectionCommand",
    "RotateComponentCommand",
    "WorkspaceCommand",
    "WorkspaceCommandStack",
]
