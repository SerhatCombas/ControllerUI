"""Unit tests for `WorkspaceModel.batch()` (S1.3d).

Covers (per ADR-019):

* basic context manager: enter/exit, empty-batch suppression, nested
  depth counter (only outermost exit emits)
* `modelChanged` signal definition and payload type
* fine-grained signal suppression inside a batch (one test per
  representative mutation method)
* `WorkspaceChangeSet` content for the common mutation paths
* diff aggregation rules (the seven scenarios from ADR-019 §"Diff
  aggregation rules")
* subscriber-exception-masking guard partial coverage (cases 1 and 3
  of the four-row caller-vs-subscriber truth table). Cases 2 and 4
  involve a subscriber exception during signal emission; under
  PySide6's default signal dispatch, subscriber exceptions are
  caught by the Qt event loop and routed to `sys.excepthook`, not
  surfaced through `signal.emit()` to Python `try/except`. The
  ADR-019 masking guard is therefore defensive-but-inactive in
  Phase 1, and cases 2 and 4 cannot be exercised here.
* `selectionChanged` is NOT suppressed during a batch (selection
  independence per ADR-019)
* `reset()` outside a batch (basic semantics)
* `reset()` inside a batch (queue discard, `reset_required=True`,
  post-reset mutations apply to the model but are not in the
  change_set)

S1.3e will extend `reset()` semantics with `_clear_dirty()` and edge
cases; this file exercises the minimal S1.3d implementation in
relation to the batch interaction.

References
----------
* `decisions/ADR-018-signal-payload-contracts.md`
* `decisions/ADR-019-batch-mutation-and-changeset.md`
* `decisions/ADR-020-dirty-tracking-semantics.md`
"""

from __future__ import annotations

from typing import Any

import pytest
from PySide6.QtCore import QPointF

from features.SystemModelingModule.model.component_instance import (
    PhysicalAttributes,
    VisualSpec,
)
from features.SystemModelingModule.model.connection import (
    PortRef,
)
from features.SystemModelingModule.model.selection_model import SelectionSnapshot
from features.SystemModelingModule.model.workspace_change_set import WorkspaceChangeSet
from features.SystemModelingModule.model.workspace_model import WorkspaceModel


def _add_kwargs(**overrides: Any) -> dict[str, Any]:
    """Default `add_component` kwargs (`QPointF` position)."""
    base: dict[str, Any] = {
        "definition_id": "electrical.analog.components.resistor",
        "type": "Resistor",
        "display_name": "Resistor",
        "domain": "electrical_analog",
        "category": "component",
        "position": QPointF(0.0, 0.0),
        "visual": VisualSpec(svg_id="resistor_default"),
        "physical_attributes": PhysicalAttributes(),
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------- #
# Basic context-manager behavior
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_batch_context_manager_enters_and_exits_cleanly() -> None:
    """`with model.batch():` produces no errors on a no-op block."""
    model = WorkspaceModel()

    with model.batch():
        pass

    assert model._batch_depth == 0
    assert model._batch_builder is None


@pytest.mark.unit
def test_empty_batch_suppresses_model_changed_emission() -> None:
    """A batch with no mutations does not emit `modelChanged`."""
    model = WorkspaceModel()
    received: list[WorkspaceChangeSet] = []
    model.modelChanged.connect(received.append)

    with model.batch():
        pass

    assert received == []


@pytest.mark.unit
def test_nested_batches_emit_once_on_outermost_exit() -> None:
    """Nested batches use a depth counter; only the outermost exit emits."""
    model = WorkspaceModel()
    received: list[WorkspaceChangeSet] = []
    model.modelChanged.connect(received.append)

    with model.batch():
        model.add_component(**_add_kwargs())
        with model.batch():
            model.add_component(**_add_kwargs())
        assert received == []

    assert len(received) == 1
    cs = received[0]
    assert len(cs.added_components) == 2


# ---------------------------------------------------------------------- #
# Signal definition
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_model_defines_model_changed_signal() -> None:
    """`modelChanged` is the 13th signal (ADR-019)."""
    model = WorkspaceModel()
    signal = getattr(model, "modelChanged", None)

    assert signal is not None
    assert hasattr(signal, "emit")
    assert hasattr(signal, "connect")


@pytest.mark.unit
def test_model_changed_payload_is_workspace_change_set() -> None:
    """`modelChanged` payload is a `WorkspaceChangeSet` instance."""
    model = WorkspaceModel()
    received: list[Any] = []
    model.modelChanged.connect(received.append)

    with model.batch():
        model.add_component(**_add_kwargs())

    assert len(received) == 1
    assert isinstance(received[0], WorkspaceChangeSet)


# ---------------------------------------------------------------------- #
# Fine-grained signal suppression inside a batch
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_component_added_suppressed_inside_batch() -> None:
    """`componentAdded` does not fire during a batch."""
    model = WorkspaceModel()
    received: list[str] = []
    model.componentAdded.connect(received.append)

    with model.batch():
        model.add_component(**_add_kwargs())

    assert received == []


@pytest.mark.unit
def test_component_removed_suppressed_inside_batch() -> None:
    """`componentRemoved` does not fire during a batch."""
    model = WorkspaceModel()
    cid = model.add_component(**_add_kwargs())
    received: list[str] = []
    model.componentRemoved.connect(received.append)

    with model.batch():
        model.remove_component(cid)

    assert received == []


@pytest.mark.unit
def test_component_moved_suppressed_inside_batch() -> None:
    """`componentMoved` does not fire during a batch."""
    model = WorkspaceModel()
    cid = model.add_component(**_add_kwargs(position=QPointF(0.0, 0.0)))
    received: list[Any] = []
    model.componentMoved.connect(lambda *args: received.append(args))

    with model.batch():
        model.move_component(cid, QPointF(50.0, 75.0))

    assert received == []


@pytest.mark.unit
def test_component_changed_suppressed_inside_batch() -> None:
    """`componentChanged` does not fire for setters during a batch."""
    model = WorkspaceModel()
    cid = model.add_component(**_add_kwargs())
    received: list[str] = []
    model.componentChanged.connect(received.append)

    with model.batch():
        model.set_custom_label(cid, "X")

    assert received == []


@pytest.mark.unit
def test_connection_signals_suppressed_inside_batch() -> None:
    """Connection-related fine-grained signals are all suppressed."""
    model = WorkspaceModel()
    a = model.add_component(**_add_kwargs())
    b = model.add_component(**_add_kwargs())
    add_received: list[str] = []
    rm_received: list[str] = []
    chg_received: list[str] = []
    model.connectionAdded.connect(add_received.append)
    model.connectionRemoved.connect(rm_received.append)
    model.connectionChanged.connect(chg_received.append)

    with model.batch():
        conn_id = model.add_connection(
            source=PortRef(component_id=a, port_id="p"),
            target=PortRef(component_id=b, port_id="p"),
        )
        model.update_connection(conn_id, label="Trunk")

    assert add_received == []
    assert chg_received == []
    assert rm_received == []


@pytest.mark.unit
def test_dirty_changed_deferred_inside_batch_and_carried_in_change_set() -> None:
    """`dirtyChanged` is not emitted during a batch; the transition is
    carried in `change_set.dirty_changed`."""
    model = WorkspaceModel()
    dirty_emissions: list[bool] = []
    model.dirtyChanged.connect(dirty_emissions.append)
    received: list[WorkspaceChangeSet] = []
    model.modelChanged.connect(received.append)

    with model.batch():
        model.add_component(**_add_kwargs())

    assert dirty_emissions == []
    assert len(received) == 1
    assert received[0].dirty_changed is True
    assert model.is_dirty is True


# ---------------------------------------------------------------------- #
# `WorkspaceChangeSet` content from common mutation paths
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_change_set_records_added_component_id() -> None:
    """A single `add_component` inside a batch shows up in `added_components`."""
    model = WorkspaceModel()
    received: list[WorkspaceChangeSet] = []
    model.modelChanged.connect(received.append)

    with model.batch():
        cid = model.add_component(**_add_kwargs())

    assert received[0].added_components == (cid,)
    assert received[0].removed_components == ()
    assert received[0].changed_components == ()


@pytest.mark.unit
def test_change_set_records_removed_pre_batch_component() -> None:
    """A component removed from pre-batch state appears in `removed_components`."""
    model = WorkspaceModel()
    cid = model.add_component(**_add_kwargs())
    received: list[WorkspaceChangeSet] = []
    model.modelChanged.connect(received.append)

    with model.batch():
        model.remove_component(cid)

    assert received[0].removed_components == (cid,)
    assert received[0].added_components == ()


@pytest.mark.unit
def test_change_set_records_changed_pre_batch_component() -> None:
    """An edit to a pre-batch component appears in `changed_components`."""
    model = WorkspaceModel()
    cid = model.add_component(**_add_kwargs())
    received: list[WorkspaceChangeSet] = []
    model.modelChanged.connect(received.append)

    with model.batch():
        model.set_custom_label(cid, "X")

    assert received[0].changed_components == (cid,)


@pytest.mark.unit
def test_change_set_records_added_connection_id() -> None:
    """A single `add_connection` shows up in `added_connections`."""
    model = WorkspaceModel()
    a = model.add_component(**_add_kwargs())
    b = model.add_component(**_add_kwargs())
    received: list[WorkspaceChangeSet] = []
    model.modelChanged.connect(received.append)

    with model.batch():
        conn_id = model.add_connection(
            source=PortRef(component_id=a, port_id="p"),
            target=PortRef(component_id=b, port_id="p"),
        )

    assert received[0].added_connections == (conn_id,)


@pytest.mark.unit
def test_change_set_preserves_insertion_order() -> None:
    """`added_components` reflects insertion order of first appearance."""
    model = WorkspaceModel()
    received: list[WorkspaceChangeSet] = []
    model.modelChanged.connect(received.append)

    with model.batch():
        first = model.add_component(**_add_kwargs())
        second = model.add_component(**_add_kwargs())
        third = model.add_component(**_add_kwargs())

    assert received[0].added_components == (first, second, third)


# ---------------------------------------------------------------------- #
# Diff aggregation rules (ADR-019)
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_diff_aggregation_add_then_remove_within_batch_is_net_zero() -> None:
    """A component added and then removed within the batch appears in
    neither `added_components` nor `removed_components`."""
    model = WorkspaceModel()
    received: list[WorkspaceChangeSet] = []
    model.modelChanged.connect(received.append)

    with model.batch():
        cid = model.add_component(**_add_kwargs())
        model.remove_component(cid)

    cs = received[0]
    assert cs.added_components == ()
    assert cs.removed_components == ()
    # dirty_changed still True because the dirty bit transitioned.
    assert cs.dirty_changed is True


@pytest.mark.unit
def test_diff_aggregation_add_then_change_yields_added_only() -> None:
    """A component added and then changed appears in `added_components`
    only; the change is not in `changed_components`."""
    model = WorkspaceModel()
    received: list[WorkspaceChangeSet] = []
    model.modelChanged.connect(received.append)

    with model.batch():
        cid = model.add_component(**_add_kwargs())
        model.set_custom_label(cid, "X")

    cs = received[0]
    assert cs.added_components == (cid,)
    assert cs.changed_components == ()


@pytest.mark.unit
def test_diff_aggregation_add_then_move_yields_added_only() -> None:
    """A component added and then moved appears in `added_components` only."""
    model = WorkspaceModel()
    received: list[WorkspaceChangeSet] = []
    model.modelChanged.connect(received.append)

    with model.batch():
        cid = model.add_component(**_add_kwargs())
        model.move_component(cid, QPointF(50.0, 75.0))

    cs = received[0]
    assert cs.added_components == (cid,)
    assert cs.changed_components == ()


@pytest.mark.unit
def test_diff_aggregation_multi_change_yields_changed_once() -> None:
    """A pre-batch component changed multiple times appears in
    `changed_components` exactly once."""
    model = WorkspaceModel()
    cid = model.add_component(**_add_kwargs())
    received: list[WorkspaceChangeSet] = []
    model.modelChanged.connect(received.append)

    with model.batch():
        model.set_custom_label(cid, "X")
        model.set_custom_label(cid, "Y")
        model.set_locked(cid, True)

    cs = received[0]
    assert cs.changed_components == (cid,)


@pytest.mark.unit
def test_diff_aggregation_move_and_rotate_yields_changed_once() -> None:
    """A pre-batch component moved AND rotated appears in
    `changed_components` exactly once."""
    model = WorkspaceModel()
    cid = model.add_component(**_add_kwargs(position=QPointF(0.0, 0.0)))
    received: list[WorkspaceChangeSet] = []
    model.modelChanged.connect(received.append)

    with model.batch():
        model.move_component(cid, QPointF(50.0, 75.0))
        model.rotate_component(cid, 90.0)

    cs = received[0]
    assert cs.changed_components == (cid,)


@pytest.mark.unit
def test_diff_aggregation_existing_then_remove_yields_removed_only() -> None:
    """A pre-batch component removed appears in `removed_components`
    only, even if intermediate edits were made."""
    model = WorkspaceModel()
    cid = model.add_component(**_add_kwargs())
    received: list[WorkspaceChangeSet] = []
    model.modelChanged.connect(received.append)

    with model.batch():
        model.set_custom_label(cid, "X")
        model.remove_component(cid)

    cs = received[0]
    assert cs.removed_components == (cid,)
    assert cs.changed_components == ()


# ---------------------------------------------------------------------- #
# Subscriber-exception masking — partial coverage (ADR-019 truth table
# cases 1 and 3 only).
#
# Cases 2 and 4 involve a subscriber raising during signal emission.
# Under PySide6's default signal dispatch, subscriber exceptions are
# caught by the Qt event loop and routed to `sys.excepthook`; they do
# NOT surface through `signal.emit()` to Python `try/except`. The
# ADR-019 `__exit__` masking guard therefore cannot be exercised by a
# unit test under default PySide6 settings — the guard is defensive
# but inactive. See the module docstring for context.
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_caller_ok_subscriber_ok_normal_emit() -> None:
    """Truth-table case 1: no exceptions; normal emission and return."""
    model = WorkspaceModel()
    received: list[WorkspaceChangeSet] = []
    model.modelChanged.connect(received.append)

    with model.batch():
        model.add_component(**_add_kwargs())

    assert len(received) == 1


@pytest.mark.unit
def test_caller_raises_subscriber_ok_caller_propagates() -> None:
    """Truth-table case 3: caller exception propagates; the change_set
    was emitted before the exception escaped (Mode B + emit-before-
    propagate)."""
    model = WorkspaceModel()
    received: list[WorkspaceChangeSet] = []
    model.modelChanged.connect(received.append)

    # PT012 is suppressed below: pytest.raises wants a single simple
    # statement, but Mode B (ADR-019) requires verifying that a
    # completed mutation reaches the change_set before the caller
    # exception escapes — the block needs both a mutation and a raise.
    with pytest.raises(ValueError, match="boom"), model.batch():  # noqa: PT012
        model.add_component(**_add_kwargs())
        raise ValueError("boom")

    assert len(received) == 1
    assert len(received[0].added_components) == 1


# ---------------------------------------------------------------------- #
# Selection independence (ADR-019)
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_selection_changed_emits_during_batch() -> None:
    """`SelectionModel` mutations are independent of `WorkspaceModel.batch()`;
    `selectionChanged` emits as it normally would, even during a model
    batch (per ADR-019 §"Selection during a batch")."""
    model = WorkspaceModel()
    received: list[Any] = []
    model.selectionChanged.connect(lambda *args: received.append(args))
    snapshot = SelectionSnapshot()  # default empty snapshot

    with model.batch():
        model.selectionChanged.emit(snapshot)

    assert len(received) == 1


# ---------------------------------------------------------------------- #
# `reset()` outside a batch (S1.3d minimal)
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_reset_outside_batch_clears_state_and_emits_model_reset() -> None:
    """`reset()` clears stores and emits `modelReset()` outside a batch."""
    model = WorkspaceModel()
    model.add_component(**_add_kwargs())
    model.add_component(**_add_kwargs())
    reset_emissions: list[None] = []
    model.modelReset.connect(lambda: reset_emissions.append(None))

    model.reset()

    assert dict(model.components) == {}
    assert dict(model.connections) == {}
    assert len(reset_emissions) == 1


@pytest.mark.unit
def test_reset_outside_batch_clears_dirty_with_transition_emit() -> None:
    """When `reset()` clears a dirty model, `dirtyChanged(False)` fires."""
    model = WorkspaceModel()
    model.add_component(**_add_kwargs())  # dirty=True
    assert model.is_dirty is True
    dirty_emissions: list[bool] = []
    model.dirtyChanged.connect(dirty_emissions.append)

    model.reset()

    assert model.is_dirty is False
    assert dirty_emissions == [False]


@pytest.mark.unit
def test_reset_outside_batch_on_clean_model_does_not_emit_dirty_changed() -> None:
    """`reset()` on an already-clean model does not emit `dirtyChanged`
    (ADR-020 transition-only rule)."""
    model = WorkspaceModel()
    dirty_emissions: list[bool] = []
    model.dirtyChanged.connect(dirty_emissions.append)

    model.reset()

    assert dirty_emissions == []


@pytest.mark.unit
def test_reset_outside_batch_on_clean_model_still_emits_model_reset() -> None:
    """`reset()` always emits `modelReset()` outside a batch, even on a
    clean model. The signal denotes "rebuild the scene from the model"
    (now empty); it is not gated on prior dirty state.
    """
    model = WorkspaceModel()
    reset_emissions: list[None] = []
    model.modelReset.connect(lambda: reset_emissions.append(None))

    model.reset()

    assert len(reset_emissions) == 1


@pytest.mark.unit
def test_reset_resets_id_generator_to_blank_slate() -> None:
    """Per Yorum A (S1.3e): `reset()` re-creates the ID generator, so
    the next component added after a reset receives a display-ID
    counter starting from `1` again, not from the previous
    high-water mark.

    Without blank-slate semantics, a fresh resistor after a reset
    would receive `resistor_4` (or similar) — a confusing UX after
    "discard everything and start over." Blank-slate aligns with
    user expectation of `reset()` = "new project".
    """
    model = WorkspaceModel()
    model.add_component(**_add_kwargs())  # resistor_1
    model.add_component(**_add_kwargs())  # resistor_2
    model.add_component(**_add_kwargs())  # resistor_3

    model.reset()
    new_id = model.add_component(**_add_kwargs())

    assert model.components[new_id].display_id == "resistor_1"


# ---------------------------------------------------------------------- #
# `reset()` inside a batch (ADR-019 reset semantics)
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_reset_inside_batch_sets_reset_required_flag() -> None:
    """Reset inside a batch sets `change_set.reset_required = True`."""
    model = WorkspaceModel()
    received: list[WorkspaceChangeSet] = []
    model.modelChanged.connect(received.append)

    with model.batch():
        model.reset()

    assert len(received) == 1
    assert received[0].reset_required is True


@pytest.mark.unit
def test_reset_inside_batch_discards_queued_mutations_in_change_set() -> None:
    """Mutations queued before `reset()` within the batch are discarded
    from the change_set; `reset_required=True` is the only signal."""
    model = WorkspaceModel()
    received: list[WorkspaceChangeSet] = []
    model.modelChanged.connect(received.append)

    with model.batch():
        model.add_component(**_add_kwargs())
        model.add_component(**_add_kwargs())
        model.reset()

    cs = received[0]
    assert cs.reset_required is True
    assert cs.added_components == ()
    assert cs.removed_components == ()
    assert cs.changed_components == ()
    assert cs.dirty_changed is False


@pytest.mark.unit
def test_reset_inside_batch_post_reset_mutations_apply_but_not_in_change_set() -> None:
    """Mutations performed after `reset()` within the batch apply to the
    model state but are NOT individually reflected in the change_set."""
    model = WorkspaceModel()
    received: list[WorkspaceChangeSet] = []
    model.modelChanged.connect(received.append)

    with model.batch():
        model.reset()
        new_id = model.add_component(**_add_kwargs())

    assert new_id in model.components
    cs = received[0]
    assert cs.reset_required is True
    assert cs.added_components == ()
