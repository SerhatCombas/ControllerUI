"""Integration tests for S2.G.1 shell composition.

Covers:

* `ConfigurationModel` + `ConfigurationCommandStack` are built
  during shell bootstrap.
* `QUndoGroup` composes both feature stacks; Edit menu actions
  are group-driven (not hardcoded per-stack).
* Active-stack tracking: every push / undo / redo on either
  stack makes that stack the group's active stack.
* Title bar combines the project name (`_UNTITLED_PROJECT_NAME`
  before save) with a dirty marker that OR's both model dirty
  bits.
* `current_bundle_path` is `None` on bootstrap (S2.G.2 mutates).
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPointF
from PySide6.QtGui import QUndoGroup

from application.SystemDesignerShell.main_window import (
    SystemDesignerShell,
)
from features.ControllerDesignModule.commands import (
    AddControllerCommand,
    ConfigurationCommandStack,
)
from features.ControllerDesignModule.model import (
    ConfigurationModel,
    ControllerSpec,
    new_controller_id,
)
from shared.registry.builtin import RESISTOR_DEFINITION


@pytest.fixture
def shell(request: pytest.FixtureRequest) -> SystemDesignerShell:
    """Shell pinned on the test node so Qt parent-chains stay alive."""
    s = SystemDesignerShell()
    request.node._shell = s
    return s


# ---------------------------------------------------------------------- #
# ConfigurationModel + ConfigurationCommandStack construction
# ---------------------------------------------------------------------- #


@pytest.mark.integration
def test_shell_builds_configuration_model(shell: SystemDesignerShell) -> None:
    """Bootstrap exposes a `ConfigurationModel` ready for command pushes."""
    assert isinstance(shell.configuration_model, ConfigurationModel)


@pytest.mark.integration
def test_shell_builds_configuration_command_stack(
    shell: SystemDesignerShell,
) -> None:
    """`ConfigurationCommandStack` is constructed and bound to the model."""
    assert isinstance(shell.configuration_command_stack, ConfigurationCommandStack)
    assert shell.configuration_command_stack.model is shell.configuration_model


@pytest.mark.integration
def test_configuration_model_starts_empty_and_clean(
    shell: SystemDesignerShell,
) -> None:
    """On bootstrap the configuration model has empty sections + is_dirty=False.

    The shell deliberately ships an empty configuration so the
    dirty bit starts at False. The File → New action (S2.G.2)
    loads Phase-1 defaults explicitly when the user requests
    a new project.
    """
    cm = shell.configuration_model
    assert cm.controller_settings.controllers == ()
    assert cm.io_selection.inputs == ()
    assert cm.io_selection.outputs == ()
    assert cm.plot_layout.slots == ()
    assert cm.is_dirty is False


# ---------------------------------------------------------------------- #
# QUndoGroup composition
# ---------------------------------------------------------------------- #


@pytest.mark.integration
def test_undo_group_contains_both_feature_stacks(
    shell: SystemDesignerShell,
) -> None:
    """Both `QUndoStack` instances are members of the shell's `QUndoGroup`."""
    assert isinstance(shell.undo_group, QUndoGroup)
    stacks = list(shell.undo_group.stacks())
    assert shell.command_stack.stack in stacks
    assert shell.configuration_command_stack.stack in stacks
    assert len(stacks) == 2


@pytest.mark.integration
def test_initial_active_stack_is_workspace(shell: SystemDesignerShell) -> None:
    """Default active stack is the workspace stack (PD1 lean)."""
    assert shell.undo_group.activeStack() is shell.command_stack.stack


@pytest.mark.integration
def test_workspace_push_makes_workspace_stack_active(
    shell: SystemDesignerShell,
) -> None:
    """A workspace command push flips active to the workspace stack."""
    # Push something on the config stack first to flip the
    # active pointer away from workspace.
    shell.configuration_command_stack.push(
        AddControllerCommand(
            shell.configuration_model,
            ControllerSpec(id=new_controller_id(), controller_type="PID"),
        )
    )
    assert shell.undo_group.activeStack() is shell.configuration_command_stack.stack

    # Now push on the workspace stack.
    shell.scene.drop_component(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    assert shell.undo_group.activeStack() is shell.command_stack.stack


@pytest.mark.integration
def test_configuration_push_makes_configuration_stack_active(
    shell: SystemDesignerShell,
) -> None:
    """A configuration command push flips active to the configuration stack."""
    shell.scene.drop_component(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    assert shell.undo_group.activeStack() is shell.command_stack.stack

    shell.configuration_command_stack.push(
        AddControllerCommand(
            shell.configuration_model,
            ControllerSpec(id=new_controller_id(), controller_type="PID"),
        )
    )
    assert shell.undo_group.activeStack() is shell.configuration_command_stack.stack


# ---------------------------------------------------------------------- #
# Edit menu — group-driven actions
# ---------------------------------------------------------------------- #


@pytest.mark.gui
def test_undo_action_routes_to_active_stack(
    shell: SystemDesignerShell,
) -> None:
    """Single Ctrl+Z undoes whichever stack was most recently mutated.

    Push a workspace command then a configuration command. The
    first Ctrl+Z must undo the configuration push (most recently
    active), leaving the workspace state intact.
    """
    shell.scene.drop_component(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    components_after_workspace = len(shell.model.components)

    shell.configuration_command_stack.push(
        AddControllerCommand(
            shell.configuration_model,
            ControllerSpec(id=new_controller_id(), controller_type="PID"),
        )
    )
    controllers_after_config = len(shell.configuration_model.controller_settings.controllers)

    # Trigger Edit → Undo via the group-driven action.
    shell._undo_action.trigger()

    # Configuration push reverted; workspace untouched.
    assert (
        len(shell.configuration_model.controller_settings.controllers)
        == controllers_after_config - 1
    )
    assert len(shell.model.components) == components_after_workspace


@pytest.mark.gui
def test_undo_action_disables_when_active_stack_empty(
    shell: SystemDesignerShell,
) -> None:
    """When the active stack has nothing to undo, the action disables.

    Phase-1 acceptable edge case (focus-based switching is a
    Phase-2 polish item). User pushes a workspace command, undoes
    it; workspace stack now empty + active. Action disabled even
    if the configuration stack still has history.
    """
    shell.scene.drop_component(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    shell._undo_action.trigger()  # undo it
    assert shell._undo_action.isEnabled() is False


# ---------------------------------------------------------------------- #
# Title bar — dirty union + project name
# ---------------------------------------------------------------------- #


@pytest.mark.integration
def test_initial_title_is_untitled_no_dirty_marker(
    shell: SystemDesignerShell,
) -> None:
    """A fresh shell shows `Untitled — System Designer`."""
    assert shell.windowTitle() == "Untitled — System Designer"


@pytest.mark.integration
def test_workspace_dirty_alone_adds_marker(shell: SystemDesignerShell) -> None:
    """Workspace mutation → title has the `*` marker."""
    shell.scene.drop_component(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    assert shell.windowTitle() == "Untitled * — System Designer"
    # Configuration stays clean.
    assert shell.configuration_model.is_dirty is False


@pytest.mark.integration
def test_configuration_dirty_alone_adds_marker(
    shell: SystemDesignerShell,
) -> None:
    """Configuration mutation → title has the `*` marker."""
    shell.configuration_command_stack.push(
        AddControllerCommand(
            shell.configuration_model,
            ControllerSpec(id=new_controller_id(), controller_type="PID"),
        )
    )
    assert shell.windowTitle() == "Untitled * — System Designer"
    assert shell.model.is_dirty is False


@pytest.mark.integration
def test_marker_clears_when_both_models_clean_again(
    shell: SystemDesignerShell,
) -> None:
    """Marker disappears once both models return to clean.

    Per-stack undo is used here rather than the group-driven
    Edit menu action because clearing both stacks requires
    touching both stacks individually — the QUndoGroup active
    pointer doesn't auto-switch when the current stack runs
    out of undo (Phase-1 accepted limitation; see
    `test_undo_action_disables_when_active_stack_empty`).
    """
    shell.scene.drop_component(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    shell.configuration_command_stack.push(
        AddControllerCommand(
            shell.configuration_model,
            ControllerSpec(id=new_controller_id(), controller_type="PID"),
        )
    )
    assert "*" in shell.windowTitle()

    # Undo each stack directly to return both models to clean.
    shell.configuration_command_stack.undo()
    shell.command_stack.undo()
    assert shell.windowTitle() == "Untitled — System Designer"


# ---------------------------------------------------------------------- #
# current_bundle_path bootstrap state
# ---------------------------------------------------------------------- #


@pytest.mark.integration
def test_current_bundle_path_is_none_on_bootstrap(
    shell: SystemDesignerShell,
) -> None:
    """`current_bundle_path` is `None` before any Save As / Open."""
    assert shell.current_bundle_path is None
