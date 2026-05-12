"""Integration test for `WorkspaceReactivityObserver` (S2.B.3).

Exercises the cross-feature wiring against a real `WorkspaceModel`
+ `ComponentRegistry` (not a stub). This is the smallest end-to-end
verification that:

* `WorkspaceModel.componentRemoved` is the right signal name the
  observer subscribes to (duck-typing breaks silently when the
  attribute name drifts; only an integration test catches that).
* The full reactive pipeline produces a stale IOEntry without any
  explicit cross-feature import in the observer module.

Per `specs/06_data_flow_and_architecture.md` §4.3.2.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPointF

from features.ControllerDesignModule.model import (
    ConfigurationModel,
    ControllerSettings,
    IOEntry,
    IOSelection,
    IOSourcePortRef,
    PlotLayout,
    SimulationSettings,
)
from features.ControllerDesignModule.observers import WorkspaceReactivityObserver
from features.SystemModelingModule.model.workspace_model import WorkspaceModel
from shared.graph.port_ref import PortRef
from shared.registry import ComponentRegistry
from shared.registry.builtin import BUILTIN_COMPONENT_DEFINITIONS, RESISTOR_DEFINITION


@pytest.mark.integration
def test_end_to_end_stale_flip_on_real_workspace_component_removal() -> None:
    """Real workspace removal flips a matching IOEntry to stale.

    Walks the full Phase-1 path: place a resistor, register an
    IOEntry pointing at it, remove the resistor via the workspace
    API, assert the entry's status is now `"stale"`.
    """
    registry = ComponentRegistry(BUILTIN_COMPONENT_DEFINITIONS)
    workspace = WorkspaceModel(registry=registry)

    resistor_id = workspace.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))

    io_entry = IOEntry(
        id="ioin_X",
        source=IOSourcePortRef(
            port_ref=PortRef(component_id=resistor_id, port_id="p"),
            variable="across",
        ),
    )
    configuration = ConfigurationModel(
        controller_settings=ControllerSettings(),
        io_selection=IOSelection(inputs=(io_entry,)),
        simulation_settings=SimulationSettings(),
        plot_layout=PlotLayout(),
    )
    observer = WorkspaceReactivityObserver(configuration=configuration)
    observer.attach_to_workspace_signals(workspace)

    # Sanity precondition: status is valid before removal.
    # Wrapped in a helper so mypy does not narrow the literal type
    # across the workspace-mutation side-effect.
    def status_of_first_input() -> str:
        return configuration.io_selection.inputs[0].status

    assert status_of_first_input() == "valid"

    workspace.remove_component(resistor_id)

    assert status_of_first_input() == "stale"


@pytest.mark.integration
def test_removing_unreferenced_component_does_not_alter_io_selection() -> None:
    """Removing a component nobody references is a complete no-op."""
    registry = ComponentRegistry(BUILTIN_COMPONENT_DEFINITIONS)
    workspace = WorkspaceModel(registry=registry)

    referenced_id = workspace.add_component_from_definition(
        RESISTOR_DEFINITION.id, QPointF(0.0, 0.0)
    )
    unreferenced_id = workspace.add_component_from_definition(
        RESISTOR_DEFINITION.id, QPointF(100.0, 0.0)
    )

    io_entry = IOEntry(
        id="ioin_X",
        source=IOSourcePortRef(
            port_ref=PortRef(component_id=referenced_id, port_id="p"),
            variable="across",
        ),
    )
    configuration = ConfigurationModel(
        controller_settings=ControllerSettings(),
        io_selection=IOSelection(inputs=(io_entry,)),
        simulation_settings=SimulationSettings(),
        plot_layout=PlotLayout(),
    )
    observer = WorkspaceReactivityObserver(configuration=configuration)
    observer.attach_to_workspace_signals(workspace)

    received: list[IOSelection] = []
    configuration.ioSelectionChanged.connect(received.append)

    workspace.remove_component(unreferenced_id)

    assert received == []
    assert configuration.io_selection.inputs[0].status == "valid"
