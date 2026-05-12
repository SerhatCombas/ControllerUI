"""Unit tests for `shared/utils/logging_events.py` (S1.8a).

Verifies:

* Every Phase-1 event constant from spec/10 §8.1 through §8.4 + §8.6 is
  declared and matches the canonical string from the spec.
* Phase 2+ events (§8.5) are intentionally NOT declared yet.
* Every category present (workspace, project, registry, command,
  system) has at least one constant.

The arch tests in `tests/architecture/test_logging_events.py`
cover naming-convention enforcement and source-vs-module
consistency; these unit tests check the spec-fidelity of the
declared names.

References:
----------
* `specs/10_logging_conventions.md` §8
"""

from __future__ import annotations

import pytest

from shared.utils import logging_events as events

# Canonical name tables sourced directly from spec/10 §8.
# Reordering or renaming any spec entry should fail one of
# these tests so the catalog stays aligned with the spec.

_EXPECTED_WORKSPACE_EVENTS: dict[str, str] = {
    "WORKSPACE_COMPONENT_ADDED": "workspace.component_added",
    "WORKSPACE_COMPONENT_REMOVED": "workspace.component_removed",
    "WORKSPACE_COMPONENT_MOVED": "workspace.component_moved",
    "WORKSPACE_COMPONENT_ROTATED": "workspace.component_rotated",
    "WORKSPACE_COMPONENT_CHANGED": "workspace.component_changed",
    "WORKSPACE_CONNECTION_ADDED": "workspace.connection_added",
    "WORKSPACE_CONNECTION_REMOVED": "workspace.connection_removed",
    "WORKSPACE_CONNECTION_MODIFIED": "workspace.connection_modified",
    "WORKSPACE_CONNECTION_REJECTED": "workspace.connection_rejected",
    "WORKSPACE_PARAMETER_CHANGED": "workspace.parameter_changed",
    "WORKSPACE_SELECTION_CHANGED": "workspace.selection_changed",
    "WORKSPACE_VALIDATION_CHANGED": "workspace.validation_changed",
    "WORKSPACE_VALIDATION_ERRORS": "workspace.validation_errors",
}

_EXPECTED_PROJECT_EVENTS: dict[str, str] = {
    "PROJECT_NEW": "project.new",
    "PROJECT_OPENED": "project.opened",
    "PROJECT_SAVED": "project.saved",
    "PROJECT_CLOSED": "project.closed",
    "PROJECT_AUTOSAVE": "project.autosave",
    "PROJECT_RECOVERY_LOADED": "project.recovery_loaded",
    "PROJECT_MIGRATION_APPLIED": "project.migration_applied",
    "PROJECT_MIGRATION_FAILED": "project.migration_failed",
    # S2.E.2 + S2.G.2 — explicit save/load lifecycle events for
    # the persistence orchestrator and the shell File menu.
    "PROJECT_SAVE_STARTED": "project.save_started",
    "PROJECT_SAVE_COMPLETED": "project.save_completed",
    "PROJECT_SAVE_FAILED": "project.save_failed",
    "PROJECT_LOAD_STARTED": "project.load_started",
    "PROJECT_LOAD_COMPLETED": "project.load_completed",
    "PROJECT_LOAD_FAILED": "project.load_failed",
}

_EXPECTED_REGISTRY_EVENTS: dict[str, str] = {
    "REGISTRY_BOOTSTRAP_STARTED": "registry.bootstrap_started",
    "REGISTRY_BOOTSTRAP_COMPLETED": "registry.bootstrap_completed",
    "REGISTRY_DEFINITION_REGISTERED": "registry.definition_registered",
    "REGISTRY_DEFINITION_LOOKUP_FAILED": "registry.definition_lookup_failed",
}

_EXPECTED_COMMAND_EVENTS: dict[str, str] = {
    "COMMAND_REDO": "command.redo",
    "COMMAND_UNDO": "command.undo",
    "COMMAND_MERGED": "command.merged",
}

_EXPECTED_SYSTEM_EVENTS: dict[str, str] = {
    "SYSTEM_STARTUP": "system.startup",
    "SYSTEM_SHUTDOWN": "system.shutdown",
    "SYSTEM_UNHANDLED_EXCEPTION": "system.unhandled_exception",
    "SYSTEM_ARCHITECTURE_INVARIANT_VIOLATED": "system.architecture_invariant_violated",
}

# Phase 2+ event names that must NOT yet be declared per the
# module docstring's deferral note.
_DEFERRED_PHASE2_NAMES: frozenset[str] = frozenset(
    {
        "ENGINE_SIMULATION_REQUESTED",
        "ENGINE_SIMULATION_COMPLETED",
        "ENGINE_SIMULATION_FAILED",
        "ENGINE_SOLVER_SELECTED",
        "ANALYSIS_LINEARIZATION_COMPLETED",
        "ANALYSIS_STABILITY_ARTIFACT_PRODUCED",
        "CONTROLLER_RUNTIME_STARTED",
        "CONTROLLER_RUNTIME_STEP_FAILED",
    }
)


# ---------------------------------------------------------------------- #
# Per-category exact-value tests
# ---------------------------------------------------------------------- #


@pytest.mark.unit
@pytest.mark.parametrize(
    ("name", "expected"),
    list(_EXPECTED_WORKSPACE_EVENTS.items()),
)
def test_workspace_event_constant_matches_spec(name: str, expected: str) -> None:
    """Each §8.1 constant equals its canonical string."""
    assert getattr(events, name) == expected


@pytest.mark.unit
@pytest.mark.parametrize(
    ("name", "expected"),
    list(_EXPECTED_PROJECT_EVENTS.items()),
)
def test_project_event_constant_matches_spec(name: str, expected: str) -> None:
    """Each §8.2 constant equals its canonical string."""
    assert getattr(events, name) == expected


@pytest.mark.unit
@pytest.mark.parametrize(
    ("name", "expected"),
    list(_EXPECTED_REGISTRY_EVENTS.items()),
)
def test_registry_event_constant_matches_spec(name: str, expected: str) -> None:
    """Each §8.3 constant equals its canonical string."""
    assert getattr(events, name) == expected


@pytest.mark.unit
@pytest.mark.parametrize(
    ("name", "expected"),
    list(_EXPECTED_COMMAND_EVENTS.items()),
)
def test_command_event_constant_matches_spec(name: str, expected: str) -> None:
    """Each §8.4 constant equals its canonical string."""
    assert getattr(events, name) == expected


@pytest.mark.unit
@pytest.mark.parametrize(
    ("name", "expected"),
    list(_EXPECTED_SYSTEM_EVENTS.items()),
)
def test_system_event_constant_matches_spec(name: str, expected: str) -> None:
    """Each §8.6 constant equals its canonical string."""
    assert getattr(events, name) == expected


# ---------------------------------------------------------------------- #
# Phase 2+ deferral guard
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_phase2_events_are_not_declared() -> None:
    """Phase 2+ event constants (§8.5) must NOT be in the module.

    Declaring them prematurely would create dead names that drift
    out of sync with whatever the Phase 2 producer eventually
    emits. The deferral is intentional; this test guards against
    accidental early declaration.
    """
    for name in _DEFERRED_PHASE2_NAMES:
        assert not hasattr(events, name), (
            f"Phase 2+ event constant {name} is declared too early "
            "(see §8.5 deferral note in logging_events.py)"
        )


# ---------------------------------------------------------------------- #
# Catalog completeness
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_phase1_event_count_matches_spec() -> None:
    """Phase 1 declares all spec/10 §8 events plus the id_generator pair.

    Total = 13 (workspace) + 8 (project) + 4 (registry) +
    3 (command) + 4 (system) + 2 (id_generator pre-S1.8
    salvage) = 34.
    """
    expected_spec_count = (
        len(_EXPECTED_WORKSPACE_EVENTS)
        + len(_EXPECTED_PROJECT_EVENTS)
        + len(_EXPECTED_REGISTRY_EVENTS)
        + len(_EXPECTED_COMMAND_EVENTS)
        + len(_EXPECTED_SYSTEM_EVENTS)
    )
    id_generator_count = 2  # ID_GENERATOR_MALFORMED_DISPLAY_ID + ...
    assert len(events.__all__) == expected_spec_count + id_generator_count


@pytest.mark.unit
def test_every_declared_constant_uses_category_prefix() -> None:
    """Every value follows `<category>.<specific>` per `10 §8`."""
    for name in events.__all__:
        value = getattr(events, name)
        assert "." in value, f"event constant {name}={value!r} missing category prefix"
        category, specific = value.split(".", 1)
        assert category, f"event constant {name}={value!r} has empty category"
        assert specific, f"event constant {name}={value!r} has empty specific part"


@pytest.mark.unit
def test_every_category_present() -> None:
    """Each Phase-1 category contributes at least one event.

    Includes the `id_generator` module-scope category for the
    pre-S1.8 salvage events.
    """
    categories = {getattr(events, name).split(".", 1)[0] for name in events.__all__}
    assert categories == {
        "workspace",
        "project",
        "registry",
        "command",
        "system",
        "id_generator",
    }


@pytest.mark.unit
def test_all_values_are_unique() -> None:
    """No two constants share a value (canonical mapping is 1:1)."""
    values = [getattr(events, name) for name in events.__all__]
    assert len(set(values)) == len(values)


@pytest.mark.unit
def test_event_module_can_be_imported_as_package_attribute() -> None:
    """`shared.utils.logging_events` is importable.

    Smoke check that the module path is correct — the arch test
    expects `src/shared/utils/logging_events.py`.
    """
    import shared.utils.logging_events  # noqa: F401
