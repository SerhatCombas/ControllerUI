"""Unit tests for `WorkspaceModel.add_component_from_definition` (S1.B.1d).

Covers the registry-backed component-creation path introduced in
S1.B.1d (decisions A1 + B1 per the S1.B planning thread):

* **A1** — `WorkspaceModel(parent=..., registry=...)` accepts an
  optional `ComponentRegistry`. When omitted, the explicit-kwarg
  `add_component` path remains usable; only the registry-backed
  entrypoint requires the wired registry.
* **B1** — `add_component_from_definition(definition_id, position, ...)`
  is a new method rather than overload of `add_component`; the latter
  is retained verbatim for backwards compatibility with all S1.3
  tests.

Validation order test rationale (consistent with the rest of the
mutation API): argument validation runs before lookup, lookup runs
before mutation; failures at each stage leave the model unchanged
and no signals fire.

Definition-derived field inheritance follows `02 §11.3`: at instance
creation the new component inherits `type`, `display_name`, `domain`,
`category`, `visual`, and `physical_attributes` from the
`ComponentDefinition`. `parameters` defaults to empty (definition
defaults are resolved at runtime per `ComponentInstance.parameters`).

References:
----------
* `specs/01_library_requirements.md` §6 (Component Definition Schema)
* `specs/02_workspace_requirements.md` §11.3 (Physical Attributes
  Origin), §11.4 (Field Mutability Matrix)
* `decisions/ADR-021-builtin-component-definitions.md`
* `decisions/ADR-018-signal-payload-contracts.md`
* `decisions/ADR-020-dirty-tracking-semantics.md`
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPointF

from features.SystemModelingModule.model.workspace_model import WorkspaceModel
from shared.registry import ComponentRegistry
from shared.registry.builtin import (
    BUILTIN_COMPONENT_DEFINITIONS,
    CONSTANT_VOLTAGE_DEFINITION,
    FIXED_DEFINITION,
    MASS_DEFINITION,
    RESISTOR_DEFINITION,
)

# ---------------------------------------------------------------------- #
# Fixtures
# ---------------------------------------------------------------------- #


@pytest.fixture
def registry() -> ComponentRegistry:
    """A `ComponentRegistry` populated with the seven core MVP defs."""
    return ComponentRegistry(BUILTIN_COMPONENT_DEFINITIONS)


@pytest.fixture
def model(registry: ComponentRegistry) -> WorkspaceModel:
    """A `WorkspaceModel` wired with the built-in registry."""
    return WorkspaceModel(registry=registry)


# ---------------------------------------------------------------------- #
# Constructor — A1
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_constructor_without_registry_keeps_backwards_compat() -> None:
    """Per A1: `WorkspaceModel()` continues to work registry-less.

    The S1.3 `add_component` explicit-kwarg path does not depend on
    a `ComponentRegistry`; this confirms the optional kwarg has the
    intended default and the existing test surface is preserved.
    """
    model = WorkspaceModel()

    assert model.is_dirty is False
    assert len(model.components) == 0


@pytest.mark.unit
def test_constructor_with_registry_stores_it(
    registry: ComponentRegistry,
) -> None:
    """`registry=...` is accepted and stored for downstream use."""
    model = WorkspaceModel(registry=registry)

    assert model._registry is registry


# ---------------------------------------------------------------------- #
# add_component_from_definition — happy path
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_add_from_definition_happy_path_resistor(model: WorkspaceModel) -> None:
    """Adding a resistor from the registry creates an instance whose
    definition-derived fields match the `ComponentDefinition`."""
    component_id = model.add_component_from_definition(
        RESISTOR_DEFINITION.id,
        QPointF(120.0, 80.0),
    )

    instance = model.components[component_id]
    assert instance.definition_id == RESISTOR_DEFINITION.id
    assert instance.display_name == RESISTOR_DEFINITION.display_name
    assert instance.type == RESISTOR_DEFINITION.display_name
    assert instance.domain == RESISTOR_DEFINITION.domain
    assert instance.category == RESISTOR_DEFINITION.category
    assert instance.position == (120.0, 80.0)
    assert instance.visual.svg_id == RESISTOR_DEFINITION.visual.svg_id
    assert instance.visual.variant == RESISTOR_DEFINITION.visual.default_variant
    # Empty parameters means "use definition defaults at runtime" per
    # `ComponentInstance.parameters` docstring.
    assert instance.parameters == {}
    # Resistor carries the empty default PhysicalAttributes.
    assert instance.physical_attributes == RESISTOR_DEFINITION.physical_attributes


@pytest.mark.unit
def test_add_from_definition_inherits_physical_attributes_source(
    model: WorkspaceModel,
) -> None:
    """A `ConstantVoltage` instance inherits `source=True` from the
    definition per `02 §11.3` (physical-attributes origin)."""
    component_id = model.add_component_from_definition(
        CONSTANT_VOLTAGE_DEFINITION.id,
        QPointF(0.0, 0.0),
    )

    instance = model.components[component_id]
    assert instance.physical_attributes.source is True
    assert instance.physical_attributes.source_type == "constant"


@pytest.mark.unit
def test_add_from_definition_inherits_physical_attributes_mechanical(
    model: WorkspaceModel,
) -> None:
    """Mass / Fixed instances inherit `motion="translational"` (and
    `boundary="fixed"` for the reference) per `02 §11.3`."""
    mass_id = model.add_component_from_definition(
        MASS_DEFINITION.id,
        QPointF(0.0, 0.0),
    )
    fixed_id = model.add_component_from_definition(
        FIXED_DEFINITION.id,
        QPointF(50.0, 0.0),
    )

    assert model.components[mass_id].physical_attributes.motion == "translational"
    assert model.components[mass_id].physical_attributes.boundary is None
    assert model.components[fixed_id].physical_attributes.boundary == "fixed"
    assert model.components[fixed_id].physical_attributes.motion == "translational"


@pytest.mark.unit
def test_add_from_definition_returns_cmp_prefixed_id(
    model: WorkspaceModel,
) -> None:
    """The returned id carries the `cmp_` prefix per ADR-002."""
    component_id = model.add_component_from_definition(
        RESISTOR_DEFINITION.id,
        QPointF(0.0, 0.0),
    )

    assert component_id.startswith("cmp_")
    assert component_id in model.components


@pytest.mark.unit
def test_add_from_definition_accepts_custom_label_and_rotation(
    model: WorkspaceModel,
) -> None:
    """User-supplied custom label and rotation flow into the instance."""
    component_id = model.add_component_from_definition(
        RESISTOR_DEFINITION.id,
        QPointF(0.0, 0.0),
        custom_label="R_load",
        rotation=90.0,
    )

    instance = model.components[component_id]
    assert instance.custom_label == "R_load"
    assert instance.rotation == 90.0


@pytest.mark.unit
def test_add_from_definition_accepts_explicit_parameter_overrides(
    model: WorkspaceModel,
) -> None:
    """Parameter overrides land verbatim on the instance.

    Parameter-value validation against the definition schema is the
    responsibility of `set_parameter` (S1.B.1e); this method records
    whatever the caller supplies so project-load / copy-paste flows
    in later stages can round-trip user-edited values.
    """
    component_id = model.add_component_from_definition(
        RESISTOR_DEFINITION.id,
        QPointF(0.0, 0.0),
        parameters={"resistance": 2200.0},
    )

    assert model.components[component_id].parameters == {"resistance": 2200.0}


# ---------------------------------------------------------------------- #
# add_component_from_definition — failure modes (validation order)
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_add_from_definition_without_registry_raises_runtime_error() -> None:
    """Per A1: registry omitted → `RuntimeError` (not a silent no-op).

    Validation order rule: argument-availability check runs before
    any model mutation, so a failed call leaves the model unchanged.
    """
    model = WorkspaceModel()  # no registry wired

    with pytest.raises(RuntimeError, match=r"ComponentRegistry"):
        model.add_component_from_definition(
            RESISTOR_DEFINITION.id,
            QPointF(0.0, 0.0),
        )

    assert len(model.components) == 0
    assert model.is_dirty is False


@pytest.mark.unit
def test_add_from_definition_unknown_id_raises_key_error(
    model: WorkspaceModel,
) -> None:
    """Unknown definition id → `KeyError` (registry pass-through)."""
    with pytest.raises(KeyError):
        model.add_component_from_definition(
            "electrical.analog.components.does_not_exist",
            QPointF(0.0, 0.0),
        )

    assert len(model.components) == 0
    assert model.is_dirty is False


@pytest.mark.unit
def test_add_from_definition_off_grid_rotation_raises_value_error(
    model: WorkspaceModel,
) -> None:
    """Rotation canonicalization happens for the new method too.

    Phase-1 rule per `02 §22` / ADR-018: only the four orthogonal
    angles are accepted; the same `_canonical_rotation` is used as
    by the existing `add_component` and `rotate_component` paths.
    """
    with pytest.raises(ValueError, match=r"rotation must be one of"):
        model.add_component_from_definition(
            RESISTOR_DEFINITION.id,
            QPointF(0.0, 0.0),
            rotation=45.0,
        )

    assert len(model.components) == 0
    assert model.is_dirty is False


# ---------------------------------------------------------------------- #
# Signal + dirty-bit behavior — same contract as add_component
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_add_from_definition_emits_component_added_signal(
    model: WorkspaceModel,
) -> None:
    """A successful add emits a single `componentAdded(id)` signal."""
    captured: list[str] = []
    model.componentAdded.connect(captured.append)

    returned_id = model.add_component_from_definition(
        RESISTOR_DEFINITION.id,
        QPointF(0.0, 0.0),
    )

    assert captured == [returned_id]


@pytest.mark.unit
def test_add_from_definition_drives_dirty_transition_once(
    model: WorkspaceModel,
) -> None:
    """ADR-020 transition-only rule still holds for the new path.

    First add transitions `False → True` (one `dirtyChanged(True)`
    emission). A second add on an already-dirty model does not
    re-emit.
    """
    dirty_signals: list[bool] = []
    model.dirtyChanged.connect(dirty_signals.append)

    model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(50.0, 0.0))

    assert dirty_signals == [True]
    assert model.is_dirty is True


@pytest.mark.unit
def test_add_from_definition_records_inside_batch(
    model: WorkspaceModel,
) -> None:
    """Per S1.3d batch contract: inside `model.batch()` the new method
    suppresses `componentAdded` and records the addition into the
    cumulative `WorkspaceChangeSet` emitted on outermost exit.

    This confirms the registry path delegates to the same mutation
    plumbing as the explicit-kwarg `add_component`.
    """
    fine_grained: list[str] = []
    change_sets: list[object] = []
    model.componentAdded.connect(fine_grained.append)
    model.modelChanged.connect(change_sets.append)

    with model.batch():
        first = model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
        second = model.add_component_from_definition(MASS_DEFINITION.id, QPointF(50.0, 0.0))

    assert fine_grained == []  # suppressed inside batch
    assert len(change_sets) == 1
    change_set = change_sets[0]
    # `WorkspaceChangeSet.added_components` is a tuple in insertion order.
    assert change_set.added_components == (first, second)  # type: ignore[attr-defined]
