"""RemoveIOOutputCommand: remove an IOEntry from IOSelection.outputs.

Structural twin of `RemoveIOInputCommand` — different bucket
(`outputs`).
"""

from __future__ import annotations

from dataclasses import replace as _replace
from typing import TYPE_CHECKING

from .configuration_command_stack import ConfigurationCommand

if TYPE_CHECKING:
    from features.ControllerDesignModule.model.configuration_model import (
        ConfigurationModel,
    )
    from features.ControllerDesignModule.model.io_selection import IOEntry


class RemoveIOOutputCommand(ConfigurationCommand):
    """Remove the output `IOEntry` with the given id.

    Args:
        model: The `ConfigurationModel` to mutate.
        entry_id: `ioout_<ULID>` of the output to remove.

    Raises:
        KeyError: No output with `entry_id` exists in the model.
    """

    def __init__(
        self,
        model: ConfigurationModel,
        entry_id: str,
    ) -> None:
        """Validate and capture the removed entry + position."""
        entry: IOEntry | None = next(
            (e for e in model.io_selection.outputs if e.id == entry_id), None
        )
        if entry is None:
            raise KeyError(entry_id)
        super().__init__(model, f"Remove output {entry.display_name or entry.id!r}")
        self._entry_id = entry_id
        self._captured_entry: IOEntry = entry
        self._original_index: int = next(
            i for i, e in enumerate(model.io_selection.outputs) if e.id == entry_id
        )

    @property
    def entry_id(self) -> str:
        """The id of the entry this command removes (test convenience)."""
        return self._entry_id

    def redo(self) -> None:  # noqa: D102 — QUndoCommand override
        self._model.set_io_selection(self._model.io_selection.with_output_removed(self._entry_id))

    def undo(self) -> None:  # noqa: D102 — QUndoCommand override
        current = self._model.io_selection
        outputs = list(current.outputs)
        outputs.insert(self._original_index, self._captured_entry)
        self._model.set_io_selection(_replace(current, outputs=tuple(outputs)))


__all__ = ["RemoveIOOutputCommand"]
