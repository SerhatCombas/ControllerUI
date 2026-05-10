"""Unit tests for `WorkspaceChangeSet` (S1.3d).

Covers:

* default construction yields an all-empty change_set
* `is_empty()` returns True for the default and False whenever any
  diff field or aggregate flag is set (including `reset_required` on
  its own)
* the dataclass is frozen — direct field assignment raises

References
----------
* `decisions/ADR-019-batch-mutation-and-changeset.md`
"""

from __future__ import annotations

import dataclasses

import pytest

from features.SystemModelingModule.model.workspace_change_set import WorkspaceChangeSet


@pytest.mark.unit
def test_default_construction_yields_all_empty_fields() -> None:
    """A default `WorkspaceChangeSet` has empty tuples and False flags."""
    cs = WorkspaceChangeSet()

    assert cs.added_components == ()
    assert cs.removed_components == ()
    assert cs.changed_components == ()
    assert cs.added_connections == ()
    assert cs.removed_connections == ()
    assert cs.changed_connections == ()
    assert cs.validation_changed is False
    assert cs.dirty_changed is False
    assert cs.reset_required is False


@pytest.mark.unit
def test_is_empty_returns_true_for_default() -> None:
    """The default change_set is empty per `is_empty()`."""
    assert WorkspaceChangeSet().is_empty() is True


@pytest.mark.unit
def test_is_empty_returns_false_when_added_components_set() -> None:
    """Any diff content makes the change_set non-empty."""
    cs = WorkspaceChangeSet(added_components=("cmp_X",))
    assert cs.is_empty() is False


@pytest.mark.unit
def test_is_empty_returns_false_when_changed_connections_set() -> None:
    """Diff content on connections also makes the change_set non-empty."""
    cs = WorkspaceChangeSet(changed_connections=("con_X",))
    assert cs.is_empty() is False


@pytest.mark.unit
def test_is_empty_returns_false_when_validation_changed_flag_set() -> None:
    """Aggregate `validation_changed` flag makes the change_set non-empty."""
    cs = WorkspaceChangeSet(validation_changed=True)
    assert cs.is_empty() is False


@pytest.mark.unit
def test_is_empty_returns_false_when_dirty_changed_flag_set() -> None:
    """Aggregate `dirty_changed` flag makes the change_set non-empty."""
    cs = WorkspaceChangeSet(dirty_changed=True)
    assert cs.is_empty() is False


@pytest.mark.unit
def test_is_empty_returns_false_when_reset_required_flag_set() -> None:
    """`reset_required=True` on its own makes the change_set non-empty.

    Per ADR-019, when `reset_required=True` all other diff fields
    are empty/False; the flag itself is the single signal of a
    full-rebuild request.
    """
    cs = WorkspaceChangeSet(reset_required=True)
    assert cs.is_empty() is False


@pytest.mark.unit
def test_frozen_dataclass_cannot_be_mutated() -> None:
    """Frozen dataclass guards against direct field assignment."""
    cs = WorkspaceChangeSet()
    with pytest.raises(dataclasses.FrozenInstanceError):
        cs.dirty_changed = True  # type: ignore[misc]


@pytest.mark.unit
def test_construction_with_explicit_fields_round_trips() -> None:
    """All fields can be supplied at construction and read back."""
    cs = WorkspaceChangeSet(
        added_components=("cmp_a", "cmp_b"),
        removed_components=("cmp_c",),
        changed_components=("cmp_d",),
        added_connections=("con_a",),
        removed_connections=("con_b",),
        changed_connections=("con_c",),
        validation_changed=True,
        dirty_changed=True,
        reset_required=False,
    )

    assert cs.added_components == ("cmp_a", "cmp_b")
    assert cs.removed_components == ("cmp_c",)
    assert cs.changed_components == ("cmp_d",)
    assert cs.added_connections == ("con_a",)
    assert cs.removed_connections == ("con_b",)
    assert cs.changed_connections == ("con_c",)
    assert cs.validation_changed is True
    assert cs.dirty_changed is True
    assert cs.reset_required is False
    assert cs.is_empty() is False
