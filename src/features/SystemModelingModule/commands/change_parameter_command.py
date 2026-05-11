"""ChangeParameterCommand: undoable parameter value change.

Per ADR-005 and spec/07 §7.12. Handles both the "update an
existing parameter" and "insert a new parameter" cases (per
`02 §11.3` an instance's parameters dict may be empty, in which
case the runtime uses the definition default — editing such a
parameter inserts the entry, and undoing the edit must REMOVE
the entry to return to the "use definition default" state).

Undo strategy (driven by what was present at construction time):

* **Param was present before**: undo calls
  `WorkspaceModel.set_parameter(component_id, param_name, old_value)`
  to restore the captured prior value.
* **Param was absent before**: undo calls
  `WorkspaceModel.unset_parameter(component_id, param_name)`
  (S1.7.2) to remove the entry the first redo inserted, so the
  instance reverts to the "use definition default" semantic.

Value-level validation against the `ParameterDefinition` (bounds,
enum membership, unit, type) is intentionally NOT enforced here —
that is Phase 1.5+ command-stack work and would block legitimate
project-load / copy-paste flows that round-trip user-edited values.

TODO(S1.7.future): Implement `QUndoCommand.mergeWith()` for
consecutive edits of the same `(component_id, param_name)` (a
live slider drag should land as one undoable command rather than
flooding the stack). Same merge rationale as
`MoveComponentCommand`.

References:
----------
* `decisions/ADR-005-command-stack-qundostack.md`
* `decisions/ADR-020-dirty-tracking-semantics.md`
* `decisions/ADR-021-builtin-component-definitions.md`
* `specs/02_workspace_requirements.md` §11.3, §11.4
* `specs/07_implementation_order.md` §7.12
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Final

from .workspace_command_stack import WorkspaceCommand

if TYPE_CHECKING:
    from features.SystemModelingModule.model.workspace_model import WorkspaceModel


# Sentinel used internally to distinguish "param was absent" from
# "param was present with value `None`". Stored on the command and
# never exposed to callers.
_ABSENT: Final[object] = object()


class ChangeParameterCommand(WorkspaceCommand):
    """Undoable parameter value change.

    Args:
        model: Target `WorkspaceModel`.
        component_id: `cmp_<ULID>` of the target component.
        param_name: Parameter id (matches `ParameterDefinition.id`
            when registered).
        new_value: Value to set. Type / bounds / enum validation
            against the `ParameterDefinition` is the Phase 1.5+
            command-layer's responsibility, not this command's.

    Raises:
        KeyError: `component_id` is not in the model.

    See Also:
        `WorkspaceModel.set_parameter` (S1.B.1e),
        `WorkspaceModel.unset_parameter` (S1.7.2),
        `ComponentInstance.parameters` (`02 §11.3` — empty means
        "use definition default at runtime").
    """

    def __init__(
        self,
        model: WorkspaceModel,
        component_id: str,
        param_name: str,
        new_value: Any,
    ) -> None:
        """Construct and capture the prior parameter state."""
        if component_id not in model.components:
            raise KeyError(component_id)
        current = model.components[component_id]
        label = current.display_name or "component"
        super().__init__(model, f"Change {label}.{param_name}")
        self._component_id = component_id
        self._param_name = param_name
        self._new_value = new_value
        # Capture prior state: presence flag + value (only meaningful
        # when present). This single capture point at __init__ avoids
        # the need to re-inspect the model on undo.
        if param_name in current.parameters:
            self._old_value: Any = current.parameters[param_name]
            self._existed_before: bool = True
        else:
            self._old_value = _ABSENT
            self._existed_before = False

    @property
    def component_id(self) -> str:
        """Target component id (test convenience)."""
        return self._component_id

    @property
    def param_name(self) -> str:
        """Target parameter id (test convenience)."""
        return self._param_name

    @property
    def existed_before(self) -> bool:
        """True when the parameter was present prior to first redo."""
        return self._existed_before

    def redo(self) -> None:
        """Set the parameter to `new_value`."""
        self._model.set_parameter(self._component_id, self._param_name, self._new_value)

    def undo(self) -> None:
        """Restore the prior parameter state.

        When the parameter existed before the edit, restore its
        previous value. When the parameter was absent, remove the
        entry so the instance reverts to the "use definition default
        at runtime" semantic per `02 §11.3`.
        """
        if self._existed_before:
            self._model.set_parameter(self._component_id, self._param_name, self._old_value)
        else:
            self._model.unset_parameter(self._component_id, self._param_name)


__all__ = ["ChangeParameterCommand"]
