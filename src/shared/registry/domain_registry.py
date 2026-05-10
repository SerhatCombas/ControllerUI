"""DomainRegistry: supported domains and compatibility rules.

Per `02 §13.2` and `02 §35`. The registry holds the set of
supported `DomainId` values and answers compatibility queries
between domains. Phase 1 compatibility is trivial — same-domain
only, per `02 §13.2` "A port belongs to exactly one domain" and
`02 §18.1` "All ports in an implicit node must belong to the
same domain". Cross-domain components (`02 §18.2`) declare
per-port domains independently; the registry's
`are_compatible(a, b)` does NOT make cross-domain components a
special case at this layer.

Phase 1 supported domains:

* `electrical_analog`
* `mechanical_translational`

Future Phase 1.5+ additions are gated on a new ADR per `02 §35`
(Domain Extensibility). Until then, the registry rejects domain
strings that are not declared in its supported set.

Instance pattern (S1.B.1b decision, matching `ComponentRegistry`):
callers construct `DomainRegistry(supported_domains)` with their
own set. Default Phase 1 set is provided by
`shared/registry/__init__.py` factory helpers (S1.B.1c+).

References:
----------
* `specs/02_workspace_requirements.md` §13.2 (Domain Rule),
  §18.1 (Node Domain Rule), §18.2 (Cross-Domain Components),
  §35 (Domain Extensibility)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

    from shared.types.domain import DomainId


class DomainRegistry:
    """Holds supported domain identifiers and compatibility rules.

    Phase 1 surface is intentionally small: `supported()`,
    `is_supported(domain)`, and `are_compatible(a, b)`. Future
    extensions (e.g., domain-pair-specific coupling rules) will
    add named methods rather than overloading these three.
    """

    def __init__(self, supported_domains: Iterable[DomainId]) -> None:
        """Build a registry from an iterable of supported domains.

        Args:
            supported_domains: Domain identifiers to register.
                Iterated once. Order is preserved for `supported()`
                enumeration.

        Raises:
            ValueError: If a domain identifier is registered twice
                in `supported_domains`.
        """
        seen: dict[DomainId, None] = {}
        for domain in supported_domains:
            if domain in seen:
                raise ValueError(f"duplicate domain id: '{domain}'")
            seen[domain] = None
        # `tuple(seen)` preserves insertion order and is immutable.
        self._supported: tuple[DomainId, ...] = tuple(seen)

    def supported(self) -> tuple[DomainId, ...]:
        """Return the supported domain identifiers in registration order."""
        return self._supported

    def is_supported(self, domain: str) -> bool:
        """Return True iff `domain` is in the supported set.

        Accepts `str` (not just `DomainId`) so callers passing
        arbitrary user input get a safe boolean rather than a type
        error.
        """
        return domain in self._supported

    def are_compatible(self, domain_a: DomainId, domain_b: DomainId) -> bool:
        """Return True iff two ports of these domains may be connected.

        Phase 1 rule (per `02 §13.2`, `02 §18.1`): same-domain only.
        Cross-domain coupling lives inside multi-domain components
        per `02 §18.2`; the connection layer never merges across
        domains.

        Future Phase 1.5+ additions may admit specific cross-domain
        pairs (e.g., signal-input / signal-output bridging); each
        such addition requires an ADR per `02 §35` and a widening of
        this method's logic.
        """
        return domain_a == domain_b


__all__ = ["DomainRegistry"]
