# Finding: PySide6 Signal Exception Dispatch (S1.3d)

**Type:** Finding (non-ADR; candidate input for a future ADR)
**Date:** 2026-05-10
**Discovered during:** S1.3d implementation (`batch()` + `modelChanged`)
**Status:** Open — runtime-inactive guard documented, no formal decision yet
**Related:** ADR-019 §"Subscriber exceptions during emission"

This file follows the precedent set by
`decisions/2026-05-05_s3-s5-handoff-design.md`: a dated lowercase
filename for non-ADR design notes that live alongside the formal ADR
catalog. It is **not** an ADR — `decisions/README.md` says ADRs are
immutable and capture decisions; this file captures a finding that
may inform a future decision.

## Background

ADR-019 §"Subscriber exceptions during emission" specifies the
following four-row truth table for caller × subscriber exception
interaction during `WorkspaceModel.modelChanged` emission inside
`_batch_exit`:

| Case | Caller exception | Subscriber exception | Specified outcome |
|---|---|---|---|
| 1 | – | – | Normal emission. |
| 2 | – | raises | Subscriber exception propagates to the caller of `with`. |
| 3 | raises | – | Caller exception propagates; change_set was emitted before. |
| 4 | raises | raises | Subscriber exception is logged via `logger.exception`; caller exception propagates (no masking). |

The ADR codifies this with a `__exit__` skeleton wrapping
`self.modelChanged.emit(change_set)` in `try/except` and dispatching
on `exc_val`:

```python
try:
    self.modelChanged.emit(change_set)
except Exception:
    if exc_val is not None:
        logger.exception("subscriber raised...; original preserved")
    else:
        raise
```

`WorkspaceModel._batch_exit` (S1.3d) implements this skeleton
faithfully.

## Finding

Under **PySide6's default signal dispatch**, subscriber exceptions
raised inside a Qt slot connected to `modelChanged` are **caught by
the Qt event loop** and routed to `sys.excepthook`. They do **not**
propagate back through `signal.emit()` to the emitting code's
`try/except` block.

Verified empirically during S1.3d test development:

* `pytest.raises(RuntimeError, ...)` around `with model.batch(): ...`
  with a subscriber that raises `RuntimeError` does **not** trigger.
* The `RuntimeError` instead surfaces in pytest's captured stderr
  as: `Exceptions caught in Qt event loop: ... RuntimeError: ...`.

Reproducible at PySide6 6.8.3 / Qt 6.8.3 / Python 3.13 on macOS
(observed in CI / local). No PySide6 documentation flag changes the
default in a way obviously usable from Python without subclassing or
custom dispatch infrastructure.

## Implication

ADR-019's truth-table cases 2 and 4 are **not exercisable** under
PySide6 defaults. The `try/except` block in `_batch_exit` is
**runtime-inactive**: the `except` branch never fires because the
subscriber exception is intercepted upstream by Qt.

Concretely:

* Case 1 (no exceptions) and case 3 (caller raises, no subscriber
  exception) are unit-testable and tested in
  `tests/features/SystemModelingModule/model/test_workspace_model_batch.py`.
* Case 2 cannot be tested: the subscriber exception bypasses
  `_batch_exit`'s `try/except` entirely.
* Case 4 cannot be tested: same reason. The "no masking" guarantee
  is technically held (because `try/except` never runs), but it is
  held by accident, not by the guard.

The dead code is preserved per ADR-019 fidelity (the ADR specifies
the skeleton; removing it would require an ADR amendment, which is
forbidden under `decisions/README.md`'s immutability rule). An
inline `NOTE` comment in `_batch_exit` is added in a follow-up
commit pointing readers here.

## Why this is a finding, not an ADR

* No decision has been made yet about how to resolve the gap.
  ADRs capture decisions; this captures a constraint we discovered.
* Three plausible responses exist (see below); choosing among them
  requires more context (S1.7 command-stack work, S2 persistence,
  whether multi-threaded mutation lands in Phase 2 or later).
* Recording the constraint now is the goal; deferring the decision
  is acceptable.

## Possible future paths

If/when this finding warrants a formal ADR (likely **ADR-021**),
candidates include:

**Path A — Custom signal dispatcher.** Replace or wrap PySide6's
default `Signal.emit` with a dispatcher that catches slot
exceptions and surfaces them to the emitting code. Plausible
implementations: a manual callback list maintained on `WorkspaceModel`
beside the Qt signal, or a `Qt.DirectConnection`-based pattern with
`sys.excepthook` interception. Cost: parallel infrastructure to
maintain; risk of behavior divergence between fine-grained signals
(still PySide6-native) and `modelChanged` (custom-dispatched).

**Path B — Narrow ADR-019 via ADR-021.** Formally restrict
ADR-019's masking-guard guarantee to cases 1 and 3 under PySide6
defaults; declare cases 2 and 4 as out of scope and supersede the
`try/except` skeleton requirement. The dead code can then be
removed cleanly. Lowest implementation cost; clearest contract.

**Path C — Reassess as part of Phase 2/3 multi-threaded work.**
ADR-018 §"Multi-threaded mutation" already defers cross-thread
emission to a future amendment. If that amendment introduces a
custom dispatcher (Path A), this finding folds into the same
work. If it doesn't, Path B becomes the natural resolution.

## What to verify before deciding

* Whether PySide6 subclassing (`Signal.emit` override on a custom
  signal type) can intercept slot exceptions without rebuilding
  signal infrastructure.
* Whether the `Qt.AutoConnection` → `Qt.DirectConnection` distinction
  affects the dispatch path (default for same-thread same-Qt-thread
  is Direct, which is what we tested; cross-thread Queued may
  behave differently).
* Whether `sys.excepthook` overrides give us a usable hook to
  re-route subscriber exceptions back to the emitter — combined
  with thread-local context to know which `_batch_exit` is in
  flight.

## What this finding does NOT change

* `_batch_exit`'s code stays as written for ADR-019 fidelity.
* The test file documents the limitation in its module docstring;
  cases 2 and 4 are explicitly omitted, not silently skipped.
* No spec or ADR is amended.

## Cross-references

* `decisions/ADR-019-batch-mutation-and-changeset.md` §"Subscriber
  exceptions during emission".
* `decisions/ADR-018-signal-payload-contracts.md` §"Multi-threaded
  mutation" (related deferred concern).
* `src/features/SystemModelingModule/model/workspace_model.py`
  `_batch_exit` method — the masking guard implementation.
* `tests/features/SystemModelingModule/model/test_workspace_model_batch.py`
  module docstring — runtime documentation of the limitation.
