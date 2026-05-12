"""Simulation settings dataclasses (S2.A scaffold).

Per spec/03 §7 and the S2 sub-commit plan. Phase 1 stores and
round-trips the schema; numeric validation (spec §7.3) and
execution belong to later stages.

The dataclass family:

* `InitialConditionOverride` — Phase-1 placeholder for the
  override-entry structure described in spec §7.4. Field names
  (`component_id`, `parameter_id`, `value`) are explicit in the
  spec; defining the dataclass now avoids a Phase-2 schema
  migration.
* `InitialConditions` — wrapper carrying the `source` discriminator
  (`component_parameters` or `explicit_overrides`) and the
  `overrides` tuple.
* `SimulationSettings` — top-level settings carrying numeric
  bounds, solver id, controller / model-snapshot flags, the
  initial-conditions container, plus the standard `metadata` /
  `extensions` carryover fields.

`solver` is stored as `str` (not `Literal`) so unknown solver
ids loaded from a newer project file are preserved per spec §7.5
and §12.2. Validation of supported values lives in S2.B.

References:
----------
* `specs/03_configuration_requirements.md` §7 (Simulation Settings)
* `specs/03_configuration_requirements.md` §11 (Persistence)
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Literal

# Spec/03 §7.4 discriminator values.
InitialConditionsSource = Literal["component_parameters", "explicit_overrides"]


@dataclass(frozen=True)
class InitialConditionOverride:
    """One entry in `InitialConditions.overrides` (Phase 1 placeholder).

    Field set is fixed by spec/03 §7.4 even though Phase 1 does not
    execute overrides: writing the dataclass now lets later phases
    grow `value` to `float | int | bool | ParameterValue` (or
    `Any`) without renaming or restructuring.

    Args:
        component_id: ULID-prefixed `cmp_<...>` workspace component id.
        parameter_id: Parameter name within that component's
            registered parameter schema.
        value: Initial value to apply at simulation start.
            Phase 1 enforces `float` to keep migration risk small;
            Phase 2 may widen the type.
    """

    component_id: str
    parameter_id: str
    value: float

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the spec/03 §7.4 override JSON entry shape."""
        return {
            "component_id": self.component_id,
            "parameter_id": self.parameter_id,
            "value": self.value,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> InitialConditionOverride:
        """Inverse of `to_dict`. Missing fields raise `KeyError`.

        Strict deserialization for override entries: every field
        is required and Phase 2 will add new fields, not omit
        existing ones.
        """
        return cls(
            component_id=str(payload["component_id"]),
            parameter_id=str(payload["parameter_id"]),
            value=float(payload["value"]),
        )


@dataclass(frozen=True)
class InitialConditions:
    """Container for the initial-conditions discriminator + overrides."""

    source: InitialConditionsSource = "component_parameters"
    overrides: tuple[InitialConditionOverride, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the spec/03 §7.4 JSON form."""
        return {
            "source": self.source,
            "overrides": [o.to_dict() for o in self.overrides],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> InitialConditions:
        """Inverse of `to_dict`. Defaults populate missing fields."""
        # Preserve unknown discriminator strings per spec/03 §7.4:
        # validation will warn at S2.B. The cast is intentional.
        source: InitialConditionsSource = payload.get("source", "component_parameters")
        overrides_raw = payload.get("overrides", [])
        if not isinstance(overrides_raw, list):
            overrides_raw = []
        overrides = tuple(
            InitialConditionOverride.from_dict(entry)
            for entry in overrides_raw
            if isinstance(entry, dict)
        )
        return cls(source=source, overrides=overrides)


# Field set that `SimulationSettings.from_dict` recognizes as
# typed; anything else gets routed into `extensions`.
_SIMULATION_KNOWN_FIELDS: frozenset[str] = frozenset(
    {
        "start_time",
        "stop_time",
        "sample_time",
        "max_step",
        "solver",
        "use_controller",
        "use_last_valid_model",
        "initial_conditions",
        "metadata",
        "extensions",
    }
)


@dataclass(frozen=True)
class SimulationSettings:
    """Top-level simulation settings (spec/03 §7.2)."""

    start_time: float = 0.0
    stop_time: float = 10.0
    sample_time: float = 0.01
    max_step: float | None = None
    solver: str = "auto"
    use_controller: bool = False
    use_last_valid_model: bool = True
    initial_conditions: InitialConditions = field(default_factory=InitialConditions)
    metadata: dict[str, Any] = field(default_factory=dict)
    extensions: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------ #
    # Immutable update helpers
    # ------------------------------------------------------------------ #

    def with_updated(self, **changes: Any) -> SimulationSettings:
        """Return a copy with `changes` applied (immutability-friendly)."""
        return replace(self, **changes)

    # ------------------------------------------------------------------ #
    # Serialization
    # ------------------------------------------------------------------ #

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the spec/03 §7.2 JSON form."""
        return {
            "start_time": self.start_time,
            "stop_time": self.stop_time,
            "sample_time": self.sample_time,
            "max_step": self.max_step,
            "solver": self.solver,
            "use_controller": self.use_controller,
            "use_last_valid_model": self.use_last_valid_model,
            "initial_conditions": self.initial_conditions.to_dict(),
            "metadata": dict(self.metadata),
            "extensions": dict(self.extensions),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> SimulationSettings:
        """Inverse of `to_dict`. Missing fields fall back to defaults.

        Unknown top-level keys are routed into `extensions` so that
        round-trip preserves forward-compatibility data per
        spec/03 §11.3.
        """
        defaults = cls()
        ic_payload = payload.get("initial_conditions", {})
        if not isinstance(ic_payload, dict):
            ic_payload = {}
        max_step_raw = payload.get("max_step", defaults.max_step)
        max_step: float | None = float(max_step_raw) if max_step_raw is not None else None
        # Capture unknown keys into extensions so they survive
        # save/load. Any explicit `extensions` value the caller
        # supplied takes priority and is then extended with the
        # unknown-key carryover.
        carry = {k: v for k, v in payload.items() if k not in _SIMULATION_KNOWN_FIELDS}
        extensions_in: dict[str, Any] = (
            dict(payload["extensions"]) if isinstance(payload.get("extensions"), dict) else {}
        )
        extensions_in.update(carry)
        return cls(
            start_time=float(payload.get("start_time", defaults.start_time)),
            stop_time=float(payload.get("stop_time", defaults.stop_time)),
            sample_time=float(payload.get("sample_time", defaults.sample_time)),
            max_step=max_step,
            solver=str(payload.get("solver", defaults.solver)),
            use_controller=bool(payload.get("use_controller", defaults.use_controller)),
            use_last_valid_model=bool(
                payload.get("use_last_valid_model", defaults.use_last_valid_model)
            ),
            initial_conditions=InitialConditions.from_dict(ic_payload),
            metadata=dict(payload.get("metadata", {}) or {}),
            extensions=extensions_in,
        )


__all__ = [
    "InitialConditionOverride",
    "InitialConditions",
    "InitialConditionsSource",
    "SimulationSettings",
]
