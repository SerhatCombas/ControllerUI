"""ToggleFullscreenCommand: set or clear `PlotLayout.fullscreen_slot_id`.

Spec §8.9 lists fullscreen toggle as transient view state with
optional persistence (project view state per `02 §29.6`). When
the toggle IS persisted, it flows through this command so undo
restores the previous fullscreen target. When the toggle is
transient (the common Phase-1 case), the UI may call
`model.set_plot_layout(layout.with_fullscreen(slot_id))` directly
without the stack — that's a UI-side policy decision, not a model
constraint.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .configuration_command_stack import ConfigurationCommand

if TYPE_CHECKING:
    from features.ControllerDesignModule.model.configuration_model import (
        ConfigurationModel,
    )


class ToggleFullscreenCommand(ConfigurationCommand):
    """Set `PlotLayout.fullscreen_slot_id` to the given value.

    Passing `None` clears the fullscreen state. Passing a slot id
    sets that slot fullscreen (any prior fullscreen slot is
    captured for clean undo).

    Args:
        model: The `ConfigurationModel` to mutate.
        new_fullscreen_slot_id: Target slot id, or `None` to
            clear. When set to a slot id, that id must exist in
            the layout (otherwise the fullscreen state would
            reference nothing; the validator surfaces such
            dangling state in later stages).

    Raises:
        KeyError: `new_fullscreen_slot_id` is non-None but no slot
            with that id exists in the layout.
        ValueError: `new_fullscreen_slot_id` equals the current
            `fullscreen_slot_id` — no-op commands stay off the
            stack.
    """

    def __init__(
        self,
        model: ConfigurationModel,
        new_fullscreen_slot_id: str | None,
    ) -> None:
        """Validate, capture prior fullscreen state, stage the new value."""
        current = model.plot_layout
        if new_fullscreen_slot_id is not None and not any(
            s.slot_id == new_fullscreen_slot_id for s in current.slots
        ):
            raise KeyError(new_fullscreen_slot_id)
        if current.fullscreen_slot_id == new_fullscreen_slot_id:
            label = "fullscreen" if new_fullscreen_slot_id else "no fullscreen"
            raise ValueError(
                f"ToggleFullscreenCommand: layout already in {label!r}; " f"nothing to apply."
            )
        target_label = (
            f"fullscreen {new_fullscreen_slot_id}" if new_fullscreen_slot_id else "exit fullscreen"
        )
        super().__init__(model, f"Plot {target_label}")
        self._new_fullscreen = new_fullscreen_slot_id
        self._old_fullscreen = current.fullscreen_slot_id

    def redo(self) -> None:  # noqa: D102 — QUndoCommand override
        self._model.set_plot_layout(self._model.plot_layout.with_fullscreen(self._new_fullscreen))

    def undo(self) -> None:  # noqa: D102 — QUndoCommand override
        self._model.set_plot_layout(self._model.plot_layout.with_fullscreen(self._old_fullscreen))


__all__ = ["ToggleFullscreenCommand"]
