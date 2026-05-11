"""AddConnectionCommand: undoable connection addition with pre-mutation validation.

Per ADR-005 and spec/07 §7.11 / §7.12. Hybrid validation strategy
(decision C from the S1.7.4 planning thread):

* `error`-severity issues from `GraphValidator` block the command:
  `__init__` raises `ConnectionValidationError` (a `ValueError`
  subclass) carrying the full `ValidationReport`. The command never
  lands on the undo stack — `QUndoStack` does not unwind a failed
  push gracefully.
* `warning`-severity issues do not block the command. They are
  captured as `command.warnings: tuple[ValidationIssue, ...]` so
  the UI (S1.9) can surface non-blocking diagnostics next to the
  successful edit.

Per the planning thread, validation runs **once** in `__init__`.
`redo()` does not re-validate after an undo: command-stack edits
are linear, so the state at construction is the state that gets
mutated, and re-running validation on every redo would block
legitimate undo→redo cycles when concurrent edits (e.g., adding a
component that the connection references) intervene.

Identity stability: the command captures the full `Connection`
record on first redo (with its minted `con_<ULID>` id) and re-
inserts it via `WorkspaceModel.restore_connection` (S1.7.3) on
subsequent redos. Undo removes the connection by id.

References:
----------
* `decisions/ADR-002-hybrid-ulid-identity-model.md`
* `decisions/ADR-005-command-stack-qundostack.md`
* `specs/02_workspace_requirements.md` §14 (Connection System),
  §20.5 (Validation Severity)
* `specs/07_implementation_order.md` §7.11 (Validation Strategy),
  §7.12 (Command System)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from features.SystemModelingModule.model.graph_validator import GraphValidator

from .workspace_command_stack import WorkspaceCommand

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from features.SystemModelingModule.model.connection import (
        Connection,
        ConnectionRouting,
        PortRef,
    )
    from features.SystemModelingModule.model.validation_report import (
        ValidationIssue,
        ValidationReport,
    )
    from features.SystemModelingModule.model.workspace_model import WorkspaceModel


class ConnectionValidationError(ValueError):
    """Raised when `AddConnectionCommand` pre-validation finds error-severity issues.

    Inherits from `ValueError` so existing `except ValueError`
    handlers (e.g., generic command-construction error paths)
    catch it. Callers that want granular handling can use
    `except ConnectionValidationError` and inspect the
    `report` attribute for the full `ValidationReport` —
    severity-filtered issues, error codes, subject ids.

    The message embeds the count and the first error's text for
    log readability; the structured detail is on `.report`.
    """

    def __init__(self, report: ValidationReport) -> None:
        """Build the exception from a blocking `ValidationReport`."""
        errors = report.by_severity("error")
        if errors:
            head = errors[0]
            message = (
                f"connection rejected by validator "
                f"({len(errors)} error(s); first: {head.code} — {head.message})"
            )
        else:
            # Defensive: callers should not construct this exception
            # without error-severity issues, but the path exists.
            message = "connection validation failed (no error-severity issues found)"
        super().__init__(message)
        self.report = report


def _make_port_lookup(model: WorkspaceModel) -> Callable[[PortRef], str | None]:
    """Build a `port_lookup` closure for `GraphValidator`.

    Per `02 §13` a port's domain is declared on the
    `ComponentDefinition` it belongs to; resolving a `PortRef` to
    a domain string requires both the component instance
    (`definition_id` lookup) and the registry (definition →
    `PortDefinition.domain` lookup). When the registry is not
    wired or the component / port is missing, the lookup returns
    `None` — the validator interprets `None` as "missing port" or
    "missing component" per `02 §20.1`.

    The closure captures the model reference rather than a
    snapshot: it is called only during `__init__` of
    `AddConnectionCommand`, which is synchronous, so any read of
    `model.components` / `model.registry` reflects the same
    consistent state.
    """
    registry = model.registry
    components = model.components

    def lookup(ref: PortRef) -> str | None:
        component = components.get(ref.component_id)
        if component is None or registry is None:
            return None
        if not registry.has(component.definition_id):
            return None
        definition = registry.get(component.definition_id)
        for port in definition.ports:
            if port.id == ref.port_id:
                return port.domain
        return None

    return lookup


class AddConnectionCommand(WorkspaceCommand):
    """Undoable connection addition with `GraphValidator` pre-mutation check.

    Args:
        model: Target `WorkspaceModel`. Should have a registry
            wired so the port-domain lookup can resolve ports.
            Without a registry the validator treats every port as
            "missing", which surfaces as error-severity issues
            and blocks the command.
        source: Source endpoint `PortRef`.
        target: Target endpoint `PortRef`.
        routing: Optional `ConnectionRouting`. Defaults to a
            fresh empty routing record at the model layer.
        label: Optional connection label.
        style: Optional style mapping.

    Raises:
        ConnectionValidationError: pre-validation found
            error-severity issues. The `report` attribute carries
            the full `ValidationReport`.

    See Also:
        `WorkspaceModel.add_connection`,
        `WorkspaceModel.restore_connection` (S1.7.3),
        `GraphValidator.validate_connection_candidate` (S1.4).
    """

    def __init__(
        self,
        model: WorkspaceModel,
        source: PortRef,
        target: PortRef,
        *,
        routing: ConnectionRouting | None = None,
        label: str = "",
        style: Mapping[str, Any] | None = None,
    ) -> None:
        """Construct, pre-validate, and capture warnings."""
        validator = GraphValidator()
        report = validator.validate_connection_candidate(
            source=source,
            target=target,
            existing_connections=model.connections.values(),
            components=model.components,
            port_lookup=_make_port_lookup(model),
        )
        if report.has_errors:
            raise ConnectionValidationError(report)
        # Warning-severity issues do not block; expose them on the
        # command so the UI can surface non-blocking diagnostics.
        # `by_severity` already returns a frozen tuple — store as-is
        # per the S1.7.4 planning thread (immutability inherited
        # from the S1.3 frozen-dataclass conventions).
        self._warnings: tuple[ValidationIssue, ...] = report.by_severity("warning")

        super().__init__(model, "Add connection")
        self._source = source
        self._target = target
        self._routing = routing
        self._label = label
        # Defensive copy of the style mapping (the caller's mapping
        # is captured at construction time so subsequent mutation
        # does not affect re-redos).
        self._style: dict[str, Any] | None = dict(style) if style is not None else None
        # Captured Connection on first redo; None until then.
        self._captured_connection: Connection | None = None

    @property
    def warnings(self) -> tuple[ValidationIssue, ...]:
        """Warning-severity validation issues found at construction.

        Returns an empty tuple when the candidate was clean. UI
        code (S1.9) can render these next to the successful edit
        per spec/07 §7.11.
        """
        return self._warnings

    @property
    def connection_id(self) -> str | None:
        """The minted connection id, or None if `redo()` has not run."""
        return self._captured_connection.id if self._captured_connection is not None else None

    def redo(self) -> None:
        """Add the connection on first execution; restore on subsequent ones.

        Per the S1.7.4 planning thread, this method does NOT
        re-validate the candidate. Validation ran once at
        construction time; the captured-state path on subsequent
        redos restores the original `Connection` verbatim with
        its `con_<ULID>` id.
        """
        if self._captured_connection is None:
            new_id = self._model.add_connection(
                source=self._source,
                target=self._target,
                routing=self._routing,
                label=self._label,
                style=self._style,
            )
            self._captured_connection = self._model.connections[new_id]
        else:
            self._model.restore_connection(self._captured_connection)

    def undo(self) -> None:
        """Remove the previously-added connection."""
        if self._captured_connection is None:
            return
        self._model.remove_connection(self._captured_connection.id)


__all__ = ["AddConnectionCommand", "ConnectionValidationError"]
