"""Unit tests for `shared.registry.PortDefinition` (S1.B.1a).

Covers per `02 §13`:

* required-field construction
* Phase 1 default `kind="bidirectional"` per `02 §13.1`
* domain field accepts both Phase 1 `DomainId` values
* frozen dataclass guard
"""

from __future__ import annotations

import dataclasses

import pytest

from shared.registry import PortDefinition


@pytest.mark.unit
def test_minimal_construction_with_phase1_defaults() -> None:
    """`id`, `display_name`, `domain` are required; `kind` defaults to
    `"bidirectional"`."""
    port = PortDefinition(
        id="p",
        display_name="Positive",
        domain="electrical_analog",
    )

    assert port.id == "p"
    assert port.display_name == "Positive"
    assert port.domain == "electrical_analog"
    assert port.kind == "bidirectional"
    assert port.relative_position == (0.0, 0.0)
    assert port.required is True


@pytest.mark.unit
def test_mechanical_domain_port() -> None:
    """`domain` accepts `mechanical_translational` as well."""
    port = PortDefinition(
        id="flange_a",
        display_name="Flange A",
        domain="mechanical_translational",
        relative_position=(0.5, 1.0),
    )

    assert port.domain == "mechanical_translational"
    assert port.relative_position == (0.5, 1.0)


@pytest.mark.unit
def test_frozen_dataclass_cannot_be_mutated() -> None:
    """Frozen + slots guards against direct field assignment."""
    port = PortDefinition(
        id="p",
        display_name="P",
        domain="electrical_analog",
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        port.domain = "mechanical_translational"  # type: ignore[misc]
