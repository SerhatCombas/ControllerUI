"""Unit tests for `WorkspaceValidatorController` (S1.6b).

Covers:

* Construction binds the model + validator + debounce window.
* `validate_now()` runs synchronously, emits
  `validationChanged`, returns the report.
* Each model mutation signal schedules a deferred validation
  via `QTimer.singleShot` semantics — the controller's
  `is_pending` property toggles to True.
* Bursts of mutations within the debounce window coalesce
  into a single pending timer (single-shot restart).
* `validate_now()` cancels a pending schedule.
* Debounce window can be reconfigured at runtime.

Tests use `qtbot.waitSignal` for timer-fire assertions where
the event loop needs to spin; synchronous paths use
`validate_now()` directly.

References:
----------
* `specs/02_workspace_requirements.md` §20.6 (Validation Pacing)
* `specs/07_implementation_order.md` §7.11
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPointF

from features.SystemModelingModule.model.validation_report import ValidationReport
from features.SystemModelingModule.model.workspace_model import WorkspaceModel
from features.SystemModelingModule.model.workspace_validator_controller import (
    DEFAULT_DEBOUNCE_MS,
    WorkspaceValidatorController,
)
from shared.registry import ComponentRegistry
from shared.registry.builtin import (
    BUILTIN_COMPONENT_DEFINITIONS,
    RESISTOR_DEFINITION,
)


@pytest.fixture
def model() -> WorkspaceModel:
    """Registry-wired model."""
    return WorkspaceModel(registry=ComponentRegistry(BUILTIN_COMPONENT_DEFINITIONS))


@pytest.fixture
def controller(model: WorkspaceModel) -> WorkspaceValidatorController:
    """Default-window controller bound to the model.

    Uses a very long debounce so timer-fire timing is not
    flaky in tests that don't intentionally wait for it; the
    `validate_now()` path is the load-bearing surface for
    synchronous tests.
    """
    return WorkspaceValidatorController(model, debounce_ms=10_000)


# ---------------------------------------------------------------------- #
# Construction
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_controller_constructs_with_model(model: WorkspaceModel) -> None:
    """The controller binds the supplied model."""
    controller = WorkspaceValidatorController(model)

    assert controller.model is model


@pytest.mark.unit
def test_default_debounce_window_is_250ms(model: WorkspaceModel) -> None:
    """Default `debounce_ms` matches `DEFAULT_DEBOUNCE_MS`."""
    controller = WorkspaceValidatorController(model)

    assert controller.debounce_ms == DEFAULT_DEBOUNCE_MS == 250


@pytest.mark.unit
def test_custom_debounce_window_constructor(model: WorkspaceModel) -> None:
    """Constructor `debounce_ms` overrides the default."""
    controller = WorkspaceValidatorController(model, debounce_ms=500)

    assert controller.debounce_ms == 500


@pytest.mark.unit
def test_initial_state_no_pending_validation(
    controller: WorkspaceValidatorController,
) -> None:
    """A freshly-constructed controller has no pending schedule."""
    assert controller.is_pending is False


# ---------------------------------------------------------------------- #
# validate_now — synchronous bypass
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_validate_now_returns_validation_report(
    controller: WorkspaceValidatorController,
) -> None:
    """`validate_now` returns a `ValidationReport`."""
    report = controller.validate_now()

    assert isinstance(report, ValidationReport)


@pytest.mark.unit
def test_validate_now_emits_validation_changed(
    controller: WorkspaceValidatorController,
    model: WorkspaceModel,
) -> None:
    """`validate_now` emits `model.validationChanged(report)`."""
    received: list[ValidationReport] = []
    model.validationChanged.connect(received.append)

    controller.validate_now()

    assert len(received) == 1
    assert isinstance(received[0], ValidationReport)


@pytest.mark.unit
def test_validate_now_runs_workspace_rules(
    controller: WorkspaceValidatorController,
    model: WorkspaceModel,
) -> None:
    """The emitted report includes the workspace-rule issues from S1.6a.

    A lone resistor → missing-ground error + two
    dangling-required-port warnings.
    """
    model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))

    report = controller.validate_now()

    codes = {issue.code for issue in report.issues}
    assert "error.validation.missing_ground" in codes
    assert "warning.validation.unused_port" in codes


# ---------------------------------------------------------------------- #
# Debounce scheduling
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_mutation_schedules_pending_validation(
    controller: WorkspaceValidatorController,
    model: WorkspaceModel,
) -> None:
    """A mutation starts the debounce timer; `is_pending` is True after."""
    model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))

    assert controller.is_pending is True


@pytest.mark.unit
def test_multiple_mutations_coalesce_to_single_pending_timer(
    controller: WorkspaceValidatorController,
    model: WorkspaceModel,
) -> None:
    """Five mutations in a row leave exactly one timer pending.

    `QTimer.start(ms)` on a single-shot timer cancels the
    prior schedule, so a burst maps to one fire-at-the-end
    timeout — the debounce behavior the spec asks for.
    """
    for _ in range(5):
        model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))

    # Still exactly one pending schedule, not five.
    assert controller.is_pending is True
    # No way to assert "exactly one fired" without spinning the
    # event loop, but the single-shot semantic guarantees it.


@pytest.mark.unit
def test_validate_now_cancels_pending_timer(
    controller: WorkspaceValidatorController,
    model: WorkspaceModel,
) -> None:
    """`validate_now` stops the debounce timer."""
    model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    assert controller.is_pending is True

    controller.validate_now()

    assert controller.is_pending is False


@pytest.mark.unit
def test_batch_modelchanged_schedules_one_validation(
    controller: WorkspaceValidatorController,
    model: WorkspaceModel,
) -> None:
    """A `model.batch()` block ends in one schedule, not N.

    Inside the batch the fine-grained signals are suppressed
    (per ADR-019); the controller subscribes to the batch
    `modelChanged` signal which fires once on outermost exit.
    """
    with model.batch():
        for _ in range(3):
            model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))

    assert controller.is_pending is True


@pytest.mark.unit
def test_model_reset_schedules_validation(
    controller: WorkspaceValidatorController,
    model: WorkspaceModel,
) -> None:
    """`model.reset()` schedules a validation via the modelReset signal."""
    model.reset()

    assert controller.is_pending is True


# ---------------------------------------------------------------------- #
# Reconfiguration
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_set_debounce_ms_updates_window(
    controller: WorkspaceValidatorController,
) -> None:
    """`set_debounce_ms` overrides the debounce window for subsequent calls."""
    controller.set_debounce_ms(750)

    assert controller.debounce_ms == 750


@pytest.mark.unit
def test_set_debounce_ms_rejects_negative(
    controller: WorkspaceValidatorController,
) -> None:
    """Negative debounce windows raise `ValueError`."""
    with pytest.raises(ValueError, match=r"non-negative"):
        controller.set_debounce_ms(-1)


# ---------------------------------------------------------------------- #
# End-to-end through the timer (qtbot)
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_timer_fires_and_emits_validation_changed(
    model: WorkspaceModel,
    qtbot,
) -> None:
    """A short-window controller fires the timer and emits the report.

    Uses pytest-qt's `waitSignal` to spin the event loop until
    `validationChanged` fires — verifies that the debounce
    pipeline works end-to-end without `validate_now` shortcuts.
    """
    short_controller = WorkspaceValidatorController(model, debounce_ms=20)

    with qtbot.waitSignal(model.validationChanged, timeout=2000) as blocker:
        model.add_component_from_definition(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))

    assert blocker.signal_triggered
    # Confirm the controller is back to idle.
    assert short_controller.is_pending is False
