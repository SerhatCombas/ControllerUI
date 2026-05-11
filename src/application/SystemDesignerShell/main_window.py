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

from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QDockWidget, QMainWindow

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

        # 10. Edit menu (Undo / Redo).
        self._build_edit_menu()

        # 11. Status bar wiring.
        self.statusBar().showMessage("Ready", _STATUS_TRANSIENT_MS)
        self._wire_status_bar_signals()

        # 12. Window title dirty indicator.
        self._wire_window_title_dirty()

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

    # ------------------------------------------------------------------ #
    # Menu / status / title wiring
    # ------------------------------------------------------------------ #

    def _build_edit_menu(self) -> None:
        """Construct the Edit menu with Undo / Redo actions."""
        menu_bar = self.menuBar()
        edit_menu = menu_bar.addMenu("&Edit")
        undo_action = edit_menu.addAction("&Undo")
        undo_action.setShortcut(QKeySequence.StandardKey.Undo)
        undo_action.triggered.connect(self._command_stack.undo)
        redo_action = edit_menu.addAction("&Redo")
        redo_action.setShortcut(QKeySequence.StandardKey.Redo)
        redo_action.triggered.connect(self._command_stack.redo)
        self._undo_action = undo_action
        self._redo_action = redo_action

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

    def _wire_window_title_dirty(self) -> None:
        """Hook `dirtyChanged` so the window title gets a `*` suffix."""
        self._model.dirtyChanged.connect(self._on_dirty_changed)

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

    def _on_dirty_changed(self, is_dirty: bool) -> None:
        """Append/remove the `*` suffix on the window title."""
        base = "Engineering System Designer"
        self.setWindowTitle(f"{base} *" if is_dirty else base)


__all__ = ["SystemDesignerShell"]
