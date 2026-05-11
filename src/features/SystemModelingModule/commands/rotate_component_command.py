"""RotateComponentCommand: undoable component rotation change.

Per ADR-005 and spec/07 §7.12. Captures the old rotation from the
model at construction time, applies the new rotation via
`WorkspaceModel.rotate_component` on `redo()`, and restores the
captured old rotation on `undo()`.

Phase-1 rotation quantization (`02 §22` / `02 §23` and ADR-018)
restricts the angle to `{0.0, 90.0, 180.0, 270.0}`. The
`WorkspaceModel.rotate_component` path canonicalizes via
`_canonical_rotation` and raises `ValueError` for off-grid values;
this command pre-validates the same way in `__init__` so a
malformed command never lands on the undo stack.

TODO(S1.7.future): Implement `QUndoCommand.mergeWith()` for
consecutive rotations of the same component (same merge rationale
as `MoveComponentCommand`).

References:
----------
* `decisions/ADR-005-command-stack-qundostack.md`
* `decisions/ADR-018-signal-payload-contracts.md`
* `specs/02_workspace_requirements.md` §22 (Move/Delete), §23
  (Rotation)
* `specs/07_implementation_order.md` §7.12
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Final

from .workspace_command_stack import WorkspaceCommand

if TYPE_CHECKING:
    from features.SystemModelingModule.model.workspace_model import WorkspaceModel


# Phase-1 valid angles per `02 §22` / `02 §23`. Mirrors the
# `_VALID_ROTATIONS` constant in workspace_model.py; duplicated
# here so the command layer can pre-validate without poking at the
# model module's private constant.
_VALID_ROTATIONS: Final[tuple[float, ...]] = (0.0, 90.0, 180.0, 270.0)
# ε per ADR-020.
_EPSILON: Final[float] = 1e-6


def _is_valid_rotation(angle: float) -> bool:
    """Return True if `angle` is within ε of a Phase-1 valid rotation."""
    return any(math.isclose(angle, valid, abs_tol=_EPSILON) for valid in _VALID_ROTATIONS)


class RotateComponentCommand(WorkspaceCommand):
    """Undoable component rotation change.

    Args:
        model: Target `WorkspaceModel`.
        component_id: `cmp_<ULID>` of the component to rotate.
        new_rotation: Target rotation in degrees. Phase 1 restricts
            the value to `{0.0, 90.0, 180.0, 270.0}` per `02 §22` /
            `02 §23` (ε-tolerant).

    Raises:
        KeyError: `component_id` is not in the model.
        ValueError: `new_rotation` is off-grid.

    See Also:
        `WorkspaceModel.rotate_component`.
    """

    def __init__(
        self,
        model: WorkspaceModel,
        component_id: str,
        new_rotation: float,
    ) -> None:
        """Construct and capture the pre-rotation angle."""
        if component_id not in model.components:
            raise KeyError(component_id)
        if not _is_valid_rotation(new_rotation):
            raise ValueError(f"rotation must be one of {_VALID_ROTATIONS}, got {new_rotation}")
        current = model.components[component_id]
        label = current.display_name or "component"
        super().__init__(model, f"Rotate {label}")
        self._component_id = component_id
        self._old_rotation = float(current.rotation)
        self._new_rotation = float(new_rotation)

    @property
    def component_id(self) -> str:
        """Target component id (test convenience)."""
        return self._component_id

    @property
    def old_rotation(self) -> float:
        """Pre-rotation angle captured at construction (test convenience)."""
        return self._old_rotation

    @property
    def new_rotation(self) -> float:
        """Target rotation (test convenience)."""
        return self._new_rotation

    def redo(self) -> None:
        """Apply the rotation to `new_rotation`."""
        self._model.rotate_component(self._component_id, self._new_rotation)

    def undo(self) -> None:
        """Restore the captured `old_rotation`."""
        self._model.rotate_component(self._component_id, self._old_rotation)


__all__ = ["RotateComponentCommand"]
