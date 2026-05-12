"""WorkspaceReactivityObserver: stale-detection bridge (S2.B.3).

Subscribes to `SystemModelingModule.WorkspaceModel`'s lifecycle
signals (duck-typed — no cross-feature import) and mutates
`ControllerDesignModule.ConfigurationModel.io_selection` so I/O
entries referencing removed workspace components get their
`status` flipped to `"stale"` per spec/03 §6.7 and spec/06 §4.3.2.

The observer is the **mutation side** of the validation pair:

* `ConfigurationValidator` (S2.B.2) reports stale references
  on-demand from a snapshot — pure function, no state change.
* `WorkspaceReactivityObserver` (this file) reacts to workspace
  events in real time — mutates `IOEntry.status` so the model
  reflects current truth even when no validation pass has run.

The observer does **not** push to the command stack: stale-flip is
not a user action, it is the deterministic consequence of a
workspace mutation. Recording it as undoable would let the user
"undo a staleness" without resurrecting the referenced component,
producing inconsistent state. (See the S2.B.3 design discussion in
the project history.)

Cross-module boundary discipline:

* The observer takes the workspace model **by duck-typed
  signal interface**, not by `WorkspaceModel` type — no
  `features.SystemModelingModule.*` import.
* The observer writes through `ConfigurationModel.set_io_selection`,
  which preserves the transition-only signal contract (ADR-020).

Phase 1 scope: `componentRemoved` only. Phase 2 candidates
(`componentChanged` for port-set changes, `connectionRemoved` if I/O
entries grow to reference connection ids) extend the same class
with new `_on_*` slots; the public attach API stays stable.

References:
----------
* `specs/06_data_flow_and_architecture.md` §4.3.2
* `specs/03_configuration_requirements.md` §6.7
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject

from features.ControllerDesignModule.model.io_selection import (
    IOEntry,
    IOSelection,
    IOSourcePortRef,
)

if TYPE_CHECKING:
    from features.ControllerDesignModule.model.configuration_model import (
        ConfigurationModel,
    )


logger = logging.getLogger(__name__)


class WorkspaceReactivityObserver(QObject):
    """Reactive bridge from workspace lifecycle events to I/O staleness.

    Args:
        configuration: The `ConfigurationModel` whose `io_selection`
            this observer mutates. The observer holds a reference;
            the model is expected to outlive the observer in normal
            Qt parent ownership.
        parent: Optional Qt parent. Defaults to `None`; the
            application shell typically passes the
            `ConfigurationModel` itself so the observer participates
            in the same lifetime.

    The observer does not subscribe at construction. Call
    `attach_to_workspace_signals(workspace_model)` after the
    workspace model exists. This split lets tests construct the
    observer with a stub QObject and lets the shell wire signals
    after both layers have been instantiated.
    """

    def __init__(
        self,
        *,
        configuration: ConfigurationModel,
        parent: QObject | None = None,
    ) -> None:
        """Bind the observer to a configuration model (no subscription yet)."""
        super().__init__(parent)
        self._configuration: ConfigurationModel = configuration

    @property
    def configuration(self) -> ConfigurationModel:
        """The `ConfigurationModel` this observer mutates (test convenience)."""
        return self._configuration

    # ------------------------------------------------------------------ #
    # Subscription
    # ------------------------------------------------------------------ #

    def attach_to_workspace_signals(self, workspace_model: QObject) -> None:
        """Subscribe to the workspace model's `componentRemoved` signal.

        `workspace_model` is typed `QObject` rather than
        `WorkspaceModel` so this module never imports across the
        feature boundary. The duck-typed `componentRemoved`
        attribute is the only field the observer touches; passing
        an object without that signal raises `AttributeError` at
        connect time, which is the right "fail-fast" behavior for
        a wiring bug.
        """
        # Phase 1: only `componentRemoved` triggers stale flips.
        # Phase 2 will add `componentChanged` (port-set change can
        # invalidate a port reference even if the component still
        # exists) and possibly `connectionRemoved`.
        workspace_model.componentRemoved.connect(  # type: ignore[attr-defined]
            self._on_component_removed
        )

    # ------------------------------------------------------------------ #
    # Slots
    # ------------------------------------------------------------------ #

    def _on_component_removed(self, component_id: str) -> None:
        """Flip every IOEntry referencing `component_id` to `status="stale"`.

        Walks the current `IOSelection.inputs` + `.outputs`, builds
        a new `IOSelection` with each referencing entry's `status`
        set to `"stale"`, and pushes the result through
        `ConfigurationModel.set_io_selection`. If no entry
        references the removed component, no mutation is performed
        and no signal fires (transition-only contract).

        Re-removal of an already-removed component (defensive
        case — the workspace should not emit twice for the same id,
        but stub clients in tests can) is idempotent: entries are
        already stale, the new value equals the old, and
        `set_io_selection` skips emission.
        """
        current = self._configuration.io_selection
        new_inputs = tuple(
            _mark_stale_if_referenced(entry, component_id) for entry in current.inputs
        )
        new_outputs = tuple(
            _mark_stale_if_referenced(entry, component_id) for entry in current.outputs
        )
        if new_inputs == current.inputs and new_outputs == current.outputs:
            # Nothing to do — no entry referenced this component.
            return
        new_selection = IOSelection(
            inputs=new_inputs,
            outputs=new_outputs,
            metadata=current.metadata,
            extensions=current.extensions,
        )
        logger.info(
            "Marking I/O entries stale after component removal",
            extra={"component_id": component_id},
        )
        self._configuration.set_io_selection(new_selection)


# ====================================================================== #
# Helpers
# ====================================================================== #


def _mark_stale_if_referenced(entry: IOEntry, removed_id: str) -> IOEntry:
    """Return a new entry with `status="stale"` if it points at `removed_id`.

    Other source variants (Phase 2 probe_ref, state_variable_ref,
    etc.) are left untouched: their stale-detection rules live in
    their own observers when they land. The Phase-1 `IOSource` alias
    is `IOSourcePortRef`; mypy narrows accordingly. The runtime
    `isinstance` check is kept defensive for the day the union
    widens.
    """
    source = entry.source
    if not isinstance(source, IOSourcePortRef):
        return entry  # type: ignore[unreachable]
    if source.port_ref.component_id != removed_id:
        return entry
    if entry.status == "stale":
        return entry
    return entry.with_updated(status="stale")


__all__ = ["WorkspaceReactivityObserver"]
