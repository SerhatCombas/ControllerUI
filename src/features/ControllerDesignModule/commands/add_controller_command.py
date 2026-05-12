"""AddControllerCommand: append a new ControllerSpec to ControllerSettings.

Parallels `SystemModelingModule.AddComponentCommand` in shape:
captured-state pattern, validation in `__init__`, single setter
push in `redo()` / `undo()`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from features.ControllerDesignModule.model.id_generator import is_controller_id

from .configuration_command_stack import ConfigurationCommand

if TYPE_CHECKING:
    from features.ControllerDesignModule.model.configuration_model import (
        ConfigurationModel,
    )
    from features.ControllerDesignModule.model.controller_settings import (
        ControllerSpec,
    )


class AddControllerCommand(ConfigurationCommand):
    """Add a `ControllerSpec` to the model's `ControllerSettings.controllers` list.

    Args:
        model: The `ConfigurationModel` to mutate.
        spec: The fully-formed `ControllerSpec` to append. Must
            carry a `ctrl_<ULID>` id; callers typically build it
            with `new_controller_id()` from
            `features.ControllerDesignModule.model.id_generator`.

    Raises:
        ValueError: `spec.id` does not match the `ctrl_<ULID>`
            shape. Validation runs in `__init__` per the
            ConfigurationCommand contract — the stack push never
            sees a malformed command.
        KeyError: A controller with the same id already exists in
            the model. Add-then-add-same-id is a caller bug, not a
            no-op.
    """

    def __init__(
        self,
        model: ConfigurationModel,
        spec: ControllerSpec,
    ) -> None:
        """Validate and capture the new controller for later redo cycles."""
        if not is_controller_id(spec.id):
            raise ValueError(f"AddControllerCommand expected a ctrl_<ULID> id; got {spec.id!r}")
        if any(c.id == spec.id for c in model.controller_settings.controllers):
            raise KeyError(spec.id)
        super().__init__(model, f"Add controller {spec.display_name or spec.id!r}")
        self._spec = spec

    @property
    def controller_id(self) -> str:
        """The id of the controller this command adds (test convenience)."""
        return self._spec.id

    def redo(self) -> None:  # noqa: D102 — QUndoCommand override
        self._model.set_controller_settings(
            self._model.controller_settings.with_controller_added(self._spec)
        )

    def undo(self) -> None:  # noqa: D102 — QUndoCommand override
        self._model.set_controller_settings(
            self._model.controller_settings.with_controller_removed(self._spec.id)
        )


__all__ = ["AddControllerCommand"]
