"""WorkspaceValidatorController: debounce-driven workspace validation.

Per spec/07 §7.11 (Validation Strategy) and `02 §20.6`
(Validation Pacing). The controller subscribes to every model
mutation signal and runs `GraphValidator.validate_workspace`
inside a Qt debounce timer so a burst of edits coalesces into
exactly one validation pass.

Design:

* **Debounce window**: default 250 ms — short enough that the
  user perceives feedback as immediate, long enough that a
  multi-frame drag does not trigger N validations.
* **Single-shot timer**: each scheduled mutation restarts the
  timer; the timer fires once at the end of the burst.
* **Synchronous bypass**: `validate_now()` cancels any pending
  schedule and runs validation immediately. Used by save flows
  (S2) and tests.
* **Signal emission**: validation results land on
  `model.validationChanged(report)` — the signal has existed
  since S1.3c.1 but had no producer until this controller.
* **Headless-safe**: `QTimer` lives in `PySide6.QtCore`
  (already permitted by the data-layer arch test). No widget
  imports.

References:
----------
* `decisions/ADR-018-signal-payload-contracts.md`
  (validationChanged payload type)
* `specs/02_workspace_requirements.md` §20.6 (Validation Pacing)
* `specs/07_implementation_order.md` §7.11
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Final

from PySide6.QtCore import QObject, QTimer

from .graph_validator import GraphValidator

if TYPE_CHECKING:
    from .validation_report import ValidationReport
    from .workspace_change_set import WorkspaceChangeSet
    from .workspace_model import WorkspaceModel


logger = logging.getLogger(__name__)

DEFAULT_DEBOUNCE_MS: Final[int] = 250


class WorkspaceValidatorController(QObject):
    """Debounce-driven workspace validation runner.

    Args:
        model: The `WorkspaceModel` to observe and validate.
        validator: Optional `GraphValidator`. Defaults to a
            fresh instance — the validator is stateless in
            Phase 1, so sharing one across controllers is safe
            but not required.
        debounce_ms: Debounce window in milliseconds. Defaults
            to `DEFAULT_DEBOUNCE_MS = 250`. Mutations within
            the window coalesce into one validation run.
        parent: Optional Qt parent (typically the shell or the
            workspace document).

    Lifecycle:

    * The controller subscribes to all 10 model mutation
      signals during `__init__`. Disconnection happens
      automatically when Qt destroys the controller.
    * Validation runs synchronously inside the Qt event loop
      callback — Phase 1 validation is cheap (O(components +
      connections + parameters)) so blocking the loop briefly
      is acceptable. ADR-018 reserves the option to move
      validation to a worker in a later phase without changing
      the public surface.
    """

    def __init__(
        self,
        model: WorkspaceModel,
        validator: GraphValidator | None = None,
        debounce_ms: int = DEFAULT_DEBOUNCE_MS,
        parent: QObject | None = None,
    ) -> None:
        """Construct, install the debounce timer, and wire model signals."""
        super().__init__(parent)
        self._model: WorkspaceModel = model
        self._validator: GraphValidator = validator if validator is not None else GraphValidator()
        self._debounce_ms: int = debounce_ms

        self._timer: QTimer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._run_validation)

        self._connect_model_signals()

    # ------------------------------------------------------------------ #
    # Read-only accessors (test + caller convenience)
    # ------------------------------------------------------------------ #

    @property
    def model(self) -> WorkspaceModel:
        """The bound `WorkspaceModel`."""
        return self._model

    @property
    def debounce_ms(self) -> int:
        """Current debounce window in milliseconds."""
        return self._debounce_ms

    @property
    def is_pending(self) -> bool:
        """True when a validation run is scheduled but not yet fired."""
        return self._timer.isActive()

    # ------------------------------------------------------------------ #
    # Configuration
    # ------------------------------------------------------------------ #

    def set_debounce_ms(self, ms: int) -> None:
        """Update the debounce window for subsequent scheduling.

        A currently-pending timer is NOT rescheduled — it fires
        on its original deadline. Subsequent mutations use the
        new window.

        Args:
            ms: New debounce window in milliseconds. Must be
                non-negative.

        Raises:
            ValueError: `ms` is negative.
        """
        if ms < 0:
            raise ValueError(f"debounce_ms must be non-negative; got {ms}")
        self._debounce_ms = ms

    # ------------------------------------------------------------------ #
    # Validation runners
    # ------------------------------------------------------------------ #

    def validate_now(self) -> ValidationReport:
        """Cancel any pending schedule and run validation immediately.

        Returns the resulting `ValidationReport` so callers
        that want the result synchronously (save flows, tests)
        can use it directly. The report is also emitted via
        `model.validationChanged(report)` for subscribers.
        """
        self._timer.stop()
        return self._run_validation()

    def _run_validation(self) -> ValidationReport:
        """Execute validation and emit `validationChanged`.

        Reads the model's current state, calls
        `validator.validate_workspace`, and emits the resulting
        report on `model.validationChanged`. The model has held
        the signal contract since S1.3c.1; this is the first
        producer.
        """
        report = self._validator.validate_workspace(
            components=self._model.components,
            connections=self._model.connections.values(),
            registry=self._model.registry,
        )
        try:
            self._model.validationChanged.emit(report)
        except RuntimeError:
            # The model's C++ object was destroyed before this
            # callback fired (e.g., teardown race in tests).
            # Log and swallow so the controller stays alive
            # until Qt cleans it up properly.
            logger.debug("validationChanged emission skipped — model already destroyed")
        return report

    # ------------------------------------------------------------------ #
    # Signal wiring
    # ------------------------------------------------------------------ #

    def _connect_model_signals(self) -> None:
        """Subscribe the controller to every mutation signal.

        The controller listens to:

        * componentAdded / componentRemoved / componentChanged
        * componentMoved / componentRotated
        * connectionAdded / connectionRemoved / connectionChanged
        * modelReset
        * modelChanged (batch — fires once on outermost batch
          exit, so a batch maps to exactly one schedule call)
        """
        m = self._model
        m.componentAdded.connect(self._on_simple_signal)
        m.componentRemoved.connect(self._on_simple_signal)
        m.componentChanged.connect(self._on_simple_signal)
        m.componentMoved.connect(self._on_component_moved)
        m.componentRotated.connect(self._on_component_rotated)
        m.connectionAdded.connect(self._on_simple_signal)
        m.connectionRemoved.connect(self._on_simple_signal)
        m.connectionChanged.connect(self._on_simple_signal)
        m.modelReset.connect(self._on_model_reset)
        m.modelChanged.connect(self._on_model_changed)

    def _on_simple_signal(self, _id: str) -> None:
        """Schedule slot for `(component_id: str)` / `(connection_id: str)` signals."""
        self._schedule()

    def _on_component_moved(
        self,
        _component_id: str,
        _old_pos: object,
        _new_pos: object,
    ) -> None:
        """Schedule slot for the 3-arg `componentMoved` signal."""
        self._schedule()

    def _on_component_rotated(
        self,
        _component_id: str,
        _old_rotation: float,
        _new_rotation: float,
    ) -> None:
        """Schedule slot for the 3-arg `componentRotated` signal."""
        self._schedule()

    def _on_model_reset(self) -> None:
        """Schedule slot for `modelReset` (no payload)."""
        self._schedule()

    def _on_model_changed(self, _change_set: WorkspaceChangeSet) -> None:
        """Schedule slot for the batch `modelChanged` signal."""
        self._schedule()

    def _schedule(self) -> None:
        """Restart the debounce timer; single-shot collapses bursts.

        `QTimer.start(ms)` on an already-active single-shot
        timer cancels the prior schedule and restarts — exactly
        the debounce behavior we want. A burst of N mutations
        within the window produces one timeout at the end.
        """
        self._timer.start(self._debounce_ms)


__all__ = [
    "DEFAULT_DEBOUNCE_MS",
    "WorkspaceValidatorController",
]
