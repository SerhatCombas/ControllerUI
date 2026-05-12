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
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import QStandardPaths
from PySide6.QtGui import QKeySequence, QUndoGroup
from PySide6.QtWidgets import QDockWidget, QFileDialog, QMainWindow, QMessageBox

from application.persistence import (
    ProjectFormatError,
    load_project,
    save_project,
)
from features.ControllerDesignModule.commands import ConfigurationCommandStack
from features.ControllerDesignModule.model import (
    ConfigurationModel,
    ControllerSettings,
    IOSelection,
    PlotLayout,
    SimulationSettings,
    load_default_configuration,
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

        # 10b. File menu (New / Open / Save / Save As — S2.G.2).
        self._build_file_menu()

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

    def _build_file_menu(self) -> None:
        """Construct the File menu (New / Open / Save / Save As — S2.G.2).

        Action shortcuts use the Qt standard-key family so they
        adapt to the platform conventions (Cmd+N on macOS,
        Ctrl+N on Windows / Linux, etc.). Save's shortcut belongs
        to `Save`, not `Save As`; `Save As` ships with no shortcut
        per Phase-1 minimalism (Cmd+Shift+S on macOS lands in
        S1.11 polish if requested).
        """
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("&File")

        new_action = file_menu.addAction("&New Project")
        new_action.setShortcut(QKeySequence.StandardKey.New)
        new_action.triggered.connect(self._on_new_project)

        open_action = file_menu.addAction("&Open Project...")
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self._on_open_project)

        file_menu.addSeparator()

        save_action = file_menu.addAction("&Save")
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self._on_save_project)

        save_as_action = file_menu.addAction("Save &As...")
        save_as_action.setShortcut(QKeySequence.StandardKey.SaveAs)
        save_as_action.triggered.connect(self._on_save_project_as)

        self._new_action = new_action
        self._open_action = open_action
        self._save_action = save_action
        self._save_as_action = save_as_action

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

    # ------------------------------------------------------------------ #
    # File menu slots (S2.G.2)
    # ------------------------------------------------------------------ #

    def _on_new_project(self) -> None:
        """File → New: reset both models to Phase-1 defaults.

        Honors the unsaved-changes flow per SI2: if either model
        is dirty, prompt with Discard / Save / Cancel before
        applying defaults. The reset itself loads
        `default_config.json` via `load_default_configuration()`
        so the user sees the Phase-1 starting state, not an
        empty configuration.
        """
        if not self._confirm_discard_or_save_if_dirty():
            return
        self._reset_to_defaults()
        self._current_bundle_path = None
        self._update_window_title()
        self.statusBar().showMessage("New project", _STATUS_TRANSIENT_MS)

    def _on_open_project(self) -> None:
        """File → Open: pick a `.systemdesign/` directory and load it."""
        if not self._confirm_discard_or_save_if_dirty():
            return
        path_str, _ = QFileDialog.getOpenFileName(
            self,
            "Open Project",
            self._default_dialog_directory(),
            f"System Designer Bundle (*{_BUNDLE_SUFFIX})",
        )
        if not path_str:
            return  # user cancelled
        self.load_project_from(Path(path_str))

    def _on_save_project(self) -> None:
        """File → Save: write to `_current_bundle_path`, or fall through to Save As.

        Returns silently after a successful save; failures are
        surfaced via `QMessageBox.critical` and the dirty bit is
        deliberately left set (the save did not happen, so the
        user's mental "I edited; I haven't saved" is still
        accurate).
        """
        if self._current_bundle_path is None:
            self._on_save_project_as()
            return
        self.save_current_project()

    def _on_save_project_as(self) -> None:
        """File → Save As: choose a new bundle path and save into it."""
        chosen = self._show_save_as_dialog()
        if chosen is None:
            return  # user cancelled
        # Mutate `_current_bundle_path` BEFORE writing so a save
        # failure leaves the path bound (the user can retry into
        # the same target without re-picking).
        self._current_bundle_path = chosen
        self._update_window_title()
        self.save_current_project()

    # ------------------------------------------------------------------ #
    # File menu helpers — public API (test + smoke harness convenience)
    # ------------------------------------------------------------------ #

    def save_current_project(self) -> bool:
        """Save to `_current_bundle_path`. Returns True on success.

        Wraps `save_project` in a try/except so menu slots and the
        smoke harness share one error UX. On success the spec/02
        §29.7 contract is honored: each command stack's current
        index is marked clean via `setClean()`, which propagates
        through `cleanChanged(True)` into each model's
        `_clear_dirty()`. The undo history itself is preserved —
        only the dirty bit transitions.
        """
        assert self._current_bundle_path is not None
        try:
            save_project(
                self._current_bundle_path,
                workspace_model=self._model,
                configuration_model=self._configuration_model,
            )
        except (OSError, ProjectFormatError) as exc:
            QMessageBox.critical(self, "Save failed", str(exc))
            self.statusBar().showMessage("Save failed", _STATUS_PERSISTENT_MS)
            return False
        # Spec §29.7 + ADR-020 save-clean atomicity: mark each
        # stack's current index as the new clean baseline. Qt
        # emits `cleanChanged(True)` from `setClean()` when the
        # stack was previously dirty; each model's binding then
        # clears its `is_dirty` flag.
        self._command_stack.stack.setClean()
        self._configuration_command_stack.stack.setClean()
        self.statusBar().showMessage(
            f"Saved to {self._current_bundle_path.name}",
            _STATUS_TRANSIENT_MS,
        )
        return True

    def load_project_from(self, bundle_path: Path) -> bool:
        """Load from `bundle_path`. Returns True on success.

        Public method so a smoke harness or future shell-side
        recovery flow can drive the load without going through the
        file dialog. Errors surface as `QMessageBox.critical`.
        """
        try:
            load_project(
                bundle_path,
                workspace_model=self._model,
                configuration_model=self._configuration_model,
            )
        except (
            ProjectFormatError,
            FileNotFoundError,
            KeyError,
            ValueError,
        ) as exc:
            QMessageBox.critical(self, "Open failed", str(exc))
            self.statusBar().showMessage("Open failed", _STATUS_PERSISTENT_MS)
            return False
        self._current_bundle_path = bundle_path
        self._update_window_title()
        self.statusBar().showMessage(
            f"Opened {bundle_path.name}",
            _STATUS_TRANSIENT_MS,
        )
        return True

    # ------------------------------------------------------------------ #
    # File menu helpers — private
    # ------------------------------------------------------------------ #

    def _confirm_discard_or_save_if_dirty(self) -> bool:
        """Run the SI2 unsaved-changes dialog. Returns True if caller may proceed.

        Behavior table:

          - Neither model dirty → return True immediately.
          - User picks Discard → return True (caller resets/loads).
          - User picks Save → run save flow. Returns True iff save
            succeeded; if Save As was cancelled or save failed,
            returns False so the outer action aborts.
          - User picks Cancel → return False.
        """
        if not (self._model.is_dirty or self._configuration_model.is_dirty):
            return True
        choice = QMessageBox.warning(
            self,
            "Unsaved changes",
            "The current project has unsaved changes. "
            "Discard them, save first, or cancel this action?",
            QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if choice == QMessageBox.StandardButton.Discard:
            return True
        if choice == QMessageBox.StandardButton.Cancel:
            return False
        # Save chosen — route through the same logic as Ctrl+S.
        if self._current_bundle_path is None:
            chosen = self._show_save_as_dialog()
            if chosen is None:
                return False  # user cancelled Save As
            self._current_bundle_path = chosen
            self._update_window_title()
        return self.save_current_project()

    def _show_save_as_dialog(self) -> Path | None:
        """Return the chosen bundle path, or `None` on cancel.

        Uses `QFileDialog.getSaveFileName` with a
        `.systemdesign` filter (SI3). Auto-appends the suffix if
        the user omits it.
        """
        path_str, _ = QFileDialog.getSaveFileName(
            self,
            "Save Project As",
            self._default_dialog_directory(),
            f"System Designer Bundle (*{_BUNDLE_SUFFIX})",
        )
        if not path_str:
            return None
        path = Path(path_str)
        if path.suffix != _BUNDLE_SUFFIX:
            path = path.with_suffix(_BUNDLE_SUFFIX)
        return path

    def _default_dialog_directory(self) -> str:
        """Return the cross-platform Documents folder for save / open dialogs.

        `QStandardPaths.DocumentsLocation` resolves to
        `~/Documents` on macOS / Linux and `%USERPROFILE%/Documents`
        on Windows. Returns an empty string when the OS can't
        provide one (rare; Qt falls back to the CWD in that case).
        """
        return QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)

    def _reset_to_defaults(self) -> None:
        """Replace both models' state with the Phase-1 defaults.

        Used by File → New. The workspace gets an empty payload
        (zero components, zero connections); the configuration
        gets the Phase-1 default sections via
        `load_default_configuration()`.
        """
        self._model.from_dict({"components": [], "connections": []})
        cfg = load_default_configuration()
        self._configuration_model.from_dict(
            {
                "controller_settings": cfg.controller_settings.to_dict(),
                "io_selection": cfg.io_selection.to_dict(),
                "simulation_settings": cfg.simulation_settings.to_dict(),
                "plot_layout": cfg.plot_layout.to_dict(),
            }
        )


__all__ = ["SystemDesignerShell"]
