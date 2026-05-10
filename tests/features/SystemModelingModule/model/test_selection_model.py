"""Unit tests for `SelectionModel` and `SelectionSnapshot`.

Signal emission is captured via a plain Python callback list — this
keeps the test free of `pytest-qt` and `QApplication` requirements.
A bare `QObject`-derived class can emit signals without an event loop
when the connection is direct (the default for in-process slots).

References
----------
* `specs/02_workspace_requirements.md` §4.1 (signal contract)
* `specs/02_workspace_requirements.md` §21 (Selection System)
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from features.SystemModelingModule.model.selection_model import (
    SelectionModel,
    SelectionSnapshot,
)

# ---------------------------------------------------------------------- #
# Fixtures / helpers
# ---------------------------------------------------------------------- #


@pytest.fixture
def model() -> SelectionModel:
    return SelectionModel()


@pytest.fixture
def captured(model: SelectionModel) -> list[SelectionSnapshot]:
    """Subscribe to `selectionChanged` and capture every emitted payload."""
    payloads: list[SelectionSnapshot] = []
    model.selectionChanged.connect(payloads.append)
    return payloads


# ---------------------------------------------------------------------- #
# Initial state
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_new_model_is_empty(model: SelectionModel) -> None:
    snapshot = model.current()
    assert snapshot.is_empty
    assert snapshot.total_count == 0
    assert snapshot.component_ids == frozenset()
    assert snapshot.connection_ids == frozenset()


@pytest.mark.unit
def test_initial_state_does_not_emit_signal(
    model: SelectionModel,
    captured: list[SelectionSnapshot],
) -> None:
    """Constructing the model alone must not emit a change signal."""
    assert captured == []


# ---------------------------------------------------------------------- #
# select_only
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_select_only_replaces_state_and_emits(
    model: SelectionModel,
    captured: list[SelectionSnapshot],
) -> None:
    model.select_only(components=["cmp_a", "cmp_b"], connections=["con_x"])

    snapshot = model.current()
    assert snapshot.component_ids == frozenset({"cmp_a", "cmp_b"})
    assert snapshot.connection_ids == frozenset({"con_x"})
    assert len(captured) == 1
    assert captured[-1] == snapshot


@pytest.mark.unit
def test_select_only_discards_prior_selection(
    model: SelectionModel,
    captured: list[SelectionSnapshot],
) -> None:
    model.select_only(components=["cmp_a", "cmp_b"])
    model.select_only(components=["cmp_c"])

    assert model.current().component_ids == frozenset({"cmp_c"})
    assert len(captured) == 2


@pytest.mark.unit
def test_select_only_with_no_args_clears_when_non_empty(
    model: SelectionModel,
    captured: list[SelectionSnapshot],
) -> None:
    model.select_only(components=["cmp_a"])
    model.select_only()

    assert model.current().is_empty
    assert len(captured) == 2
    assert captured[-1].is_empty


@pytest.mark.unit
def test_select_only_is_no_op_when_state_unchanged(
    model: SelectionModel,
    captured: list[SelectionSnapshot],
) -> None:
    model.select_only(components=["cmp_a", "cmp_b"])
    captured.clear()

    # Re-applying the same selection (different iterable order) must not emit.
    model.select_only(components=["cmp_b", "cmp_a"])

    assert captured == []


# ---------------------------------------------------------------------- #
# add
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_add_extends_existing_selection(
    model: SelectionModel,
    captured: list[SelectionSnapshot],
) -> None:
    model.select_only(components=["cmp_a"])
    captured.clear()

    model.add(components=["cmp_b"], connections=["con_x"])

    snapshot = model.current()
    assert snapshot.component_ids == frozenset({"cmp_a", "cmp_b"})
    assert snapshot.connection_ids == frozenset({"con_x"})
    assert len(captured) == 1


@pytest.mark.unit
def test_add_is_idempotent_no_op_when_all_already_present(
    model: SelectionModel,
    captured: list[SelectionSnapshot],
) -> None:
    model.select_only(components=["cmp_a", "cmp_b"])
    captured.clear()

    model.add(components=["cmp_a"])  # already present
    model.add(components=["cmp_a", "cmp_b"])  # all present

    assert captured == []


@pytest.mark.unit
def test_add_emits_only_for_actually_new_items(
    model: SelectionModel,
    captured: list[SelectionSnapshot],
) -> None:
    model.select_only(components=["cmp_a"])
    captured.clear()

    # cmp_a already present, cmp_b new → still emits because state changes.
    model.add(components=["cmp_a", "cmp_b"])
    assert len(captured) == 1
    assert captured[-1].component_ids == frozenset({"cmp_a", "cmp_b"})


# ---------------------------------------------------------------------- #
# remove
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_remove_drops_present_items_and_emits(
    model: SelectionModel,
    captured: list[SelectionSnapshot],
) -> None:
    model.select_only(components=["cmp_a", "cmp_b"], connections=["con_x"])
    captured.clear()

    model.remove(components=["cmp_a"], connections=["con_x"])

    snapshot = model.current()
    assert snapshot.component_ids == frozenset({"cmp_b"})
    assert snapshot.connection_ids == frozenset()
    assert len(captured) == 1


@pytest.mark.unit
def test_remove_silently_ignores_unknown_ids(
    model: SelectionModel,
    captured: list[SelectionSnapshot],
) -> None:
    model.select_only(components=["cmp_a"])
    captured.clear()

    model.remove(components=["cmp_NOT_PRESENT"])

    assert model.current().component_ids == frozenset({"cmp_a"})
    assert captured == []  # no-op suppression — nothing actually removed


# ---------------------------------------------------------------------- #
# toggle
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_toggle_adds_when_absent_removes_when_present(
    model: SelectionModel,
    captured: list[SelectionSnapshot],
) -> None:
    model.toggle(components=["cmp_a"])  # absent → add
    assert model.current().component_ids == frozenset({"cmp_a"})

    model.toggle(components=["cmp_a"])  # present → remove
    assert model.current().component_ids == frozenset()

    assert len(captured) == 2


@pytest.mark.unit
def test_toggle_handles_mixed_state_in_single_call(
    model: SelectionModel,
    captured: list[SelectionSnapshot],
) -> None:
    model.select_only(components=["cmp_a"])
    captured.clear()

    # cmp_a present → removed; cmp_b absent → added.
    model.toggle(components=["cmp_a", "cmp_b"])

    assert model.current().component_ids == frozenset({"cmp_b"})
    assert len(captured) == 1


@pytest.mark.unit
def test_toggle_with_empty_iterables_is_no_op(
    model: SelectionModel,
    captured: list[SelectionSnapshot],
) -> None:
    model.toggle()  # no args → no-op
    assert captured == []


# ---------------------------------------------------------------------- #
# clear
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_clear_empties_selection_and_emits(
    model: SelectionModel,
    captured: list[SelectionSnapshot],
) -> None:
    model.select_only(components=["cmp_a"], connections=["con_x"])
    captured.clear()

    model.clear()

    assert model.current().is_empty
    assert len(captured) == 1
    assert captured[-1].is_empty


@pytest.mark.unit
def test_clear_on_empty_selection_is_no_op(
    model: SelectionModel,
    captured: list[SelectionSnapshot],
) -> None:
    model.clear()
    assert captured == []


# ---------------------------------------------------------------------- #
# Read-only API
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_is_component_selected_and_is_connection_selected(
    model: SelectionModel,
) -> None:
    model.select_only(components=["cmp_a"], connections=["con_x"])

    assert model.is_component_selected("cmp_a")
    assert not model.is_component_selected("cmp_b")
    assert model.is_connection_selected("con_x")
    assert not model.is_connection_selected("con_y")
    # Component IDs and connection IDs live in disjoint namespaces; the
    # query does not mix them up.
    assert not model.is_component_selected("con_x")
    assert not model.is_connection_selected("cmp_a")


# ---------------------------------------------------------------------- #
# SelectionSnapshot
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_snapshot_is_frozen() -> None:
    snapshot = SelectionSnapshot()
    with pytest.raises(FrozenInstanceError):
        snapshot.component_ids = frozenset({"cmp_x"})  # type: ignore[misc]


@pytest.mark.unit
def test_snapshot_total_count_sums_both_collections() -> None:
    snapshot = SelectionSnapshot(
        component_ids=frozenset({"cmp_a", "cmp_b"}),
        connection_ids=frozenset({"con_x"}),
    )
    assert snapshot.total_count == 3
    assert not snapshot.is_empty


@pytest.mark.unit
def test_subscriber_holds_immutable_snapshot(
    model: SelectionModel,
    captured: list[SelectionSnapshot],
) -> None:
    """Mutating the model after a signal emit must not retroactively
    change the snapshot the subscriber received.
    """
    model.select_only(components=["cmp_a"])
    first_snapshot = captured[-1]

    model.add(components=["cmp_b"])

    # The subscriber's snapshot is still the pre-mutation state.
    assert first_snapshot.component_ids == frozenset({"cmp_a"})
    # Latest snapshot reflects the new state.
    assert captured[-1].component_ids == frozenset({"cmp_a", "cmp_b"})
