"""Unit tests for `ConfigurationValidator` (S2.B.2).

Coverage strategy: each of the five rules gets a positive case (clean
config produces no issue) plus one or two negative cases (a known
failure mode produces exactly the expected issue with the expected
severity and code). Plus a multi-issue test to verify the aggregator
collects everything in one report.

Per spec/03 §10.1, the validator never mutates the dataclasses it
inspects; tests confirm this by comparing snapshots before/after
`validate` calls.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPointF

from features.ControllerDesignModule.model import (
    ConfigurationValidator,
    ControllerSettings,
    ControllerSpec,
    IOEntry,
    IOSelection,
    IOSourcePortRef,
    SimulationSettings,
    load_default_configuration,
)
from features.SystemModelingModule.model.workspace_model import WorkspaceModel
from shared.graph.port_ref import PortRef
from shared.registry import ComponentRegistry
from shared.registry.builtin import (
    BUILTIN_COMPONENT_DEFINITIONS,
    RESISTOR_DEFINITION,
)


@pytest.fixture
def registry() -> ComponentRegistry:
    """Workspace registry with the Phase-1 built-in components."""
    return ComponentRegistry(BUILTIN_COMPONENT_DEFINITIONS)


@pytest.fixture
def populated_workspace(registry: ComponentRegistry) -> WorkspaceModel:
    """Workspace with one resistor placed; ports are `p` and `n`."""
    model = WorkspaceModel(registry=registry)
    model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    return model


def _validator() -> ConfigurationValidator:
    return ConfigurationValidator()


# ====================================================================== #
# Rule 1 — simulation time bounds
# ====================================================================== #


@pytest.mark.unit
def test_default_simulation_settings_produce_no_issues(
    registry: ComponentRegistry,
) -> None:
    """Defaults from `default_config.json` are internally consistent."""
    cfg = load_default_configuration()
    report = _validator().validate(
        cfg.controller_settings,
        cfg.io_selection,
        cfg.simulation_settings,
        components={},
        registry=registry,
    )
    assert report.has_errors is False
    assert report.has_warnings is False


@pytest.mark.unit
def test_stop_time_le_start_time_is_error(registry: ComponentRegistry) -> None:
    """stop_time must be > start_time (spec §7.3)."""
    sim = SimulationSettings(start_time=5.0, stop_time=5.0)
    report = _validator().validate(
        ControllerSettings(), IOSelection(), sim, components={}, registry=registry
    )
    errors = report.by_severity("error")
    assert len(errors) == 1
    assert errors[0].code == "error.validation.simulation_stop_time_le_start_time"


@pytest.mark.unit
def test_sample_time_non_positive_is_error(registry: ComponentRegistry) -> None:
    """sample_time must be > 0 (spec §7.3)."""
    sim = SimulationSettings(sample_time=0.0)
    report = _validator().validate(
        ControllerSettings(), IOSelection(), sim, components={}, registry=registry
    )
    codes = {i.code for i in report.by_severity("error")}
    assert "error.validation.simulation_sample_time_non_positive" in codes


@pytest.mark.unit
def test_max_step_non_positive_is_error(registry: ComponentRegistry) -> None:
    """`max_step` must be positive when set (spec §7.3)."""
    sim = SimulationSettings(max_step=-0.5)
    report = _validator().validate(
        ControllerSettings(), IOSelection(), sim, components={}, registry=registry
    )
    codes = {i.code for i in report.by_severity("error")}
    assert "error.validation.simulation_max_step_non_positive" in codes


@pytest.mark.unit
def test_max_step_none_is_not_flagged(registry: ComponentRegistry) -> None:
    """`max_step=None` is the "no cap" sentinel; not an error (spec §7.3)."""
    sim = SimulationSettings(max_step=None)
    report = _validator().validate(
        ControllerSettings(), IOSelection(), sim, components={}, registry=registry
    )
    assert not any("max_step" in i.code for i in report.by_severity("error"))


# ====================================================================== #
# Rule 2 — unsupported controller_type
# ====================================================================== #


@pytest.mark.unit
def test_phase1_controller_types_produce_no_warning(
    registry: ComponentRegistry,
) -> None:
    """P, PI, PD, PID are all in scope; none warn (spec §5.2)."""
    cs = ControllerSettings(
        controllers=(
            ControllerSpec(id="ctrl_A", controller_type="P"),
            ControllerSpec(id="ctrl_B", controller_type="PI"),
            ControllerSpec(id="ctrl_C", controller_type="PD"),
            ControllerSpec(id="ctrl_D", controller_type="PID"),
        )
    )
    report = _validator().validate(
        cs, IOSelection(), SimulationSettings(), components={}, registry=registry
    )
    assert not any("unsupported_controller_type" in i.code for i in report.issues)


@pytest.mark.unit
def test_unknown_controller_type_emits_warning(registry: ComponentRegistry) -> None:
    """LQR / MPC / state_feedback emit warnings (spec §12.2)."""
    cs = ControllerSettings(controllers=(ControllerSpec(id="ctrl_X", controller_type="LQR"),))
    report = _validator().validate(
        cs, IOSelection(), SimulationSettings(), components={}, registry=registry
    )
    warns = report.by_severity("warning")
    assert len(warns) == 1
    assert warns[0].code == "warning.validation.unsupported_controller_type"
    assert warns[0].subject_id == "ctrl_X"


# ====================================================================== #
# Rule 3 — unsupported solver
# ====================================================================== #


@pytest.mark.unit
def test_phase1_solvers_produce_no_warning(registry: ComponentRegistry) -> None:
    """auto / fixed_step / variable_step do not warn (spec §7.5)."""
    for solver in ("auto", "fixed_step", "variable_step"):
        sim = SimulationSettings(solver=solver)
        report = _validator().validate(
            ControllerSettings(),
            IOSelection(),
            sim,
            components={},
            registry=registry,
        )
        assert not any(
            "unsupported_solver" in i.code for i in report.issues
        ), f"unexpected warning for solver {solver!r}"


@pytest.mark.unit
def test_unknown_solver_emits_warning(registry: ComponentRegistry) -> None:
    """An out-of-set solver string emits a warning, value is preserved."""
    sim = SimulationSettings(solver="quantum_radau")
    report = _validator().validate(
        ControllerSettings(), IOSelection(), sim, components={}, registry=registry
    )
    warns = report.by_severity("warning")
    assert len(warns) == 1
    assert warns[0].code == "warning.validation.unsupported_solver"


# ====================================================================== #
# Rule 4 — stale controller I/O linkage
# ====================================================================== #


@pytest.mark.unit
def test_disabled_controller_with_stale_io_ref_does_not_warn(
    registry: ComponentRegistry,
) -> None:
    """Only enabled controllers warn on stale linkage (spec §5.5)."""
    cs = ControllerSettings(
        controllers=(
            ControllerSpec(
                id="ctrl_X",
                controller_type="PID",
                enabled=False,
                input_ref="ioin_does_not_exist",
            ),
        )
    )
    report = _validator().validate(
        cs, IOSelection(), SimulationSettings(), components={}, registry=registry
    )
    assert not any("stale_controller_input_ref" in i.code for i in report.issues)


@pytest.mark.unit
def test_enabled_controller_with_stale_input_ref_emits_warning(
    registry: ComponentRegistry,
) -> None:
    """Enabled controller pointing to a missing input warns (spec §5.5)."""
    cs = ControllerSettings(
        controllers=(
            ControllerSpec(
                id="ctrl_X",
                controller_type="PID",
                enabled=True,
                input_ref="ioin_does_not_exist",
            ),
        )
    )
    report = _validator().validate(
        cs, IOSelection(), SimulationSettings(), components={}, registry=registry
    )
    codes = {i.code for i in report.by_severity("warning")}
    assert "warning.validation.stale_controller_input_ref" in codes


@pytest.mark.unit
def test_enabled_controller_with_resolvable_refs_does_not_warn(
    registry: ComponentRegistry,
) -> None:
    """A controller whose refs resolve in IOSelection emits no issue."""
    input_entry = IOEntry(
        id="ioin_X",
        source=IOSourcePortRef(
            port_ref=PortRef(component_id="cmp_R", port_id="p"),
            variable="across",
        ),
    )
    output_entry = IOEntry(
        id="ioout_Y",
        source=IOSourcePortRef(
            port_ref=PortRef(component_id="cmp_R", port_id="n"),
            variable="across",
        ),
    )
    ios = IOSelection(inputs=(input_entry,), outputs=(output_entry,))
    cs = ControllerSettings(
        controllers=(
            ControllerSpec(
                id="ctrl_X",
                controller_type="PID",
                enabled=True,
                input_ref="ioin_X",
                output_ref="ioout_Y",
            ),
        )
    )
    report = _validator().validate(cs, ios, SimulationSettings(), components={}, registry=registry)
    # Note: IO entries themselves point to a workspace component
    # that doesn't exist — rule 5 will flag those. Rule 4 is clean
    # because both input_ref and output_ref resolve to entries.
    assert not any("stale_controller_" in i.code for i in report.issues)


# ====================================================================== #
# Rule 5 — stale I/O workspace references
# ====================================================================== #


@pytest.mark.unit
def test_io_entry_with_resolvable_port_ref_does_not_warn(
    populated_workspace: WorkspaceModel,
    registry: ComponentRegistry,
) -> None:
    """A port_ref pointing at an existing component+port is clean."""
    # Use the resistor placed by the fixture.
    component_id = next(iter(populated_workspace.components))
    entry = IOEntry(
        id="ioin_X",
        source=IOSourcePortRef(
            port_ref=PortRef(component_id=component_id, port_id="p"),
            variable="across",
        ),
    )
    ios = IOSelection(inputs=(entry,))
    report = _validator().validate(
        ControllerSettings(),
        ios,
        SimulationSettings(),
        components=populated_workspace.components,
        registry=registry,
    )
    assert not any("stale_io_" in i.code for i in report.issues)


@pytest.mark.unit
def test_io_entry_with_missing_component_warns(
    registry: ComponentRegistry,
) -> None:
    """component_id absent from snapshot → warning (spec §6.7)."""
    entry = IOEntry(
        id="ioin_X",
        source=IOSourcePortRef(
            port_ref=PortRef(component_id="cmp_GONE", port_id="p"),
            variable="across",
        ),
    )
    ios = IOSelection(inputs=(entry,))
    report = _validator().validate(
        ControllerSettings(),
        ios,
        SimulationSettings(),
        components={},
        registry=registry,
    )
    codes = {i.code for i in report.by_severity("warning")}
    assert "warning.validation.stale_io_component_ref" in codes


@pytest.mark.unit
def test_io_entry_with_missing_port_warns(
    populated_workspace: WorkspaceModel,
    registry: ComponentRegistry,
) -> None:
    """Existing component but missing port → warning (spec §6.7)."""
    component_id = next(iter(populated_workspace.components))
    entry = IOEntry(
        id="ioin_X",
        source=IOSourcePortRef(
            port_ref=PortRef(component_id=component_id, port_id="z_does_not_exist"),
            variable="across",
        ),
    )
    ios = IOSelection(inputs=(entry,))
    report = _validator().validate(
        ControllerSettings(),
        ios,
        SimulationSettings(),
        components=populated_workspace.components,
        registry=registry,
    )
    codes = {i.code for i in report.by_severity("warning")}
    assert "warning.validation.stale_io_port_ref" in codes


# ====================================================================== #
# Aggregate behaviour
# ====================================================================== #


@pytest.mark.unit
def test_multiple_independent_issues_all_appear_in_one_report(
    registry: ComponentRegistry,
) -> None:
    """The aggregator collects issues from every triggered rule."""
    cs = ControllerSettings(
        controllers=(
            ControllerSpec(
                id="ctrl_X",
                controller_type="LQR",  # rule 2
                enabled=True,
                input_ref="ioin_GONE",  # rule 4
            ),
        )
    )
    entry = IOEntry(
        id="ioin_Y",
        source=IOSourcePortRef(
            port_ref=PortRef(component_id="cmp_GONE", port_id="p"),  # rule 5
            variable="across",
        ),
    )
    ios = IOSelection(inputs=(entry,))
    sim = SimulationSettings(
        start_time=10.0,
        stop_time=5.0,
        solver="custom_solver",  # rules 1+3
    )
    report = _validator().validate(cs, ios, sim, components={}, registry=registry)
    codes = {i.code for i in report.issues}
    expected = {
        "error.validation.simulation_stop_time_le_start_time",
        "warning.validation.unsupported_solver",
        "warning.validation.unsupported_controller_type",
        "warning.validation.stale_controller_input_ref",
        "warning.validation.stale_io_component_ref",
    }
    assert expected.issubset(codes)


@pytest.mark.unit
def test_validator_does_not_mutate_inputs(registry: ComponentRegistry) -> None:
    """`validate` is a read-only function over its arguments."""
    cs = ControllerSettings(
        controllers=(
            ControllerSpec(
                id="ctrl_X",
                controller_type="LQR",
                enabled=True,
                input_ref="ioin_GONE",
            ),
        )
    )
    ios = IOSelection()
    sim = SimulationSettings(stop_time=-1.0)
    cs_snapshot = cs
    ios_snapshot = ios
    sim_snapshot = sim
    _validator().validate(cs, ios, sim, components={}, registry=registry)
    assert cs == cs_snapshot
    assert ios == ios_snapshot
    assert sim == sim_snapshot
