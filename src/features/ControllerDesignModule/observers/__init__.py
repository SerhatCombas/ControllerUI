"""ControllerDesignModule cross-module reactivity observers (S2.B.3+).

Holds the observer classes that subscribe to other features' Qt
signals and react by mutating ControllerDesignModule state. The
sub-package exists so the cross-module boundary surface is visible
at the directory level rather than buried inside `model/`:

* `model/` — internal data layer (frozen value types + the QObject
  host that owns them)
* `observers/` — bridge layer; reads other features via signal
  subscription (duck-typed) and writes through `ConfigurationModel`

Phase 1 contents:

* `WorkspaceReactivityObserver` — subscribes to
  `WorkspaceModel.componentRemoved` and flips `IOEntry.status` to
  `"stale"` for affected entries (S2.B.3).

Phase 2+ candidates:

* Controller-runtime observer (S5)
* Simulation-state observer

References:
----------
* `specs/06_data_flow_and_architecture.md` §4.3.2
  (Cross-Module Reference Handling)
* `specs/03_configuration_requirements.md` §6.7
  (Stale Reference Handling)
"""

from .workspace_reactivity_observer import WorkspaceReactivityObserver

__all__ = ["WorkspaceReactivityObserver"]
