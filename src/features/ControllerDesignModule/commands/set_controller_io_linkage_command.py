"""SetControllerIOLinkageCommand: bind/unbind a controller's I/O refs."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .configuration_command_stack import ConfigurationCommand

if TYPE_CHECKING:
    from features.ControllerDesignModule.model.configuration_model import (
        ConfigurationModel,
    )


class SetControllerIOLinkageCommand(ConfigurationCommand):
    """Update a controller's `input_ref` / `output_ref` in one atomic action.

    Treats the (input_ref, output_ref) pair as a unit: changing
    only one of them is a separate command instance with the
    unchanged side passed as its current value. This matches the
    user's mental model — "set linkage" is one binding action,
    even if only one side is edited at a time, since
    `ConfigurationValidator` evaluates both refs together for the
    stale-linkage warning (spec §5.5).

    Passing `None` on either side clears that binding.

    Args:
        model: The `ConfigurationModel` to mutate.
        controller_id: `ctrl_<ULID>` identifying the controller.
        new_input_ref: `ioin_<ULID>` or `None`.
        new_output_ref: `ioout_<ULID>` or `None`.

    Raises:
        KeyError: No controller with `controller_id` exists.
    """

    def __init__(
        self,
        model: ConfigurationModel,
        controller_id: str,
        new_input_ref: str | None,
        new_output_ref: str | None,
    ) -> None:
        """Capture prior refs and stage the new values."""
        spec = next(
            (c for c in model.controller_settings.controllers if c.id == controller_id),
            None,
        )
        if spec is None:
            raise KeyError(controller_id)
        super().__init__(model, f"Set I/O linkage on {spec.display_name or spec.id!r}")
        self._controller_id = controller_id
        self._new_input_ref = new_input_ref
        self._new_output_ref = new_output_ref
        self._old_input_ref = spec.input_ref
        self._old_output_ref = spec.output_ref

    def redo(self) -> None:  # noqa: D102 — QUndoCommand override
        self._apply_linkage(self._new_input_ref, self._new_output_ref)

    def undo(self) -> None:  # noqa: D102 — QUndoCommand override
        self._apply_linkage(self._old_input_ref, self._old_output_ref)

    def _apply_linkage(self, input_ref: str | None, output_ref: str | None) -> None:
        current = self._model.controller_settings
        spec = next(c for c in current.controllers if c.id == self._controller_id)
        self._model.set_controller_settings(
            current.with_controller_replaced(
                spec.with_updated(input_ref=input_ref, output_ref=output_ref)
            )
        )


__all__ = ["SetControllerIOLinkageCommand"]
