"""RemoveControllerCommand: remove a ControllerSpec from ControllerSettings."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .configuration_command_stack import ConfigurationCommand

if TYPE_CHECKING:
    from features.ControllerDesignModule.model.configuration_model import (
        ConfigurationModel,
    )
    from features.ControllerDesignModule.model.controller_settings import (
        ControllerSpec,
    )


class RemoveControllerCommand(ConfigurationCommand):
    """Remove the `ControllerSpec` with the given id.

    Captures the removed spec in `__init__` so `undo()` can restore
    the exact pre-removal value (display_name, parameters, refs,
    everything). The capture happens before mutation so undo
    survives even if other state changes between push and undo.

    Args:
        model: The `ConfigurationModel` to mutate.
        controller_id: `ctrl_<ULID>` of the controller to remove.

    Raises:
        KeyError: No controller with `controller_id` exists at the
            time of construction.
    """

    def __init__(
        self,
        model: ConfigurationModel,
        controller_id: str,
    ) -> None:
        """Validate and capture the removed controller."""
        spec = next(
            (c for c in model.controller_settings.controllers if c.id == controller_id),
            None,
        )
        if spec is None:
            raise KeyError(controller_id)
        super().__init__(model, f"Remove controller {spec.display_name or spec.id!r}")
        self._controller_id = controller_id
        # Capture position so undo restores at the same list index.
        self._captured_spec: ControllerSpec = spec
        self._original_index: int = next(
            i for i, c in enumerate(model.controller_settings.controllers) if c.id == controller_id
        )

    @property
    def controller_id(self) -> str:
        """The id of the controller this command removes (test convenience)."""
        return self._controller_id

    def redo(self) -> None:  # noqa: D102 — QUndoCommand override
        current = self._model.controller_settings
        self._model.set_controller_settings(current.with_controller_removed(self._controller_id))

    def undo(self) -> None:  # noqa: D102 — QUndoCommand override
        current = self._model.controller_settings
        # Restore at the original index to preserve display order.
        controllers = list(current.controllers)
        controllers.insert(self._original_index, self._captured_spec)
        from dataclasses import replace as _replace

        self._model.set_controller_settings(_replace(current, controllers=tuple(controllers)))


__all__ = ["RemoveControllerCommand"]
