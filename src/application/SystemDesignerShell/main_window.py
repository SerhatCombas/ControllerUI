"""SystemDesignerShell: top-level main window.

Per `specs/02_workspace_requirements.md` §2 / §32 and
`specs/07_implementation_order.md` §7.13. The shell composes
every layer wired during Phase 1:

* `ComponentRegistry` — built-in definition catalog
* `WorkspaceModel` — source of truth for placed components +
  connections + dirty flag
* `WorkspaceValidatorController` — debounce-driven workspace
  validation, emits `validationChanged` on the model
* `WorkspaceCommandStack` — undo/redo + dirty binding via
  `cleanChanged`
* `WorkspaceScene` / `WorkspaceView` — QGraphics rendering
* `ComponentLibraryTree` — drag source for component placement
* `ComponentInfoPanel` — parameter editor for the current
  selection

Bootstrap order (S1.10 minimum integration):

1. Logging (configured by `application/main.py` before shell
   construction)
2. `ComponentRegistry(BUILTIN_COMPONENT_DEFINITIONS)`
3. `WorkspaceModel(registry=...)`
4. `WorkspaceValidatorController(model)` — listens to model
   signals only; can come before the command stack
5. `WorkspaceCommandStack(model)` — wires `cleanChanged` to
   the model's dirty bit
6. `WorkspaceScene(model, command_stack=stack)` — scene
   subscribes to model signals and routes drops through the
   command stack
7. `WorkspaceView(scene)` — host widget
8. `ComponentLibraryTree(BUILTIN_COMPONENT_DEFINITIONS)` — drag
   source
9. `ComponentInfoPanel(model, scene, command_stack=stack)` —
   selection-driven parameter editor
10. Status bar wiring — `model.validationChanged` →
    summary message; `model.dirtyChanged` → window-title
    asterisk

S1.10 scope deliberately excludes:

* Project file persistence (S2)
* Save / Open menu actions (S2)
* Autosave timer (S2)
* Delete keyboard shortcut + paste handler (separate sub-commit)
* SVG icons in the library tree (S1.11 polish)
* Selection-mode toolbar / status indicator (deferred to a
  post-smoke pass)

References:
----------
* `specs/02_workspace_requirements.md` §2 (Workspace), §32
  (Error Handling and Status Reporting)
* `specs/06_data_flow_and_architecture.md` §2.1, §3
  (Initialization Order)
* `specs/07_implementation_order.md` §7.13
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtGui import QKeySequence, QUndoGroup
from PySide6.QtWidgets import QDockWidget, QMainWindow

from features.ControllerDesignModule.commands import ConfigurationCommandStack
from features.ControllerDesignModule.model import (
    ConfigurationModel,
    ControllerSettings,
    IOSelection,
    PlotLayout,
    SimulationSettings,
)
from features.SystemModelingModule.commands import WorkspaceCommandStack
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
from shared.registry.builtin import BUILTIN_COMPONENT_DEFINITIONS

if TYPE_CHECKING:
    from pathlib import Path

    from PySide6.QtWidgets import QWidget

    from features.SystemModelingModule.model.validation_report import (
        ValidationReport,
    )


logger = logging.getLogger(__name__)

# `showMessage(msg, msecs)` clears the message after `msecs`
# milliseconds. 4-second persistence matches the spec/02 §32.2
# rule for transient messages.
_STATUS_TRANSIENT_MS: int = 4000
# Persistent messages (errors / warnings) use 0 per the same
# spec section ("remain until the user dismisses them or
# another error replaces them").
_STATUS_PERSISTENT_MS: int = 0

# Untitled-project display name in the window title before the
# user has saved the project (`_current_bundle_path is None`).
# Update lives in `_update_window_title`; the value lands here so
# tests can assert against it without depending on the string
# formatting of `setWindowTitle`.
_UNTITLED_PROJECT_NAME: str = "Untitled"

# Suffix shared with the file save / open dialogs (S2.G.2) so the
# directory-bundle suffix is defined in one place.
_BUNDLE_SUFFIX: str = ".systemdesign"


class SystemDesignerShell(QMainWindow):
    """Top-level main window composing every Phase-1 component.

    Construction is fully synchronous and deterministic: every
    dependency is instantiated in the order documented in the
    module docstring. The shell holds strong references to all
    instantiated objects so Qt's parent-child garbage collection
    does not destroy them prematurely.

    Tests can construct the shell headlessly under the
    session-scoped `QApplication` fixture in `tests/conftest.py`
    without entering the event loop.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        """Wire every Phase-1 layer in deterministic bootstrap order."""
        super().__init__(parent)
        self.setWindowTitle("Engineering System Designer")
        self.resize(1280, 800)

        # 2. Component registry — built-in MVP definitions.
        self._registry: ComponentRegistry = ComponentRegistry(BUILTIN_COMPONENT_DEFINITIONS)

        # 3. Workspace model.
        self._model: WorkspaceModel = WorkspaceModel(registry=self._registry)

        # 4. Validator controller (model signals only — order
        # before the command stack is fine).
        self._validator_controller: WorkspaceValidatorController = WorkspaceValidatorController(
            self._model
        )

        # 5. Command stack — wires `cleanChanged` to model dirty bit.
        self._command_stack: WorkspaceCommandStack = WorkspaceCommandStack(self._model)

        # 5b. Configuration model + command stack (S2.G.1). The
        # configuration model holds the four spec/03 §9 sections
        # (controller_settings, io_selection, simulation_settings,
        # plot_layout) and emits the matching per-section signals.
        # Phase-1 default sections come from `load_default_configuration()`
        # but the shell builds the model with **empty** sections to
        # keep the dirty bit `False` on bootstrap; the file menu's
        # "New" action (S2.G.2) loads defaults explicitly when the
        # user requests a new project.
        self._configuration_model: ConfigurationModel = ConfigurationModel(
            controller_settings=ControllerSettings(),
            io_selection=IOSelection(),
            simulation_settings=SimulationSettings(),
            plot_layout=PlotLayout(),
        )
        self._configuration_command_stack: ConfigurationCommandStack = ConfigurationCommandStack(
            self._configuration_model
        )

        # 5c. Current project bundle path (S2.G.1 placeholder;
        # mutated by S2.G.2 Save / Open actions). `None` on
        # bootstrap means "Untitled" — the title bar's project
        # name segment renders the `_UNTITLED_PROJECT_NAME`
        # constant in that state.
        self._current_bundle_path: Path | None = None

        # 6. Workspace scene + 7. view.
        self._scene: WorkspaceScene = WorkspaceScene(self._model, command_stack=self._command_stack)
        self._view: WorkspaceView = WorkspaceView(self._scene)
        self.setCentralWidget(self._view)

        # 8. Library panel (left dock).
        self._library_tree: ComponentLibraryTree = ComponentLibraryTree(
            BUILTIN_COMPONENT_DEFINITIONS
        )
        library_dock = QDockWidget("Library", self)
        library_dock.setObjectName("LibraryDock")
        library_dock.setWidget(self._library_tree)
        from PySide6.QtCore import Qt as QtNamespace  # local for type forward-compat

        self.addDockWidget(QtNamespace.DockWidgetArea.LeftDockWidgetArea, library_dock)
        self._library_dock = library_dock

        # 9. Component info panel (right dock).
        self._info_panel: ComponentInfoPanel = ComponentInfoPanel(
            model=self._model,
            scene=self._scene,
            command_stack=self._command_stack,
        )
        info_dock = QDockWidget("Properties", self)
        info_dock.setObjectName("InfoDock")
        info_dock.setWidget(self._info_panel)
        self.addDockWidget(QtNamespace.DockWidgetArea.RightDockWidgetArea, info_dock)
        self._info_dock = info_dock

        # 10. Edit menu (Undo / Redo via QUndoGroup — S2.G.1).
        self._build_edit_menu()

        # 11. Status bar wiring.
        self.statusBar().showMessage("Ready", _STATUS_TRANSIENT_MS)
        self._wire_status_bar_signals()

        # 12. Window title — project name + dirty marker.
        self._wire_window_title()

        logger.info(
            "SystemDesignerShell construction complete",
            extra={
                "definition_count": len(BUILTIN_COMPONENT_DEFINITIONS),
            },
        )

    # ------------------------------------------------------------------ #
    # Read-only accessors (test convenience)
    # ------------------------------------------------------------------ #

    @property
    def registry(self) -> ComponentRegistry:
        """The bound `ComponentRegistry`."""
        return self._registry

    @property
    def model(self) -> WorkspaceModel:
        """The bound `WorkspaceModel`."""
        return self._model

    @property
    def command_stack(self) -> WorkspaceCommandStack:
        """The bound `WorkspaceCommandStack`."""
        return self._command_stack

    @property
    def validator_controller(self) -> WorkspaceValidatorController:
        """The bound `WorkspaceValidatorController`."""
        return self._validator_controller

    @property
    def scene(self) -> WorkspaceScene:
        """The bound `WorkspaceScene`."""
        return self._scene

    @property
    def view(self) -> WorkspaceView:
        """The bound `WorkspaceView`."""
        return self._view

    @property
    def library_tree(self) -> ComponentLibraryTree:
        """The library panel's `ComponentLibraryTree`."""
        return self._library_tree

    @property
    def info_panel(self) -> ComponentInfoPanel:
        """The right-dock `ComponentInfoPanel`."""
        return self._info_panel

    @property
    def configuration_model(self) -> ConfigurationModel:
        """The bound `ConfigurationModel` (S2.G.1)."""
        return self._configuration_model

    @property
    def configuration_command_stack(self) -> ConfigurationCommandStack:
        """The bound `ConfigurationCommandStack` (S2.G.1)."""
        return self._configuration_command_stack

    @property
    def undo_group(self) -> QUndoGroup:
        """The `QUndoGroup` composing workspace + configuration stacks.

        Exposed for test convenience; the application Edit menu's
        Undo / Redo actions route through this group so a single
        Ctrl+Z reaches the most recently mutated stack.
        """
        return self._undo_group

    @property
    def current_bundle_path(self) -> Path | None:
        """The current project's `.systemdesign/` bundle, or `None`.

        Mutated by S2.G.2 Save / Open actions. Initial state is
        `None` (Untitled project).
        """
        return self._current_bundle_path

    # ------------------------------------------------------------------ #
    # Menu / status / title wiring
    # ------------------------------------------------------------------ #

    def _build_edit_menu(self) -> None:
        """Construct the Edit menu, routing Undo / Redo through a QUndoGroup.

        PD1 from the S2.D pre-scan locked Qt's native `QUndoGroup`
        as the dispatch mechanism: each feature owns its own
        `QUndoStack`, but the menu actions auto-route to whichever
        stack is currently active. The active stack tracks the
        most recently mutated one — `indexChanged` from a push
        / undo / redo on either stack flips the active pointer
        before the menu sees the next user gesture.

        This preserves the per-feature architectural separation
        (no shared stack, no cross-feature imports) while giving
        the user a single Ctrl+Z timeline.
        """
        self._undo_group: QUndoGroup = QUndoGroup(self)
        workspace_qstack = self._command_stack.stack
        config_qstack = self._configuration_command_stack.stack
        self._undo_group.addStack(workspace_qstack)
        self._undo_group.addStack(config_qstack)

        # Track the most-recently-mutated stack as active. Every
        # push / undo / redo fires `indexChanged` on its stack;
        # the slot makes that stack the group's active one so the
        # menu actions reach it on the user's next Ctrl+Z. Edge
        # case the user accepted on the S2.G.1 pre-scan: when the
        # active stack runs out of undo, Ctrl+Z is disabled until
        # the user touches the other stack — Phase-1 acceptable;
        # focus-based switching is a Phase-2 polish item.
        workspace_qstack.indexChanged.connect(
            lambda _: self._undo_group.setActiveStack(workspace_qstack)
        )
        config_qstack.indexChanged.connect(lambda _: self._undo_group.setActiveStack(config_qstack))

        menu_bar = self.menuBar()
        edit_menu = menu_bar.addMenu("&Edit")
        undo_action = self._undo_group.createUndoAction(self, "&Undo")
        undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        edit_menu.addAction(undo_action)
        redo_action = self._undo_group.createRedoAction(self, "&Redo")
        redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        edit_menu.addAction(redo_action)
        self._undo_action = undo_action
        self._redo_action = redo_action

        # Default active stack on bootstrap: workspace. The most
        # likely first user action is dropping a component, which
        # would set the active stack anyway — this default just
        # makes Ctrl+Z route somewhere sensible if the user
        # invokes it before any push (where it will be a no-op
        # because the workspace stack is empty).
        self._undo_group.setActiveStack(workspace_qstack)

    def _wire_status_bar_signals(self) -> None:
        """Subscribe the status bar to model events for live feedback.

        Phase-1 sources:

        * `validationChanged(report)` — translate into a
          "N errors, M warnings" summary or the first issue's
          message, depending on report contents.
        * `componentAdded`, `componentRemoved`,
          `connectionAdded`, `connectionRemoved` — show transient
          confirmation messages so a user dropping a component
          gets the "Component X added" feedback `02 §32.2` calls
          for.
        """
        self._model.validationChanged.connect(self._on_validation_changed)
        self._model.componentAdded.connect(self._on_component_added_status)
        self._model.componentRemoved.connect(self._on_component_removed_status)
        self._model.connectionAdded.connect(self._on_connection_added_status)
        self._model.connectionRemoved.connect(self._on_connection_removed_status)
        # S1.10.1 — visible feedback for validator-rejected
        # connection attempts. Without this binding a cross-domain
        # or duplicate connection drop produces no UI response
        # (the scene logs a warning and swallows the exception).
        self._scene.connectionRejected.connect(self._on_connection_rejected)

    def _wire_window_title(self) -> None:
        """Wire both models' `dirtyChanged` signals to the title refresher.

        Per the SI4 pre-scan decision: title combines the project
        name (or `_UNTITLED_PROJECT_NAME` when no bundle is set)
        with a `*` dirty marker whenever EITHER model is dirty.
        OR'ing the two flags at refresh time is simpler than a
        computed property and matches WorkspaceModel's existing
        title pattern.
        """
        self._model.dirtyChanged.connect(self._on_dirty_changed)
        self._configuration_model.dirtyChanged.connect(self._on_dirty_changed)
        # Initial title render so the bootstrap window doesn't
        # show the stub from `__init__`'s `setWindowTitle` call
        # while the project is empty.
        self._update_window_title()

    # ------------------------------------------------------------------ #
    # Slots
    # ------------------------------------------------------------------ #

    def _on_validation_changed(self, report: ValidationReport) -> None:
        """Render the validation summary in the status bar."""
        errors = len(report.by_severity("error"))
        warnings = len(report.by_severity("warning"))
        if errors == 0 and warnings == 0:
            self.statusBar().showMessage(
                "Validation: OK",
                _STATUS_TRANSIENT_MS,
            )
            return
        summary_parts = []
        if errors:
            summary_parts.append(f"{errors} error{'s' if errors != 1 else ''}")
        if warnings:
            summary_parts.append(f"{warnings} warning{'s' if warnings != 1 else ''}")
        summary = ", ".join(summary_parts)
        # First-error message helps the user understand WHY:
        first_error = (
            report.by_severity("error")[0].message
            if errors
            else report.by_severity("warning")[0].message
        )
        message = f"Validation: {summary} — {first_error}"
        # Errors are persistent per `02 §32.2`; warnings transient.
        timeout = _STATUS_PERSISTENT_MS if errors else _STATUS_TRANSIENT_MS
        self.statusBar().showMessage(message, timeout)

    def _on_component_added_status(self, component_id: str) -> None:
        """Show a transient "Component added" status message."""
        instance = self._model.components.get(component_id)
        if instance is None:
            return
        label = instance.display_name or instance.id
        self.statusBar().showMessage(
            f"Component {label!r} added",
            _STATUS_TRANSIENT_MS,
        )

    def _on_component_removed_status(self, component_id: str) -> None:
        """Show a transient "Component removed" status message."""
        self.statusBar().showMessage(
            f"Component {component_id!r} removed",
            _STATUS_TRANSIENT_MS,
        )

    def _on_connection_added_status(self, connection_id: str) -> None:
        """Show a transient "Connection added" status message."""
        self.statusBar().showMessage(
            f"Connection {connection_id!r} added",
            _STATUS_TRANSIENT_MS,
        )

    def _on_connection_removed_status(self, connection_id: str) -> None:
        """Show a transient "Connection removed" status message."""
        self.statusBar().showMessage(
            f"Connection {connection_id!r} removed",
            _STATUS_TRANSIENT_MS,
        )

    def _on_connection_rejected(self, report: ValidationReport) -> None:
        """Render a persistent rejection message in the status bar.

        Shows the first error-severity issue's message. The full
        report travels with the signal so a future S1.11 polish
        pass can swap this slot for a multi-line or modal display
        without touching the scene-side emit.
        """
        errors = report.by_severity("error")
        if not errors:
            return
        first = errors[0]
        self.statusBar().showMessage(
            f"Connection rejected: {first.message}",
            _STATUS_PERSISTENT_MS,
        )

    def _on_dirty_changed(self, _is_dirty: bool) -> None:
        """Refresh the window title.

        Both models call this slot; the per-emission boolean is
        ignored in favor of an OR over the two `is_dirty`
        properties — that way we don't have to remember which
        side fired most recently to compute the marker.
        """
        self._update_window_title()

    def _update_window_title(self) -> None:
        """Compose `'<project-name>[ *] — System Designer'` and apply it.

        Helper isolates title formatting from the dirty-signal slot
        so the file-action slots in S2.G.2 (Save As, Open, New)
        can call this directly after mutating
        `_current_bundle_path` without depending on a signal
        emission to refresh the title.
        """
        is_dirty = self._model.is_dirty or self._configuration_model.is_dirty
        if self._current_bundle_path is None:
            project_name = _UNTITLED_PROJECT_NAME
        else:
            # `.stem` strips the `.systemdesign` suffix so the
            # title shows "quarter_car" rather than
            # "quarter_car.systemdesign".
            project_name = self._current_bundle_path.stem
        dirty_marker = " *" if is_dirty else ""
        self.setWindowTitle(f"{project_name}{dirty_marker} — System Designer")


__all__ = ["SystemDesignerShell"]
