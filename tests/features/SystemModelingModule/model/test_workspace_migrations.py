"""Unit tests for the schema-migration framework (S2.E.1).

The framework lives in `features/SystemModelingModule/model/migrations/`.
Phase-1 ships an empty registry (no production migration exists at
this point in the project's lifetime), but the registry's dispatch
path is fully exercised here via a SYNTHETIC `0.1.0 → 0.2.0`
migration registered just for these tests.

Test strategy:

* Verify the empty-registry-pass-through case: a `0.2.0` input
  returns identical to current.
* Synthetic 0.1.0 fixture: registered migration walks the chain.
* Newer-version refusal: `0.3.0` input raises
  `SchemaMigrationError`.
* Missing `schema_version` raises.
* Cycle detection raises (defensive).

The synthetic migration is installed via a `monkeypatch.setitem`
on `WorkspaceModelMigrations.MIGRATIONS` so it doesn't leak into
other test files.
"""

from __future__ import annotations

from typing import Any

import pytest

from features.SystemModelingModule.model.migrations import (
    CURRENT_SCHEMA_VERSION,
    SchemaMigrationError,
    WorkspaceModelMigrations,
)

# ====================================================================== #
# Pass-through: input already at target
# ====================================================================== #


@pytest.mark.unit
def test_current_version_input_returns_identical_payload() -> None:
    """Input at `CURRENT_SCHEMA_VERSION` returns a copy of the same data."""
    data = {"schema_version": CURRENT_SCHEMA_VERSION, "components": []}
    out = WorkspaceModelMigrations.migrate(data)
    assert out == data
    assert out is not data  # never mutates input


# ====================================================================== #
# Synthetic chain: 0.1.0 → 0.2.0 via a test-installed migration
# ====================================================================== #


def _migrate_0_1_0_to_0_2_0(data: dict[str, Any]) -> dict[str, Any]:
    """Synthetic migration installed only during these tests.

    Models a typical schema bump: bump `schema_version`, add a
    new top-level field that didn't exist in 0.1.0, leave the
    rest untouched. Pure function — no I/O.
    """
    return {**data, "schema_version": "0.2.0", "added_field": "phase1_default"}


@pytest.mark.unit
def test_synthetic_migration_chain_runs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A registered 0.1.0 → 0.2.0 entry walks from older payload to target."""
    monkeypatch.setitem(
        WorkspaceModelMigrations.MIGRATIONS,
        ("0.1.0", "0.2.0"),
        _migrate_0_1_0_to_0_2_0,
    )
    legacy = {"schema_version": "0.1.0", "components": []}
    migrated = WorkspaceModelMigrations.migrate(legacy)
    assert migrated["schema_version"] == "0.2.0"
    assert migrated["added_field"] == "phase1_default"
    assert migrated["components"] == []
    # Input untouched.
    assert legacy["schema_version"] == "0.1.0"
    assert "added_field" not in legacy


@pytest.mark.unit
def test_multi_step_migration_chain(monkeypatch: pytest.MonkeyPatch) -> None:
    """Migration registry walks transitive chains: 0.1.0 → 0.1.5 → 0.2.0."""

    def to_0_1_5(d: dict[str, Any]) -> dict[str, Any]:
        return {**d, "schema_version": "0.1.5", "step_a": 1}

    def to_0_2_0(d: dict[str, Any]) -> dict[str, Any]:
        return {**d, "schema_version": "0.2.0", "step_b": 2}

    monkeypatch.setitem(
        WorkspaceModelMigrations.MIGRATIONS,
        ("0.1.0", "0.1.5"),
        to_0_1_5,
    )
    monkeypatch.setitem(
        WorkspaceModelMigrations.MIGRATIONS,
        ("0.1.5", "0.2.0"),
        to_0_2_0,
    )
    out = WorkspaceModelMigrations.migrate({"schema_version": "0.1.0"})
    assert out["schema_version"] == "0.2.0"
    assert out["step_a"] == 1
    assert out["step_b"] == 2


# ====================================================================== #
# Error paths
# ====================================================================== #


@pytest.mark.unit
def test_missing_schema_version_raises() -> None:
    """A payload without `schema_version` cannot be dispatched."""
    with pytest.raises(SchemaMigrationError, match="missing 'schema_version'"):
        WorkspaceModelMigrations.migrate({"components": []})


@pytest.mark.unit
def test_newer_version_input_raises() -> None:
    """`0.3.0` input fails forward compatibility against `0.2.0` target."""
    data = {"schema_version": "0.3.0", "components": []}
    with pytest.raises(SchemaMigrationError, match="newer than"):
        WorkspaceModelMigrations.migrate(data)


@pytest.mark.unit
def test_unknown_older_version_raises() -> None:
    """An older version with no registered migration raises `no path`."""
    # 0.0.5 < 0.2.0 but no migration registered → no path.
    data = {"schema_version": "0.0.5", "components": []}
    with pytest.raises(SchemaMigrationError, match="no migration path"):
        WorkspaceModelMigrations.migrate(data)


@pytest.mark.unit
def test_migration_chain_cycle_detected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Defensive cycle detection raises rather than spinning forever."""

    def to_a(d: dict[str, Any]) -> dict[str, Any]:
        return {**d, "schema_version": "test_a"}

    def back_to_start(d: dict[str, Any]) -> dict[str, Any]:
        return {**d, "schema_version": "test_start"}

    monkeypatch.setitem(
        WorkspaceModelMigrations.MIGRATIONS,
        ("test_start", "test_a"),
        to_a,
    )
    monkeypatch.setitem(
        WorkspaceModelMigrations.MIGRATIONS,
        ("test_a", "test_start"),
        back_to_start,
    )
    with pytest.raises(SchemaMigrationError, match="cycle"):
        WorkspaceModelMigrations.migrate(
            {"schema_version": "test_start"},
            target_version="0.2.0",
        )


@pytest.mark.unit
def test_phase_1_registry_is_empty() -> None:
    """Phase-1 ships an empty registry; no production migrations exist yet."""
    assert WorkspaceModelMigrations.MIGRATIONS == {}
