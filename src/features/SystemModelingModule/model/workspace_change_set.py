"""WorkspaceChangeSet: cumulative diff payload for `modelChanged` (ADR-019).

The frozen dataclass emitted by `WorkspaceModel.modelChanged` exactly
once on the outermost batch exit per ADR-019. Subscribers consume the
diff to perform a single bulk rebuild instead of N incremental
updates from individual fine-grained signals (which are suppressed
during a batch).

Tuples carry component / connection internal IDs (per ADR-002) in
**insertion order of first appearance** during the batch. Aggregate
boolean flags (`validation_changed`, `dirty_changed`,
`reset_required`) summarize state-level transitions; subscribers that
need the actual report query `model.validation_report` /
`model.is_dirty` directly (synchronous emission per ADR-018 makes
this race-free).

Diff aggregation rules (per ADR-019):

* Component is added then removed within the batch: appears in
  **neither** `added_components` nor `removed_components`.
* Component is added then changed (parameters / label / move /
  rotate / etc.): `added_components` only.
* Component is changed multiple times (or moved + rotated): one
  entry in `changed_components`.
* Component exists pre-batch and is removed (with or without
  intermediate edits): `removed_components` only; intermediate
  changes are dropped.

The `reset_required` flag is special: when `True`, all other diff
fields MUST be empty / `False`. Subscribers receiving
`reset_required=True` perform a full rebuild from the current model
state and ignore the diff fields.

Lives in `features/SystemModelingModule/model/` (workspace-internal
payload, not a cross-feature artifact); `ControllerDesignModule` does
not subscribe.

References:
----------
* `decisions/ADR-019-batch-mutation-and-changeset.md`
* `decisions/ADR-018-signal-payload-contracts.md`
* `decisions/ADR-002-hybrid-ulid-identity-model.md`
* `specs/02_workspace_requirements.md` §4 (Signals)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class WorkspaceChangeSet:
    """Cumulative diff emitted by `modelChanged` on outermost batch exit.

    All fields default to empty / `False`. An empty change_set
    (`is_empty()` returns `True`) is structurally valid but is
    **not** emitted: an empty batch suppresses the signal entirely.

    Attributes:
        added_components: Internal IDs of components added during
            the batch (insertion order of first appearance).
        removed_components: Internal IDs of components present pre-
            batch and removed (insertion order of first appearance).
        changed_components: Internal IDs of components present pre-
            batch and modified (parameters, label, position, rotation,
            tags, lock, annotations). Each ID appears at most once
            regardless of how many edits occurred.
        added_connections: Same shape for connections.
        removed_connections: Same shape for connections.
        changed_connections: Same shape for connections.
        validation_changed: True if the validation report changed
            during the batch (post-batch validation pass differs from
            pre-batch).
        dirty_changed: True if the dirty bit transitioned during the
            batch (False → True or True → False).
        reset_required: True if `model.reset()` was called inside the
            batch. When True, all other diff fields are empty /
            `False`; subscribers must full-rebuild from the current
            model state.

    See Also:
        ADR-019, ADR-018, ADR-020.
    """

    added_components: tuple[str, ...] = ()
    removed_components: tuple[str, ...] = ()
    changed_components: tuple[str, ...] = ()
    added_connections: tuple[str, ...] = ()
    removed_connections: tuple[str, ...] = ()
    changed_connections: tuple[str, ...] = ()
    validation_changed: bool = False
    dirty_changed: bool = False
    reset_required: bool = False

    def is_empty(self) -> bool:
        """True if no diff content and no aggregate flags are set.

        Used by `WorkspaceModel._batch_exit()` to decide whether to
        emit `modelChanged` on outermost batch exit. Empty batches
        suppress the signal entirely per ADR-019.
        """
        return (
            not self.added_components
            and not self.removed_components
            and not self.changed_components
            and not self.added_connections
            and not self.removed_connections
            and not self.changed_connections
            and not self.validation_changed
            and not self.dirty_changed
            and not self.reset_required
        )


__all__ = [
    "WorkspaceChangeSet",
]
