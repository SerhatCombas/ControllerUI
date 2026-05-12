"""ChangePlotTypeCommand: switch a slot's plot_type, applying spec §8.7.

Delegates the §8.7 kind-change rule (preserve same-kind selection,
reset across-kind selection, preserve unknown plot_type) to the
S2.C `PlotSlotConfig.with_plot_type` value-type helper. The
command is a thin wrapper around the helper + the model's
`set_plot_layout` setter; the captured-state pattern preserves
the full prior slot for clean undo.

Mirror-sync: the resulting `set_plot_layout` call fires
`plotLayoutChanged` once, which both the Configuration panel
dropdown and the per-plot header dropdown subscribe to (ADR-017).
S2.D.3 also lands a multi-subscriber verification test.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .configuration_command_stack import ConfigurationCommand

if TYPE_CHECKING:
    from features.ControllerDesignModule.model.configuration_model import (
        ConfigurationModel,
    )
    from features.ControllerDesignModule.model.plot_layout import PlotSlotConfig


class ChangePlotTypeCommand(ConfigurationCommand):
    """Change the `plot_type` on a slot identified by `slot_id`.

    Args:
        model: The `ConfigurationModel` to mutate.
        slot_id: Free-form slot identifier (`"plot_1".."plot_4"` for
            Phase-1 defaults).
        new_plot_type: The new `plot_type` label (e.g., `"bode"`).
            `str` not `Literal` so unknown values round-trip per
            spec §12.2.

    Raises:
        KeyError: No slot with `slot_id` exists in the layout.
        ValueError: `new_plot_type` equals the slot's current
            plot_type — the resulting layout is value-equal,
            `set_plot_layout` would no-op, and the stack would
            carry a wasted undo slot.
    """

    def __init__(
        self,
        model: ConfigurationModel,
        slot_id: str,
        new_plot_type: str,
    ) -> None:
        """Locate the slot, capture the prior config, stage the new one."""
        slot: PlotSlotConfig | None = next(
            (s for s in model.plot_layout.slots if s.slot_id == slot_id), None
        )
        if slot is None:
            raise KeyError(slot_id)
        if slot.plot_type == new_plot_type:
            raise ValueError(
                f"ChangePlotTypeCommand: slot {slot_id!r} already has "
                f"plot_type {new_plot_type!r}; nothing to apply."
            )
        super().__init__(
            model,
            f"Change {slot_id} plot type to {new_plot_type}",
        )
        self._slot_id = slot_id
        self._old_slot: PlotSlotConfig = slot
        # Apply the §8.7 rule once at construction so `redo()` is a
        # plain replacement — keeps the per-redo cost cheap and the
        # final state deterministic regardless of mutation order.
        self._new_slot: PlotSlotConfig = slot.with_plot_type(new_plot_type)

    @property
    def slot_id(self) -> str:
        """The slot this command edits (test convenience)."""
        return self._slot_id

    def redo(self) -> None:  # noqa: D102 — QUndoCommand override
        self._model.set_plot_layout(self._model.plot_layout.with_slot_replaced(self._new_slot))

    def undo(self) -> None:  # noqa: D102 — QUndoCommand override
        self._model.set_plot_layout(self._model.plot_layout.with_slot_replaced(self._old_slot))


__all__ = ["ChangePlotTypeCommand"]
