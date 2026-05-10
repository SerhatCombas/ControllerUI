"""Unit tests for `WorkspaceModel.set_parameter` schema dispatch (S1.B.1e).

Covers the registry-backed no-op suppression path introduced in
S1.B.1e (closes the `TODO(S1.6)` marker on `set_parameter`):

* `float` parameters use ε-tolerance equality per ADR-020 — sub-ε
  numeric drift does not fire `componentChanged`.
* `int`, `bool`, `string`, `enum`, `expression` parameters use exact
  `==` — discrete or syntactic types where ε-tolerance does not
  apply.
* When the registry cannot resolve the parameter's declared type
  (no registry wired / unregistered definition / unregistered
  parameter id), the method falls back to exact `==`, preserving
  the pre-S1.B.1d behavior used by all S1.3 tests.

The schema dispatch only affects no-op suppression. Insertion of
parameters that the instance does not yet carry remains an
unconditional upsert (parameter-id validation against the definition
is a Phase 1.5+ command-stack concern; see the method docstring).

References:
----------
* `specs/01_library_requirements.md` §6 (Parameter Definition Schema)
* `specs/02_workspace_requirements.md` §11.4 (Field Mutability Matrix)
* `decisions/ADR-020-dirty-tracking-semantics.md` (transition-only +
  ε-tolerance no-op rule)
* `decisions/ADR-021-builtin-component-definitions.md`
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPointF

from features.SystemModelingModule.model.component_instance import (
    PhysicalAttributes,
    VisualSpec,
)
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
    RESISTOR_DEFINITION,
)

# ---------------------------------------------------------------------- #
# Fixtures
# ---------------------------------------------------------------------- #

# A custom test-only definition that exercises every Phase 1 parameter
# type (float / int / bool / string / enum / expression) so that the
# schema-dispatch branches can be tested without depending on what the
# built-in MVP set happens to declare. The built-ins (S1.B.1c) only
# carry float parameters, so the int/bool/string/enum branches need
# a synthetic definition.
_CUSTOM_DEFINITION = ComponentDefinition(
    id="test.schema.custom",
    display_name="SchemaTestCustom",
    domain="electrical_analog",
    library_path=("Test", "Schema"),
    category="component",
    ports=(PortDefinition(id="p", display_name="P", domain="electrical_analog"),),
    parameters=(
        ParameterDefinition(id="f_val", display_name="F", type="float", default=1.0),
        ParameterDefinition(id="i_val", display_name="I", type="int", default=1),
        ParameterDefinition(id="b_val", display_name="B", type="bool", default=False),
        ParameterDefinition(id="s_val", display_name="S", type="string", default="x"),
        ParameterDefinition(
            id="e_val",
            display_name="E",
            type="enum",
            default="a",
            allowed_values=("a", "b", "c"),
        ),
        ParameterDefinition(
            id="x_val",
            display_name="X",
            type="expression",
            default="1+1",
            supports_expression=True,
        ),
    ),
    visual=LibraryVisualSpec(svg_id="test_schema_custom_default"),
)


@pytest.fixture
def registry() -> ComponentRegistry:
    """A `ComponentRegistry` with the seven MVP defs plus the schema-test def."""
    return ComponentRegistry((*BUILTIN_COMPONENT_DEFINITIONS, _CUSTOM_DEFINITION))


@pytest.fixture
def model(registry: ComponentRegistry) -> WorkspaceModel:
    """A `WorkspaceModel` wired with the schema-test registry."""
    return WorkspaceModel(registry=registry)


def _make_resistor(model: WorkspaceModel, resistance: float = 1000.0) -> str:
    """Create a resistor instance with an explicit `resistance` value.

    Tests need a known starting value to assert no-op vs. mutate
    behavior; the explicit-parameter form ensures `parameters` is
    populated rather than empty (which would always take the
    insertion branch).
    """
    return model.add_component_from_definition(
        RESISTOR_DEFINITION.id,
        QPointF(0.0, 0.0),
        parameters={"resistance": resistance},
    )


def _make_custom(model: WorkspaceModel, **overrides: object) -> str:
    """Create a `_CUSTOM_DEFINITION` instance with explicit parameters.

    Each test that exercises non-float types seeds the relevant param
    so the schema-dispatched no-op path runs against an established
    value rather than falling through to insertion.
    """
    parameters: dict[str, object] = {
        "f_val": 1.0,
        "i_val": 1,
        "b_val": False,
        "s_val": "x",
        "e_val": "a",
        "x_val": "1+1",
    }
    parameters.update(overrides)
    return model.add_component_from_definition(
        _CUSTOM_DEFINITION.id,
        QPointF(0.0, 0.0),
        parameters=parameters,
    )


# ---------------------------------------------------------------------- #
# Float — ε-tolerance no-op suppression (ADR-020)
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_set_parameter_float_sub_epsilon_drift_suppresses_signal(
    model: WorkspaceModel,
) -> None:
    """Sub-ε float drift on a registered `float` param fires no signal.

    The schema lookup discovers `resistance` is declared as `float`
    in `RESISTOR_DEFINITION`, so `_parameter_values_equal` dispatches
    to `approx_equal_float` (ε=1e-6 per ADR-020), which treats the
    new value as equal and suppresses the mutation.
    """
    component_id = _make_resistor(model, resistance=1000.0)
    received: list[str] = []
    model.componentChanged.connect(received.append)
    initial_dirty = model.is_dirty

    # Force the dirty bit back to clean so the no-op check is observable
    # without the initial-add transition. ADR-020 transition-only rule
    # means a second add would have left dirty True; we want to verify
    # that the no-op path does NOT mark dirty (i.e., it returns early).
    if initial_dirty:
        model._clear_dirty()

    model.set_parameter(component_id, "resistance", 1000.0 + 1e-9)

    assert received == []
    assert model.is_dirty is False
    assert model.components[component_id].parameters == {"resistance": 1000.0}


@pytest.mark.unit
def test_set_parameter_float_meaningful_change_emits_signal(
    model: WorkspaceModel,
) -> None:
    """A real float change (well above ε) mutates and emits."""
    component_id = _make_resistor(model, resistance=1000.0)
    received: list[str] = []
    model.componentChanged.connect(received.append)

    model.set_parameter(component_id, "resistance", 2200.0)

    assert received == [component_id]
    assert model.components[component_id].parameters == {"resistance": 2200.0}


# ---------------------------------------------------------------------- #
# Discrete types — exact `==` no-op suppression
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_set_parameter_int_exact_match_suppresses_signal(
    model: WorkspaceModel,
) -> None:
    """`int`-typed param: exact `==` match → no-op, no signal."""
    component_id = _make_custom(model, i_val=5)
    received: list[str] = []
    model.componentChanged.connect(received.append)

    model.set_parameter(component_id, "i_val", 5)

    assert received == []


@pytest.mark.unit
def test_set_parameter_int_change_emits_signal(model: WorkspaceModel) -> None:
    """`int`-typed param: different value mutates and emits."""
    component_id = _make_custom(model, i_val=5)
    received: list[str] = []
    model.componentChanged.connect(received.append)

    model.set_parameter(component_id, "i_val", 7)

    assert received == [component_id]
    assert model.components[component_id].parameters["i_val"] == 7


@pytest.mark.unit
def test_set_parameter_bool_exact_match_suppresses_signal(
    model: WorkspaceModel,
) -> None:
    """`bool`-typed param: exact `==` match → no-op.

    Important: even though `bool` is a subclass of `int` in Python,
    a `bool` param must NOT use ε-tolerance. The dispatcher's bool
    guard ensures `False == False` stays exact and does not coerce
    into the float branch.
    """
    component_id = _make_custom(model, b_val=False)
    received: list[str] = []
    model.componentChanged.connect(received.append)

    model.set_parameter(component_id, "b_val", False)

    assert received == []


@pytest.mark.unit
def test_set_parameter_string_exact_match_suppresses_signal(
    model: WorkspaceModel,
) -> None:
    """`string`-typed param: identical string → no-op."""
    component_id = _make_custom(model, s_val="hello")
    received: list[str] = []
    model.componentChanged.connect(received.append)

    model.set_parameter(component_id, "s_val", "hello")

    assert received == []


@pytest.mark.unit
def test_set_parameter_enum_exact_match_suppresses_signal(
    model: WorkspaceModel,
) -> None:
    """`enum`-typed param: identical allowed value → no-op."""
    component_id = _make_custom(model, e_val="b")
    received: list[str] = []
    model.componentChanged.connect(received.append)

    model.set_parameter(component_id, "e_val", "b")

    assert received == []


@pytest.mark.unit
def test_set_parameter_expression_exact_match_suppresses_signal(
    model: WorkspaceModel,
) -> None:
    """`expression`-typed param: identical source string → no-op.

    Expression evaluation is Phase 2+ work; for Phase 1 no-op
    dispatch, an expression compares as a string at exact equality.
    """
    component_id = _make_custom(model, x_val="2*3")
    received: list[str] = []
    model.componentChanged.connect(received.append)

    model.set_parameter(component_id, "x_val", "2*3")

    assert received == []


# ---------------------------------------------------------------------- #
# Fallback path — exact `==` when registry cannot resolve the type
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_set_parameter_without_registry_falls_back_to_exact_equality() -> None:
    """No registry wired → exact `==` (preserves S1.3 behavior).

    A sub-ε float drift on a registry-less model fires `componentChanged`
    because the schema dispatch cannot reach the `float` branch — the
    fallback `bool(existing == value)` returns False for `1000.0 ==
    1000.0 + 1e-9`, so the mutation proceeds.
    """
    model = WorkspaceModel()  # no registry
    # Use the explicit-kwarg add_component path so we don't need a
    # registry to seed the instance.
    component_id = model.add_component(
        definition_id="electrical.analog.components.resistor",
        type="Resistor",
        display_name="Resistor",
        domain="electrical_analog",
        category="component",
        position=QPointF(0.0, 0.0),
        visual=VisualSpec(svg_id="resistor_default"),
        physical_attributes=PhysicalAttributes(),
        parameters={"resistance": 1000.0},
    )
    received: list[str] = []
    model.componentChanged.connect(received.append)

    model.set_parameter(component_id, "resistance", 1000.0 + 1e-9)

    assert received == [component_id]


@pytest.mark.unit
def test_set_parameter_with_unregistered_definition_falls_back_to_exact_equality(
    registry: ComponentRegistry,
) -> None:
    """Registry wired but the component's `definition_id` is not in it.

    Sub-ε drift still fires the signal because the fallback path runs.
    This guards against a future scenario where a project file
    references a definition that was renamed or removed from the
    registry — `set_parameter` should still function (with the
    safe fallback semantic) rather than silently swallowing edits.
    """
    model = WorkspaceModel(registry=registry)
    # Build an instance whose definition_id is intentionally absent
    # from the registry by using the low-level add_component path.
    component_id = model.add_component(
        definition_id="electrical.analog.components.NOT_REGISTERED",
        type="Mystery",
        display_name="Mystery",
        domain="electrical_analog",
        category="component",
        position=QPointF(0.0, 0.0),
        visual=VisualSpec(svg_id="mystery_default"),
        physical_attributes=PhysicalAttributes(),
        parameters={"resistance": 1000.0},
    )
    received: list[str] = []
    model.componentChanged.connect(received.append)

    model.set_parameter(component_id, "resistance", 1000.0 + 1e-9)

    assert received == [component_id]


@pytest.mark.unit
def test_set_parameter_with_unregistered_param_id_falls_back_to_exact_equality(
    model: WorkspaceModel,
) -> None:
    """Registry has the definition but `param_id` is not declared on it.

    Sub-ε drift fires the signal under the fallback path because
    `_lookup_parameter_type` returns `None` for parameters not in the
    definition schema. This preserves the upsert-friendly contract
    for legacy / forward-compatible parameters (e.g., metadata-like
    fields that the schema does not yet declare).
    """
    component_id = _make_resistor(model, resistance=1000.0)
    # Seed an off-schema parameter via direct set_parameter (insertion
    # branch always allows it, regardless of registry contents).
    model.set_parameter(component_id, "tolerance", 0.05)
    received: list[str] = []
    model.componentChanged.connect(received.append)

    model.set_parameter(component_id, "tolerance", 0.05 + 1e-9)

    assert received == [component_id]


# ---------------------------------------------------------------------- #
# Insertion + error-path semantics
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_set_parameter_new_param_insertion_always_mutates(
    model: WorkspaceModel,
) -> None:
    """Parameter not present on instance → always insert, no comparison.

    The schema-dispatch path only runs when the param is already
    present. Inserting a brand-new param fires `componentChanged`
    regardless of the declared type (so commands that build up
    parameter sets incrementally remain observable).
    """
    component_id = model.add_component_from_definition(
        RESISTOR_DEFINITION.id,
        QPointF(0.0, 0.0),
        parameters={},  # explicitly empty
    )
    received: list[str] = []
    model.componentChanged.connect(received.append)

    model.set_parameter(component_id, "resistance", 1000.0)

    assert received == [component_id]
    assert model.components[component_id].parameters == {"resistance": 1000.0}


@pytest.mark.unit
def test_set_parameter_unknown_component_id_raises_key_error(
    model: WorkspaceModel,
) -> None:
    """Unknown component_id → `KeyError` (existence check is first).

    Confirms the validation-order rule (existence before schema
    lookup) is preserved; the schema-dispatch code path is not
    reachable from an invalid component id.
    """
    with pytest.raises(KeyError) as exc_info:
        model.set_parameter("cmp_nonexistent", "resistance", 1000.0)

    assert "cmp_nonexistent" in str(exc_info.value)


# ---------------------------------------------------------------------- #
# Dirty-bit + batch contract
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_set_parameter_float_no_op_does_not_drive_dirty_bit(
    model: WorkspaceModel,
) -> None:
    """ε-tolerance no-op must NOT mark the model dirty.

    The whole point of ADR-020 transition-only dirty-tracking plus
    schema-dispatched no-op suppression is that meaningless edits
    leave the model clean. A subscriber to `dirtyChanged` should not
    see a transition when only sub-ε drift was applied.
    """
    component_id = _make_resistor(model, resistance=1000.0)
    model._clear_dirty()
    dirty_emits: list[bool] = []
    model.dirtyChanged.connect(dirty_emits.append)

    model.set_parameter(component_id, "resistance", 1000.0 + 1e-9)

    assert dirty_emits == []
    assert model.is_dirty is False


@pytest.mark.unit
def test_set_parameter_inside_batch_records_change_when_mutates(
    model: WorkspaceModel,
) -> None:
    """Inside batch: schema-dispatched mutate path records the change."""
    component_id = _make_resistor(model, resistance=1000.0)
    fine_grained: list[str] = []
    change_sets: list[object] = []
    model.componentChanged.connect(fine_grained.append)
    model.modelChanged.connect(change_sets.append)

    with model.batch():
        model.set_parameter(component_id, "resistance", 2200.0)

    assert fine_grained == []  # suppressed inside batch
    assert len(change_sets) == 1
    assert change_sets[0].changed_components == (component_id,)  # type: ignore[attr-defined]


@pytest.mark.unit
def test_set_parameter_inside_batch_suppresses_no_op_completely(
    model: WorkspaceModel,
) -> None:
    """Inside batch: schema-dispatched no-op contributes nothing to the change_set.

    ε-tolerance suppression runs before the batch-builder record, so
    a sub-ε edit inside a batch leaves the `WorkspaceChangeSet`
    empty and no `modelChanged` emission fires on exit.
    """
    component_id = _make_resistor(model, resistance=1000.0)
    model._clear_dirty()
    change_sets: list[object] = []
    model.modelChanged.connect(change_sets.append)

    with model.batch():
        model.set_parameter(component_id, "resistance", 1000.0 + 1e-9)

    assert change_sets == []
    assert model.is_dirty is False
