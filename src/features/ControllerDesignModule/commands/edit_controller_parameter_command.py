"""EditControllerParameterCommand: change one scalar parameter value.

Spec §5.4: parameters are `kp`/`ki`/`kd` in Phase 1, typed as
scalar floats (decision K1 from the S2.A pre-scan). This command
updates a single key on the controller's `parameters` dict by
producing a new `ControllerSpec` value.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .configuration_command_stack import ConfigurationCommand

if TYPE_CHECKING:
    from features.ControllerDesignModule.model.configuration_model import (
        ConfigurationModel,
    )


class EditControllerParameterCommand(ConfigurationCommand):
    """Set a single scalar parameter on a controller.

    Captures the prior value (or the absence flag) so `undo()`
    restores the exact pre-edit state. Phase-1 keys: `kp`, `ki`,
    `kd`. Future MIMO / discrete-time keys flow through this same
    command; the value type is widened in S2.D's K1 follow-up if
    needed.

    Args:
        model: The `ConfigurationModel` to mutate.
        controller_id: `ctrl_<ULID>` identifying the controller.
        param_name: Parameter key (e.g., `"kp"`).
        new_value: New scalar value.

    Raises:
        KeyError: No controller with `controller_id` exists.
    """

    _ABSENT = object()

    def __init__(
        self,
        model: ConfigurationModel,
        controller_id: str,
        param_name: str,
        new_value: float,
    ) -> None:
        """Capture prior parameter state for clean undo."""
        spec = next(
            (c for c in model.controller_settings.controllers if c.id == controller_id),
            None,
        )
        if spec is None:
            raise KeyError(controller_id)
        super().__init__(
            model,
            f"Edit {spec.display_name or spec.id!r}.{param_name}",
        )
        self._controller_id = controller_id
        self._param_name = param_name
        self._new_value = float(new_value)
        if param_name in spec.parameters:
            self._old_value: float | object = spec.parameters[param_name]
            self._existed_before: bool = True
        else:
            self._old_value = self._ABSENT
            self._existed_before = False

    def redo(self) -> None:  # noqa: D102 — QUndoCommand override
        self._apply_parameter(self._param_name, self._new_value, present=True)

    def undo(self) -> None:  # noqa: D102 — QUndoCommand override
        if self._existed_before:
            # `_existed_before` flag carries the present/absent
            # information; `_old_value` is a captured float in this
            # branch (the sentinel is only stored when
            # `_existed_before` is False).
            assert self._old_value is not self._ABSENT
            self._apply_parameter(
                self._param_name,
                float(self._old_value),  # type: ignore[arg-type]
                present=True,
            )
        else:
            self._apply_parameter(self._param_name, 0.0, present=False)

    def _apply_parameter(self, key: str, value: float, *, present: bool) -> None:
        current = self._model.controller_settings
        spec = next(c for c in current.controllers if c.id == self._controller_id)
        new_params = dict(spec.parameters)
        if present:
            new_params[key] = value
        else:
            new_params.pop(key, None)
        self._model.set_controller_settings(
            current.with_controller_replaced(spec.with_updated(parameters=new_params))
        )


__all__ = ["EditControllerParameterCommand"]
