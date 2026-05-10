"""Unit tests for `shared.registry.LibraryVisualSpec` (S1.B.1a)."""

from __future__ import annotations

import dataclasses

import pytest

from shared.registry import LibraryVisualSpec


@pytest.mark.unit
def test_default_construction_yields_single_default_variant() -> None:
    """A minimal spec carries `svg_id` plus a single `"default"` variant."""
    spec = LibraryVisualSpec(svg_id="electrical_resistor_default")

    assert spec.svg_id == "electrical_resistor_default"
    assert spec.default_variant == "default"
    assert spec.variants == ("default",)


@pytest.mark.unit
def test_frozen_dataclass_cannot_be_mutated() -> None:
    """Frozen + slots guards against direct field assignment."""
    spec = LibraryVisualSpec(svg_id="x")
    with pytest.raises(dataclasses.FrozenInstanceError):
        spec.svg_id = "y"  # type: ignore[misc]
