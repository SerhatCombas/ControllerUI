"""Unit tests for `GraphValidator.validate_workspace` (S1.6a).

Covers the three Phase-1 workspace-level rules from `02 §20`:

1. Required ports must be connected (warning) — `02 §20.1`.
2. Domain reference rule — electrical → Ground, mechanical →
   Fixed (error) — `02 §20.4`.
3. Parameter validation via `ParameterValidator` (error) —
   `02 §9.4`.

Empty / registry-less paths are also exercised so callers
(future debounce controller in S1.6b) can rely on safe
behavior across partial states.

References:
----------
* `specs/02_workspace_requirements.md` §9.4, §20
* `specs/11_error_code_catalog.md` §7.3, §7.7
* `specs/07_implementation_order.md` §7.11
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPointF

from features.SystemModelingModule.model.connection import PortRef
from features.SystemModelingModule.model.graph_validator import GraphValidator
from features.SystemModelingModule.model.workspace_model import WorkspaceModel
from shared.registry import (
    ComponentDefinition,
    ComponentRegistry,
    LibraryVisualSpec,
    ParameterDefinition,
    PortDefinition,
)
from shared.registry.builtin import (
    BUILTIN_COMPONENT_DEFINITIONS,
    FIXED_DEFINITION,
    GROUND_ELECTRIC_DEFINITION,
    MASS_DEFINITION,
    RESISTOR_DEFINITION,
)


@pytest.fixture
def validator() -> GraphValidator:
    """A `GraphValidator` instance."""
    return GraphValidator()


@pytest.fixture
def registry() -> ComponentRegistry:
    """Registry populated with the Phase-1 MVP definitions."""
    return ComponentRegistry(BUILTIN_COMPONENT_DEFINITIONS)


@pytest.fixture
def model(registry: ComponentRegistry) -> WorkspaceModel:
    """Registry-wired empty workspace."""
    return WorkspaceModel(registry=registry)


def _run(
    validator: GraphValidator,
    model: WorkspaceModel,
    *,
    registry: ComponentRegistry | None = None,
) -> object:
    """Invoke `validate_workspace` from a model snapshot."""
    return validator.validate_workspace(
        components=model.components,
        connections=model.connections.values(),
        registry=registry if registry is not None else model.registry,
    )


# ---------------------------------------------------------------------- #
# Empty / minimum-state paths
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_empty_workspace_yields_empty_report(
    validator: GraphValidator,
    model: WorkspaceModel,
) -> None:
    """No components → no rules apply → clean report."""
    report = _run(validator, model)

    assert report.issues == ()


@pytest.mark.unit
def test_registry_less_model_skips_port_and_parameter_rules(
    validator: GraphValidator,
) -> None:
    """Without a registry the port + parameter rules cannot run.

    The domain-reference rule still runs because it reads
    `instance.domain` directly. With one electrical component
    and no ground in a registry-less model, only the missing-
    ground error appears — the dangling-port warning that
    would otherwise fire is silent.
    """
    from features.SystemModelingModule.model.component_instance import (
        PhysicalAttributes,
        VisualSpec,
    )

    no_registry = WorkspaceModel()
    no_registry.add_component(
        definition_id="electrical.analog.components.resistor",
        type="Resistor",
        display_name="Resistor",
        domain="electrical_analog",
        category="component",
        position=QPointF(0.0, 0.0),
        visual=VisualSpec(svg_id="x"),
        physical_attributes=PhysicalAttributes(),
    )

    report = validator.validate_workspace(
        components=no_registry.components,
        connections=no_registry.connections.values(),
        registry=None,
    )

    codes = [issue.code for issue in report.issues]
    assert codes == ["error.validation.missing_ground"]


# ---------------------------------------------------------------------- #
# Rule 1: required ports must be connected
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_isolated_component_reports_warnings_for_each_required_port(
    validator: GraphValidator,
    model: WorkspaceModel,
) -> None:
    """A resistor with no connections triggers `unused_port` for both `p` and `n`.

    Plus the missing-ground error (electrical domain has a
    component but no ground reference).
    """
    model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))

    report = _run(validator, model)

    unused_port_codes = [
        issue for issue in report.issues if issue.code == "warning.validation.unused_port"
    ]
    assert len(unused_port_codes) == 2
    assert {issue.context["port_id"] for issue in unused_port_codes} == {"p", "n"}


@pytest.mark.unit
def test_connected_required_ports_emit_no_warnings(
    validator: GraphValidator,
    model: WorkspaceModel,
) -> None:
    """When every required port is connected, no `unused_port` warning fires.

    Two resistors fully wired together — both ports of each
    resistor are connected. Still produces a missing-ground
    error (no ground in the workspace).
    """
    cid_a = model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    cid_b = model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(60.0, 0.0))
    model.add_connection(
        source=PortRef(component_id=cid_a, port_id="p"),
        target=PortRef(component_id=cid_b, port_id="p"),
    )
    model.add_connection(
        source=PortRef(component_id=cid_a, port_id="n"),
        target=PortRef(component_id=cid_b, port_id="n"),
    )

    report = _run(validator, model)

    unused = [i for i in report.issues if i.code == "warning.validation.unused_port"]
    assert unused == []


# ---------------------------------------------------------------------- #
# Rule 2: domain reference (ground / fixed)
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_electrical_without_ground_reports_missing_ground(
    validator: GraphValidator,
    model: WorkspaceModel,
) -> None:
    """A resistor without a ground component triggers `missing_ground`."""
    model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))

    report = _run(validator, model)

    missing = [i for i in report.issues if i.code == "error.validation.missing_ground"]
    assert len(missing) == 1
    assert missing[0].subject_kind == "workspace"


@pytest.mark.unit
def test_electrical_with_ground_does_not_report_missing_ground(
    validator: GraphValidator,
    model: WorkspaceModel,
) -> None:
    """Adding a ground silences the `missing_ground` error."""
    model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    model.add_component_from_definition(GROUND_ELECTRIC_DEFINITION.id, QPointF(60.0, 0.0))

    report = _run(validator, model)

    missing = [i for i in report.issues if i.code == "error.validation.missing_ground"]
    assert missing == []


@pytest.mark.unit
def test_mechanical_without_fixed_reports_missing_fixed_reference(
    validator: GraphValidator,
    model: WorkspaceModel,
) -> None:
    """A mass without a fixed component triggers `missing_fixed_reference`."""
    model.add_component_from_definition(MASS_DEFINITION.id, QPointF(0.0, 0.0))

    report = _run(validator, model)

    missing = [i for i in report.issues if i.code == "error.validation.missing_fixed_reference"]
    assert len(missing) == 1


@pytest.mark.unit
def test_mechanical_with_fixed_does_not_report_missing_fixed_reference(
    validator: GraphValidator,
    model: WorkspaceModel,
) -> None:
    """Adding a fixed silences the `missing_fixed_reference` error."""
    model.add_component_from_definition(MASS_DEFINITION.id, QPointF(0.0, 0.0))
    model.add_component_from_definition(FIXED_DEFINITION.id, QPointF(60.0, 0.0))

    report = _run(validator, model)

    missing = [i for i in report.issues if i.code == "error.validation.missing_fixed_reference"]
    assert missing == []


# ---------------------------------------------------------------------- #
# Rule 3: parameter validation
# ---------------------------------------------------------------------- #


# A definition with strict parameter constraints so the
# parameter-validation rule has something to find.
_STRICT_PARAM_DEFINITION = ComponentDefinition(
    id="test.strict.params",
    display_name="Strict",
    short_name="S",
    domain="electrical_analog",
    library_path=("Test",),
    category="component",
    ports=(PortDefinition(id="p", display_name="P", domain="electrical_analog"),),
    parameters=(
        ParameterDefinition(
            id="bounded",
            display_name="Bounded",
            type="float",
            default=0.5,
            min=0.0,
            max=1.0,
        ),
        ParameterDefinition(
            id="mode",
            display_name="Mode",
            type="enum",
            default="a",
            allowed_values=("a", "b"),
        ),
    ),
    visual=LibraryVisualSpec(svg_id="x"),
)


@pytest.fixture
def strict_registry() -> ComponentRegistry:
    """Registry with the MVP set + the strict-param test definition."""
    return ComponentRegistry((*BUILTIN_COMPONENT_DEFINITIONS, _STRICT_PARAM_DEFINITION))


@pytest.fixture
def strict_model(strict_registry: ComponentRegistry) -> WorkspaceModel:
    """Model wired with the strict-param registry."""
    return WorkspaceModel(registry=strict_registry)


@pytest.mark.unit
def test_parameter_out_of_range_reports_error(
    validator: GraphValidator,
    strict_model: WorkspaceModel,
) -> None:
    """A float parameter above its declared max triggers `out_of_range`."""
    strict_model.add_component_from_definition(
        _STRICT_PARAM_DEFINITION.id,
        QPointF(0.0, 0.0),
        parameters={"bounded": 5.0},  # > max=1.0
    )

    report = _run(validator, strict_model)

    out_of_range = [i for i in report.issues if i.code == "error.parameter.out_of_range"]
    assert len(out_of_range) == 1
    assert out_of_range[0].context["param_id"] == "bounded"


@pytest.mark.unit
def test_parameter_invalid_enum_reports_error(
    validator: GraphValidator,
    strict_model: WorkspaceModel,
) -> None:
    """An enum parameter outside `allowed_values` triggers `invalid_enum`."""
    strict_model.add_component_from_definition(
        _STRICT_PARAM_DEFINITION.id,
        QPointF(0.0, 0.0),
        parameters={"mode": "z"},  # not in ("a", "b")
    )

    report = _run(validator, strict_model)

    invalid_enum = [i for i in report.issues if i.code == "error.parameter.invalid_enum"]
    assert len(invalid_enum) == 1
    assert invalid_enum[0].context["param_id"] == "mode"


@pytest.mark.unit
def test_parameter_type_mismatch_reports_error(
    validator: GraphValidator,
    strict_model: WorkspaceModel,
) -> None:
    """A wrong-type value triggers `type_mismatch`."""
    strict_model.add_component_from_definition(
        _STRICT_PARAM_DEFINITION.id,
        QPointF(0.0, 0.0),
        parameters={"bounded": "not a number"},
    )

    report = _run(validator, strict_model)

    type_mismatches = [i for i in report.issues if i.code == "error.parameter.type_mismatch"]
    assert len(type_mismatches) == 1
    assert type_mismatches[0].context["param_id"] == "bounded"


# ---------------------------------------------------------------------- #
# Issue id stability (S1.6b debounce relies on this for diff)
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_repeated_validation_produces_stable_issue_ids(
    validator: GraphValidator,
    model: WorkspaceModel,
) -> None:
    """Two consecutive validations produce the same `issue_id`s for the same issues.

    Per `02 §20.6`, debounced revalidations diff against prior
    reports using `issue_id`. The id format is
    `<code>:<distinguishing-fields>`, so two clean runs over
    the same workspace must yield identical id sets.
    """
    model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))

    first = _run(validator, model)
    second = _run(validator, model)

    assert {i.issue_id for i in first.issues} == {i.issue_id for i in second.issues}
