"""Integration tests for S2.G.2 shell File menu + save / load wiring.

Covers:

* File menu shape + standard-key shortcuts.
* `save_current_project()` round-trip into a tmpdir bundle plus
  spec §29.7 dirty-clear on success.
* `load_project_from()` round-trip + title / dirty / bundle path
  updates.
* Save failure surfaces as `QMessageBox.critical` with the
  dirty bit deliberately left set (the save did not happen).
* Unsaved-changes dialog flow: Discard / Save / Cancel and the
  nested Save → Save As fallback path. `QMessageBox.warning`
  monkeypatched per test scenario.
* File → New resets to Phase-1 defaults; honors unsaved-changes
  flow.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QMessageBox

from application.SystemDesignerShell.main_window import SystemDesignerShell
from shared.registry.builtin import RESISTOR_DEFINITION

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def shell(request: pytest.FixtureRequest) -> SystemDesignerShell:
    """Shell pinned on the test node so Qt parent-chains stay alive."""
    s = SystemDesignerShell()
    request.node._shell = s
    return s


# ---------------------------------------------------------------------- #
# File menu shape
# ---------------------------------------------------------------------- #


@pytest.mark.integration
def test_file_menu_has_four_phase1_actions(shell: SystemDesignerShell) -> None:
    """File menu carries exactly the SI1-locked action set."""
    texts = [
        a.text()
        for a in (
            shell._new_action,
            shell._open_action,
            shell._save_action,
            shell._save_as_action,
        )
    ]
    assert texts == [
        "&New Project",
        "&Open Project...",
        "&Save",
        "Save &As...",
    ]


# ---------------------------------------------------------------------- #
# save_current_project — spec §29.7 dirty clear + path update
# ---------------------------------------------------------------------- #


@pytest.mark.integration
def test_save_current_project_succeeds_and_clears_dirty(
    tmp_path: Path, shell: SystemDesignerShell
) -> None:
    """A successful save writes the bundle AND clears both models' dirty bits."""

    def workspace_dirty() -> bool:
        return shell.model.is_dirty

    def config_dirty() -> bool:
        return shell.configuration_model.is_dirty

    shell.scene.drop_component(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    assert workspace_dirty() is True

    bundle = tmp_path / "save_round_trip.systemdesign"
    shell._current_bundle_path = bundle
    shell._update_window_title()

    success = shell.save_current_project()
    assert success is True
    assert (bundle / "project.json").is_file()
    assert workspace_dirty() is False
    assert config_dirty() is False
    assert " * " not in shell.windowTitle()


@pytest.mark.integration
def test_save_current_project_handles_oserror_and_keeps_dirty(
    tmp_path: Path,
    shell: SystemDesignerShell,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`OSError` during save → critical dialog suppressed, dirty stays set."""
    shell.scene.drop_component(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    bundle = tmp_path / "save_failure.systemdesign"
    shell._current_bundle_path = bundle

    # Suppress the modal critical dialog.
    monkeypatch.setattr(QMessageBox, "critical", lambda *args, **kwargs: None)

    # Inject a save failure.
    def _raise_oserror(*_args: object, **_kwargs: object) -> None:
        raise OSError("Mock disk-full simulation")

    monkeypatch.setattr(
        "application.SystemDesignerShell.main_window.save_project",
        _raise_oserror,
    )

    success = shell.save_current_project()
    assert success is False
    assert shell.model.is_dirty is True  # spec §29.7: failure leaves dirty


# ---------------------------------------------------------------------- #
# load_project_from — round-trip + path + dirty
# ---------------------------------------------------------------------- #


@pytest.mark.integration
def test_load_project_from_round_trip(tmp_path: Path, shell: SystemDesignerShell) -> None:
    """`load_project_from` populates the shell from a bundle on disk."""
    # Prepare a bundle on disk.
    shell.scene.drop_component(RESISTOR_DEFINITION.id, QPointF(10.0, 20.0))
    bundle = tmp_path / "load_round_trip.systemdesign"
    shell._current_bundle_path = bundle
    shell.save_current_project()

    # Mutate after save so we can detect the load restored state.
    shell.scene.drop_component(RESISTOR_DEFINITION.id, QPointF(99.0, 99.0))
    assert len(shell.model.components) == 2

    success = shell.load_project_from(bundle)
    assert success is True
    assert len(shell.model.components) == 1
    assert shell.current_bundle_path == bundle
    assert "load_round_trip" in shell.windowTitle()
    assert " * " not in shell.windowTitle()
    assert shell.model.is_dirty is False


@pytest.mark.integration
def test_load_project_from_missing_bundle_returns_false(
    tmp_path: Path,
    shell: SystemDesignerShell,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Loading a nonexistent bundle surfaces a dialog and returns False."""
    monkeypatch.setattr(QMessageBox, "critical", lambda *args, **kwargs: None)
    success = shell.load_project_from(tmp_path / "ghost.systemdesign")
    assert success is False


# ---------------------------------------------------------------------- #
# Save with no `_current_bundle_path` → Save As fallback
# ---------------------------------------------------------------------- #


@pytest.mark.integration
def test_on_save_with_no_path_falls_through_to_save_as(
    tmp_path: Path,
    shell: SystemDesignerShell,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`Ctrl+S` on an untitled project opens the Save As dialog instead."""
    shell.scene.drop_component(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    assert shell.current_bundle_path is None

    chosen = tmp_path / "from_save_as.systemdesign"
    monkeypatch.setattr(shell, "_show_save_as_dialog", lambda: chosen)

    shell._on_save_project()  # equivalent to Ctrl+S
    assert shell.current_bundle_path == chosen
    assert (chosen / "project.json").is_file()
    assert shell.model.is_dirty is False


# ---------------------------------------------------------------------- #
# Unsaved-changes dialog flow (SI2)
# ---------------------------------------------------------------------- #


@pytest.mark.integration
def test_unsaved_dialog_discard_branch_returns_true(
    shell: SystemDesignerShell,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`Discard` choice → caller may proceed."""
    shell.scene.drop_component(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args, **kwargs: QMessageBox.StandardButton.Discard,
    )
    assert shell._confirm_discard_or_save_if_dirty() is True


@pytest.mark.integration
def test_unsaved_dialog_cancel_branch_returns_false(
    shell: SystemDesignerShell,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`Cancel` choice → caller aborts."""
    shell.scene.drop_component(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args, **kwargs: QMessageBox.StandardButton.Cancel,
    )
    assert shell._confirm_discard_or_save_if_dirty() is False


@pytest.mark.integration
def test_unsaved_dialog_save_branch_with_existing_path_returns_true(
    tmp_path: Path,
    shell: SystemDesignerShell,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`Save` with a known path → direct save → returns True."""
    shell._current_bundle_path = tmp_path / "save_branch.systemdesign"
    shell.scene.drop_component(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args, **kwargs: QMessageBox.StandardButton.Save,
    )
    assert shell._confirm_discard_or_save_if_dirty() is True
    assert (shell._current_bundle_path / "project.json").is_file()


@pytest.mark.integration
def test_unsaved_dialog_save_branch_with_no_path_routes_through_save_as(
    tmp_path: Path,
    shell: SystemDesignerShell,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`Save` on untitled project → Save As dialog. Cancel aborts the outer action."""
    shell.scene.drop_component(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args, **kwargs: QMessageBox.StandardButton.Save,
    )
    # User cancels Save As → outer action aborted.
    monkeypatch.setattr(shell, "_show_save_as_dialog", lambda: None)
    assert shell._confirm_discard_or_save_if_dirty() is False


@pytest.mark.integration
def test_unsaved_dialog_save_branch_save_failure_returns_false(
    tmp_path: Path,
    shell: SystemDesignerShell,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`Save` succeeds at dialog but write fails → returns False."""
    shell._current_bundle_path = tmp_path / "save_failure.systemdesign"
    shell.scene.drop_component(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args, **kwargs: QMessageBox.StandardButton.Save,
    )
    monkeypatch.setattr(QMessageBox, "critical", lambda *args, **kwargs: None)

    def _raise(*_args: object, **_kwargs: object) -> None:
        raise OSError("write blocked")

    monkeypatch.setattr(
        "application.SystemDesignerShell.main_window.save_project",
        _raise,
    )
    assert shell._confirm_discard_or_save_if_dirty() is False


@pytest.mark.integration
def test_unsaved_dialog_skipped_when_models_clean(
    shell: SystemDesignerShell,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Clean models → no dialog shown, caller may proceed immediately."""

    def _fail_if_called(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("dialog should not show when both models clean")

    monkeypatch.setattr(QMessageBox, "warning", _fail_if_called)
    assert shell._confirm_discard_or_save_if_dirty() is True


# ---------------------------------------------------------------------- #
# File → New
# ---------------------------------------------------------------------- #


@pytest.mark.integration
def test_new_project_resets_to_phase1_defaults(
    shell: SystemDesignerShell,
) -> None:
    """File → New loads `default_config.json` into both models."""
    # Trigger via the slot (clean state — no dialog).
    shell._on_new_project()

    # Workspace empty; configuration carries the four default plot
    # slots + one PID controller per spec §13.
    assert len(shell.model.components) == 0
    assert len(shell.configuration_model.plot_layout.slots) == 4
    assert len(shell.configuration_model.controller_settings.controllers) == 1
    assert shell.configuration_model.controller_settings.controllers[0].controller_type == "PID"
    assert shell.current_bundle_path is None
    assert " * " not in shell.windowTitle()


@pytest.mark.integration
def test_new_project_with_dirty_state_aborts_on_cancel(
    shell: SystemDesignerShell,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dirty + Cancel → model unchanged after File → New is invoked."""
    shell.scene.drop_component(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    initial_components = len(shell.model.components)
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda *args, **kwargs: QMessageBox.StandardButton.Cancel,
    )
    shell._on_new_project()
    assert len(shell.model.components) == initial_components


# ---------------------------------------------------------------------- #
# `.systemdesign` extension auto-append (SI3)
# ---------------------------------------------------------------------- #


@pytest.mark.integration
def test_save_as_dialog_appends_systemdesign_suffix(
    tmp_path: Path,
    shell: SystemDesignerShell,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """User types `my_project` → dialog returns `my_project.systemdesign`."""
    raw_path = tmp_path / "my_project"  # no .systemdesign suffix
    monkeypatch.setattr(
        "PySide6.QtWidgets.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: (str(raw_path), ""),
    )
    chosen = shell._show_save_as_dialog()
    assert chosen is not None
    assert chosen.suffix == ".systemdesign"
    assert chosen.stem == "my_project"


@pytest.mark.integration
def test_save_as_dialog_preserves_explicit_systemdesign_suffix(
    tmp_path: Path,
    shell: SystemDesignerShell,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """User types `my_project.systemdesign` → suffix not duplicated."""
    raw_path = tmp_path / "my_project.systemdesign"
    monkeypatch.setattr(
        "PySide6.QtWidgets.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: (str(raw_path), ""),
    )
    chosen = shell._show_save_as_dialog()
    assert chosen is not None
    assert chosen.name == "my_project.systemdesign"
