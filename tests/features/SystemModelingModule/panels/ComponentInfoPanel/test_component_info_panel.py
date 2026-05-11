"""Unit tests for `ComponentInfoPanel` (S1.9.6).

Covers:

* Empty state on no selection.
* Single-component display: title + per-parameter editor row.
* Multi-select: count placeholder, no editors.
* Editor types by ParameterType (float / int / bool / string /
  enum).
* Parameter edit → `ChangeParameterCommand` pushed onto the
  stack.
* `componentChanged` signal refreshes widget values without
  re-pushing a command (re-entrancy guard).
* Selected component removed → panel resets to empty.
* No command_stack → edit no-ops with warning.

References:
----------
* `specs/02_workspace_requirements.md` §28
* `specs/07_implementation_order.md` §7.13
"""

from __future__ import annotations

import logging

import pytest
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QLabel,
    QLineEdit,
    QSpinBox,
)

from features.SystemModelingModule.commands import WorkspaceCommandStack
from features.SystemModelingModule.model.workspace_model import WorkspaceModel
from features.SystemModelingModule.panels.ComponentInfoPanel.component_info_panel import (
    ComponentInfoPanel,
)
from features.SystemModelingModule.workspace.BlockDiagramWorkspace.workspace_scene import (
    WorkspaceScene,
)
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

# A synthetic definition exercising every Phase 1 parameter type
# so the panel's per-type editor selection has full test coverage.
_MULTITYPE_DEFINITION = ComponentDefinition(
    id="test.multitype",
    display_name="Multitype",
    short_name="MT",
    domain="electrical_analog",
    library_path=("Test",),
    category="component",
    ports=(PortDefinition(id="p", display_name="P", domain="electrical_analog"),),
    parameters=(
        ParameterDefinition(id="f_val", display_name="F", type="float", default=1.0),
        ParameterDefinition(id="i_val", display_name="I", type="int", default=2),
        ParameterDefinition(id="b_val", display_name="B", type="bool", default=False),
        ParameterDefinition(id="s_val", display_name="S", type="string", default="hello"),
        ParameterDefinition(
            id="e_val",
            display_name="E",
            type="enum",
            default="a",
            allowed_values=("a", "b", "c"),
        ),
    ),
    visual=LibraryVisualSpec(svg_id="multitype_default"),
)


@pytest.fixture
def model() -> WorkspaceModel:
    """Registry-wired model with the MVP set + the multitype def."""
    registry = ComponentRegistry(BUILTIN_COMPONENT_DEFINITIONS + (_MULTITYPE_DEFINITION,))
    return WorkspaceModel(registry=registry)


@pytest.fixture
def stack(model: WorkspaceModel) -> WorkspaceCommandStack:
    """Command stack."""
    return WorkspaceCommandStack(model)


@pytest.fixture
def scene(model: WorkspaceModel, stack: WorkspaceCommandStack) -> WorkspaceScene:
    """Workspace scene wired with model + stack."""
    return WorkspaceScene(model, command_stack=stack)


@pytest.fixture
def panel(
    model: WorkspaceModel,
    scene: WorkspaceScene,
    stack: WorkspaceCommandStack,
) -> ComponentInfoPanel:
    """The info panel under test, with all three dependencies wired."""
    return ComponentInfoPanel(model=model, scene=scene, command_stack=stack)


# ---------------------------------------------------------------------- #
# Empty / multi-select states
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_panel_empty_state_on_no_selection(panel: ComponentInfoPanel) -> None:
    """Freshly constructed panel shows the 'No selection' placeholder."""
    assert panel.current_component_id is None
    assert panel.parameter_editors == {}
    # `_empty_label` is the only visible top-level state widget.
    assert panel._empty_label.isVisibleTo(panel)


@pytest.mark.unit
def test_panel_multi_select_shows_count_placeholder(
    panel: ComponentInfoPanel,
    scene: WorkspaceScene,
) -> None:
    """Two selected components produce '2 components selected'."""
    cid_a = scene.model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    cid_b = scene.model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(50.0, 0.0))
    scene._component_items[cid_a].setSelected(True)
    scene._component_items[cid_b].setSelected(True)

    assert panel.current_component_id is None
    assert "2 components" in panel._multi_label.text()


# ---------------------------------------------------------------------- #
# Single-component display
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_panel_shows_display_name_for_single_selection(
    panel: ComponentInfoPanel,
    scene: WorkspaceScene,
) -> None:
    """Single selection populates the title label with `display_name`."""
    cid = scene.model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    scene._component_items[cid].setSelected(True)

    assert panel.current_component_id == cid
    assert panel._title_label.text() == RESISTOR_DEFINITION.display_name


@pytest.mark.unit
def test_panel_builds_one_editor_per_parameter(
    panel: ComponentInfoPanel,
    scene: WorkspaceScene,
) -> None:
    """A resistor has one parameter (`resistance`) → one editor row."""
    cid = scene.model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    scene._component_items[cid].setSelected(True)

    assert set(panel.parameter_editors.keys()) == {"resistance"}


# ---------------------------------------------------------------------- #
# Editor type by ParameterType
# ---------------------------------------------------------------------- #


def _select_multitype(scene: WorkspaceScene) -> str:
    """Place a multitype component and select it."""
    cid = scene.model.add_component_from_definition(_MULTITYPE_DEFINITION.id, QPointF(0.0, 0.0))
    scene._component_items[cid].setSelected(True)
    return cid


@pytest.mark.unit
def test_panel_float_param_renders_as_double_spinbox(
    panel: ComponentInfoPanel,
    scene: WorkspaceScene,
) -> None:
    """`type='float'` maps to `QDoubleSpinBox`."""
    _select_multitype(scene)

    assert isinstance(panel.parameter_editors["f_val"], QDoubleSpinBox)


@pytest.mark.unit
def test_panel_int_param_renders_as_spinbox(
    panel: ComponentInfoPanel,
    scene: WorkspaceScene,
) -> None:
    """`type='int'` maps to `QSpinBox`."""
    _select_multitype(scene)

    assert isinstance(panel.parameter_editors["i_val"], QSpinBox)


@pytest.mark.unit
def test_panel_bool_param_renders_as_checkbox(
    panel: ComponentInfoPanel,
    scene: WorkspaceScene,
) -> None:
    """`type='bool'` maps to `QCheckBox`."""
    _select_multitype(scene)

    assert isinstance(panel.parameter_editors["b_val"], QCheckBox)


@pytest.mark.unit
def test_panel_enum_param_renders_as_combobox(
    panel: ComponentInfoPanel,
    scene: WorkspaceScene,
) -> None:
    """`type='enum'` maps to `QComboBox` populated from `allowed_values`."""
    _select_multitype(scene)

    combo = panel.parameter_editors["e_val"]
    assert isinstance(combo, QComboBox)
    assert [combo.itemText(i) for i in range(combo.count())] == ["a", "b", "c"]


@pytest.mark.unit
def test_panel_string_param_renders_as_line_edit(
    panel: ComponentInfoPanel,
    scene: WorkspaceScene,
) -> None:
    """`type='string'` maps to `QLineEdit`."""
    _select_multitype(scene)

    assert isinstance(panel.parameter_editors["s_val"], QLineEdit)


# ---------------------------------------------------------------------- #
# Parameter edit → command push
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_param_edit_pushes_change_parameter_command(
    panel: ComponentInfoPanel,
    scene: WorkspaceScene,
    stack: WorkspaceCommandStack,
) -> None:
    """Calling `_on_param_edit` with a new value pushes a command."""
    cid = scene.model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    scene._component_items[cid].setSelected(True)
    pre_count = stack.count()

    panel._on_param_edit("resistance", 2200.0)

    assert stack.count() == pre_count + 1
    assert scene.model.components[cid].parameters == {"resistance": 2200.0}


@pytest.mark.unit
def test_param_edit_without_command_stack_no_ops(
    model: WorkspaceModel,
    scene: WorkspaceScene,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """No command_stack → edit logs warning, no model change."""
    no_stack_panel = ComponentInfoPanel(model=model, scene=scene, command_stack=None)
    cid = scene.model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    scene._component_items[cid].setSelected(True)

    caplog.clear()
    with caplog.at_level(
        logging.WARNING,
        logger="features.SystemModelingModule.panels.ComponentInfoPanel.component_info_panel",
    ):
        no_stack_panel._on_param_edit("resistance", 2200.0)

    assert scene.model.components[cid].parameters == {}
    assert any("no command_stack" in r.getMessage() for r in caplog.records)


# ---------------------------------------------------------------------- #
# Refresh on componentChanged + re-entrancy guard
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_panel_refreshes_widgets_on_component_changed(
    panel: ComponentInfoPanel,
    scene: WorkspaceScene,
) -> None:
    """An external `set_parameter` triggers a widget refresh."""
    cid = scene.model.add_component_from_definition(
        RESISTOR_DEFINITION.id,
        QPointF(0.0, 0.0),
        parameters={"resistance": 1000.0},
    )
    scene._component_items[cid].setSelected(True)
    spinbox = panel.parameter_editors["resistance"]
    assert isinstance(spinbox, QDoubleSpinBox)

    # External edit via the model API (bypasses the panel).
    scene.model.set_parameter(cid, "resistance", 3300.0)

    assert spinbox.value() == 3300.0


@pytest.mark.unit
def test_panel_refresh_does_not_push_redundant_command(
    panel: ComponentInfoPanel,
    scene: WorkspaceScene,
    stack: WorkspaceCommandStack,
) -> None:
    """The re-entrancy guard prevents a refresh from re-emitting a command.

    Two scenarios in one test: an external set_parameter triggers
    one model mutation (no stack push because direct API
    bypasses commands) and the resulting widget refresh must
    NOT push a follow-up `ChangeParameterCommand`.
    """
    cid = scene.model.add_component_from_definition(
        RESISTOR_DEFINITION.id,
        QPointF(0.0, 0.0),
        parameters={"resistance": 1000.0},
    )
    scene._component_items[cid].setSelected(True)
    pre_count = stack.count()

    scene.model.set_parameter(cid, "resistance", 3300.0)

    # No command was pushed (direct API bypasses commands; the
    # widget refresh did not synthesize one).
    assert stack.count() == pre_count


# ---------------------------------------------------------------------- #
# Removal / cleanup
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_panel_resets_when_selected_component_removed(
    panel: ComponentInfoPanel,
    scene: WorkspaceScene,
) -> None:
    """Removing the displayed component returns the panel to empty state."""
    cid = scene.model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    scene._component_items[cid].setSelected(True)
    assert panel.current_component_id == cid

    scene.model.remove_component(cid)

    assert panel.current_component_id is None
    assert panel.parameter_editors == {}


@pytest.mark.unit
def test_panel_empty_label_visible_after_deselect(
    panel: ComponentInfoPanel,
    scene: WorkspaceScene,
) -> None:
    """Deselecting (no item selected) returns to empty state."""
    cid = scene.model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    scene._component_items[cid].setSelected(True)
    assert panel.current_component_id == cid

    scene._component_items[cid].setSelected(False)

    assert panel.current_component_id is None


# ---------------------------------------------------------------------- #
# Title-label uses display_name (smoke)
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_panel_title_is_qlabel(panel: ComponentInfoPanel) -> None:
    """The title widget is a QLabel (smoke; rules out widget-tree drift)."""
    assert isinstance(panel._title_label, QLabel)
