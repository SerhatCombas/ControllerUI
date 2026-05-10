"""WorkspaceModel: source-of-truth for workspace state.

The single source of truth for placed components, connections, and the
dirty flag. UI subscribes to its signals; widgets never store canonical
data per ADR-003. Per ADR-018 / ADR-019 / ADR-020 the model emits 13
signals total once S1.3 is complete: 12 fine-grained signals for
individual mutations and one coarse-grained `modelChanged` signal for
batch operations (added in S1.3d).

This file is part of the data layer. It must not import any Qt UI
classes. Importing `QObject`, `QPointF`, and `Signal` from
`PySide6.QtCore` is permitted because change notification is the
cross-layer interface (ADR-003) and `QPointF` is the canonical
scene-coordinate type (ADR-018 signal payload table).

Phase 1 build order within S1.3:

* S1.3a: skeleton — constructor, internal stores, dirty flag,
  read-only views, internal builders.
* S1.3b: ε-tolerance equality helpers in sibling module `equality.py`.
* S1.3c.1 (this commit): 12 fine-grained signals (ADR-018) +
  `add_component` / `remove_component` / `move_component` mutation
  methods + transition-only `_set_dirty()` helper.
* S1.3c.2: rotation, connection mutations, parameter and property
  setters.
* S1.3d: `batch()` context manager + `WorkspaceChangeSet` + 13th
  signal `modelChanged`.
* S1.3e: `reset()` + `modelReset()` signal + `_clear_dirty()`.

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

from dataclasses import replace
from datetime import UTC, datetime
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QObject, QPointF, Signal

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
from .equality import approx_equal_qpointf
from .id_generator import WorkspaceIdGenerator
from .selection_model import SelectionSnapshot
from .validation_report import ValidationReport

if TYPE_CHECKING:
    from collections.abc import Mapping


class WorkspaceModel(QObject):
    """Source of truth for workspace state.

    Holds the canonical state of components, connections, and the
    dirty flag for a single workspace document. Per ADR-003 the model
    owns truth and the UI is a pure consumer; per ADR-005 user edits
    enter through `QUndoCommand` subclasses (S1.7 work) that call
    public mutation methods on this model. Per ADR-018 / ADR-019 /
    ADR-020 the model emits 13 signals total once S1.3 is complete.

    Mutation API status:

    * S1.3c.1 (current): `add_component`, `remove_component`,
      `move_component` plus the 12 fine-grained signal definitions
      and the transition-only `_set_dirty()` helper.
    * S1.3c.2 (next): rotation, connection mutations, parameter and
      property setters.
    * S1.3d (later): `batch()` context manager and `modelChanged`.
    * S1.3e (last): `reset()` and `_clear_dirty()`.

    Attributes:
        is_dirty: Read-only dirty flag per ADR-020. Cleared by
            `reset()` (S1.3e), save (S2), and undo-to-clean (S1.7).
        components: Read-only mapping of `cmp_<ULID>` →
            `ComponentInstance`.
        connections: Read-only mapping of `con_<ULID>` → `Connection`.

    Signals:
        componentAdded(component_id: str)
        componentRemoved(component_id: str)
        componentChanged(component_id: str)
        componentMoved(component_id: str, old_pos: QPointF, new_pos: QPointF)
        componentRotated(component_id: str, old_rotation: float, new_rotation: float)
        connectionAdded(connection_id: str)
        connectionRemoved(connection_id: str)
        connectionChanged(connection_id: str)
        selectionChanged(snapshot: SelectionSnapshot)
        validationChanged(report: ValidationReport)
        modelReset()
        dirtyChanged(is_dirty: bool)

    See Also:
        `02 §3`, `02 §4`, ADR-003, ADR-018, ADR-019, ADR-020.
    """

    # ------------------------------------------------------------------ #
    # Fine-grained signals (ADR-018 §"Signal payload type table")
    #
    # Payload types follow the delta-vs-id-only design principle:
    #
    # * delta-bearing where the field set is small and fixed (move,
    #   rotate); subscribers can avoid a refetch and command-merging
    #   (ADR-005) inspects old/new without touching the model.
    # * id-only for `*Added`, `*Removed`, `*Changed` where the field
    #   set is wide or dynamic; subscribers refetch the model under
    #   the synchronous-emission guarantee.
    # ------------------------------------------------------------------ #
    componentAdded = Signal(str)
    componentRemoved = Signal(str)
    componentChanged = Signal(str)
    componentMoved = Signal(str, QPointF, QPointF)
    componentRotated = Signal(str, float, float)
    connectionAdded = Signal(str)
    connectionRemoved = Signal(str)
    connectionChanged = Signal(str)
    selectionChanged = Signal(SelectionSnapshot)
    validationChanged = Signal(ValidationReport)
    modelReset = Signal()
    dirtyChanged = Signal(bool)

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
        transitions to True via `_set_dirty()`. `reset()` (S1.3e) and
        save (S2) transition back to False via `_clear_dirty()`.
        """
        return self._dirty

    @property
    def components(self) -> Mapping[str, ComponentInstance]:
        """Read-only mapping of `component_id` → `ComponentInstance`.

        Returned as a `MappingProxyType` so callers cannot mutate the
        underlying dict. Mutations go through the public mutation API,
        which is the only sanctioned write path per ADR-003.
        """
        return MappingProxyType(self._components)

    @property
    def connections(self) -> Mapping[str, Connection]:
        """Read-only mapping of `connection_id` → `Connection`.

        Same immutability contract as `components`.
        """
        return MappingProxyType(self._connections)

    # ------------------------------------------------------------------ #
    # Public mutation API — components
    # ------------------------------------------------------------------ #

    def add_component(
        self,
        *,
        definition_id: str,
        type: str,
        display_name: str,
        domain: str,
        category: str,
        position: QPointF,
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
    ) -> str:
        """Add a new component to the workspace and return its `id`.

        Mints a fresh `ComponentInstance` via
        `_build_component_instance`, inserts it into `_components`,
        transitions dirty if needed, and emits
        `componentAdded(component_id)`.

        `position` is taken as a `QPointF` to match the signal contract
        (ADR-018) and stored internally as a `tuple[float, float]` to
        match `ComponentInstance.position`. The conversion happens at
        this boundary.

        Args:
            definition_id: Dotted identifier of the source component
                definition.
            type: Definition type label.
            display_name: Human-readable definition name.
            domain: Physical domain identifier.
            category: Library category from the definition.
            position: Scene-coordinate point as `QPointF`.
            visual: SVG variant selector.
            physical_attributes: Declared physical-attribute flags.
            custom_label: Optional user-editable label.
            rotation: Initial rotation in degrees (typically
                `0`/`90`/`180`/`270` per `02 §22`/`§23`).
            parameters: Optional parameter mapping. Copied.
            locked: Initial locked state.
            tags: Tuple of free-form tags.
            annotations: Optional annotations mapping. Copied.
            metadata: Optional metadata mapping. Copied.
            extensions: Optional extensions mapping. Copied.

        Returns:
            Internal `component_id` (`cmp_<ULID>`) of the new component.
        """
        # TODO(S1.B): Replace explicit kwargs with ComponentDefinition
        # lookup once ComponentRegistry is implemented. See `specs/07`
        # §16 and the S1.B grouping in `specs/07` §7.
        instance = self._build_component_instance(
            definition_id=definition_id,
            type=type,
            display_name=display_name,
            domain=domain,
            category=category,
            position=(position.x(), position.y()),
            visual=visual,
            physical_attributes=physical_attributes,
            custom_label=custom_label,
            rotation=rotation,
            parameters=parameters,
            locked=locked,
            tags=tags,
            annotations=annotations,
            metadata=metadata,
            extensions=extensions,
        )
        self._components[instance.id] = instance
        self._set_dirty()
        self.componentAdded.emit(instance.id)
        return instance.id

    def remove_component(self, component_id: str) -> None:
        """Remove a component from the workspace.

        Note: this is a low-level mutation. It does **not** remove
        connections attached to the component's ports. Atomic delete
        with attached connections is the responsibility of the
        compound `DeleteComponentCommand` (S1.7) per ADR-005, typically
        wrapped in `model.batch()` (ADR-019).

        Args:
            component_id: Internal `cmp_<ULID>` identifier.

        Raises:
            KeyError: If `component_id` is not present in the
                workspace.
        """
        if component_id not in self._components:
            raise KeyError(component_id)
        del self._components[component_id]
        self._set_dirty()
        self.componentRemoved.emit(component_id)

    def move_component(self, component_id: str, new_pos: QPointF) -> None:
        """Move a component to a new scene-coordinate position.

        Applies ε=1e-6 no-op suppression per ADR-020: if the new
        position is approximately equal to the current position
        (squared-distance tolerance), the call is a no-op — no signal,
        no dirty change, no `modified_at` bump.

        On a real move, `componentMoved(id, old_pos, new_pos)` is
        emitted with both endpoints as `QPointF` per ADR-018.

        Args:
            component_id: Internal `cmp_<ULID>` identifier.
            new_pos: Target scene-coordinate position.

        Raises:
            KeyError: If `component_id` is not present in the
                workspace.
        """
        current = self._components.get(component_id)
        if current is None:
            raise KeyError(component_id)
        current_pos = QPointF(current.position[0], current.position[1])
        if approx_equal_qpointf(current_pos, new_pos):
            return
        new_instance = replace(
            current,
            position=(new_pos.x(), new_pos.y()),
            modified_at=_now_iso8601(),
        )
        self._components[component_id] = new_instance
        self._set_dirty()
        self.componentMoved.emit(component_id, current_pos, new_pos)

    # ------------------------------------------------------------------ #
    # Internal builders
    #
    # These produce fresh frozen-dataclass instances with newly
    # generated identity fields and timestamps. They do NOT mutate
    # `_components` / `_connections` — that is the responsibility of
    # the public mutation API. Splitting build from insert keeps ID
    # generation testable in isolation and lets future commands
    # construct candidate instances before deciding whether to commit.
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
        caller (the public mutation method `add_component`) is
        responsible for insertion. Splitting build from insert keeps
        ID generation testable in isolation.

        Args:
            definition_id: Dotted identifier of the source component
                definition (e.g.,
                `"electrical.analog.components.resistor"`).
            type: Definition type label used for display.
            display_name: Human-readable definition name.
            domain: Physical domain identifier (e.g.,
                `"electrical_analog"`).
            category: Library category from the definition.
            position: Scene-coordinate `(x, y)` of the component
                anchor.
            visual: SVG variant selector.
            physical_attributes: Declared physical-attribute flags.
            custom_label: Optional user-editable label. Defaults to
                "".
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
        `add_connection`, S1.3c.2) is responsible for insertion.

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

    # ------------------------------------------------------------------ #
    # Dirty-bit helpers
    # ------------------------------------------------------------------ #

    def _set_dirty(self) -> None:
        """Transition dirty `False → True` and emit `dirtyChanged(True)`.

        Per ADR-020 §"`dirtyChanged` emits on transitions only", this
        helper is idempotent: a second call while already dirty is a
        no-op (no extra emission). Mutation methods may call this on
        every successful edit without worrying about spam.

        TODO(S1.7): Replace with `QUndoStack.cleanChanged` binding
        once the command stack lands. See ADR-020 §"`QUndoStack.cleanState`
        integration (S1.7)".
        """
        if not self._dirty:
            self._dirty = True
            self.dirtyChanged.emit(True)


def _now_iso8601() -> str:
    """Return current UTC time as an ISO-8601 string.

    Used to stamp `created_at` / `modified_at` on freshly built or
    mutated `ComponentInstance` records. Microsecond precision is
    included so that two builds in the same millisecond do not collide
    on the timestamp (instance uniqueness is still guaranteed by
    ULID).
    """
    return datetime.now(UTC).isoformat(timespec="microseconds")


__all__ = [
    "WorkspaceModel",
]
