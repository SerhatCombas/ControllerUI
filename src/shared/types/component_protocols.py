"""Cross-feature read-only Protocols for workspace component access.

Defines the minimal structural views that consumers outside
`SystemModelingModule` need over a `ComponentInstance` (or any
duck-typed equivalent). Each Protocol exposes **only** the fields a
validator demonstrably reads — adding fields preemptively turns the
Protocol into a shadow copy of `ComponentInstance` and defeats the
boundary it exists to enforce.

Currently exposed:

* `ComponentInstanceLike` — surfaces `definition_id`, the only field
  required by `ControllerDesignModule.ConfigurationValidator` for
  stale-port-reference checks.

When a new validator or downstream consumer needs an additional
field, add it here with a one-line justification — not as
speculative future-proofing.

References:
----------
* `decisions/ADR-018-signal-payload-contracts.md`
  ("subscribers refetch via model query")
* `specs/06_data_flow_and_architecture.md` §4.3 (cross-module access
  is read-only and goes through `shared/` types)
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class ComponentInstanceLike(Protocol):
    """Minimal read-only view of a workspace component instance.

    Implementers expose only the fields cross-feature consumers
    actually need. The canonical implementation is
    `features.SystemModelingModule.model.component_instance.ComponentInstance`
    (which already exposes `definition_id: str`); test fixtures
    can satisfy the Protocol with any duck-typed stand-in.

    The `@runtime_checkable` decorator lets test code use
    `isinstance(value, ComponentInstanceLike)` for sanity checks.
    Note that this only verifies presence of `definition_id`, not
    its type — `mypy` enforces typing at compile time.
    """

    @property
    def definition_id(self) -> str:
        """Dotted-namespace id of the component's `ComponentDefinition`."""
        ...


__all__ = ["ComponentInstanceLike"]
