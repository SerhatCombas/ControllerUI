"""AddComponentCommand: undo/redo-aware component addition.

Per ADR-005 (command stack) and spec/07 §7.12. Adds a new
component to the workspace via
`WorkspaceModel.add_component_from_definition` (S1.B.1d) and
captures the resulting `ComponentInstance` on first redo so that
undo → redo cycles preserve the original `cmp_<ULID>` id (`02 §8`,
ADR-002).

Identity-stability protocol:

1. **First `redo()`** — calls
   `model.add_component_from_definition(...)`, captures the
   resulting `ComponentInstance` (frozen dataclass with the minted
   id) into `self._captured_instance`.
2. **`undo()`** — calls `model.remove_component(self._captured_instance.id)`.
3. **Subsequent `redo()`** — calls
   `model.restore_component(self._captured_instance)` so the
   component is re-inserted verbatim with its original id.

The frozen-dataclass capture is safe to keep across the undo/redo
cycle: `ComponentInstance` is immutable, so the stored reference
cannot be mutated by other code paths in the meantime.

Registry requirement: the bound model MUST have a
`ComponentRegistry` wired at construction time (otherwise
`add_component_from_definition` raises `RuntimeError`).
`__init__` pre-validates this so a failing command never lands on
the undo stack in a half-broken state.

References:
----------
* `decisions/ADR-002-hybrid-ulid-identity-model.md` (id stability)
* `decisions/ADR-005-command-stack-qundostack.md`
* `decisions/ADR-021-builtin-component-definitions.md`
* `specs/02_workspace_requirements.md` §8, §25
* `specs/07_implementation_order.md` §7.12
* `specs/09_coding_standards.md` §7.2.4
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .workspace_command_stack import WorkspaceCommand

if TYPE_CHECKING:
    from collections.abc import Mapping

    from PySide6.QtCore import QPointF

    from features.SystemModelingModule.model.component_instance import (
        ComponentInstance,
    )
    from features.SystemModelingModule.model.workspace_model import WorkspaceModel


class AddComponentCommand(WorkspaceCommand):
    """Undoable component addition from a `ComponentDefinition`.

    Args:
        model: Target `WorkspaceModel`. MUST have a registry wired
            at construction time.
        definition_id: Dotted-namespace identifier of a registered
            `ComponentDefinition`.
        position: Scene-coordinate placement.
        custom_label: Optional user-editable instance label.
        rotation: Initial rotation in degrees. Phase 1 rule
            restricts the value to `{0.0, 90.0, 180.0, 270.0}` per
            `02 §22` / ADR-018; off-grid values raise `ValueError`
            from the underlying model call. Pre-validation in
            `__init__` would duplicate that check; the constructor
            instead lets the first `redo()` raise — which Qt's
            `QUndoStack.push` propagates synchronously before
            stacking the command, so the stack stays consistent.

            (Actually pre-validating is cleaner because Qt's
            QUndoStack does not unwind a failed push completely;
            see implementation notes below.)
        parameters: Optional explicit parameter overrides at
            placement time (project-load / copy-paste flows).

    Raises:
        RuntimeError: `model.registry is None`.
        KeyError: `definition_id` not registered.

    See Also:
        `WorkspaceModel.add_component_from_definition` (S1.B.1d),
        `WorkspaceModel.restore_component` (S1.7.1).
    """

    def __init__(
        self,
        model: WorkspaceModel,
        definition_id: str,
        position: QPointF,
        *,
        custom_label: str = "",
        rotation: float = 0.0,
        parameters: Mapping[str, Any] | None = None,
    ) -> None:
        """Construct and pre-validate the command."""
        # Validate registry availability and definition_id BEFORE
        # constructing the QUndoCommand base. A command that fails
        # validation must not land on the undo stack — pre-checking
        # here lets the caller catch the error before push().
        if model.registry is None:
            raise RuntimeError(
                "AddComponentCommand requires a registry-wired WorkspaceModel; "
                "construct WorkspaceModel(registry=...)."
            )
        definition = model.registry.get(definition_id)
        super().__init__(model, f"Add {definition.display_name}")
        self._definition_id = definition_id
        self._position = position
        self._custom_label = custom_label
        self._rotation = rotation
        # Defensive copy: the caller's mapping is captured at
        # construction time so subsequent mutation by the caller
        # does not affect re-redos.
        self._parameters: dict[str, Any] | None = (
            dict(parameters) if parameters is not None else None
        )
        # Set on first redo; None until then.
        self._captured_instance: ComponentInstance | None = None

    @property
    def component_id(self) -> str | None:
        """The minted instance id, or None if `redo()` has not run yet.

        Test convenience: after `stack.push(command)` returns this
        is the id of the new component; useful for following-up
        with `model.components[component_id]` lookups.
        """
        return self._captured_instance.id if self._captured_instance is not None else None

    def redo(self) -> None:
        """Apply or re-apply the addition.

        First execution mints the component (id, timestamps, etc.);
        subsequent executions after undo restore the captured
        instance verbatim so identity is preserved across the
        undo/redo cycle (ADR-002, `02 §8`).
        """
        if self._captured_instance is None:
            new_id = self._model.add_component_from_definition(
                self._definition_id,
                self._position,
                custom_label=self._custom_label,
                rotation=self._rotation,
                parameters=self._parameters,
            )
            self._captured_instance = self._model.components[new_id]
        else:
            self._model.restore_component(self._captured_instance)

    def undo(self) -> None:
        """Remove the previously-added component.

        Defensively no-ops when `redo()` has never run (which
        `QUndoStack` should not allow under normal use). The
        captured instance is retained so a subsequent `redo()`
        re-inserts it.
        """
        if self._captured_instance is None:
            return
        self._model.remove_component(self._captured_instance.id)


__all__ = ["AddComponentCommand"]
