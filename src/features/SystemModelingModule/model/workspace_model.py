"""WorkspaceModel: source-of-truth for workspace state.

The single source of truth for placed components, connections, and the
dirty flag. UI subscribes to its signals (added in S1.3c+); widgets
never store canonical data per ADR-003. Per ADR-018 / ADR-019 / ADR-020
the model will eventually emit 13 signals — 12 fine-grained signals for
individual mutations and one coarse-grained `modelChanged` signal for
batch operations.

This file is part of the data layer. It must not import any Qt UI
classes. Importing `QObject` from `PySide6.QtCore` is permitted because
change notification is the cross-layer interface (ADR-003).

Phase 1 build order within S1.3:

* S1.3a (this commit): skeleton — constructor, internal stores,
  dirty flag, read-only views, internal builders that produce frozen
  dataclass instances. No public mutation API yet, no signals yet.
* S1.3b: equality helpers (`_approx_equal_qpointf`,
  `_approx_equal_float`) for ε=1e-6 no-op suppression.
* S1.3c: 12 fine-grained signals (ADR-018) + public mutation methods
  (add/remove/move/rotate/connect/...). No-op suppression with
  ε=1e-6 tolerance per ADR-020.
* S1.3d: `batch()` context manager + `WorkspaceChangeSet` + 13th
  signal `modelChanged` per ADR-019.
* S1.3e: `reset()` + `modelReset()` signal emission.

References:
----------
* `decisions/ADR-003-workspace-ui-data-separation.md`
* `decisions/ADR-018-signal-payload-contracts.md`
* `decisions/ADR-019-batch-mutation-and-changeset.md`
* `decisions/ADR-020-dirty-tracking-semantics.md`
* `specs/02_workspace_requirements.md` §3 (Source of Truth), §4 (Signals)
* `specs/06_data_flow_and_architecture.md` §4.2
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject

from .component_instance import (
    ComponentInstance,
    PhysicalAttributes,
    VisualSpec,
)
from .connection import (
    Connection,
    ConnectionRouting,
    PortRef,
)
from .id_generator import WorkspaceIdGenerator

if TYPE_CHECKING:
    from collections.abc import Mapping


class WorkspaceModel(QObject):
    """Source of truth for workspace state.

    Holds the canonical state of components, connections, and the
    dirty flag for a single workspace document. Per ADR-003 the model
    owns truth and the UI is a pure consumer; per ADR-005 user edits
    enter through `QUndoCommand` subclasses (S1.7 work) that call
    public mutation methods on this model. Per ADR-018 / ADR-019 /
    ADR-020 the model emits 13 signals total once S1.3 is complete —
    12 fine-grained signals for individual mutations and one
    coarse-grained `modelChanged` signal for batch operations.

    This S1.3a commit is the skeleton only: state container,
    read-only views, and internal builders that produce frozen
    dataclass instances. No public mutation API and no signals are
    defined yet; those land in S1.3b through S1.3e.

    Attributes:
        is_dirty: Read-only dirty flag per ADR-020. Cleared by
            `reset()` (S1.3e), save (S2), and undo-to-clean (S1.7).
        components: Read-only mapping of `cmp_<ULID>` → `ComponentInstance`.
        connections: Read-only mapping of `con_<ULID>` → `Connection`.

    See Also:
        `02 §3`, `02 §4`, ADR-003, ADR-018, ADR-019, ADR-020.
    """

    def __init__(self, parent: QObject | None = None) -> None:
        """Initialize an empty, clean workspace model.

        A freshly constructed model is clean (`is_dirty=False`) per
        ADR-020 §"Initial state". `dirtyChanged` is not emitted at
        construction time; subscribers read the initial state via the
        `is_dirty` property after wiring.

        Args:
            parent: Optional Qt parent; usually `None`. Provided for
                consistency with other `QObject` subclasses.
        """
        super().__init__(parent)
        self._components: dict[str, ComponentInstance] = {}
        self._connections: dict[str, Connection] = {}
        self._dirty: bool = False
        self._id_generator: WorkspaceIdGenerator = WorkspaceIdGenerator()

    # ------------------------------------------------------------------ #
    # Read-only views
    # ------------------------------------------------------------------ #

    @property
    def is_dirty(self) -> bool:
        """Current dirty bit per ADR-020.

        A newly constructed model is clean; the first meaningful edit
        (S1.3c) transitions to True, and `reset()` (S1.3e) transitions
        back to False.
        """
        return self._dirty

    @property
    def components(self) -> Mapping[str, ComponentInstance]:
        """Read-only mapping of `component_id` → `ComponentInstance`.

        Returned as a `MappingProxyType` so callers cannot mutate the
        underlying dict. Mutations go through the public mutation API
        (S1.3c+), which is the only sanctioned write path per ADR-003.
        """
        return MappingProxyType(self._components)

    @property
    def connections(self) -> Mapping[str, Connection]:
        """Read-only mapping of `connection_id` → `Connection`.

        Same immutability contract as `components`.
        """
        return MappingProxyType(self._connections)

    # ------------------------------------------------------------------ #
    # Internal builders
    #
    # These produce fresh frozen-dataclass instances with newly
    # generated identity fields and timestamps. They do NOT mutate
    # `_components` / `_connections` — that is the responsibility of
    # the public mutation API added in S1.3c.
    # ------------------------------------------------------------------ #

    def _build_component_instance(
        self,
        *,
        definition_id: str,
        type: str,
        display_name: str,
        domain: str,
        category: str,
        position: tuple[float, float],
        visual: VisualSpec,
        physical_attributes: PhysicalAttributes,
        custom_label: str = "",
        rotation: int = 0,
        parameters: Mapping[str, Any] | None = None,
        locked: bool = False,
        tags: tuple[str, ...] = (),
        annotations: Mapping[str, Any] | None = None,
        metadata: Mapping[str, Any] | None = None,
        extensions: Mapping[str, Any] | None = None,
    ) -> ComponentInstance:
        """Mint a fresh `ComponentInstance` with new identity and timestamps.

        Generates the internal ULID (`cmp_…`), the next monotonic
        display ID for the component type, and matching `created_at` /
        `modified_at` timestamps. The `type_slug` for display-counter
        lookup is taken as the last dotted segment of `definition_id`
        per the convention used by `WorkspaceIdGenerator`.

        The returned instance is **not** added to `_components`; the
        caller (the public mutation method `add_component`, S1.3c) is
        responsible for insertion. Splitting build from insert keeps
        ID generation testable in isolation and lets future commands
        construct candidate instances before deciding whether to
        commit.

        Args:
            definition_id: Dotted identifier of the source component
                definition (e.g., `"electrical.analog.components.resistor"`).
            type: Definition type label used for display.
            display_name: Human-readable definition name.
            domain: Physical domain identifier (e.g., `"electrical_analog"`).
            category: Library category from the definition.
            position: Scene-coordinate `(x, y)` of the component anchor.
            visual: SVG variant selector.
            physical_attributes: Declared physical-attribute flags.
            custom_label: Optional user-editable label. Defaults to "".
            rotation: Rotation in degrees. Defaults to 0.
            parameters: Optional parameter mapping. Copied to insulate
                callers from later mutations. Defaults to empty.
            locked: Initial locked state. Defaults to False.
            tags: Tuple of free-form tags.
            annotations: Optional annotations mapping. Copied.
            metadata: Optional metadata mapping. Copied.
            extensions: Optional extensions mapping. Copied.

        Returns:
            Newly constructed `ComponentInstance` with freshly minted
            `id`, `display_id`, `created_at`, and `modified_at`.
        """
        type_slug = definition_id.rsplit(".", 1)[-1]
        now = _now_iso8601()
        return ComponentInstance(
            id=self._id_generator.new_component_id(),
            display_id=self._id_generator.next_component_display_id(type_slug),
            definition_id=definition_id,
            type=type,
            display_name=display_name,
            domain=domain,
            category=category,
            position=position,
            visual=visual,
            physical_attributes=physical_attributes,
            custom_label=custom_label,
            rotation=rotation,
            parameters=dict(parameters) if parameters else {},
            locked=locked,
            tags=tags,
            annotations=dict(annotations) if annotations else {},
            metadata=dict(metadata) if metadata else {},
            extensions=dict(extensions) if extensions else {},
            created_at=now,
            modified_at=now,
        )

    def _build_connection(
        self,
        *,
        source: PortRef,
        target: PortRef,
        routing: ConnectionRouting | None = None,
        label: str = "",
        style: Mapping[str, Any] | None = None,
        metadata: Mapping[str, Any] | None = None,
        extensions: Mapping[str, Any] | None = None,
    ) -> Connection:
        """Mint a fresh `Connection` with new identity.

        Generates the internal ULID (`con_…`) and the next monotonic
        global display ID (`conn_<n>`). The returned instance is
        **not** added to `_connections`; the caller (public
        `add_connection`, S1.3c) is responsible for insertion.

        Args:
            source: Endpoint reference at the source side.
            target: Endpoint reference at the target side.
            routing: Optional routing specification. Defaults to a
                fresh `ConnectionRouting()` (orthogonal style, empty
                waypoints).
            label: Optional wire label. Defaults to "".
            style: Optional visual style overrides per `02 §39`.
                Copied to insulate callers from later mutations.
            metadata: Optional metadata mapping. Copied.
            extensions: Optional extensions mapping. Copied.

        Returns:
            Newly constructed `Connection` with freshly minted `id`
            and `display_id`.
        """
        return Connection(
            id=self._id_generator.new_connection_id(),
            display_id=self._id_generator.next_connection_display_id(),
            source=source,
            target=target,
            routing=routing if routing is not None else ConnectionRouting(),
            label=label,
            style=dict(style) if style else {},
            metadata=dict(metadata) if metadata else {},
            extensions=dict(extensions) if extensions else {},
        )


def _now_iso8601() -> str:
    """Return current UTC time as an ISO-8601 string.

    Used to stamp `created_at` / `modified_at` on freshly built
    `ComponentInstance` records. Microsecond precision is included so
    that two builds in the same millisecond do not collide on the
    timestamp (instance uniqueness is still guaranteed by ULID).
    """
    return datetime.now(UTC).isoformat(timespec="microseconds")


__all__ = [
    "WorkspaceModel",
]
