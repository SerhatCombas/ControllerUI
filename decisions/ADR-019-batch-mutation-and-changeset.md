# ADR-019: Batch Mutation Mode and WorkspaceChangeSet

**Status:** Accepted  
**Date:** 2026-05-10  
**Deciders:** Serhat Combas  
**Stage:** S1  
**Supersedes:** —  
**Superseded by:** —

## Context

`02 §4.1` defines 12 fine-grained signals that emit on each individual mutation. This works well for single-edit operations (drag a component, rotate one item, edit one parameter), but is inefficient or incorrect for **bulk** operations:

* **Project load** can add 100 components and 300 connections; emitting 400 individual signals causes 400 scene rebuilds at intermediate inconsistent states.
* **Paste of a multi-component selection** is logically one user action; subscribers should not see partial intermediate states.
* **Undo/redo of compound commands** (e.g., `DeleteComponentCommand` that also removes attached connections) needs atomic visual update.
* **Migrations** during `from_dict` rebuild the entire model and should not flood the validator/UI with per-mutation noise.

A simple "suppress and replay" of fine-grained signals is also wrong for subscribers that want the **cumulative diff**: they cannot reconstruct "what changed in this bulk operation" from a stream of individual signals without state-keeping.

This ADR introduces a batch mutation mode and a 13th signal that carries a structured diff.

## Decision

### Public API

`WorkspaceModel` provides a context manager:

```python
class WorkspaceModel:
    def batch(self) -> AbstractContextManager[None]: ...

with model.batch():
    model.add_component(c1)
    model.add_component(c2)
    model.add_connection(conn)
# on exit, fine-grained signals are NOT emitted; modelChanged(change_set) fires once.
```

### Signal contract — 13th signal

A 13th signal extends `02 §4.1`:

```python
modelChanged(change_set: WorkspaceChangeSet)
```

The 12 fine-grained signals and `modelChanged` are **mutually exclusive within a single mutation cycle**:

* **Outside any batch** → fine-grained signals emit on each mutation; `modelChanged` does not emit.
* **Inside a batch** → fine-grained signals are suppressed; on the outermost batch exit, `modelChanged(change_set)` emits exactly once.

Subscribers never receive both for the same mutation. This rules out double-handling.

The signal name `modelChanged` is chosen to sit naturally beside `modelReset`: both are coarse-grained signals about `WorkspaceModel` as a whole. `modelReset` says "discard everything and rebuild"; `modelChanged` says "the model changed in a structured way; here is the diff."

### Subscriber rule

```
For high-frequency, fine-grained updates (single mutations):
  → Subscribe to individual signals (componentAdded, componentMoved, ...)

For bulk/structural updates (paste, load, reset, multi-step edits):
  → Subscribe to modelChanged(change_set)

Widgets that must react to BOTH:
  → Subscribe to both. modelChanged.change_set carries the full cumulative
    diff; individual signals are NOT emitted during a batch.
    The two signal classes are mutually exclusive within a single mutation
    cycle: either individual signals fire (batch-free) or modelChanged
    fires (batch active).
```

`BlockDiagramWorkspaceScene` is the canonical "both" subscriber: fine-grained signals for incremental edits (drag, rotate, single add) and `modelChanged` for bulk rebuilds (load, paste, reset).

### Selection during a batch

`SelectionModel` mutations are **independent** of `WorkspaceModel.batch()`. `selectionChanged` emits as it normally would, even during a model batch — selection is a UI affordance, not part of the model diff carried by `WorkspaceChangeSet`. If a batch removes components that are currently selected, the caller is responsible for updating selection (typically via the same command that performs the removal). The batch context manager neither suppresses nor mediates `selectionChanged`.

### `WorkspaceChangeSet` schema

Lives in `features/SystemModelingModule/model/workspace_change_set.py` (workspace-internal payload, not a cross-feature artifact — `ControllerDesignModule` does not subscribe).

```python
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class WorkspaceChangeSet:
    added_components: tuple[str, ...]    = ()
    removed_components: tuple[str, ...]  = ()
    changed_components: tuple[str, ...]  = ()
    added_connections: tuple[str, ...]   = ()
    removed_connections: tuple[str, ...] = ()
    changed_connections: tuple[str, ...] = ()
    validation_changed: bool = False
    dirty_changed: bool      = False
    reset_required: bool     = False

    def is_empty(self) -> bool:
        """True if no diff content and no aggregate flags are set."""
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
```

Field rules:

* Tuples carry component/connection internal IDs (per ADR-002), in **insertion order of first appearance** during the batch. Internal collection uses a `list`; conversion to `tuple` happens at emission time.
* `validation_changed` / `dirty_changed` are aggregate booleans. Subscribers needing the actual report query `model.validation_report` / `model.is_dirty` (synchronous emission per ADR-018 makes this race-free).
* All fields default to empty/false. An empty change_set (no diff fields, all booleans false, `reset_required=False`) is structurally valid but **must not be emitted**: an empty batch suppresses the signal entirely.

### Diff aggregation rules

When the same component or connection is touched multiple times within a single batch, the change_set carries the **net effect** of the batch, not a list of all operations:

| Sequence within batch | Result in change_set |
|---|---|
| Component is added, then removed | Appears in **neither** `added_components` nor `removed_components` (net zero) |
| Component is added, then changed (parameters/label/etc.) | `added_components` only — post-batch state is what subscribers refetch |
| Component is added, then moved/rotated | `added_components` only — same reason |
| Component is changed multiple times | `changed_components` exactly once |
| Component exists pre-batch and is removed | `removed_components` only |
| Component exists pre-batch, is changed, then removed | `removed_components` only — change is moot once removed |
| Component exists pre-batch, is moved and/or rotated (one or more times) | `changed_components` exactly once; per-mutation old/new deltas are not preserved across a batch |

The same rules apply to connections.

The principle: tuples carry **identities of entities whose net status changed**, in insertion order of first appearance. Delta payloads from individual `componentMoved`/`componentRotated` signals are intentionally lost across a batch — subscribers reconstruct the post-batch state by querying the model, which is correct after a full bulk rebuild.

### Validation deferral inside a batch

Automatic validation (per `02 §20.6`) that would normally fire after a graph-changing mutation is **suppressed** during a batch. On the outermost batch exit, exactly one validation pass runs against the final model state. If the resulting validation report differs from the pre-batch report, `change_set.validation_changed = True`.

Outside a batch, validation runs synchronously per mutation as `02 §20.6` describes (subject to its own debouncing rules).

Rationale: intermediate model states inside a batch may be transiently inconsistent (e.g., a paste that adds components before connections), and per-mutation validation would produce noise without informational value. A single post-batch validation run is both faster and semantically correct.

### Reset semantics inside a batch

If `model.reset()` is called inside a batch:

* All previously queued mutations are **discarded from the model** — model state rolls back to empty (the post-`reset()` state).
* `change_set.reset_required = True`.
* All other diff fields remain empty (`()` and `False`).
* Mutations performed *after* `reset()` within the same batch **are applied to the model normally**, but are **not** individually reflected in the change_set. They contribute to the post-batch model state that subscribers will rebuild from.

Subscribers MUST check `reset_required` first. If `True`, ignore all diff fields and refetch model state directly via a full rebuild.

Rationale: `reset()` is the strongest possible mutation; carrying a partial pre-reset diff alongside `reset_required=True` would mislead subscribers. The full-rebuild rule means post-reset mutations do not need diff entries — the subscriber discovers them by walking the current model.

### Nested batches

`batch()` is reentrant via a depth counter:

```python
with model.batch():           # depth 1
    model.add_component(c1)
    with model.batch():       # depth 2 (no-op; just increments counter)
        model.add_component(c2)
    # depth back to 1; no emission yet
# depth 0; modelChanged emits with both adds.
```

Only the outermost exit emits. Inner exits decrement the counter and return.

### Exception handling — Mode B (best-effort commit)

If an exception is raised inside a batch:

```python
with model.batch():
    model.add_component(c1)   # success
    model.add_component(c2)   # raises
# c1 stays; c2 was never applied; modelChanged emits with
# added_components=(c1.id,); the exception propagates to the caller.
```

The completed mutations remain in the model. The change_set reflects what was actually applied. The exception still propagates after the change_set is emitted (in the `__exit__` path before re-raising).

**Rejected — Mode A (transactional rollback):** would require a per-batch undo log distinct from `QUndoStack`, duplicating effort for the S1.7 command stack. Transactional grouping is instead delegated to `QUndoStack.beginMacro` / `endMacro` (ADR-005), where it is already integrated with redo/undo. A common pattern:

```python
class PasteSelectionCommand(QUndoCommand):
    def redo(self) -> None:
        with self._model.batch():
            for c in self._components:
                self._model.add_component(c)
            for conn in self._connections:
                self._model.add_connection(conn)

    def undo(self) -> None:
        with self._model.batch():
            for conn in reversed(self._connections):
                self._model.remove_connection(conn.id)
            for c in reversed(self._components):
                self._model.remove_component(c.id)
```

`QUndoStack.beginMacro` provides transactional rollback at the command layer; `model.batch()` provides signal coalescing at the model layer. The two compose without overlap.

### Subscriber exceptions during emission

A subscriber slot invoked during `modelChanged` emission may itself raise. The batch context manager MUST NOT let a subscriber exception mask a caller exception that triggered the exit. Required `__exit__` behavior:

```python
def __exit__(self, exc_type, exc_val, exc_tb):
    self._batch_depth -= 1
    if self._batch_depth == 0:
        change_set = self._build_change_set()
        if not change_set.is_empty():
            try:
                self.modelChanged.emit(change_set)
            except Exception:
                if exc_val is not None:
                    # Caller exception is propagating; do not mask it.
                    logger.exception(
                        "subscriber raised during batched modelChanged emission; "
                        "original mutation exception preserved"
                    )
                else:
                    raise
    return False  # propagate exc_val if any
```

Behavior summary:

| Caller raised? | Subscriber raised? | Outcome |
|---|---|---|
| No | No | Normal commit; signal fired. |
| No | Yes | Subscriber exception propagates to the caller. |
| Yes | No | Caller exception propagates; change_set was emitted. |
| Yes | Yes | Subscriber exception is logged via `logger.exception(...)`; caller exception propagates (not masked). |

Subscriber exceptions never roll back model state. Mode B's commit-what-was-done invariant is preserved regardless of subscriber failures.

## Alternatives Considered

### Alternative 1: Yol β — replay queued individual signals at batch exit

At batch end, replay all queued individual signals in order; do not introduce a 13th signal.

**Rejected because:**

* Loses the cumulative diff; subscribers wanting "what changed in this bulk op?" must reconstruct it from a stream.
* Paste/load with hundreds of mutations causes hundreds of synchronous slot calls at exit time, defeating the coalescing goal.
* Subscribers cannot perform a single bulk rebuild; each individual signal triggers an incremental update.

### Alternative 2: Mode A — transactional rollback inside batch

On exception, undo all mutations performed during the batch.

**Rejected because:**

* Requires a per-batch undo log decoupled from `QUndoStack`, duplicating ADR-005 work.
* `QUndoStack.beginMacro` already provides command-level transactional grouping with redo/undo integration.
* Phase 1 caller pattern: each user action wraps in one command; exceptions mid-action are rare and surface upstream. Mode B's propagation is sufficient.

### Alternative 3: Always emit `modelChanged`, never emit fine-grained signals

Remove the 12 individual signals; rebuild everything from change_set every time.

**Rejected because:**

* Drag-induced mutations would carry a change_set with one entry, forcing subscribers to look up `change_set.changed_components[0]` for every mouse-move tick.
* Loses the typed shape of `componentMoved(id, old_pos, new_pos)` from ADR-018 (animations, command merging).
* Existing UI design patterns (per-item handlers) would need a rewrite for no benefit on the common case.

### Alternative 4: Different signal names — `workspaceChanged`, `batchCompleted`, `bulkChange`

**Rejected because:**

* `workspaceChanged` is acceptable but slightly more verbose; `modelChanged` matches the convention of `modelReset` (also defined on the same model).
* `batchCompleted` exposes the implementation mechanism (batch context) rather than the semantic intent (the model changed).
* `bulkChange` is unconventional for a Qt signal and reads as a verb rather than a state notification.

`modelChanged` is the chosen name because it pairs cleanly with `modelReset` and reads as "the model has changed; here's the diff."

## Consequences

### Positive

* Bulk operations (load, paste, reset, multi-step edits) trigger one signal and one rebuild, not N.
* Subscribers wanting a cumulative diff get one ready-made; no reconstruction.
* The mutual-exclusivity rule (fine-grained XOR `modelChanged`) prevents double-handling.
* Mode B + `QUndoStack.beginMacro` cleanly separates signal coalescing from transactional grouping.
* `WorkspaceChangeSet` is a frozen dataclass; safe to share across slots.
* Validation deferral aligns with §20.6 debouncing intent: bulk operations produce one validation pass instead of N.
* Subscriber-exception masking rule preserves caller-exception propagation under failure.

### Negative

* Two subscription paths to reason about; widgets needing both must subscribe twice.
* `02 §4.1` grows from 12 to 13 signals; spec must be updated.
* Subscribers that only listen to `componentAdded` will miss components added inside a batch — this is by design but is a real footgun. The subscriber rule above is the mitigation.
* Diff aggregation discards per-mutation deltas (e.g., move old/new) across a batch; subscribers needing those must use fine-grained signals, which means avoiding batch.

### Risks

* A subscriber forgets to handle `modelChanged` and silently misses bulk additions.
* *Mitigation:* `BlockDiagramWorkspaceScene` is the canonical "both" example; reviewers check new subscribers against the rule. A future architecture test could verify scene-level subscribers connect to both.
* Future async/threaded mutation breaks the synchronous refetch guarantee from ADR-018; `change_set` would need snapshot semantics.
* *Mitigation:* deferred to a future ADR amendment, same trigger as ADR-018's multi-threaded gate.
* `reset_required=True` discards a partial diff; a subscriber depending on partial info would break.
* *Mitigation:* explicitly documented; subscribers must check `reset_required` first before reading other fields.
* A subscriber raising during `modelChanged` emission could swallow a caller exception under naïve `__exit__` implementations.
* *Mitigation:* the explicit `__exit__` skeleton above; unit tests for the four caller/subscriber exception combinations.

## Related ADRs

- ADR-003 Workspace UI/Data Separation (subscriber-side rule)
- ADR-005 Command Stack with QUndoStack (transactional grouping via `beginMacro/endMacro`)
- ADR-018 WorkspaceModel Signal Payload Contracts (defines the 12 fine-grained signals; this ADR adds the 13th)
- ADR-020 Dirty Tracking Semantics (`dirty_changed` aggregate flag in change_set)

## References

- `02_workspace_requirements.md` §4.1 (Required Workspace Signals; this ADR extends to 13), §4.2 (UI Reaction Rules), §20.6 (Validation Timing and Debouncing), §22.2 (Atomic deletion), §29.7 (Dirty State Semantics)
- `06_data_flow_and_architecture.md` §4.2 (SystemModelingModule responsibilities)
- `07_implementation_order.md` §7.8 (S1 WorkspaceModel)
