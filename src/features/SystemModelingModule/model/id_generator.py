"""WorkspaceIdGenerator: ULID + display-counter id generation.

Generates the three identity field families described in ADR-002 / `02 §8`:

* internal IDs — prefixed ULIDs (`cmp_<ULID>`, `con_<ULID>`); never reused.
* display IDs — readable counters: per-type for components (`resistor_3`),
  global for connections (`conn_12`).

This generator is **session-scoped**: each `WorkspaceModel` instance owns
exactly one generator. Counter state is *derived* state, not a source of
truth — `WorkspaceModel.components` / `.connections` remain authoritative
per ADR-003. After a load or partial recovery the model calls
`rebuild_counters_from(...)` so the generator continues from the right
high-water mark (`02 §8.3`, §8.8).

The generator is intentionally type-slug-agnostic for components: the
caller passes the slug (e.g., the last segment of `definition_id`). This
keeps the slug-derivation rule out of the generator and prevents future
slug-rule changes from rippling here.

References:
----------
* `decisions/ADR-002-hybrid-ulid-identity-model.md`
* `decisions/ADR-003-workspace-ui-data-separation.md`
* `specs/02_workspace_requirements.md` §8.2 (Internal ID Format)
* `specs/02_workspace_requirements.md` §8.3 (Display ID Policy)
* `specs/02_workspace_requirements.md` §8.6 (Connection IDs)
* `specs/02_workspace_requirements.md` §8.8 (Display ID Collision Handling)
* `specs/09_coding_standards.md` §7.2.1 (Component IDs)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ulid import ULID

if TYPE_CHECKING:
    from collections.abc import Iterable

    from .component_instance import ComponentInstance
    from .connection import Connection


logger = logging.getLogger(__name__)


# Internal-ID prefixes per `02 §8.2`.
_COMPONENT_ID_PREFIX = "cmp_"
_CONNECTION_ID_PREFIX = "con_"

# Display-ID prefix for connections per `02 §8.6` (`conn_12`).
# Note the asymmetry with the internal-ID prefix `con_`.
_CONNECTION_DISPLAY_PREFIX = "conn"


class WorkspaceIdGenerator:
    """Owns ULID and display-counter generation for a single workspace.

    Counter state is private; the canonical state lives in the
    `WorkspaceModel`'s components and connections dictionaries. This
    object can be rebuilt from those at any time, which is the only
    persistence story the generator needs.

    Attributes:
        _component_counters: Mapping of component type slug to the
            highest counter value already issued for that slug.
        _connection_counter: Highest connection display counter
            already issued. Connections share a single global counter
            per `02 §8.6`.
    """

    def __init__(self) -> None:
        """Initialize an empty generator with all counters at zero."""
        self._component_counters: dict[str, int] = {}
        self._connection_counter: int = 0

    # ------------------------------------------------------------------ #
    # Internal IDs (ULID-prefixed, stable, never reused)
    # ------------------------------------------------------------------ #

    def new_component_id(self) -> str:
        """Return a fresh internal component ID.

        Returns:
            ULID with the `cmp_` prefix
            (e.g., `"cmp_01HV7N9G8K4QZ7R2M6P3A1B9C0"`). Generated at
            instance creation; never reused per `02 §8.2`.
        """
        return f"{_COMPONENT_ID_PREFIX}{ULID()}"

    def new_connection_id(self) -> str:
        """Return a fresh internal connection ID.

        Returns:
            ULID with the `con_` prefix
            (e.g., `"con_01HV7NA2K8M4X7GQ1DR9V5M2F6"`). Note the
            display-ID counterpart uses the `conn_` prefix per
            `02 §8.6`.
        """
        return f"{_CONNECTION_ID_PREFIX}{ULID()}"

    # ------------------------------------------------------------------ #
    # Display IDs (human-readable, monotonic counters)
    # ------------------------------------------------------------------ #

    def next_component_display_id(self, type_slug: str) -> str:
        """Return the next monotonic display ID for a component type.

        The slug is treated as opaque text. The caller decides the
        slug-derivation rule (typically the last segment of
        `definition_id`); the generator only tracks counters by slug.

        Counters are monotonic and never reissued for the same slug,
        even after deletes (`02 §8.3`): if `resistor_2` is deleted,
        the next resistor still gets `resistor_3`.

        Args:
            type_slug: Component type identifier as a snake_case slug
                (e.g., `"resistor"`, `"voltage_source"`). Empty string
                is permitted but should be avoided in production.

        Returns:
            Display ID of the form `f"{type_slug}_{n}"` where `n` is
            the next counter value (1-based).
        """
        next_n = self._component_counters.get(type_slug, 0) + 1
        self._component_counters[type_slug] = next_n
        return f"{type_slug}_{next_n}"

    def next_connection_display_id(self) -> str:
        """Return the next monotonic display ID for a connection.

        Connections share a single global counter (not per-type) per
        `02 §8.6`. The display prefix is `conn_` regardless of the
        internal-ID prefix `con_`.

        Returns:
            Display ID of the form `f"conn_{n}"` (e.g., `"conn_12"`).
        """
        self._connection_counter += 1
        return f"{_CONNECTION_DISPLAY_PREFIX}_{self._connection_counter}"

    # ------------------------------------------------------------------ #
    # Recovery
    # ------------------------------------------------------------------ #

    def rebuild_counters_from(
        self,
        components: Iterable[ComponentInstance],
        connections: Iterable[Connection],
    ) -> None:
        """Reset and reconstruct counters from existing entities.

        Used after project load and after partial recovery (`02 §8.3`,
        `02 §8.8`). For each entity, parses the trailing integer from
        its `display_id` and updates the corresponding counter to the
        maximum value seen. Malformed display IDs are logged at
        WARNING and skipped; they do not abort recovery.

        Counter state is fully reset before parsing — this method is
        idempotent and may be called multiple times.

        Args:
            components: Iterable of `ComponentInstance` objects
                (typically `WorkspaceModel.components.values()`).
            connections: Iterable of `Connection` objects (typically
                `WorkspaceModel.connections.values()`).

        See Also:
            `02 §8.3` last bullet (counter reconstruction
            requirement); `02 §8.8` (corrupted display ID handling).
        """
        self._component_counters.clear()
        self._connection_counter = 0

        for component in components:
            parsed = _parse_display_id(component.display_id)
            if parsed is None:
                logger.warning(
                    "Skipping malformed component display_id during recovery",
                    extra={
                        "event": "id_generator.malformed_display_id",
                        "component_id": component.id,
                        "display_id": component.display_id,
                    },
                )
                continue
            slug, n = parsed
            current = self._component_counters.get(slug, 0)
            if n > current:
                self._component_counters[slug] = n

        for connection in connections:
            parsed = _parse_display_id(connection.display_id)
            if parsed is None:
                logger.warning(
                    "Skipping malformed connection display_id during recovery",
                    extra={
                        "event": "id_generator.malformed_display_id",
                        "connection_id": connection.id,
                        "display_id": connection.display_id,
                    },
                )
                continue
            slug, n = parsed
            if slug != _CONNECTION_DISPLAY_PREFIX:
                logger.warning(
                    "Connection display_id has unexpected prefix; " "still using its counter",
                    extra={
                        "event": "id_generator.unexpected_connection_prefix",
                        "connection_id": connection.id,
                        "display_id": connection.display_id,
                        "expected_prefix": _CONNECTION_DISPLAY_PREFIX,
                        "found_prefix": slug,
                    },
                )
            if n > self._connection_counter:
                self._connection_counter = n


def _parse_display_id(display_id: str) -> tuple[str, int] | None:
    """Parse a display ID into `(slug, counter)` or return None.

    Display IDs follow the convention `<slug>_<integer>` where the slug
    itself may contain underscores (e.g., `voltage_source_42` parses to
    `("voltage_source", 42)`). The split is right-anchored so the
    integer is always the rightmost component.

    Returns `None` if the input is empty, has no underscore, or the
    suffix is not a valid non-negative integer.
    """
    if not display_id or "_" not in display_id:
        return None
    slug, _, suffix = display_id.rpartition("_")
    if not slug or not suffix.isdigit():
        return None
    return slug, int(suffix)


__all__ = [
    "WorkspaceIdGenerator",
]
