"""Unit tests for `shared.graph.ImplicitNode` (S1.5).

Covers:

* default construction with id / port_refs / domain
* frozen + slots: direct field assignment raises
* domain=None representable (mixed-domain node per `02 §18.1`)
* explicit construction with all fields

References
----------
* `specs/02_workspace_requirements.md` §17 (Implicit Node Behavior),
  §18 (Implicit Node Assembly), §18.1 (Node Domain Rule), §8.7
  (Implicit Node IDs)
"""

from __future__ import annotations

import dataclasses

import pytest

from shared.graph.implicit_node import ImplicitNode
from shared.graph.port_ref import PortRef


@pytest.mark.unit
def test_default_construction_round_trips_fields() -> None:
    """All explicit fields read back unchanged."""
    refs = (
        PortRef(component_id="cmp_A", port_id="p"),
        PortRef(component_id="cmp_B", port_id="p"),
    )
    node = ImplicitNode(id="node_1", port_refs=refs, domain="electrical_analog")

    assert node.id == "node_1"
    assert node.port_refs == refs
    assert node.domain == "electrical_analog"


@pytest.mark.unit
def test_frozen_dataclass_cannot_be_mutated() -> None:
    """Frozen + slots guards against direct field assignment."""
    node = ImplicitNode(id="node_1", port_refs=(), domain="electrical_analog")

    with pytest.raises(dataclasses.FrozenInstanceError):
        node.domain = "mechanical_translational"  # type: ignore[misc]


@pytest.mark.unit
def test_mixed_domain_is_representable_via_none_domain() -> None:
    """Per `02 §18.1`, a mixed-domain node is invalid; the dataclass
    represents this state with `domain=None`. Subsequent validation
    pipelines (S1.6+) flag `domain is None` as a violation."""
    refs = (
        PortRef(component_id="cmp_A", port_id="p"),
        PortRef(component_id="cmp_B", port_id="flange"),
    )

    node = ImplicitNode(id="node_1", port_refs=refs, domain=None)

    assert node.domain is None
