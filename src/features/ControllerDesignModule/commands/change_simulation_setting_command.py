"""ChangeSimulationSettingCommand: replace SimulationSettings with a new value.

Single command class covering every field of SimulationSettings
(start_time, stop_time, sample_time, max_step, solver,
use_controller, use_last_valid_model, initial_conditions). The
caller produces the new value via
`SimulationSettings.with_updated(field=value, ...)` and passes it
in; the command captures the old value for undo.

Matches the `EditIOEntryCommand` precedent from S2.D.2: ADR-005
granularity stays per-user-action at the call site (one push per
edit gesture), without a class explosion across the 7+ fields
that SimulationSettings exposes.

Booleans (`use_controller`, `use_last_valid_model`) flow through
this same command — not their own toggle classes — because the
section is global (no entity id discriminator like
ToggleControllerEnabledCommand needs). Caller builds
`settings.with_updated(use_controller=False)` and pushes one
command.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .configuration_command_stack import ConfigurationCommand

if TYPE_CHECKING:
    from features.ControllerDesignModule.model.configuration_model import (
        ConfigurationModel,
    )
    from features.ControllerDesignModule.model.simulation_settings import (
        SimulationSettings,
    )


class ChangeSimulationSettingCommand(ConfigurationCommand):
    """Replace `SimulationSettings` with `new_settings`.

    Captures the prior value in `__init__` (the captured-state
    pattern) so `undo()` restores the exact pre-edit settings even
    if other commands have mutated the model in between.

    Args:
        model: The `ConfigurationModel` to mutate.
        new_settings: The fully-formed replacement value. Build it
            from `model.simulation_settings.with_updated(field=value)`
            on the caller side.

    Raises:
        ValueError: `new_settings` is value-equal to the current
            settings. A no-op command would still land on the
            QUndoStack and waste an undo slot; rejecting it at
            `__init__` keeps the stack tight per the
            captured-state pattern's "validate before push"
            rule.
    """

    def __init__(
        self,
        model: ConfigurationModel,
        new_settings: SimulationSettings,
    ) -> None:
        """Capture the prior settings and stage the new value."""
        current = model.simulation_settings
        if current == new_settings:
            raise ValueError(
                "ChangeSimulationSettingCommand received settings equal to the "
                "current value; nothing to apply."
            )
        super().__init__(model, "Change simulation settings")
        self._old_settings: SimulationSettings = current
        self._new_settings: SimulationSettings = new_settings

    @property
    def new_settings(self) -> SimulationSettings:
        """The replacement value (test convenience)."""
        return self._new_settings

    @property
    def old_settings(self) -> SimulationSettings:
        """The captured prior value (test convenience)."""
        return self._old_settings

    def redo(self) -> None:  # noqa: D102 — QUndoCommand override
        self._model.set_simulation_settings(self._new_settings)

    def undo(self) -> None:  # noqa: D102 — QUndoCommand override
        self._model.set_simulation_settings(self._old_settings)


__all__ = ["ChangeSimulationSettingCommand"]
