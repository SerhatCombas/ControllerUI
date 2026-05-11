"""QUndoCommand subclasses for workspace editing.

Every user action that mutates `WorkspaceModel` must go through a
command in this package. UI code creates commands and pushes them to
`WorkspaceCommandStack` (the per-document wrapper around
`QUndoStack`); commands call `WorkspaceModel` methods.

Stack placement (decision B from the S1.7 planning thread): the
`QUndoStack` lives on `WorkspaceCommandStack`, NOT on
`WorkspaceModel`. The model stays Qt-undo-agnostic — same separation
of concerns rationale as ADR-003.

Phase 1 commands (populated incrementally across S1.7.x):

* `AddComponentCommand` — S1.7.1 ✓
* `MoveComponentCommand` — S1.7.2 ✓
* `RotateComponentCommand` — S1.7.2 ✓
* `ChangeParameterCommand` — S1.7.2 ✓
* `DeleteComponentCommand` — S1.7.3 ✓ (with connection cascade)
* `AddConnectionCommand` — S1.7.4 ✓ (calls GraphValidator; raises
  `ConnectionValidationError` on error-severity issues; exposes
  warning issues via `command.warnings`)
* `DeleteConnectionCommand` — S1.7.4 ✓
* `ModifyConnectionCommand` — S1.7.4 ✓
* `PasteSelectionCommand` — S1.7.5 (macro)

Merge-defer note: S1.7.2 commands do not yet override
`QUndoCommand.mergeWith()` / `id()`; consecutive same-target
edits stack as N separate entries. Merge implementation is
parked behind a `TODO(S1.7.future)` in each command file and is
expected to land alongside the S1.9 UI drag handlers.

References:
----------
* ADR-005: Command Stack with QUndoStack
  (`decisions/ADR-005-command-stack-qundostack.md`)
* ADR-003: Workspace UI / data separation
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
    "RotateComponentCommand",
    "WorkspaceCommand",
    "WorkspaceCommandStack",
]
