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
* `MoveComponentCommand` — S1.7.2
* `RotateComponentCommand` — S1.7.2
* `ChangeParameterCommand` — S1.7.2
* `DeleteComponentCommand` — S1.7.3 (with connection cascade)
* `AddConnectionCommand` — S1.7.4 (calls GraphValidator first)
* `DeleteConnectionCommand` — S1.7.4
* `ModifyConnectionCommand` — S1.7.4
* `PasteSelectionCommand` — S1.7.5 (macro)

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
from .workspace_command_stack import WorkspaceCommand, WorkspaceCommandStack

__all__ = [
    "AddComponentCommand",
    "WorkspaceCommand",
    "WorkspaceCommandStack",
]
