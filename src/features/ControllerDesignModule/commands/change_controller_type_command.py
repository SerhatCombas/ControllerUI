"""ChangeControllerTypeCommand: switch a controller's `controller_type`.

Spec §5.6: changing `controller_type` preserves common parameters
(e.g., `kp` survives PID → PI). The dataclass already keeps unused
keys per S2.A — this command just replaces the type label and
delegates the parameter-retention behavior to the value-type's
existing semantics.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .configuration_command_stack import ConfigurationCommand

if TYPE_CHECKING:
    from features.ControllerDesignModule.model.configuration_model import (
        ConfigurationModel,
    )


class ChangeControllerTypeCommand(ConfigurationCommand):
    """Change the `controller_type` on an existing controller.

    The previous type is captured in `__init__` for clean undo.
    Parameters are preserved verbatim per spec §5.6; the validator
    surfaces unused-key warnings at S2.B.2 if the type changes the
    canonical parameter set.

    Args:
        model: The `ConfigurationModel` to mutate.
        controller_id: `ctrl_<ULID>` identifying the controller.
        new_type: The new `controller_type` label (e.g., `"PI"`).
            `str` rather than `Literal` so unknown future types
            also flow through this command for forward-compat
            round-trip safety.

    Raises:
        KeyError: No controller with `controller_id` exists.
    """

    def __init__(
        self,
        model: ConfigurationModel,
        controller_id: str,
        new_type: str,
    ) -> None:
        """Capture the prior type and stage the new value."""
        spec = next(
            (c for c in model.controller_settings.controllers if c.id == controller_id),
            None,
        )
        if spec is None:
            raise KeyError(controller_id)
        super().__init__(
            model, f"Change controller {spec.display_name or spec.id!r} type to {new_type}"
        )
        self._controller_id = controller_id
        self._new_type = new_type
        self._old_type = spec.controller_type

    def redo(self) -> None:  # noqa: D102 — QUndoCommand override
        self._apply_type(self._new_type)

    def undo(self) -> None:  # noqa: D102 — QUndoCommand override
        self._apply_type(self._old_type)

    def _apply_type(self, controller_type: str) -> None:
        current = self._model.controller_settings
        spec = next(c for c in current.controllers if c.id == self._controller_id)
        self._model.set_controller_settings(
            current.with_controller_replaced(spec.with_updated(controller_type=controller_type))
        )


__all__ = ["ChangeControllerTypeCommand"]
