"""Unit tests for `WorkspaceIdGenerator`.

Covers:

* internal-ID format (prefix, ULID length, base32 charset)
* monotonic component display counters per slug, with deletion gaps
* slug independence (resistor counter does not bleed into capacitor)
* connection display counters use a single global sequence
* `rebuild_counters_from` resets state, parses underscore-bearing slugs
  correctly (`voltage_source_42`), respects deletion gaps, and skips
  malformed display IDs without aborting recovery.

References
----------
* `specs/02_workspace_requirements.md` §8 (ID Generation Policy)
* `decisions/ADR-002-hybrid-ulid-identity-model.md`
"""

from __future__ import annotations

import re

import pytest

from features.SystemModelingModule.model.component_instance import (
    ComponentInstance,
    PhysicalAttributes,
    VisualSpec,
)
from features.SystemModelingModule.model.connection import (
    Connection,
    PortRef,
)
from features.SystemModelingModule.model.id_generator import WorkspaceIdGenerator

# Crockford base32 alphabet used by ULIDs (case-insensitive in spec; the
# `python-ulid` library emits uppercase, so we accept either to be safe).
_ULID_BODY_RE = re.compile(r"^[0-9A-HJKMNP-TV-Za-hjkmnp-tv-z]{26}$")


# ---------------------------------------------------------------------- #
# Helpers
# ---------------------------------------------------------------------- #


def _make_component(*, component_id: str, display_id: str) -> ComponentInstance:
    """Build a minimal `ComponentInstance` for recovery-input tests."""
    return ComponentInstance(
        id=component_id,
        display_id=display_id,
        definition_id="electrical.analog.components.resistor",
        type="Resistor",
        display_name="Resistor",
        domain="electrical_analog",
        category="component",
        position=(0.0, 0.0),
        visual=VisualSpec(svg_id="resistor_default"),
        physical_attributes=PhysicalAttributes(),
    )


def _make_connection(*, connection_id: str, display_id: str) -> Connection:
    """Build a minimal `Connection` for recovery-input tests."""
    return Connection(
        id=connection_id,
        display_id=display_id,
        source=PortRef(component_id="cmp_a", port_id="p"),
        target=PortRef(component_id="cmp_b", port_id="p"),
    )


# ---------------------------------------------------------------------- #
# Internal ID format
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_new_component_id_has_cmp_prefix_and_ulid_body() -> None:
    gen = WorkspaceIdGenerator()
    cid = gen.new_component_id()
    assert cid.startswith("cmp_")
    assert _ULID_BODY_RE.match(
        cid.removeprefix("cmp_")
    ), f"ULID body must be 26 base32 chars, got {cid!r}"


@pytest.mark.unit
def test_new_connection_id_has_con_prefix_and_ulid_body() -> None:
    gen = WorkspaceIdGenerator()
    cid = gen.new_connection_id()
    assert cid.startswith("con_")
    assert _ULID_BODY_RE.match(cid.removeprefix("con_"))


@pytest.mark.unit
def test_internal_ids_are_unique_across_calls() -> None:
    gen = WorkspaceIdGenerator()
    ids = {gen.new_component_id() for _ in range(50)}
    assert len(ids) == 50, "ULIDs must not collide across rapid generation"


# ---------------------------------------------------------------------- #
# Display ID counters (components)
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_component_display_counter_is_monotonic_per_slug() -> None:
    gen = WorkspaceIdGenerator()
    assert gen.next_component_display_id("resistor") == "resistor_1"
    assert gen.next_component_display_id("resistor") == "resistor_2"
    assert gen.next_component_display_id("resistor") == "resistor_3"


@pytest.mark.unit
def test_component_display_counters_are_independent_across_slugs() -> None:
    gen = WorkspaceIdGenerator()
    assert gen.next_component_display_id("resistor") == "resistor_1"
    assert gen.next_component_display_id("capacitor") == "capacitor_1"
    assert gen.next_component_display_id("resistor") == "resistor_2"
    assert gen.next_component_display_id("capacitor") == "capacitor_2"


@pytest.mark.unit
def test_component_display_counter_supports_underscore_in_slug() -> None:
    gen = WorkspaceIdGenerator()
    assert gen.next_component_display_id("voltage_source") == "voltage_source_1"
    assert gen.next_component_display_id("voltage_source") == "voltage_source_2"


# ---------------------------------------------------------------------- #
# Display ID counter (connections)
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_connection_display_counter_is_global_and_monotonic() -> None:
    gen = WorkspaceIdGenerator()
    assert gen.next_connection_display_id() == "conn_1"
    assert gen.next_connection_display_id() == "conn_2"
    assert gen.next_connection_display_id() == "conn_3"


@pytest.mark.unit
def test_connection_counter_independent_from_component_counters() -> None:
    gen = WorkspaceIdGenerator()
    gen.next_component_display_id("resistor")
    gen.next_component_display_id("resistor")
    assert gen.next_connection_display_id() == "conn_1"


# ---------------------------------------------------------------------- #
# rebuild_counters_from
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_rebuild_counters_from_empty_inputs_resets_state() -> None:
    gen = WorkspaceIdGenerator()
    # warm up some state
    gen.next_component_display_id("resistor")
    gen.next_connection_display_id()

    gen.rebuild_counters_from(components=[], connections=[])

    # After reset both sequences should restart from 1.
    assert gen.next_component_display_id("resistor") == "resistor_1"
    assert gen.next_connection_display_id() == "conn_1"


@pytest.mark.unit
def test_rebuild_counters_from_uses_max_seen_value_skipping_deleted_ids() -> None:
    """If `resistor_2` was deleted, next must still be `resistor_6` after
    seeing `resistor_5`. Counters never reissue `02 §8.3`.
    """
    gen = WorkspaceIdGenerator()
    components = [
        _make_component(component_id="cmp_a", display_id="resistor_1"),
        _make_component(component_id="cmp_b", display_id="resistor_5"),
    ]
    gen.rebuild_counters_from(components=components, connections=[])
    assert gen.next_component_display_id("resistor") == "resistor_6"


@pytest.mark.unit
def test_rebuild_counters_from_handles_underscore_in_slug() -> None:
    """`voltage_source_42` must parse as ('voltage_source', 42), not
    ('voltage', 42) and not ('voltage_source_4', 2).
    """
    gen = WorkspaceIdGenerator()
    components = [
        _make_component(component_id="cmp_a", display_id="voltage_source_42"),
    ]
    gen.rebuild_counters_from(components=components, connections=[])
    assert gen.next_component_display_id("voltage_source") == "voltage_source_43"


@pytest.mark.unit
def test_rebuild_counters_from_skips_malformed_display_ids(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Malformed display IDs must be logged and skipped, not crash recovery
    (`02 §8.8` corrupted-file tolerance).
    """
    gen = WorkspaceIdGenerator()
    components = [
        _make_component(component_id="cmp_a", display_id="resistor_3"),
        _make_component(component_id="cmp_b", display_id="no_underscore_only_words"),
        _make_component(component_id="cmp_c", display_id=""),
        _make_component(component_id="cmp_d", display_id="resistor_NaN"),
    ]
    with caplog.at_level("WARNING"):
        gen.rebuild_counters_from(components=components, connections=[])

    # Recovery succeeds: the only valid one was resistor_3 → next is _4.
    assert gen.next_component_display_id("resistor") == "resistor_4"
    # Three malformed entries should have produced warnings.
    malformed_records = [
        r for r in caplog.records if r.message.startswith("Skipping malformed component display_id")
    ]
    assert len(malformed_records) == 3


@pytest.mark.unit
def test_rebuild_counters_from_recovers_connection_counter() -> None:
    gen = WorkspaceIdGenerator()
    connections = [
        _make_connection(connection_id="con_a", display_id="conn_1"),
        _make_connection(connection_id="con_b", display_id="conn_8"),
    ]
    gen.rebuild_counters_from(components=[], connections=connections)
    assert gen.next_connection_display_id() == "conn_9"


@pytest.mark.unit
def test_rebuild_counters_from_warns_on_unexpected_connection_prefix(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """If a connection's display_id has the wrong slug (e.g., manual edit),
    log a warning but still use the integer suffix to advance the counter.
    """
    gen = WorkspaceIdGenerator()
    connections = [
        _make_connection(connection_id="con_a", display_id="wire_5"),
    ]
    with caplog.at_level("WARNING"):
        gen.rebuild_counters_from(components=[], connections=connections)

    assert gen.next_connection_display_id() == "conn_6"
    unexpected_records = [
        r
        for r in caplog.records
        if r.message.startswith("Connection display_id has unexpected prefix")
    ]
    assert len(unexpected_records) == 1


@pytest.mark.unit
def test_rebuild_counters_from_is_idempotent() -> None:
    gen = WorkspaceIdGenerator()
    components = [
        _make_component(component_id="cmp_a", display_id="resistor_4"),
    ]
    gen.rebuild_counters_from(components=components, connections=[])
    gen.rebuild_counters_from(components=components, connections=[])
    # Second call must produce the same next value as the first would have.
    assert gen.next_component_display_id("resistor") == "resistor_5"


@pytest.mark.unit
def test_rebuild_counters_from_does_not_lower_counter() -> None:
    """If the on-disk state shows a higher counter than the generator's
    current value, recovery raises it; if lower, recovery still raises
    it relative to whatever was loaded — but the prior in-memory state
    is irrelevant because rebuild resets first. This test pins that
    contract.
    """
    gen = WorkspaceIdGenerator()
    # Pre-warm to resistor_10 in memory.
    for _ in range(10):
        gen.next_component_display_id("resistor")
    # Load contains only resistor_3.
    components = [
        _make_component(component_id="cmp_a", display_id="resistor_3"),
    ]
    gen.rebuild_counters_from(components=components, connections=[])
    # After rebuild, counter reflects loaded data (3), not in-memory (10).
    assert gen.next_component_display_id("resistor") == "resistor_4"
