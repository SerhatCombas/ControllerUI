"""AddIOInputCommand: append a new IOEntry to IOSelection.inputs."""

from __future__ import annotations

from typing import TYPE_CHECKING

from features.ControllerDesignModule.model.id_generator import is_io_input_id

from .configuration_command_stack import ConfigurationCommand

if TYPE_CHECKING:
    from features.ControllerDesignModule.model.configuration_model import (
        ConfigurationModel,
    )
    from features.ControllerDesignModule.model.io_selection import IOEntry


class AddIOInputCommand(ConfigurationCommand):
    """Append an `IOEntry` to the model's `IOSelection.inputs` list.

    Args:
        model: The `ConfigurationModel` to mutate.
        entry: The fully-formed `IOEntry` to append. Must carry a
            `ioin_<ULID>` id; callers typically build it with
            `new_io_input_id()`.

    Raises:
        ValueError: `entry.id` does not match the `ioin_<ULID>`
            shape. Validated at `__init__` per the
            `ConfigurationCommand` contract.
        KeyError: An input with the same id already exists.
    """

    def __init__(
        self,
        model: ConfigurationModel,
        entry: IOEntry,
    ) -> None:
        """Validate and capture the new entry for later redo cycles."""
        if not is_io_input_id(entry.id):
            raise ValueError(f"AddIOInputCommand expected an ioin_<ULID> id; got {entry.id!r}")
        if any(e.id == entry.id for e in model.io_selection.inputs):
            raise KeyError(entry.id)
        super().__init__(model, f"Add input {entry.display_name or entry.id!r}")
        self._entry = entry

    @property
    def entry_id(self) -> str:
        """The id of the entry this command adds (test convenience)."""
        return self._entry.id

    def redo(self) -> None:  # noqa: D102 — QUndoCommand override
        self._model.set_io_selection(self._model.io_selection.with_input_added(self._entry))

    def undo(self) -> None:  # noqa: D102 — QUndoCommand override
        self._model.set_io_selection(self._model.io_selection.with_input_removed(self._entry.id))


__all__ = ["AddIOInputCommand"]
