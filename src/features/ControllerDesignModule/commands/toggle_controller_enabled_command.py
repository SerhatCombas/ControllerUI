"""ToggleControllerEnabledCommand: flip a controller's `enabled` flag."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .configuration_command_stack import ConfigurationCommand

if TYPE_CHECKING:
    from features.ControllerDesignModule.model.configuration_model import (
        ConfigurationModel,
    )


class ToggleControllerEnabledCommand(ConfigurationCommand):
    """Flip the `enabled` boolean on a controller.

    Two-state command — `redo` applies the new value, `undo`
    restores the prior. Captured-state pattern.

    Args:
        model: The `ConfigurationModel` to mutate.
        controller_id: `ctrl_<ULID>` identifying the controller.
        new_enabled: The boolean to install.

    Raises:
        KeyError: No controller with `controller_id` exists.
    """

    def __init__(
        self,
        model: ConfigurationModel,
        controller_id: str,
        new_enabled: bool,
    ) -> None:
        """Capture prior state and stage the new value."""
        spec = next(
            (c for c in model.controller_settings.controllers if c.id == controller_id),
            None,
        )
        if spec is None:
            raise KeyError(controller_id)
        label = "Enable" if new_enabled else "Disable"
        super().__init__(model, f"{label} controller {spec.display_name or spec.id!r}")
        self._controller_id = controller_id
        self._new_enabled = bool(new_enabled)
        self._old_enabled = spec.enabled

    def redo(self) -> None:  # noqa: D102 — QUndoCommand override
        self._apply_enabled(self._new_enabled)

    def undo(self) -> None:  # noqa: D102 — QUndoCommand override
        self._apply_enabled(self._old_enabled)

    def _apply_enabled(self, enabled: bool) -> None:
        current = self._model.controller_settings
        spec = next(c for c in current.controllers if c.id == self._controller_id)
        self._model.set_controller_settings(
            current.with_controller_replaced(spec.with_updated(enabled=enabled))
        )


__all__ = ["ToggleControllerEnabledCommand"]
