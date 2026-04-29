"""QUndoCommand subclasses for workspace editing.

Every user action that mutates `WorkspaceModel` must go through a
command in this package. UI code creates commands and pushes them to
`QUndoStack`; commands call `WorkspaceModel` methods.

Phase 1 commands (planned, populated during Stage S1):

* AddComponentCommand
* MoveComponentCommand
* RotateComponentCommand
* DeleteComponentCommand
* AddConnectionCommand
* DeleteConnectionCommand
* ModifyConnectionCommand
* ChangeParameterCommand
* PasteSelectionCommand

References
----------
* ADR-005: Command Stack with QUndoStack (`decisions/ADR-005-command-stack-qundostack.md`)
* `specs/02_workspace_requirements.md` §25
* `specs/09_coding_standards.md` §7.2.4 (Command naming)
"""

__all__: list[str] = []
