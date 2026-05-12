"""EditIOEntryCommand: replace one IOEntry with a new version.

Single command class covering all per-entry edits (display_name,
quantity, unit, source, variable, status changes). The caller
builds the new entry via `entry.with_updated(field=value, ...)`
and passes it in; the command captures the pre-edit value for
clean undo.

ADR-005 granularity is satisfied at the caller level: each
user action (one text-field commit, one dropdown change)
constructs one `EditIOEntryCommand` with the single delta
applied. Multi-field user actions (rare) bundle their fields
into one `with_updated` call and push a single command — which
is correct undo granularity since it's one user gesture.

The command auto-detects whether the entry lives in `inputs` or
`outputs` based on its id prefix. The model's `IOSelection` does
not allow the same id in both buckets, so the lookup is
unambiguous.
"""

from __future__ import annotations

from dataclasses import replace as _replace
from typing import TYPE_CHECKING

from .configuration_command_stack import ConfigurationCommand

if TYPE_CHECKING:
    from features.ControllerDesignModule.model.configuration_model import (
        ConfigurationModel,
    )
    from features.ControllerDesignModule.model.io_selection import IOEntry, IOSelection


class EditIOEntryCommand(ConfigurationCommand):
    """Replace an IOEntry (in either inputs or outputs) with a new version.

    Args:
        model: The `ConfigurationModel` to mutate.
        new_entry: The fully-formed `IOEntry` to install. The
            command looks up the entry to replace by `new_entry.id`
            (in either bucket) and captures the prior value for
            undo. The caller is responsible for producing
            `new_entry` from the current one via
            `entry.with_updated(field=value)`.

    Raises:
        KeyError: No entry with `new_entry.id` exists in either
            `inputs` or `outputs`.
    """

    def __init__(
        self,
        model: ConfigurationModel,
        new_entry: IOEntry,
    ) -> None:
        """Locate the current entry, capture it, stage the new value."""
        bucket, idx, current_entry = _locate_entry(model.io_selection, new_entry.id)
        super().__init__(model, f"Edit IO entry {new_entry.display_name or new_entry.id!r}")
        self._bucket = bucket  # "inputs" | "outputs"
        self._index = idx
        self._old_entry: IOEntry = current_entry
        self._new_entry: IOEntry = new_entry

    @property
    def entry_id(self) -> str:
        """The id of the entry this command edits (test convenience)."""
        return self._new_entry.id

    @property
    def bucket(self) -> str:
        """The bucket name (`"inputs"` or `"outputs"`) the entry lives in."""
        return self._bucket

    def redo(self) -> None:  # noqa: D102 — QUndoCommand override
        self._apply(self._new_entry)

    def undo(self) -> None:  # noqa: D102 — QUndoCommand override
        self._apply(self._old_entry)

    def _apply(self, entry: IOEntry) -> None:
        current = self._model.io_selection
        if self._bucket == "inputs":
            new_list = list(current.inputs)
            new_list[self._index] = entry
            self._model.set_io_selection(_replace(current, inputs=tuple(new_list)))
        else:
            new_list = list(current.outputs)
            new_list[self._index] = entry
            self._model.set_io_selection(_replace(current, outputs=tuple(new_list)))


def _locate_entry(io_selection: IOSelection, entry_id: str) -> tuple[str, int, IOEntry]:
    """Find an entry by id across both buckets.

    Returns `(bucket_name, index, entry)`. Raises `KeyError` when
    no entry matches. Captures the bucket so undo restores the
    entry in the correct list.
    """
    for i, entry in enumerate(io_selection.inputs):
        if entry.id == entry_id:
            return "inputs", i, entry
    for i, entry in enumerate(io_selection.outputs):
        if entry.id == entry_id:
            return "outputs", i, entry
    raise KeyError(entry_id)


__all__ = ["EditIOEntryCommand"]
