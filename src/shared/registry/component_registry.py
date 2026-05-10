"""ComponentRegistry: in-memory store of `ComponentDefinition`s.

Per `01 §1.114` and ADR-021. The registry is the runtime entry
point for definition lookup; UI panels, mutation methods, and the
graph validator / assembler each consume the registry through one
or more of the lookup methods declared here.

Phase 1 instance pattern (S1.B.1b decision): callers construct
their own `ComponentRegistry(BUILTIN_DEFINITIONS)`. There is no
global singleton or lazy bootstrap function — every consumer
either accepts the registry as a constructor argument or asks the
application bootstrap layer for one. This makes tests trivial to
isolate (each test builds its own registry from explicit
definitions) and keeps the future plugin path additive (a
plugin-loading variant of the constructor goes in alongside the
default, no flow change for existing callers).

References:
----------
* `specs/01_library_requirements.md` §1.114 (registry bootstrap),
  §6 (Component Definition Schema)
* `specs/06_data_flow_and_architecture.md` §5.2 (shared/registry)
* `decisions/ADR-021-builtin-component-definitions.md`
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .port_definition import PortDefinition  # noqa: TCH001 — used in return type

if TYPE_CHECKING:
    from collections.abc import Iterable

    from shared.types.domain import DomainId

    from .component_definition import ComponentDefinition


class ComponentRegistry:
    """In-memory store for component definitions.

    Order of definitions is preserved in insertion order (Python
    `dict` semantics, 3.7+). Lookup methods raise `KeyError` on
    miss; the constructor raises `ValueError` on duplicate ids at
    bootstrap time (fail-fast).

    The registry is **immutable from outside**: there is no public
    `register` / `unregister` / `update` API in Phase 1.
    Construction-time only. Future plugin support will add an
    explicit reload entry point rather than mutating in place.

    Attributes (read-only):
        — none publicly exposed. All access goes through methods.
    """

    def __init__(self, definitions: Iterable[ComponentDefinition]) -> None:
        """Build a registry from an iterable of definitions.

        Args:
            definitions: Definitions to register. Iterated once.
                Order is preserved for `all()` enumeration.

        Raises:
            ValueError: If two definitions share the same `id`.
                Bootstrap fails fast — the registry never enters a
                half-populated state.
        """
        self._definitions: dict[str, ComponentDefinition] = {}
        for definition in definitions:
            if definition.id in self._definitions:
                raise ValueError(f"duplicate component definition id: '{definition.id}'")
            self._definitions[definition.id] = definition

    # ------------------------------------------------------------------ #
    # Primary lookup
    # ------------------------------------------------------------------ #

    def get(self, definition_id: str) -> ComponentDefinition:
        """Return the definition with the given id.

        Args:
            definition_id: Dotted-namespace id (e.g.,
                `"electrical.analog.components.resistor"`).

        Returns:
            The `ComponentDefinition` registered under `definition_id`.

        Raises:
            KeyError: If `definition_id` is not registered.
        """
        try:
            return self._definitions[definition_id]
        except KeyError:
            raise KeyError(definition_id) from None

    def has(self, definition_id: str) -> bool:
        """Return True iff `definition_id` is registered."""
        return definition_id in self._definitions

    def all(self) -> tuple[ComponentDefinition, ...]:
        """Return all registered definitions in insertion order."""
        return tuple(self._definitions.values())

    # ------------------------------------------------------------------ #
    # Filtered views
    # ------------------------------------------------------------------ #

    def by_domain(self, domain: DomainId) -> tuple[ComponentDefinition, ...]:
        """Return definitions whose primary `domain` matches.

        Multi-domain components (per `02 §18.2`) are returned under
        their declared `domain` field, which is the principal /
        library-categorization domain. Per-port domain queries use
        `port_definition(...).domain` directly.

        Args:
            domain: Domain identifier (Literal).

        Returns:
            Tuple of matching definitions, in registration order.
        """
        return tuple(d for d in self._definitions.values() if d.domain == domain)

    def by_library_path(
        self,
        path: tuple[str, ...] = (),
    ) -> tuple[ComponentDefinition, ...]:
        """Return definitions whose `library_path` starts with `path`.

        The default `path=()` returns every registered definition,
        matching `all()`. A specific prefix (e.g.,
        `("Electrical",)`) narrows the result to that library
        subtree.

        Args:
            path: Library-path prefix. Empty tuple matches all.

        Returns:
            Tuple of definitions whose `library_path[:len(path)] ==
            path`, in registration order.
        """
        prefix_len = len(path)
        return tuple(d for d in self._definitions.values() if d.library_path[:prefix_len] == path)

    # ------------------------------------------------------------------ #
    # Port-level lookup (used by validator / assembler wiring in S1.B.1d)
    # ------------------------------------------------------------------ #

    def port_definition(
        self,
        definition_id: str,
        port_id: str,
    ) -> PortDefinition:
        """Return the `PortDefinition` for the given component + port.

        Used by callers that build the `port_lookup` callable for
        `GraphValidator` / `GraphAssembler` (S1.B.1d wiring).

        Args:
            definition_id: Component definition id.
            port_id: Port id within that definition.

        Returns:
            The matching `PortDefinition`.

        Raises:
            KeyError: If either `definition_id` is unregistered or
                `port_id` is not declared on the resolved
                definition.
        """
        definition = self.get(definition_id)  # KeyError if missing
        for port in definition.ports:
            if port.id == port_id:
                return port
        raise KeyError(f"port '{port_id}' not declared on component '{definition_id}'")


__all__ = ["ComponentRegistry"]
