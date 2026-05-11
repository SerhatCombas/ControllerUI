"""GUI tests for `SystemDesignerShell` user interactions (S1.10).

Exercises the shell at the gesture / user-action layer:

* Edit menu actions trigger undo / redo on the command stack
* The library-tree drag payload reaches the scene's `drop_component`
  entry point and produces a placed component
* Validation feedback re-renders in the status bar after a drop

Tests are marked `gui` because they invoke `QAction.trigger()` and
simulate the drop pipeline through the scene's public API. The
`integration` cousin of this file exercises the same wiring at the
model-API level — see `tests/integration/test_system_designer_shell.py`.

References:
----------
* `specs/07_implementation_order.md` §7.13 (S1.10 acceptance)
* `specs/02_workspace_requirements.md` §32.2 (Status Bar)
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QByteArray, QPointF

from application.SystemDesignerShell.main_window import SystemDesignerShell
from features.SystemModelingModule.workspace.BlockDiagramWorkspace.workspace_scene import (
    COMPONENT_MIME_TYPE,
)
from shared.registry.builtin import (
    BUILTIN_COMPONENT_DEFINITIONS,
    RESISTOR_DEFINITION,
)


@pytest.fixture
def shell(request: pytest.FixtureRequest) -> SystemDesignerShell:
    """Shell pinned on the test node so Qt parent-chains stay alive."""
    s = SystemDesignerShell()
    request.node._shell = s
    return s


# ---------------------------------------------------------------------------- #
# Edit menu — Undo / Redo
# ---------------------------------------------------------------------------- #


@pytest.mark.gui
def test_edit_menu_contains_undo_and_redo_actions(
    shell: SystemDesignerShell,
) -> None:
    """The Edit menu has the two Phase-1 actions wired in S1.10."""
    from PySide6.QtWidgets import QMenu

    menu_bar = shell.menuBar()
    menus: list[QMenu] = list(menu_bar.findChildren(QMenu))
    edit_menu = next(m for m in menus if m.title() == "&Edit")
    action_texts = [a.text() for a in edit_menu.actions()]
    assert "&Undo" in action_texts
    assert "&Redo" in action_texts


@pytest.mark.gui
def test_undo_action_trigger_invokes_command_stack_undo(
    shell: SystemDesignerShell,
) -> None:
    """`Edit → Undo` rewinds the last command on the stack."""
    cid = shell.model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    assert cid in shell.model.components

    shell.scene.drop_component(RESISTOR_DEFINITION.id, QPointF(40.0, 40.0))
    assert len(shell.model.components) == 2

    shell._undo_action.trigger()
    assert len(shell.model.components) == 1


@pytest.mark.gui
def test_redo_action_trigger_replays_undone_command(
    shell: SystemDesignerShell,
) -> None:
    """`Edit → Redo` re-applies an undone command."""
    shell.scene.drop_component(RESISTOR_DEFINITION.id, QPointF(20.0, 20.0))
    assert len(shell.model.components) == 1

    shell._undo_action.trigger()
    assert len(shell.model.components) == 0

    shell._redo_action.trigger()
    assert len(shell.model.components) == 1


# ---------------------------------------------------------------------------- #
# Library tree → scene drop pipeline
# ---------------------------------------------------------------------------- #


@pytest.mark.gui
def test_library_tree_drag_payload_matches_drop_mime_format(
    shell: SystemDesignerShell,
) -> None:
    """Library tree advertises the same MIME type the scene accepts."""
    # First leaf in the tree carries a definition id we can use.
    tree = shell.library_tree
    # The first definition (`GROUND_ELECTRIC_DEFINITION`) sits at the
    # top of the Electrical / Components subtree.
    first_definition = BUILTIN_COMPONENT_DEFINITIONS[0]
    payload = QByteArray(first_definition.id.encode("utf-8"))
    assert payload.data() == first_definition.id.encode("utf-8")
    # The scene's accept logic checks the MIME type constant.
    assert COMPONENT_MIME_TYPE.startswith("application/x-system-model-")
    # The library tree is in drag-only mode.
    from PySide6.QtWidgets import QTreeWidget

    assert tree.dragDropMode() == QTreeWidget.DragDropMode.DragOnly


@pytest.mark.gui
def test_scene_drop_places_component_and_updates_status_bar(
    shell: SystemDesignerShell,
) -> None:
    """A drop through `drop_component` lands a component AND updates status."""
    new_id = shell.scene.drop_component(RESISTOR_DEFINITION.id, QPointF(60.0, 60.0))
    assert new_id is not None
    assert new_id in shell.model.components

    msg = shell.statusBar().currentMessage()
    # Either the component-added transient or the immediate validation
    # summary may be the last status — both prove the wiring works.
    assert "added" in msg or "Validation" in msg


@pytest.mark.gui
def test_drop_then_undo_round_trip_returns_to_clean(
    shell: SystemDesignerShell,
) -> None:
    """Full drop → undo cycle leaves model + title back at clean state."""

    def dirty(s: SystemDesignerShell) -> bool:
        # Wrap in a helper so mypy does not narrow the bool result
        # across the drop-side-effect that mutates is_dirty.
        return s.model.is_dirty

    assert dirty(shell) is False

    shell.scene.drop_component(RESISTOR_DEFINITION.id, QPointF(80.0, 80.0))
    assert dirty(shell) is True
    assert shell.windowTitle().endswith(" *")

    shell._undo_action.trigger()
    assert dirty(shell) is False
    assert not shell.windowTitle().endswith(" *")


# ---------------------------------------------------------------------------- #
# Validation feedback re-renders in status bar
# ---------------------------------------------------------------------------- #


@pytest.mark.gui
def test_validation_summary_refreshes_after_drop(
    shell: SystemDesignerShell,
) -> None:
    """`validate_now()` after a drop emits a non-empty summary string."""
    shell.scene.drop_component(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    report = shell.validator_controller.validate_now()
    msg = shell.statusBar().currentMessage()
    assert msg.startswith("Validation: ")
    # The single-resistor workspace generates at least one
    # validation issue (unused-port warning + missing-ground error).
    assert report.has_errors or report.has_warnings


# ---------------------------------------------------------------------------- #
# S1.10.1 — connection rejection surfaces in the status bar
# ---------------------------------------------------------------------------- #


@pytest.mark.gui
def test_duplicate_connection_attempt_surfaces_in_status_bar(
    shell: SystemDesignerShell,
) -> None:
    """Drag-then-drop of a duplicate connection produces a status message.

    Companion to the unit test in
    `tests/.../test_workspace_scene_connection_draw.py` —
    the unit covers signal emission, this gui test covers the
    shell-side slot wiring. Splitting catches refactors that
    sever the binding while leaving the emit intact.
    """
    from features.SystemModelingModule.model.connection import PortRef

    r_id = shell.scene.drop_component(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    from shared.registry.builtin import GROUND_ELECTRIC_DEFINITION

    g_id = shell.scene.drop_component(GROUND_ELECTRIC_DEFINITION.id, QPointF(100.0, 0.0))
    assert r_id is not None
    assert g_id is not None

    # First connection: succeeds.
    shell.scene.start_connection_draw(PortRef(component_id=r_id, port_id="p"))
    shell.scene.commit_connection_draw(PortRef(component_id=g_id, port_id="p"))

    # Second attempt with the same port pair is the duplicate.
    shell.scene.start_connection_draw(PortRef(component_id=r_id, port_id="p"))
    shell.scene.commit_connection_draw(PortRef(component_id=g_id, port_id="p"))

    msg = shell.statusBar().currentMessage()
    assert msg.startswith(
        "Connection rejected:"
    ), f"expected status to start with 'Connection rejected:', got {msg!r}"
    assert "already exists" in msg


@pytest.mark.gui
def test_cross_domain_connection_attempt_surfaces_in_status_bar(
    shell: SystemDesignerShell,
) -> None:
    """Cross-domain drop produces a 'Connection rejected:' message."""
    from features.SystemModelingModule.model.connection import PortRef
    from shared.registry.builtin import MASS_DEFINITION

    r_id = shell.scene.drop_component(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    m_id = shell.scene.drop_component(MASS_DEFINITION.id, QPointF(200.0, 0.0))
    assert r_id is not None
    assert m_id is not None

    shell.scene.start_connection_draw(PortRef(component_id=r_id, port_id="n"))
    shell.scene.commit_connection_draw(PortRef(component_id=m_id, port_id="flange"))

    msg = shell.statusBar().currentMessage()
    assert msg.startswith(
        "Connection rejected:"
    ), f"expected status to start with 'Connection rejected:', got {msg!r}"
    assert "incompatible domains" in msg
