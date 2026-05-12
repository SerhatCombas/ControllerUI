"""PlotLayout dataclasses (S2.C scaffold).

Implements the four-slot plot configuration from spec/03 §8 and the
typed `channel_selection.kind` schema from ADR-016. Phase 1 stores
the schema; placeholder rendering and the mirror-sync UI live in
S2.D and later.

Dataclass family:

* `ChannelSelection` — typed selection container with a `kind`
  discriminator (`"channels"` | `"io_pair"` | `"system_wide"`) and
  three payload-bearing fields. Flat `input` / `output` siblings
  per ADR-016 (post spec/03 §8.6 alignment commit). No
  `__post_init__` cross-field invariant: kind / payload coherence
  is the validator's responsibility (S2.C also extends
  `ConfigurationValidator` with the matching rule) so forward-
  compat data can load and surface a warning instead of crashing.
* `AxisConfig` — optional axis customization, all `None` in
  Phase-1 defaults.
* `PlotSlotConfig` — one of the four slots. Carries the per-slot
  plot_type-change rule from spec §8.7 in its `with_plot_type`
  method (kind-preserving same-kind change vs. reset-to-defaults
  on kind change; unknown plot_types pass through with no reset
  so forward-compat data round-trips intact).
* `PlotLayout` — top-level container holding the four slots plus
  `fullscreen_slot_id` and the standard `metadata` / `extensions`
  carryover fields.

Design choices (S2.C pre-scan):

* `plot_type: str` — kept as `str` not `Literal` so unknown values
  loaded from a newer schema are preserved per spec §12.2 (same
  pattern as `controller_type` and `solver`).
* `PLOT_TYPE_KIND_MAP` — module-level constant covering the 11
  plot types listed in spec §8.6. Unknown plot types fall through
  to "no kind known"; validator warns via
  `warning.validation.unknown_plot_type`.
* `slot_id: str` — free-form per spec §8.3. Phase-1 defaults are
  `"plot_1".."plot_4"`; future grids (3-slot, 6-slot) widen the
  shape without schema migration.

Known spec contradiction (Type-1 doc error, backlog cleanup):

  Spec/03 §8.6 maps `root_locus → system_wide` ("entire system +
  gain parameter"). ADR-016's table lists `root locus → io_pair`.
  Following spec/03 here — the description column matches the
  system_wide semantics. ADR-016 row reads as a typo. Flagged for
  a follow-up `docs(decisions)` cleanup.

References:
----------
* `specs/03_configuration_requirements.md` §8 (Plot Layout Settings)
* `specs/03_configuration_requirements.md` §8.6 (Plot Type Compatibility)
* `specs/03_configuration_requirements.md` §8.7 (Plot Type Change Behavior)
* `decisions/ADR-016-channel-selection-kind-schema.md`
* `decisions/ADR-017-mirror-sync-plot-dropdowns.md`
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Final, Literal

# Channel-selection discriminator per ADR-016.
PlotKind = Literal["channels", "io_pair", "system_wide"]

# Plot type → channel-selection kind mapping per spec §8.6.
# Add Phase-2 plot types here as they land; unknown plot types fall
# through to "no kind known" and surface a validator warning.
PLOT_TYPE_KIND_MAP: Final[dict[str, PlotKind]] = {
    # Phase 1 plot types
    "time_response": "channels",
    "step_response": "io_pair",
    "bode": "io_pair",
    "pole_zero": "system_wide",
    # Phase 2 plot types (selectable but placeholder-rendered in Phase 1)
    "state_variables": "channels",
    "input_output_signal": "channels",
    "road_profile": "channels",
    "force": "channels",
    "nyquist": "io_pair",
    "root_locus": "system_wide",
    "eigenvalue": "system_wide",
}

# Allowed `ChannelSelection.kind` values for runtime validation of
# `from_dict` payloads. Mirrors the Literal but available as a
# `frozenset` for membership tests.
_PLOT_KIND_VALUES: Final[frozenset[str]] = frozenset({"channels", "io_pair", "system_wide"})


# ====================================================================== #
# ChannelSelection
# ====================================================================== #


_CHANNEL_SELECTION_KNOWN_FIELDS: frozenset[str] = frozenset(
    {"kind", "channels", "input", "output", "metadata", "extensions"}
)


@dataclass(frozen=True)
class ChannelSelection:
    """Typed selection container for one plot slot.

    Flat siblings `input` / `output` per ADR-016 (NOT a nested
    `io_pair` object). The `kind` field discriminates which subset
    of fields is meaningful for the active plot type:

    * `kind == "channels"` → `channels` carries the selection;
      `input`, `output` are `None`.
    * `kind == "io_pair"` → `input` and `output` carry the I/O
      entry ids; `channels` is empty.
    * `kind == "system_wide"` → all payload fields empty / `None`.

    No `__post_init__` invariant enforces kind/payload coherence:
    incoherent combinations are surfaced by
    `ConfigurationValidator` as
    `error.validation.channel_selection_kind_mismatch` so
    forward-compat data loads intact and the user gets actionable
    feedback rather than a load crash.
    """

    kind: PlotKind  # required; no default
    channels: tuple[str, ...] = ()
    input: str | None = None
    output: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    extensions: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the spec/03 §8.6 JSON form (flat-sibling shape)."""
        return {
            "kind": self.kind,
            "channels": list(self.channels),
            "input": self.input,
            "output": self.output,
            "metadata": dict(self.metadata),
            "extensions": dict(self.extensions),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ChannelSelection:
        """Inverse of `to_dict`. Required: `kind`."""
        kind = payload.get("kind")
        if kind not in _PLOT_KIND_VALUES:
            raise ValueError(
                f"ChannelSelection.kind must be one of "
                f"'channels'/'io_pair'/'system_wide'; got {kind!r}"
            )
        channels_raw = payload.get("channels", []) or []
        if not isinstance(channels_raw, list):
            channels_raw = []
        channels: tuple[str, ...] = tuple(str(c) for c in channels_raw)
        carry = {k: v for k, v in payload.items() if k not in _CHANNEL_SELECTION_KNOWN_FIELDS}
        extensions_in: dict[str, Any] = (
            dict(payload["extensions"]) if isinstance(payload.get("extensions"), dict) else {}
        )
        extensions_in.update(carry)
        return cls(
            kind=kind,
            channels=channels,
            input=_optional_str(payload.get("input")),
            output=_optional_str(payload.get("output")),
            metadata=dict(payload.get("metadata", {}) or {}),
            extensions=extensions_in,
        )


def default_channel_selection_for_kind(kind: PlotKind) -> ChannelSelection:
    """Return the empty default `ChannelSelection` for a given kind.

    Used by `PlotSlotConfig.with_plot_type` to reset selection when
    the plot_type change crosses a kind boundary (spec §8.7).
    """
    return ChannelSelection(kind=kind)


# ====================================================================== #
# AxisConfig
# ====================================================================== #


@dataclass(frozen=True)
class AxisConfig:
    """Optional per-axis customization. Phase-1 defaults are all `None`."""

    x_label: str | None = None
    y_label: str | None = None
    x_range: tuple[float, float] | None = None
    y_range: tuple[float, float] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize ranges as JSON lists (tuples not JSON-native)."""
        return {
            "x_label": self.x_label,
            "y_label": self.y_label,
            "x_range": list(self.x_range) if self.x_range is not None else None,
            "y_range": list(self.y_range) if self.y_range is not None else None,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> AxisConfig:
        """Inverse of `to_dict`. Missing fields default to `None`."""
        return cls(
            x_label=_optional_str(payload.get("x_label")),
            y_label=_optional_str(payload.get("y_label")),
            x_range=_range_from_payload(payload.get("x_range")),
            y_range=_range_from_payload(payload.get("y_range")),
        )


# ====================================================================== #
# PlotSlotConfig
# ====================================================================== #


_PLOT_SLOT_KNOWN_FIELDS: frozenset[str] = frozenset(
    {
        "slot_id",
        "plot_type",
        "title",
        "channel_selection",
        "axis_config",
        "metadata",
        "extensions",
    }
)


@dataclass(frozen=True)
class PlotSlotConfig:
    """One slot inside `PlotLayout.slots`.

    The `with_plot_type` method encodes the spec §8.7 rule: when
    the new plot_type maps to the same `kind` as the current one,
    `channel_selection` is preserved; when the kind changes, it
    resets to the kind's default empty selection. Unknown
    plot_types are preserved as-is and their `channel_selection`
    is **not** reset — per spec §12.2 forward-compat, unknown
    values round-trip until UI surfaces them under an "Unknown"
    placeholder group.
    """

    slot_id: str  # required
    plot_type: str  # required
    channel_selection: ChannelSelection  # required
    title: str = ""
    axis_config: AxisConfig = field(default_factory=AxisConfig)
    metadata: dict[str, Any] = field(default_factory=dict)
    extensions: dict[str, Any] = field(default_factory=dict)

    def with_plot_type(self, new_plot_type: str) -> PlotSlotConfig:
        """Return a new slot with `plot_type` updated per spec §8.7.

        Behavior table:

        * Same `kind` as current (per `PLOT_TYPE_KIND_MAP`) →
          `channel_selection` preserved.
        * Different `kind` → `channel_selection` reset to
          `default_channel_selection_for_kind(new_kind)`.
        * Unknown plot_type (either side not in
          `PLOT_TYPE_KIND_MAP`) → `channel_selection` preserved
          to honor spec §12.2 forward-compat (round-trip safety).
        """
        current_kind = PLOT_TYPE_KIND_MAP.get(self.plot_type)
        new_kind = PLOT_TYPE_KIND_MAP.get(new_plot_type)
        if current_kind is None or new_kind is None:
            return replace(self, plot_type=new_plot_type)
        if current_kind == new_kind:
            return replace(self, plot_type=new_plot_type)
        return replace(
            self,
            plot_type=new_plot_type,
            channel_selection=default_channel_selection_for_kind(new_kind),
        )

    def with_updated(self, **changes: Any) -> PlotSlotConfig:
        """Return a copy with `changes` applied (immutability-friendly)."""
        return replace(self, **changes)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the spec/03 §8.2 JSON form."""
        return {
            "slot_id": self.slot_id,
            "plot_type": self.plot_type,
            "title": self.title,
            "channel_selection": self.channel_selection.to_dict(),
            "axis_config": self.axis_config.to_dict(),
            "metadata": dict(self.metadata),
            "extensions": dict(self.extensions),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> PlotSlotConfig:
        """Inverse of `to_dict`. Required: `slot_id`, `plot_type`, `channel_selection`."""
        slot_id = payload.get("slot_id")
        if not isinstance(slot_id, str) or not slot_id:
            raise KeyError("PlotSlotConfig payload missing required 'slot_id' field")
        plot_type = payload.get("plot_type")
        if not isinstance(plot_type, str) or not plot_type:
            raise KeyError("PlotSlotConfig payload missing required 'plot_type' field")
        cs_payload = payload.get("channel_selection")
        if not isinstance(cs_payload, dict):
            raise KeyError("PlotSlotConfig payload missing required 'channel_selection' object")
        axis_payload = payload.get("axis_config", {}) or {}
        if not isinstance(axis_payload, dict):
            axis_payload = {}
        carry = {k: v for k, v in payload.items() if k not in _PLOT_SLOT_KNOWN_FIELDS}
        extensions_in: dict[str, Any] = (
            dict(payload["extensions"]) if isinstance(payload.get("extensions"), dict) else {}
        )
        extensions_in.update(carry)
        return cls(
            slot_id=slot_id,
            plot_type=plot_type,
            channel_selection=ChannelSelection.from_dict(cs_payload),
            title=str(payload.get("title", "")),
            axis_config=AxisConfig.from_dict(axis_payload),
            metadata=dict(payload.get("metadata", {}) or {}),
            extensions=extensions_in,
        )


# ====================================================================== #
# PlotLayout
# ====================================================================== #


_PLOT_LAYOUT_KNOWN_FIELDS: frozenset[str] = frozenset(
    {"slots", "fullscreen_slot_id", "metadata", "extensions"}
)


@dataclass(frozen=True)
class PlotLayout:
    """Top-level plot-layout container (spec/03 §8.2)."""

    slots: tuple[PlotSlotConfig, ...] = ()
    fullscreen_slot_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    extensions: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------ #
    # Immutable update helpers
    # ------------------------------------------------------------------ #

    def with_slot_replaced(self, new_slot: PlotSlotConfig) -> PlotLayout:
        """Return a copy where the slot with `new_slot.slot_id` is swapped in.

        Raises `KeyError` when no slot in the layout shares the id —
        silent no-op is a likely caller bug.
        """
        if not any(s.slot_id == new_slot.slot_id for s in self.slots):
            raise KeyError(new_slot.slot_id)
        return replace(
            self,
            slots=tuple(new_slot if s.slot_id == new_slot.slot_id else s for s in self.slots),
        )

    def with_fullscreen(self, slot_id: str | None) -> PlotLayout:
        """Return a copy with `fullscreen_slot_id` set to `slot_id`."""
        return replace(self, fullscreen_slot_id=slot_id)

    # ------------------------------------------------------------------ #
    # Serialization
    # ------------------------------------------------------------------ #

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the spec/03 §8.2 JSON form."""
        return {
            "slots": [s.to_dict() for s in self.slots],
            "fullscreen_slot_id": self.fullscreen_slot_id,
            "metadata": dict(self.metadata),
            "extensions": dict(self.extensions),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> PlotLayout:
        """Inverse of `to_dict`. Missing fields fall back to defaults."""
        slots_raw = payload.get("slots", []) or []
        if not isinstance(slots_raw, list):
            slots_raw = []
        slots = tuple(
            PlotSlotConfig.from_dict(entry) for entry in slots_raw if isinstance(entry, dict)
        )
        carry = {k: v for k, v in payload.items() if k not in _PLOT_LAYOUT_KNOWN_FIELDS}
        extensions_in: dict[str, Any] = (
            dict(payload["extensions"]) if isinstance(payload.get("extensions"), dict) else {}
        )
        extensions_in.update(carry)
        return cls(
            slots=slots,
            fullscreen_slot_id=_optional_str(payload.get("fullscreen_slot_id")),
            metadata=dict(payload.get("metadata", {}) or {}),
            extensions=extensions_in,
        )


# ====================================================================== #
# Internal helpers
# ====================================================================== #


def _optional_str(raw: Any) -> str | None:
    """Coerce a payload value into `str | None` for optional string fields."""
    if raw is None or raw == "":
        return None
    if isinstance(raw, str):
        return raw
    return str(raw)


def _range_from_payload(raw: Any) -> tuple[float, float] | None:
    """Coerce a JSON list/tuple of two numbers into a `tuple[float, float]`."""
    if raw is None:
        return None
    if not isinstance(raw, list | tuple) or len(raw) != 2:
        return None
    return (float(raw[0]), float(raw[1]))


__all__ = [
    "PLOT_TYPE_KIND_MAP",
    "AxisConfig",
    "ChannelSelection",
    "PlotKind",
    "PlotLayout",
    "PlotSlotConfig",
    "default_channel_selection_for_kind",
]
