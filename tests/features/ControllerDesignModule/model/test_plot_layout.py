"""Unit tests for PlotLayout dataclass family (S2.C scaffold).

Covers:

* `ChannelSelection` — kind discriminator, flat-sibling JSON shape
  per ADR-016, no `__post_init__` invariant (loose dataclass).
* `AxisConfig` — optional axis customization round-trip.
* `PlotSlotConfig` — spec §8.7 `with_plot_type` rule (kind-preserving,
  reset on kind change, unknown-plot-type preservation).
* `PlotLayout` — slot replacement, fullscreen toggle, top-level
  round-trip.
"""

from __future__ import annotations

import json
from dataclasses import FrozenInstanceError

import pytest

from features.ControllerDesignModule.model import (
    PLOT_TYPE_KIND_MAP,
    AxisConfig,
    ChannelSelection,
    PlotLayout,
    PlotSlotConfig,
    default_channel_selection_for_kind,
)


def _slot(plot_type: str, kind: str = "channels", slot_id: str = "plot_1") -> PlotSlotConfig:
    return PlotSlotConfig(
        slot_id=slot_id,
        plot_type=plot_type,
        channel_selection=ChannelSelection(kind=kind),  # type: ignore[arg-type]
    )


# ====================================================================== #
# ChannelSelection
# ====================================================================== #


@pytest.mark.unit
def test_channel_selection_round_trip_for_each_kind() -> None:
    """Each kind variant survives a JSON round-trip."""
    for kind in ("channels", "io_pair", "system_wide"):
        cs = ChannelSelection(kind=kind)  # type: ignore[arg-type]
        cs_back = ChannelSelection.from_dict(json.loads(json.dumps(cs.to_dict())))
        assert cs_back == cs


@pytest.mark.unit
def test_channel_selection_io_pair_payload_round_trip() -> None:
    """`input`/`output` siblings survive round-trip (no nested io_pair)."""
    cs = ChannelSelection(kind="io_pair", input="ioin_X", output="ioout_Y")
    payload = cs.to_dict()
    assert payload["input"] == "ioin_X"
    assert payload["output"] == "ioout_Y"
    assert "io_pair" not in payload
    cs_back = ChannelSelection.from_dict(payload)
    assert cs_back == cs


@pytest.mark.unit
def test_channel_selection_channels_payload_round_trip() -> None:
    """`channels` tuple survives round-trip via JSON list."""
    cs = ChannelSelection(kind="channels", channels=("ch_a", "ch_b"))
    cs_back = ChannelSelection.from_dict(cs.to_dict())
    assert cs_back.channels == ("ch_a", "ch_b")


@pytest.mark.unit
def test_channel_selection_invalid_kind_raises() -> None:
    """A payload with an unknown `kind` value raises `ValueError`."""
    with pytest.raises(ValueError, match="kind"):
        ChannelSelection.from_dict({"kind": "future_kind"})


@pytest.mark.unit
def test_channel_selection_no_post_init_invariant() -> None:
    """Loose dataclass: incoherent kind/payload combos are accepted at construction.

    Validation surfaces them as
    `error.validation.channel_selection_kind_mismatch`; the dataclass
    itself does not raise so forward-compat data can load.
    """
    weird = ChannelSelection(kind="system_wide", channels=("orphan",), input="leftover")
    assert weird.kind == "system_wide"
    assert weird.channels == ("orphan",)


@pytest.mark.unit
def test_channel_selection_unknown_top_level_keys_route_into_extensions() -> None:
    """Forward-compat: unknown keys land in `extensions`."""
    payload = ChannelSelection(kind="channels").to_dict()
    payload["future_field"] = {"phase2": True}
    cs_back = ChannelSelection.from_dict(payload)
    assert cs_back.extensions["future_field"] == {"phase2": True}


@pytest.mark.unit
def test_channel_selection_is_frozen() -> None:
    """`ChannelSelection` is immutable."""
    cs = ChannelSelection(kind="channels")
    with pytest.raises(FrozenInstanceError):
        cs.kind = "io_pair"  # type: ignore[misc]


# ====================================================================== #
# AxisConfig
# ====================================================================== #


@pytest.mark.unit
def test_axis_config_defaults_are_all_none() -> None:
    """Phase-1 default `AxisConfig()` has every field `None`."""
    ax = AxisConfig()
    assert ax.x_label is None
    assert ax.y_label is None
    assert ax.x_range is None
    assert ax.y_range is None


@pytest.mark.unit
def test_axis_config_range_round_trip_as_list() -> None:
    """`x_range`/`y_range` round-trip through JSON lists."""
    ax = AxisConfig(x_range=(0.0, 10.0), y_range=(-1.0, 1.0), x_label="time (s)")
    payload = ax.to_dict()
    assert payload["x_range"] == [0.0, 10.0]
    assert payload["y_range"] == [-1.0, 1.0]
    ax_back = AxisConfig.from_dict(payload)
    assert ax_back == ax


# ====================================================================== #
# PlotSlotConfig — §8.7 with_plot_type
# ====================================================================== #


@pytest.mark.unit
def test_with_plot_type_same_kind_preserves_channel_selection() -> None:
    """spec §8.7: same kind preserves channel_selection (e.g., time → state_variables)."""
    slot = PlotSlotConfig(
        slot_id="plot_1",
        plot_type="time_response",
        channel_selection=ChannelSelection(kind="channels", channels=("ch_a", "ch_b")),
    )
    out = slot.with_plot_type("state_variables")
    assert out.plot_type == "state_variables"
    assert out.channel_selection.channels == ("ch_a", "ch_b")


@pytest.mark.unit
def test_with_plot_type_different_kind_resets_to_defaults() -> None:
    """spec §8.7: kind change resets channel_selection to kind defaults."""
    slot = PlotSlotConfig(
        slot_id="plot_1",
        plot_type="time_response",
        channel_selection=ChannelSelection(kind="channels", channels=("ch_a",)),
    )
    out = slot.with_plot_type("bode")  # channels → io_pair
    assert out.plot_type == "bode"
    assert out.channel_selection.kind == "io_pair"
    assert out.channel_selection.channels == ()
    assert out.channel_selection.input is None


@pytest.mark.unit
def test_with_plot_type_unknown_plot_type_preserves_selection() -> None:
    """spec §12.2 forward-compat: unknown plot_type does NOT reset selection."""
    slot = PlotSlotConfig(
        slot_id="plot_1",
        plot_type="time_response",
        channel_selection=ChannelSelection(kind="channels", channels=("ch_a",)),
    )
    out = slot.with_plot_type("future_unknown_plot")
    assert out.plot_type == "future_unknown_plot"
    assert out.channel_selection.channels == ("ch_a",)


@pytest.mark.unit
def test_with_plot_type_from_unknown_to_known_preserves_selection() -> None:
    """An unknown current plot_type → known new type: preserve forward-compat."""
    slot = PlotSlotConfig(
        slot_id="plot_1",
        plot_type="future_unknown_plot",
        channel_selection=ChannelSelection(kind="io_pair", input="ioin_X", output="ioout_Y"),
    )
    out = slot.with_plot_type("bode")
    assert out.plot_type == "bode"
    # Selection preserved because current kind is unknown — caller can
    # fix up the selection if they want; round-trip is non-destructive.
    assert out.channel_selection.input == "ioin_X"


@pytest.mark.unit
def test_default_channel_selection_for_kind_returns_empty_kind_variant() -> None:
    """Helper returns the empty default for each kind."""
    for kind in ("channels", "io_pair", "system_wide"):
        cs = default_channel_selection_for_kind(kind)  # type: ignore[arg-type]
        assert cs.kind == kind
        assert cs.channels == ()
        assert cs.input is None
        assert cs.output is None


# ====================================================================== #
# PlotSlotConfig — round-trip
# ====================================================================== #


@pytest.mark.unit
def test_plot_slot_config_round_trip() -> None:
    """A populated slot survives JSON round-trip."""
    slot = PlotSlotConfig(
        slot_id="plot_3",
        plot_type="bode",
        title="Bode",
        channel_selection=ChannelSelection(kind="io_pair", input="ioin_X", output="ioout_Y"),
        axis_config=AxisConfig(x_label="freq (Hz)", x_range=(1e-2, 1e3)),
        metadata={"note": "test"},
    )
    slot_back = PlotSlotConfig.from_dict(json.loads(json.dumps(slot.to_dict())))
    assert slot_back == slot


@pytest.mark.unit
def test_plot_slot_config_from_dict_missing_required_field_raises() -> None:
    """`slot_id`, `plot_type`, and `channel_selection` are required."""
    base = _slot("time_response").to_dict()
    for required in ("slot_id", "plot_type", "channel_selection"):
        payload = {k: v for k, v in base.items() if k != required}
        with pytest.raises(KeyError):
            PlotSlotConfig.from_dict(payload)


@pytest.mark.unit
def test_plot_slot_config_unknown_top_level_keys_route_into_extensions() -> None:
    """Forward-compat: unknown slot fields land in `extensions`."""
    payload = _slot("time_response").to_dict()
    payload["future_setting"] = "on"
    slot_back = PlotSlotConfig.from_dict(payload)
    assert slot_back.extensions["future_setting"] == "on"


# ====================================================================== #
# PlotLayout
# ====================================================================== #


@pytest.mark.unit
def test_plot_layout_default_is_empty() -> None:
    """A fresh `PlotLayout()` has no slots and no fullscreen target."""
    layout = PlotLayout()
    assert layout.slots == ()
    assert layout.fullscreen_slot_id is None


@pytest.mark.unit
def test_plot_layout_with_slot_replaced_swaps_in_place() -> None:
    """`with_slot_replaced` returns a copy with the matching slot swapped."""
    a = _slot("time_response", "channels", slot_id="plot_1")
    b = _slot("bode", "io_pair", slot_id="plot_2")
    layout = PlotLayout(slots=(a, b))
    a_new = a.with_plot_type("state_variables")
    out = layout.with_slot_replaced(a_new)
    assert out.slots[0] == a_new
    assert out.slots[1] is b


@pytest.mark.unit
def test_plot_layout_with_slot_replaced_unknown_raises() -> None:
    """`with_slot_replaced` raises `KeyError` when no slot matches."""
    layout = PlotLayout()
    with pytest.raises(KeyError):
        layout.with_slot_replaced(_slot("time_response", slot_id="plot_X"))


@pytest.mark.unit
def test_plot_layout_with_fullscreen_sets_id() -> None:
    """`with_fullscreen` toggles `fullscreen_slot_id`."""
    layout = PlotLayout()
    out = layout.with_fullscreen("plot_2")
    assert out.fullscreen_slot_id == "plot_2"
    cleared = out.with_fullscreen(None)
    assert cleared.fullscreen_slot_id is None


@pytest.mark.unit
def test_plot_layout_round_trip_with_four_slots() -> None:
    """Four-slot layout (Phase-1 default shape) survives round-trip."""
    layout = PlotLayout(
        slots=(
            _slot("time_response", "channels", "plot_1"),
            _slot("step_response", "io_pair", "plot_2"),
            _slot("bode", "io_pair", "plot_3"),
            _slot("pole_zero", "system_wide", "plot_4"),
        ),
        fullscreen_slot_id="plot_3",
    )
    layout_back = PlotLayout.from_dict(json.loads(json.dumps(layout.to_dict())))
    assert layout_back == layout


@pytest.mark.unit
def test_plot_layout_unknown_top_level_keys_route_into_extensions() -> None:
    """Forward-compat: unknown layout-level keys land in `extensions`."""
    payload = PlotLayout().to_dict()
    payload["future_grid_shape"] = "3x2"
    layout_back = PlotLayout.from_dict(payload)
    assert layout_back.extensions["future_grid_shape"] == "3x2"


# ====================================================================== #
# PLOT_TYPE_KIND_MAP coverage
# ====================================================================== #


@pytest.mark.unit
def test_phase1_plot_types_all_present_in_kind_map() -> None:
    """The four Phase-1 plot_types map to the §8.6 kinds."""
    assert PLOT_TYPE_KIND_MAP["time_response"] == "channels"
    assert PLOT_TYPE_KIND_MAP["step_response"] == "io_pair"
    assert PLOT_TYPE_KIND_MAP["bode"] == "io_pair"
    assert PLOT_TYPE_KIND_MAP["pole_zero"] == "system_wide"
