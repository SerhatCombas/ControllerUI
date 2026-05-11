"""Unit tests for `ComponentRegistry` event emission (S1.8c).

Verifies the four `registry.*` events from spec/10 §8.3 fire
at the expected lifecycle points:

* `registry.bootstrap_started` — entry of `__init__`
* `registry.definition_registered` — one per definition
  successfully added to the internal dict
* `registry.bootstrap_completed` — exit of `__init__` (with
  total count in the payload)
* `registry.definition_lookup_failed` — `get()` raises
  `KeyError` for an unregistered id (warning severity)

References:
----------
* `specs/10_logging_conventions.md` §8.3
"""

from __future__ import annotations

import logging

import pytest

from shared.registry import ComponentRegistry
from shared.registry.builtin import (
    BUILTIN_COMPONENT_DEFINITIONS,
    RESISTOR_DEFINITION,
)
from shared.utils import logging_events as events

_REGISTRY_LOGGER = "shared.registry.component_registry"


def _events_with(
    records: list[logging.LogRecord],
    event_name: str,
) -> list[logging.LogRecord]:
    """Filter records to those carrying `extra={"event": event_name}`."""
    return [r for r in records if getattr(r, "event", None) == event_name]


@pytest.mark.unit
def test_bootstrap_emits_started_and_completed_events(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Constructor emits `bootstrap_started` then `bootstrap_completed`."""
    caplog.clear()
    with caplog.at_level(logging.INFO, logger=_REGISTRY_LOGGER):
        ComponentRegistry(BUILTIN_COMPONENT_DEFINITIONS)

    started = _events_with(caplog.records, events.REGISTRY_BOOTSTRAP_STARTED)
    completed = _events_with(caplog.records, events.REGISTRY_BOOTSTRAP_COMPLETED)
    assert len(started) == 1
    assert len(completed) == 1
    assert completed[0].definition_count == len(BUILTIN_COMPONENT_DEFINITIONS)  # type: ignore[attr-defined]


@pytest.mark.unit
def test_bootstrap_emits_one_definition_registered_per_entry(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """One `definition_registered` event fires per registered definition."""
    caplog.clear()
    with caplog.at_level(logging.INFO, logger=_REGISTRY_LOGGER):
        ComponentRegistry(BUILTIN_COMPONENT_DEFINITIONS)

    registered = _events_with(caplog.records, events.REGISTRY_DEFINITION_REGISTERED)
    assert len(registered) == len(BUILTIN_COMPONENT_DEFINITIONS)
    # Each event carries the definition id + domain + category.
    ids = {r.definition_id for r in registered}  # type: ignore[attr-defined]
    assert ids == {d.id for d in BUILTIN_COMPONENT_DEFINITIONS}


@pytest.mark.unit
def test_get_unknown_id_emits_lookup_failed_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """`get()` raises `KeyError` AND emits a warning event."""
    registry = ComponentRegistry(BUILTIN_COMPONENT_DEFINITIONS)

    caplog.clear()
    with (
        caplog.at_level(logging.WARNING, logger=_REGISTRY_LOGGER),
        pytest.raises(KeyError),
    ):
        registry.get("electrical.unknown.does_not_exist")

    failed = _events_with(caplog.records, events.REGISTRY_DEFINITION_LOOKUP_FAILED)
    assert len(failed) == 1
    assert failed[0].definition_id == "electrical.unknown.does_not_exist"  # type: ignore[attr-defined]


@pytest.mark.unit
def test_get_known_id_does_not_emit_lookup_failed(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Successful `get()` is silent — no warning event."""
    registry = ComponentRegistry(BUILTIN_COMPONENT_DEFINITIONS)

    caplog.clear()
    with caplog.at_level(logging.WARNING, logger=_REGISTRY_LOGGER):
        registry.get(RESISTOR_DEFINITION.id)

    assert _events_with(caplog.records, events.REGISTRY_DEFINITION_LOOKUP_FAILED) == []
