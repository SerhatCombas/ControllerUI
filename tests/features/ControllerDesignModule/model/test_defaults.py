"""Unit tests for default-configuration loader (S2.B.1).

Verifies that `shared/registry/default_config.json` is shipped,
parseable, and materializes into the S2.A dataclass families with
the exact Phase-1 defaults from spec/03 §13.
"""

from __future__ import annotations

import json
from importlib.resources import files

import pytest

from features.ControllerDesignModule.model import (
    ControllerSettings,
    DefaultConfiguration,
    IOSelection,
    SimulationSettings,
    is_controller_id,
    load_default_configuration,
    load_default_controller_settings,
    load_default_io_selection,
    load_default_simulation_settings,
)

# ---------------------------------------------------------------------- #
# File existence + parseability
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_default_config_json_is_packaged_and_parseable() -> None:
    """`shared/registry/default_config.json` ships and parses as a JSON object."""
    resource = files("shared.registry") / "default_config.json"
    assert resource.is_file(), "default_config.json must be packaged"
    payload = json.loads(resource.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    # The three Phase-1 sections must be present; plot_layout
    # arrives in S2.C.
    assert "controller_settings" in payload
    assert "io_selection" in payload
    assert "simulation_settings" in payload


# ---------------------------------------------------------------------- #
# ControllerSettings defaults match spec §13
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_default_controller_settings_has_single_disabled_pid() -> None:
    """Spec §13: one disabled PID with kp=1.0, ki=0.0, kd=0.0."""
    cs = load_default_controller_settings()
    assert isinstance(cs, ControllerSettings)
    assert len(cs.controllers) == 1
    pid = cs.controllers[0]
    assert pid.controller_type == "PID"
    assert pid.enabled is False
    assert pid.parameters == {"kp": 1.0, "ki": 0.0, "kd": 0.0}
    assert pid.input_ref is None
    assert pid.output_ref is None


@pytest.mark.unit
def test_default_controller_id_is_freshly_generated_ulid() -> None:
    """The loader fills in `ctrl_<ULID>` so each call returns a unique id."""
    cs = load_default_controller_settings()
    assert is_controller_id(cs.controllers[0].id)


@pytest.mark.unit
def test_default_controller_ids_are_distinct_across_calls() -> None:
    """Re-calling the loader produces a new ULID per ADR-002.

    ADR-002 forbids ULID reuse. The default config template
    omits the `id` field on purpose; the loader injects a fresh
    one each time so consecutive "New Project" actions never
    share controller identities.
    """
    cs1 = load_default_controller_settings()
    cs2 = load_default_controller_settings()
    assert cs1.controllers[0].id != cs2.controllers[0].id


# ---------------------------------------------------------------------- #
# IOSelection + SimulationSettings defaults
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_default_io_selection_is_empty() -> None:
    """Spec §13: `io_selection.inputs` and `.outputs` are empty lists."""
    ios = load_default_io_selection()
    assert isinstance(ios, IOSelection)
    assert ios.inputs == ()
    assert ios.outputs == ()


@pytest.mark.unit
def test_default_simulation_settings_matches_spec_section_13() -> None:
    """Spec §13: `start_time=0.0`, `stop_time=10.0`, `sample_time=0.01`,
    `solver="auto"`."""
    s = load_default_simulation_settings()
    assert isinstance(s, SimulationSettings)
    assert s.start_time == 0.0
    assert s.stop_time == 10.0
    assert s.sample_time == 0.01
    assert s.solver == "auto"
    # Phase-1 default for `use_last_valid_model` is True per the
    # default_config.json shipping in this commit.
    assert s.use_last_valid_model is True
    assert s.use_controller is False
    # `initial_conditions.overrides` is empty until a user
    # populates it (Phase 2 work per spec §7.4).
    assert s.initial_conditions.source == "component_parameters"
    assert s.initial_conditions.overrides == ()


# ---------------------------------------------------------------------- #
# Aggregate loader
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_load_default_configuration_returns_all_three_sections() -> None:
    """`load_default_configuration()` aggregates the three Phase-1 sections."""
    cfg = load_default_configuration()
    assert isinstance(cfg, DefaultConfiguration)
    assert isinstance(cfg.controller_settings, ControllerSettings)
    assert isinstance(cfg.io_selection, IOSelection)
    assert isinstance(cfg.simulation_settings, SimulationSettings)


@pytest.mark.unit
def test_load_default_configuration_is_independent_of_any_project_file() -> None:
    """Spec §13 — defaults must load without a project file.

    The loader reads only from packaged resources; this test
    proves it works when no project directory or file argument
    is supplied.
    """
    cfg = load_default_configuration()
    # The PID controller is present, has a fresh ULID, and is
    # not bound to any I/O entry (no inputs/outputs exist yet).
    assert len(cfg.controller_settings.controllers) == 1
    assert cfg.controller_settings.controllers[0].input_ref is None
    assert cfg.controller_settings.controllers[0].output_ref is None
    assert cfg.io_selection.inputs == ()
    assert cfg.io_selection.outputs == ()
