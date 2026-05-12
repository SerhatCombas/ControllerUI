"""Controller settings dataclasses (S2.A scaffold).

Per spec/03 §5 and the S2 sub-commit plan. Phase 1 stores, edits,
and round-trips controller configuration; numeric validation
(spec §10.1) and runtime execution (spec §5.6) belong to later
stages.

Design choices (decisions K1 / K2 from the S2.A pre-scan):

* `parameters: dict[str, float]` — flat untyped dict per
  controller_type. Phase 1 supports P/PI/PD/PID, every parameter
  is scalar (kp, ki, kd). Phase 1.5+ widening to
  `dict[str, ParameterValue]` carries a schema migration borç.
* `controller_type: str` — kept as `str` (not `Literal`) so
  unknown types loaded from a newer project file are preserved
  per spec §12.2. Validation of supported set lives in S2.B.
* `input_ref` / `output_ref` — optional `ioin_<ULID>` /
  `ioout_<ULID>` references into `IOSelection`. Phase 1 allows
  unbound controllers; staleness detection is S2.B.

References:
----------
* `specs/03_configuration_requirements.md` §5 (Controller Settings)
* `specs/03_configuration_requirements.md` §10.1 (Validation)
* `specs/03_configuration_requirements.md` §11.3 (Forward Compat)
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

# Field set `from_dict` recognizes as known; anything else is
# routed into `extensions` to keep round-trip forward-compatible
# per spec/03 §11.3.
_CONTROLLER_SPEC_KNOWN_FIELDS: frozenset[str] = frozenset(
    {
        "id",
        "display_name",
        "enabled",
        "controller_type",
        "parameters",
        "input_ref",
        "output_ref",
        "metadata",
        "extensions",
    }
)

_CONTROLLER_SETTINGS_KNOWN_FIELDS: frozenset[str] = frozenset(
    {
        "controllers",
        "metadata",
        "extensions",
    }
)


@dataclass(frozen=True)
class ControllerSpec:
    """Single controller entry inside `ControllerSettings.controllers`.

    Mirrors the JSON shape from spec/03 §5.3 verbatim. Identity
    is the `id` field — a `ctrl_<ULID>` string per ADR-002 / spec
    §5.3. `display_name` is user-facing and editable; never use
    it as a reference.

    Args:
        id: Internal `ctrl_<ULID>` identifier. Stable across edits
            and persistence; never reused.
        display_name: Human-readable label shown in the UI.
        enabled: Whether the controller participates in
            simulation (Phase 2+). Default `False` per spec/03 §13.
        controller_type: Controller kind label. Phase 1 values:
            `"P"`, `"PI"`, `"PD"`, `"PID"`. Unknown values are
            preserved on load per spec §12.2.
        parameters: Flat scalar parameter map (e.g.,
            `{"kp": 1.0, "ki": 0.0, "kd": 0.0}`). Phase 1 keys
            are kp / ki / kd; unused entries may be retained
            across `controller_type` changes per spec §5.6.
        input_ref: Optional `ioin_<ULID>` link into
            `IOSelection.inputs`. None when unbound.
        output_ref: Optional `ioout_<ULID>` link into
            `IOSelection.outputs`. None when unbound.
        metadata: Free-form caller-owned dict for UI hints.
        extensions: Forward-compatibility carryover for unknown
            JSON fields encountered during load.
    """

    id: str
    controller_type: str
    display_name: str = ""
    enabled: bool = False
    parameters: dict[str, float] = field(default_factory=dict)
    input_ref: str | None = None
    output_ref: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    extensions: dict[str, Any] = field(default_factory=dict)

    def with_updated(self, **changes: Any) -> ControllerSpec:
        """Return a copy with `changes` applied (immutability-friendly)."""
        return replace(self, **changes)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the spec/03 §5.3 JSON form."""
        return {
            "id": self.id,
            "display_name": self.display_name,
            "enabled": self.enabled,
            "controller_type": self.controller_type,
            "parameters": dict(self.parameters),
            "input_ref": self.input_ref,
            "output_ref": self.output_ref,
            "metadata": dict(self.metadata),
            "extensions": dict(self.extensions),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ControllerSpec:
        """Inverse of `to_dict`. Missing optional fields fall back to defaults.

        `id` and `controller_type` are required — both are part of
        identity. Unknown top-level keys are routed into
        `extensions` to preserve forward-compatibility data per
        spec/03 §11.3.
        """
        raw_id = payload.get("id")
        if not isinstance(raw_id, str) or not raw_id:
            raise KeyError("ControllerSpec payload missing required 'id' field")
        raw_type = payload.get("controller_type")
        if not isinstance(raw_type, str) or not raw_type:
            raise KeyError("ControllerSpec payload missing required 'controller_type' field")
        carry = {k: v for k, v in payload.items() if k not in _CONTROLLER_SPEC_KNOWN_FIELDS}
        extensions_in: dict[str, Any] = (
            dict(payload["extensions"]) if isinstance(payload.get("extensions"), dict) else {}
        )
        extensions_in.update(carry)
        parameters_in = payload.get("parameters", {}) or {}
        parameters: dict[str, float] = (
            {str(k): float(v) for k, v in parameters_in.items()}
            if isinstance(parameters_in, dict)
            else {}
        )
        return cls(
            id=raw_id,
            controller_type=raw_type,
            display_name=str(payload.get("display_name", "")),
            enabled=bool(payload.get("enabled", False)),
            parameters=parameters,
            input_ref=_optional_str(payload.get("input_ref")),
            output_ref=_optional_str(payload.get("output_ref")),
            metadata=dict(payload.get("metadata", {}) or {}),
            extensions=extensions_in,
        )


@dataclass(frozen=True)
class ControllerSettings:
    """Top-level controller-list container (spec/03 §5.3)."""

    controllers: tuple[ControllerSpec, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    extensions: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------ #
    # Immutable update helpers
    # ------------------------------------------------------------------ #

    def with_controller_added(self, spec: ControllerSpec) -> ControllerSettings:
        """Return a copy with `spec` appended to `controllers`."""
        return replace(self, controllers=(*self.controllers, spec))

    def with_controller_removed(self, controller_id: str) -> ControllerSettings:
        """Return a copy with the controller matching `controller_id` removed."""
        return replace(
            self,
            controllers=tuple(c for c in self.controllers if c.id != controller_id),
        )

    def with_controller_replaced(self, spec: ControllerSpec) -> ControllerSettings:
        """Return a copy where the controller with `spec.id` is replaced.

        Raises `KeyError` when no entry shares the id, since
        silent no-op is a likely caller bug.
        """
        existing_ids = [c.id for c in self.controllers]
        if spec.id not in existing_ids:
            raise KeyError(spec.id)
        return replace(
            self,
            controllers=tuple(spec if c.id == spec.id else c for c in self.controllers),
        )

    # ------------------------------------------------------------------ #
    # Serialization
    # ------------------------------------------------------------------ #

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the spec/03 §5.3 JSON form."""
        return {
            "controllers": [c.to_dict() for c in self.controllers],
            "metadata": dict(self.metadata),
            "extensions": dict(self.extensions),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ControllerSettings:
        """Inverse of `to_dict`. Missing fields fall back to defaults."""
        controllers_raw = payload.get("controllers", [])
        if not isinstance(controllers_raw, list):
            controllers_raw = []
        controllers = tuple(
            ControllerSpec.from_dict(entry) for entry in controllers_raw if isinstance(entry, dict)
        )
        carry = {k: v for k, v in payload.items() if k not in _CONTROLLER_SETTINGS_KNOWN_FIELDS}
        extensions_in: dict[str, Any] = (
            dict(payload["extensions"]) if isinstance(payload.get("extensions"), dict) else {}
        )
        extensions_in.update(carry)
        return cls(
            controllers=controllers,
            metadata=dict(payload.get("metadata", {}) or {}),
            extensions=extensions_in,
        )


def _optional_str(raw: Any) -> str | None:
    """Coerce a payload value into `str | None` for `*_ref` fields."""
    if raw is None or raw == "":
        return None
    if isinstance(raw, str):
        return raw
    return str(raw)


__all__ = [
    "ControllerSettings",
    "ControllerSpec",
]
