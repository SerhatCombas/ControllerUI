"""ChangePlotTitleCommand: rename a plot slot's user-visible title."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .configuration_command_stack import ConfigurationCommand

if TYPE_CHECKING:
    from features.ControllerDesignModule.model.configuration_model import (
        ConfigurationModel,
    )
    from features.ControllerDesignModule.model.plot_layout import PlotSlotConfig


class ChangePlotTitleCommand(ConfigurationCommand):
    """Change a plot slot's `title` field.

    Args:
        model: The `ConfigurationModel` to mutate.
        slot_id: Free-form slot identifier.
        new_title: The new title text. Empty string is allowed
            (defaults back to a system-generated label in the UI).

    Raises:
        KeyError: No slot with `slot_id` exists.
        ValueError: `new_title` equals the slot's current title —
            keeps no-op commands off the stack.
    """

    def __init__(
        self,
        model: ConfigurationModel,
        slot_id: str,
        new_title: str,
    ) -> None:
        """Locate the slot, capture the prior title, stage the new one."""
        slot: PlotSlotConfig | None = next(
            (s for s in model.plot_layout.slots if s.slot_id == slot_id), None
        )
        if slot is None:
            raise KeyError(slot_id)
        if slot.title == new_title:
            raise ValueError(
                f"ChangePlotTitleCommand: slot {slot_id!r} already has "
                f"title {new_title!r}; nothing to apply."
            )
        super().__init__(model, f"Rename {slot_id} title to {new_title!r}")
        self._slot_id = slot_id
        self._old_title = slot.title
        self._new_title = new_title

    @property
    def slot_id(self) -> str:
        """The slot this command edits (test convenience)."""
        return self._slot_id

    def redo(self) -> None:  # noqa: D102 — QUndoCommand override
        self._apply_title(self._new_title)

    def undo(self) -> None:  # noqa: D102 — QUndoCommand override
        self._apply_title(self._old_title)

    def _apply_title(self, title: str) -> None:
        current = self._model.plot_layout
        slot = next(s for s in current.slots if s.slot_id == self._slot_id)
        self._model.set_plot_layout(current.with_slot_replaced(slot.with_updated(title=title)))


__all__ = ["ChangePlotTitleCommand"]
