"""Tests for the project save/load orchestrator (S2.E.2).

Three coverage axes:

* **Round-trip** at three scales: empty project, single-component
  + single-controller, every Phase-1 built-in component.
* **Determinism**: save → load → save produces byte-identical
  `project.json`. Catches dict-key reorder bugs and float drift.
* **Failure paths**: file-not-directory, missing project.json,
  malformed JSON, newer schema_version, cross-model atomicity
  via injected failure on the configuration side.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from PySide6.QtCore import QPointF

from application.persistence import (
    ProjectFormatError,
    load_project,
    save_project,
)
from features.ControllerDesignModule.model import (
    ConfigurationModel,
    ControllerSettings,
    IOSelection,
    PlotLayout,
    SimulationSettings,
    load_default_configuration,
)
from features.SystemModelingModule.model.migrations import SchemaMigrationError
from features.SystemModelingModule.model.workspace_model import WorkspaceModel
from shared.registry import ComponentRegistry
from shared.registry.builtin import (
    BUILTIN_COMPONENT_DEFINITIONS,
    RESISTOR_DEFINITION,
)

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def registry() -> ComponentRegistry:
    return ComponentRegistry(BUILTIN_COMPONENT_DEFINITIONS)


def _build_fresh_models(
    registry: ComponentRegistry,
) -> tuple[WorkspaceModel, ConfigurationModel]:
    """Return a clean (workspace, configuration) pair for load tests."""
    return (
        WorkspaceModel(registry=registry),
        ConfigurationModel(
            controller_settings=ControllerSettings(),
            io_selection=IOSelection(),
            simulation_settings=SimulationSettings(),
            plot_layout=PlotLayout(),
        ),
    )


def _populate_default_config(cm: ConfigurationModel, cfg_loader: object | None = None) -> None:
    """Apply the spec/03 §13 defaults to an empty ConfigurationModel."""
    cfg = load_default_configuration()
    cm.set_controller_settings(cfg.controller_settings)
    cm.set_io_selection(cfg.io_selection)
    cm.set_simulation_settings(cfg.simulation_settings)
    cm.set_plot_layout(cfg.plot_layout)


# ====================================================================== #
# Round-trip at three scales
# ====================================================================== #


@pytest.mark.integration
def test_round_trip_empty_project(tmp_path: Path, registry: ComponentRegistry) -> None:
    """Empty project: save + load round-trips with zero data."""
    ws, cm = _build_fresh_models(registry)
    bundle = tmp_path / "empty.systemdesign"
    save_project(bundle, workspace_model=ws, configuration_model=cm)

    ws2, cm2 = _build_fresh_models(registry)
    load_project(bundle, workspace_model=ws2, configuration_model=cm2)
    assert len(ws2.components) == 0
    assert len(ws2.connections) == 0
    assert cm2.controller_settings == ControllerSettings()


@pytest.mark.integration
def test_round_trip_single_component_and_controller(
    tmp_path: Path, registry: ComponentRegistry
) -> None:
    """One workspace component + Phase-1 default config round-trip."""
    ws, cm = _build_fresh_models(registry)
    rid = ws.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(10.0, 20.0))
    _populate_default_config(cm)

    bundle = tmp_path / "single.systemdesign"
    save_project(bundle, workspace_model=ws, configuration_model=cm)

    ws2, cm2 = _build_fresh_models(registry)
    load_project(bundle, workspace_model=ws2, configuration_model=cm2)

    # Components survived round-trip with their ULID identity.
    assert set(ws2.components.keys()) == {rid}
    # Phase-1 default controller transferred.
    assert len(cm2.controller_settings.controllers) == 1
    assert cm2.controller_settings.controllers[0].controller_type == "PID"
    # Plot layout 4-slot defaults transferred.
    assert len(cm2.plot_layout.slots) == 4


@pytest.mark.integration
def test_round_trip_every_builtin_component(tmp_path: Path, registry: ComponentRegistry) -> None:
    """All 23 BUILTIN_COMPONENT_DEFINITIONS placed + round-tripped."""
    ws, cm = _build_fresh_models(registry)
    for i, definition in enumerate(BUILTIN_COMPONENT_DEFINITIONS):
        ws.add_component_from_definition(definition.id, QPointF(50.0 * i, 50.0))
    _populate_default_config(cm)

    bundle = tmp_path / "full.systemdesign"
    save_project(bundle, workspace_model=ws, configuration_model=cm)

    ws2, cm2 = _build_fresh_models(registry)
    load_project(bundle, workspace_model=ws2, configuration_model=cm2)

    assert len(ws2.components) == len(BUILTIN_COMPONENT_DEFINITIONS)
    loaded_definition_ids = {c.definition_id for c in ws2.components.values()}
    expected_definition_ids = {d.id for d in BUILTIN_COMPONENT_DEFINITIONS}
    assert loaded_definition_ids == expected_definition_ids


# ====================================================================== #
# Determinism (spec §29.3.1 deterministic output)
# ====================================================================== #


@pytest.mark.integration
def test_save_load_save_yields_byte_identical_project_json(
    tmp_path: Path, registry: ComponentRegistry
) -> None:
    """save → load → save produces an identical project.json byte stream.

    Catches dict-key reorder bugs, list-iteration nondeterminism,
    and float drift across the to_dict/from_dict cycle.
    """
    ws, cm = _build_fresh_models(registry)
    for i, definition in enumerate(BUILTIN_COMPONENT_DEFINITIONS[:5]):
        ws.add_component_from_definition(definition.id, QPointF(50.0 * i, 100.0))
    _populate_default_config(cm)

    bundle = tmp_path / "deterministic.systemdesign"
    save_project(bundle, workspace_model=ws, configuration_model=cm)
    first_bytes = (bundle / "project.json").read_bytes()

    ws2, cm2 = _build_fresh_models(registry)
    load_project(bundle, workspace_model=ws2, configuration_model=cm2)
    save_project(bundle, workspace_model=ws2, configuration_model=cm2)
    second_bytes = (bundle / "project.json").read_bytes()

    assert first_bytes == second_bytes


# ====================================================================== #
# Bundle layout
# ====================================================================== #


@pytest.mark.integration
def test_save_creates_three_phase1_subdirectories(
    tmp_path: Path, registry: ComponentRegistry
) -> None:
    """`results/`, `exports/`, `recovery/` exist after save per ADR-012."""
    ws, cm = _build_fresh_models(registry)
    bundle = tmp_path / "layout.systemdesign"
    save_project(bundle, workspace_model=ws, configuration_model=cm)
    assert (bundle / "results").is_dir()
    assert (bundle / "exports").is_dir()
    assert (bundle / "recovery").is_dir()
    assert (bundle / "project.json").is_file()


@pytest.mark.integration
def test_save_into_existing_bundle_overwrites_project_json(
    tmp_path: Path, registry: ComponentRegistry
) -> None:
    """Re-saving into the same bundle replaces project.json atomically."""
    ws, cm = _build_fresh_models(registry)
    bundle = tmp_path / "rewrite.systemdesign"
    save_project(bundle, workspace_model=ws, configuration_model=cm)
    first_payload = (bundle / "project.json").read_text(encoding="utf-8")

    ws.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0, 0))
    save_project(bundle, workspace_model=ws, configuration_model=cm)
    second_payload = (bundle / "project.json").read_text(encoding="utf-8")

    assert first_payload != second_payload
    # No stray temp file lingers.
    assert not (bundle / "project.json.tmp").exists()


@pytest.mark.integration
def test_save_recreates_missing_subdirectories(tmp_path: Path, registry: ComponentRegistry) -> None:
    """Lenient policy: deleted subdirs are recreated on next save."""
    ws, cm = _build_fresh_models(registry)
    bundle = tmp_path / "recreate.systemdesign"
    save_project(bundle, workspace_model=ws, configuration_model=cm)

    (bundle / "results").rmdir()
    assert not (bundle / "results").exists()
    save_project(bundle, workspace_model=ws, configuration_model=cm)
    assert (bundle / "results").is_dir()


# ====================================================================== #
# Failure paths
# ====================================================================== #


@pytest.mark.integration
def test_load_file_path_raises_with_clear_message(
    tmp_path: Path, registry: ComponentRegistry
) -> None:
    """A regular file path explains the directory-bundle requirement."""
    bad_path = tmp_path / "legacy.json"
    bad_path.write_text("{}", encoding="utf-8")
    ws, cm = _build_fresh_models(registry)
    with pytest.raises(ProjectFormatError, match="directory bundle"):
        load_project(bad_path, workspace_model=ws, configuration_model=cm)


@pytest.mark.integration
def test_load_missing_bundle_raises_file_not_found(
    tmp_path: Path, registry: ComponentRegistry
) -> None:
    """A nonexistent path raises `FileNotFoundError`, not a generic format error."""
    ws, cm = _build_fresh_models(registry)
    with pytest.raises(FileNotFoundError):
        load_project(
            tmp_path / "ghost.systemdesign",
            workspace_model=ws,
            configuration_model=cm,
        )


@pytest.mark.integration
def test_load_bundle_without_project_json_raises(
    tmp_path: Path, registry: ComponentRegistry
) -> None:
    """A directory exists but lacks `project.json` → `ProjectFormatError`."""
    empty_bundle = tmp_path / "empty.systemdesign"
    empty_bundle.mkdir()
    ws, cm = _build_fresh_models(registry)
    with pytest.raises(ProjectFormatError, match="project.json"):
        load_project(empty_bundle, workspace_model=ws, configuration_model=cm)


@pytest.mark.integration
def test_load_malformed_json_raises_project_format_error(
    tmp_path: Path, registry: ComponentRegistry
) -> None:
    """Corrupted JSON surfaces as a structured error, not a JSONDecodeError."""
    bundle = tmp_path / "corrupted.systemdesign"
    bundle.mkdir()
    (bundle / "project.json").write_text("{not valid json", encoding="utf-8")
    ws, cm = _build_fresh_models(registry)
    with pytest.raises(ProjectFormatError, match="malformed JSON"):
        load_project(bundle, workspace_model=ws, configuration_model=cm)


@pytest.mark.integration
def test_load_newer_schema_version_raises_migration_error(
    tmp_path: Path, registry: ComponentRegistry
) -> None:
    """A future `schema_version` is forward-incompatible → migration error."""
    bundle = tmp_path / "future.systemdesign"
    bundle.mkdir()
    future_payload = {
        "schema_version": "9.9.9",
        "application_version": "9.9.9",
        "components": [],
        "connections": [],
    }
    (bundle / "project.json").write_text(json.dumps(future_payload), encoding="utf-8")
    ws, cm = _build_fresh_models(registry)
    with pytest.raises(SchemaMigrationError, match="newer than"):
        load_project(bundle, workspace_model=ws, configuration_model=cm)


@pytest.mark.integration
def test_save_into_existing_file_path_raises(tmp_path: Path, registry: ComponentRegistry) -> None:
    """Saving to a path that is a regular file (not a bundle) → ProjectFormatError."""
    bad_path = tmp_path / "not_a_bundle"
    bad_path.write_text("placeholder", encoding="utf-8")
    ws, cm = _build_fresh_models(registry)
    with pytest.raises(ProjectFormatError, match="regular file"):
        save_project(bad_path, workspace_model=ws, configuration_model=cm)


# ====================================================================== #
# Cross-model atomicity (snapshot + rollback)
# ====================================================================== #


@pytest.mark.integration
def test_load_workspace_unchanged_when_configuration_section_malformed(
    tmp_path: Path, registry: ComponentRegistry
) -> None:
    """Cross-model atomicity: if config parse fails, workspace stays prior.

    Save a valid bundle, manually corrupt the configuration
    section in project.json, then load into populated models.
    The workspace model should NOT be reset to the malformed
    bundle's workspace content; both models stay at their prior
    state via snapshot-rollback.
    """
    ws_source, cm_source = _build_fresh_models(registry)
    ws_source.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    _populate_default_config(cm_source)
    bundle = tmp_path / "broken_config.systemdesign"
    save_project(bundle, workspace_model=ws_source, configuration_model=cm_source)

    # Corrupt the configuration section: insert a malformed
    # controller (missing controller_type → ControllerSpec.from_dict
    # raises). Workspace section stays valid.
    payload = json.loads((bundle / "project.json").read_text(encoding="utf-8"))
    payload["controller_settings"] = {
        "controllers": [{"id": "ctrl_X"}],  # missing controller_type
        "metadata": {},
        "extensions": {},
    }
    (bundle / "project.json").write_text(json.dumps(payload), encoding="utf-8")

    # Pre-populate the target models with distinct prior state.
    ws_target = WorkspaceModel(registry=registry)
    cid_existing = ws_target.add_component_from_definition(
        RESISTOR_DEFINITION.id, QPointF(99.0, 99.0)
    )
    cm_target = ConfigurationModel(
        controller_settings=ControllerSettings(),
        io_selection=IOSelection(),
        simulation_settings=SimulationSettings(stop_time=77.0),
        plot_layout=PlotLayout(),
    )

    with pytest.raises(KeyError):
        load_project(bundle, workspace_model=ws_target, configuration_model=cm_target)

    # Workspace rolled back to its prior state.
    assert set(ws_target.components.keys()) == {cid_existing}
    # Configuration untouched.
    assert cm_target.simulation_settings.stop_time == 77.0


# ====================================================================== #
# application_version + JSON formatting checks
# ====================================================================== #


@pytest.mark.integration
def test_saved_project_carries_application_version(
    tmp_path: Path, registry: ComponentRegistry
) -> None:
    """`application_version` is written from `importlib.metadata`."""
    ws, cm = _build_fresh_models(registry)
    bundle = tmp_path / "versioned.systemdesign"
    save_project(bundle, workspace_model=ws, configuration_model=cm)
    payload = json.loads((bundle / "project.json").read_text(encoding="utf-8"))
    # The actual value comes from pyproject.toml; verify it's a
    # nonempty string in dotted-version form rather than a fixed
    # constant (so a future pyproject bump doesn't break the test).
    assert isinstance(payload["application_version"], str)
    assert payload["application_version"].count(".") >= 1


@pytest.mark.integration
def test_saved_project_uses_lf_line_endings(tmp_path: Path, registry: ComponentRegistry) -> None:
    """PD6 encoding: LF line endings only, no CRLF."""
    ws, cm = _build_fresh_models(registry)
    bundle = tmp_path / "lf.systemdesign"
    save_project(bundle, workspace_model=ws, configuration_model=cm)
    raw = (bundle / "project.json").read_bytes()
    assert b"\r\n" not in raw, "project.json should use LF line endings only"


@pytest.mark.integration
def test_saved_project_uses_utf8_no_bom(tmp_path: Path, registry: ComponentRegistry) -> None:
    """PD6 encoding: UTF-8 without BOM."""
    ws, cm = _build_fresh_models(registry)
    bundle = tmp_path / "utf8.systemdesign"
    save_project(bundle, workspace_model=ws, configuration_model=cm)
    raw = (bundle / "project.json").read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf"), "BOM forbidden in project.json"
    # Confirm decodable as UTF-8 strict.
    raw.decode("utf-8")


@pytest.mark.integration
def test_saved_project_uses_indent_2(tmp_path: Path, registry: ComponentRegistry) -> None:
    """PD6 encoding: human-diffable 2-space indent."""
    ws, cm = _build_fresh_models(registry)
    bundle = tmp_path / "indent.systemdesign"
    save_project(bundle, workspace_model=ws, configuration_model=cm)
    text = (bundle / "project.json").read_text(encoding="utf-8")
    # `indent=2` produces leading 2-space indentation on
    # second-level keys. Spot-check the schema_version line nesting.
    assert '  "schema_version":' in text
