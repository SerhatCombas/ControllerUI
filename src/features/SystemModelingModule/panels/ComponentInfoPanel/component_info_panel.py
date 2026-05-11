"""ComponentInfoPanel: parameter editor for the current selection.

Per spec/07 §7.13 and `02 §28`. The panel is the bottom-of-
window properties view: it shows the display name, definition
id, and parameter editors for the single currently-selected
`ComponentGraphicsItem` (or a placeholder when nothing / many
things are selected).

Parameter edits commit through the command stack via
`ChangeParameterCommand` (S1.7.2), so every edit is undoable
and routes through the same model-canonical path as project
load and copy/paste. The panel also subscribes to
`model.componentChanged` so external edits (undo / redo, a
different panel, a script) reflect back into its widgets
without manual refresh.

Re-entrancy guard: when the panel programmatically updates a
widget value in response to `componentChanged`, the widget's
own valueChanged / editingFinished signal fires. Without
suppression that would push a redundant `ChangeParameterCommand`
back through the stack. The `_updating_widgets` flag short-
circuits this re-entry.

Editor selection by `ParameterType` (`01 §6`):

* `float`  → `QDoubleSpinBox` (range from definition's
  `min`/`max`, falls back to ±1e9)
* `int`    → `QSpinBox` (range similarly)
* `bool`   → `QCheckBox`
* `enum`   → `QComboBox` populated from `allowed_values`
* `string`, `expression` → `QLineEdit`

References:
----------
* `decisions/ADR-003-workspace-ui-data-separation.md`
* `decisions/ADR-005-command-stack-qundostack.md`
* `specs/02_workspace_requirements.md` §28 (Component Info Panel),
  §11 (Component Data Model)
* `specs/07_implementation_order.md` §7.13
"""

from __future__ import annotations

import contextlib
import logging
from typing import TYPE_CHECKING, Any

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from features.SystemModelingModule.commands import ChangeParameterCommand
from features.SystemModelingModule.workspace.BlockDiagramWorkspace.component_graphics_item import (
    ComponentGraphicsItem,
)

if TYPE_CHECKING:
    from features.SystemModelingModule.commands import WorkspaceCommandStack
    from features.SystemModelingModule.model.component_instance import (
        ComponentInstance,
    )
    from features.SystemModelingModule.model.workspace_model import WorkspaceModel
    from features.SystemModelingModule.workspace.BlockDiagramWorkspace.workspace_scene import (
        WorkspaceScene,
    )
    from shared.registry import ParameterDefinition


logger = logging.getLogger(__name__)

_EMPTY_PLACEHOLDER: str = "No selection"
_SPINBOX_FALLBACK_RANGE: float = 1.0e9
_INT_SPINBOX_FALLBACK_RANGE: int = 1_000_000_000


class ComponentInfoPanel(QWidget):
    """Parameter editor for the current single-component selection.

    Args:
        model: The `WorkspaceModel` to read instance state and
            push parameter edits through.
        scene: The `WorkspaceScene` whose `selectionChanged`
            signal drives the panel's contents.
        command_stack: Optional `WorkspaceCommandStack`. When
            `None`, parameter widgets render and display values
            but edits do not push commands (the panel logs a
            warning on the first attempted edit). UI bootstraps
            wire a real stack; tests can omit it to exercise
            display-only paths.
        parent: Optional Qt parent.
    """

    def __init__(
        self,
        model: WorkspaceModel,
        scene: WorkspaceScene,
        command_stack: WorkspaceCommandStack | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Construct the widget tree and subscribe to model + scene signals."""
        super().__init__(parent)
        self._model = model
        self._scene = scene
        self._command_stack = command_stack
        # State: which component_id (if any) the panel currently
        # mirrors. `None` for empty / multi-select states.
        self._current_component_id: str | None = None
        # param_id → widget mapping for re-render and re-entrancy
        # guard. Cleared and re-populated each selection.
        self._param_editors: dict[str, QWidget] = {}
        # Re-entrancy guard for programmatic widget updates.
        self._updating_widgets: bool = False

        # ----------------------------- Widget tree ----------------------------- #
        self._layout = QVBoxLayout(self)
        self._title_label = QLabel()
        self._title_label.setObjectName("ComponentInfoPanelTitle")
        self._empty_label = QLabel(_EMPTY_PLACEHOLDER)
        self._empty_label.setObjectName("ComponentInfoPanelEmpty")
        self._multi_label = QLabel()
        self._multi_label.setObjectName("ComponentInfoPanelMulti")
        # The params container groups the form so we can clear
        # and rebuild as the selection changes.
        self._params_container = QWidget()
        self._params_form = QFormLayout(self._params_container)
        self._layout.addWidget(self._title_label)
        self._layout.addWidget(self._empty_label)
        self._layout.addWidget(self._multi_label)
        self._layout.addWidget(self._params_container)
        self._layout.addStretch()

        # ----------------------------- Initial state --------------------------- #
        self._show_empty()

        # ----------------------------- Signal wiring --------------------------- #
        scene.selectionChanged.connect(self._on_scene_selection_changed)
        model.componentChanged.connect(self._on_model_component_changed)
        model.componentRemoved.connect(self._on_model_component_removed)

    # ------------------------------------------------------------------ #
    # Public read-only accessors (test convenience)
    # ------------------------------------------------------------------ #

    @property
    def current_component_id(self) -> str | None:
        """The component_id the panel currently mirrors, or `None`."""
        return self._current_component_id

    @property
    def parameter_editors(self) -> dict[str, QWidget]:
        """Snapshot of the param_id → editor widget mapping."""
        return dict(self._param_editors)

    # ------------------------------------------------------------------ #
    # Display-state transitions
    # ------------------------------------------------------------------ #

    def _show_empty(self) -> None:
        """No selection — placeholder text, no parameter rows."""
        self._current_component_id = None
        self._clear_params()
        self._title_label.setVisible(False)
        self._multi_label.setVisible(False)
        self._empty_label.setVisible(True)
        self._params_container.setVisible(False)

    def _show_multi(self, count: int) -> None:
        """Multiple components selected — show count placeholder."""
        self._current_component_id = None
        self._clear_params()
        self._title_label.setVisible(False)
        self._empty_label.setVisible(False)
        self._multi_label.setText(f"{count} components selected")
        self._multi_label.setVisible(True)
        self._params_container.setVisible(False)

    def _show_single(self, component_id: str) -> None:
        """Single component selected — show header + parameter editors."""
        instance = self._model.components.get(component_id)
        if instance is None:
            self._show_empty()
            return
        self._current_component_id = component_id
        self._title_label.setText(instance.display_name or instance.id)
        self._title_label.setVisible(True)
        self._empty_label.setVisible(False)
        self._multi_label.setVisible(False)
        self._build_param_editors(instance)
        self._params_container.setVisible(True)

    def _clear_params(self) -> None:
        """Remove every row from the params form and clear the editor dict."""
        while self._params_form.rowCount() > 0:
            self._params_form.removeRow(0)
        self._param_editors.clear()

    def _build_param_editors(self, instance: ComponentInstance) -> None:
        """Mint one row per parameter in the registered definition."""
        self._clear_params()
        registry = self._model.registry
        if registry is None or not registry.has(instance.definition_id):
            return
        definition = registry.get(instance.definition_id)
        for param_def in definition.parameters:
            editor = self._build_one_editor(param_def, instance)
            if editor is None:
                continue
            self._param_editors[param_def.id] = editor
            self._params_form.addRow(param_def.display_name, editor)

    def _build_one_editor(
        self,
        param_def: ParameterDefinition,
        instance: ComponentInstance,
    ) -> QWidget | None:
        """Build a type-appropriate editor widget for one parameter."""
        # Resolve the current value from the instance, falling
        # back to the definition default when the instance has
        # not yet set this parameter (the "use defaults at
        # runtime" semantic from `02 §11.3`).
        current_value = instance.parameters.get(param_def.id, param_def.default)
        param_id = param_def.id

        if param_def.type == "float":
            spin = QDoubleSpinBox()
            spin.setDecimals(6)
            min_val = (
                float(param_def.min) if param_def.min is not None else -_SPINBOX_FALLBACK_RANGE
            )
            max_val = float(param_def.max) if param_def.max is not None else _SPINBOX_FALLBACK_RANGE
            spin.setRange(min_val, max_val)
            try:
                spin.setValue(float(current_value))
            except (TypeError, ValueError):
                spin.setValue(0.0)
            spin.editingFinished.connect(
                lambda pid=param_id, s=spin: self._on_param_edit(pid, s.value())
            )
            return spin

        if param_def.type == "int":
            ispin = QSpinBox()
            min_int = (
                int(param_def.min) if param_def.min is not None else -_INT_SPINBOX_FALLBACK_RANGE
            )
            max_int = (
                int(param_def.max) if param_def.max is not None else _INT_SPINBOX_FALLBACK_RANGE
            )
            ispin.setRange(min_int, max_int)
            try:
                ispin.setValue(int(current_value))
            except (TypeError, ValueError):
                ispin.setValue(0)
            ispin.editingFinished.connect(
                lambda pid=param_id, s=ispin: self._on_param_edit(pid, s.value())
            )
            return ispin

        if param_def.type == "bool":
            check = QCheckBox()
            check.setChecked(bool(current_value))
            check.toggled.connect(lambda checked, pid=param_id: self._on_param_edit(pid, checked))
            return check

        if param_def.type == "enum":
            combo = QComboBox()
            for allowed in param_def.allowed_values or ():
                combo.addItem(allowed)
            combo.setCurrentText(str(current_value))
            combo.currentTextChanged.connect(
                lambda text, pid=param_id: self._on_param_edit(pid, text)
            )
            return combo

        # string, expression — both render as a free-form line edit
        # in Phase 1.
        line = QLineEdit()
        line.setText(str(current_value))
        line.editingFinished.connect(
            lambda pid=param_id, e=line: self._on_param_edit(pid, e.text())
        )
        return line

    # ------------------------------------------------------------------ #
    # Signal handlers
    # ------------------------------------------------------------------ #

    def _on_scene_selection_changed(self) -> None:
        """Update the panel from the scene's current selection.

        Defensive `try/except RuntimeError` handles the
        PySide6 teardown race where the scene's underlying C++
        object is destroyed while this slot is still connected
        (e.g., closing a project while the panel is alive). In
        that case there's nothing to display — fall through.
        """
        try:
            selected = self._scene.selectedItems()
        except RuntimeError:
            return
        items = [item for item in selected if isinstance(item, ComponentGraphicsItem)]
        if not items:
            self._show_empty()
        elif len(items) == 1:
            self._show_single(items[0].component_id)
        else:
            self._show_multi(len(items))

    def _on_model_component_changed(self, component_id: str) -> None:
        """Refresh widget values when the model fires `componentChanged`.

        Suppressed via `_updating_widgets` so the value-set
        triggers do not re-enter `_on_param_edit`. Only refreshes
        when the changed component matches the currently-displayed
        one — other components' edits are irrelevant.
        """
        if component_id != self._current_component_id:
            return
        instance = self._model.components.get(component_id)
        if instance is None:
            return
        self._updating_widgets = True
        try:
            for param_id, editor in self._param_editors.items():
                value = instance.parameters.get(param_id)
                if value is None:
                    continue
                self._refresh_editor_value(editor, value)
        finally:
            self._updating_widgets = False

    def _refresh_editor_value(self, editor: QWidget, value: Any) -> None:
        """Write `value` into `editor` using the type-appropriate setter."""
        if isinstance(editor, QDoubleSpinBox):
            with contextlib.suppress(TypeError, ValueError):
                editor.setValue(float(value))
        elif isinstance(editor, QSpinBox):
            with contextlib.suppress(TypeError, ValueError):
                editor.setValue(int(value))
        elif isinstance(editor, QCheckBox):
            editor.setChecked(bool(value))
        elif isinstance(editor, QComboBox):
            editor.setCurrentText(str(value))
        elif isinstance(editor, QLineEdit):
            editor.setText(str(value))

    def _on_model_component_removed(self, component_id: str) -> None:
        """If the displayed component was removed, reset to empty state."""
        if component_id == self._current_component_id:
            self._show_empty()

    def _on_param_edit(self, param_name: str, new_value: Any) -> None:
        """Push a `ChangeParameterCommand` for a user-initiated edit.

        Re-entrancy guard: skip when the panel is programmatically
        updating widgets in response to `componentChanged`.
        """
        if self._updating_widgets:
            return
        if self._current_component_id is None:
            return
        if self._command_stack is None:
            logger.warning("ComponentInfoPanel: parameter edit ignored — no command_stack wired")
            return
        if self._current_component_id not in self._model.components:
            return
        command = ChangeParameterCommand(
            self._model, self._current_component_id, param_name, new_value
        )
        self._command_stack.push(command)


__all__ = ["ComponentInfoPanel"]
