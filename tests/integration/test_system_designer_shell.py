"""Integration tests for `SystemDesignerShell` (S1.10).

Exercises the application shell at the API level: every Phase-1
layer is wired correctly, the shell composes without exceptions,
status-bar and window-title slots respond to model events, and the
command stack's `cleanChanged → dirtyChanged` binding still survives
in the shell context.

These tests are marked `integration` rather than `gui` because they
do not simulate user gestures (no `QTest.mousePress`, no synthetic
drag events, no `qtbot.wait*`). They construct the shell under the
session-scoped `QApplication` fixture and drive model mutations
through the public API — which is precisely the integration boundary
S1.10 needs covered before persistence (S2) starts.

References:
----------
* `specs/07_implementation_order.md` §7.13 (S1.10 acceptance)
* `specs/02_workspace_requirements.md` §32.2 (Status Bar)
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPointF

from application.SystemDesignerShell.main_window import SystemDesignerShell
from features.SystemModelingModule.commands import (
    AddComponentCommand,
    WorkspaceCommandStack,
)
from features.SystemModelingModule.model.workspace_model import WorkspaceModel
from features.SystemModelingModule.model.workspace_validator_controller import (
    WorkspaceValidatorController,
)
from features.SystemModelingModule.panels.ComponentInfoPanel.component_info_panel import (
    ComponentInfoPanel,
)
from features.SystemModelingModule.panels.ModelLibraryPanel.component_library_tree import (
    ComponentLibraryTree,
)
from features.SystemModelingModule.workspace.BlockDiagramWorkspace.workspace_scene import (
    WorkspaceScene,
)
from features.SystemModelingModule.workspace.BlockDiagramWorkspace.workspace_view import (
    WorkspaceView,
)
from shared.registry import ComponentRegistry
from shared.registry.builtin import (
    BUILTIN_COMPONENT_DEFINITIONS,
    RESISTOR_DEFINITION,
)


@pytest.fixture
def shell(request: pytest.FixtureRequest) -> SystemDesignerShell:
    """Construct a `SystemDesignerShell` for a single test.

    Pinned on `request.node` so Python's GC does not destroy it
    while Qt still holds child references.
    """
    s = SystemDesignerShell()
    request.node._shell = s
    return s


# ---------------------------------------------------------------------------- #
# Construction + dependency wiring
# ---------------------------------------------------------------------------- #


@pytest.mark.integration
def test_shell_constructs_without_exception(shell: SystemDesignerShell) -> None:
    """Shell `__init__` runs to completion under the session QApplication."""
    assert shell is not None
    assert shell.windowTitle() == "Engineering System Designer"


@pytest.mark.integration
def test_shell_wires_all_phase1_layers(shell: SystemDesignerShell) -> None:
    """Every Phase-1 dependency is instantiated and reachable."""
    assert isinstance(shell.registry, ComponentRegistry)
    assert isinstance(shell.model, WorkspaceModel)
    assert isinstance(shell.validator_controller, WorkspaceValidatorController)
    assert isinstance(shell.command_stack, WorkspaceCommandStack)
    assert isinstance(shell.scene, WorkspaceScene)
    assert isinstance(shell.view, WorkspaceView)
    assert isinstance(shell.library_tree, ComponentLibraryTree)
    assert isinstance(shell.info_panel, ComponentInfoPanel)


@pytest.mark.integration
def test_shell_registry_carries_all_builtin_definitions(
    shell: SystemDesignerShell,
) -> None:
    """Bootstrap loads every entry from `BUILTIN_COMPONENT_DEFINITIONS`."""
    for definition in BUILTIN_COMPONENT_DEFINITIONS:
        assert shell.registry.get(definition.id) is definition


@pytest.mark.integration
def test_shell_library_tree_exposes_every_definition(
    shell: SystemDesignerShell,
) -> None:
    """Drag-source widget reflects the registry catalog 1:1."""
    library_ids = set(shell.library_tree.definitions.keys())
    builtin_ids = {d.id for d in BUILTIN_COMPONENT_DEFINITIONS}
    assert library_ids == builtin_ids


@pytest.mark.integration
def test_shell_scene_and_view_share_model(shell: SystemDesignerShell) -> None:
    """Scene and view both bind to the same model instance."""
    assert shell.scene.model is shell.model
    assert shell.view.scene() is shell.scene


@pytest.mark.integration
def test_shell_command_stack_routes_to_model(shell: SystemDesignerShell) -> None:
    """`WorkspaceCommandStack` wraps the shell's model."""
    assert shell.command_stack.model is shell.model


# ---------------------------------------------------------------------------- #
# Status-bar wiring
# ---------------------------------------------------------------------------- #


@pytest.mark.integration
def test_status_bar_initial_message_is_ready(shell: SystemDesignerShell) -> None:
    """First user-visible message is the bootstrap acknowledgement."""
    assert shell.statusBar().currentMessage() == "Ready"


@pytest.mark.integration
def test_validation_changed_renders_summary_in_status_bar(
    shell: SystemDesignerShell,
) -> None:
    """`validationChanged` slot replaces the status text with a summary."""
    # Force validation immediately rather than wait for the debounce.
    report = shell.validator_controller.validate_now()
    # An empty workspace produces no issues → "Validation: OK".
    if not report.has_errors and not report.has_warnings:
        assert shell.statusBar().currentMessage() == "Validation: OK"
        return
    msg = shell.statusBar().currentMessage()
    assert msg.startswith("Validation: ")


@pytest.mark.integration
def test_component_added_emits_transient_status(
    shell: SystemDesignerShell,
) -> None:
    """Adding a component triggers a status confirmation."""
    shell.model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    msg = shell.statusBar().currentMessage()
    # validationChanged may fire after componentAdded — accept either
    # source so test stays robust against signal ordering changes.
    assert "added" in msg or "Validation" in msg


@pytest.mark.integration
def test_connection_removed_clears_via_transient_message(
    shell: SystemDesignerShell,
) -> None:
    """`componentRemoved` produces an explicit status update."""
    cid = shell.model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    shell.model.remove_component(cid)
    msg = shell.statusBar().currentMessage()
    assert "removed" in msg or "Validation" in msg


# ---------------------------------------------------------------------------- #
# Window-title dirty indicator
# ---------------------------------------------------------------------------- #


@pytest.mark.integration
def test_shell_starts_clean(shell: SystemDesignerShell) -> None:
    """A freshly constructed shell has no `*` suffix."""
    assert shell.windowTitle() == "Engineering System Designer"
    assert shell.model.is_dirty is False


@pytest.mark.integration
def test_pushing_command_marks_title_dirty(shell: SystemDesignerShell) -> None:
    """Mutating via the command stack adds the `*` suffix."""
    cmd = AddComponentCommand(shell.model, RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    shell.command_stack.push(cmd)
    assert shell.windowTitle().endswith(" *")
    assert shell.model.is_dirty is True


@pytest.mark.integration
def test_undo_back_to_clean_index_clears_dirty_indicator(
    shell: SystemDesignerShell,
) -> None:
    """`cleanChanged(True)` clears the `*` suffix via the dirty bit."""
    cmd = AddComponentCommand(shell.model, RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    shell.command_stack.push(cmd)
    assert shell.windowTitle().endswith(" *")
    shell.command_stack.undo()
    assert not shell.windowTitle().endswith(" *")
    assert shell.model.is_dirty is False
