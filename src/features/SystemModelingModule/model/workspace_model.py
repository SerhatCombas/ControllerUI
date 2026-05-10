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
* S1.3c.1: 12 fine-grained signals (ADR-018) + `add_component` /
  `remove_component` / `move_component` mutation methods +
  transition-only `_set_dirty()` helper.
* S1.3c.2a: `ComponentInstance.rotation` schema fix (`int → float`
  per ADR-018), shared `_canonical_rotation` helper, rotation
  validation on `add_component`, and the `rotate_component` mutation
  method.
* S1.3c.2b (this commit): five component property setters
  (`set_parameter`, `set_custom_label`, `set_locked`, `set_tags`,
  `set_annotations`) and three connection mutations (`add_connection`,
  `remove_connection`, `update_connection`). Per `02 §11.4 Field
  Mutability Matrix`, `metadata` and `extensions` have no public
  setter in Phase 1 (forward-compatibility containers, write path
  via `_build_*` and `from_dict` only).
* S1.3d: `batch()` context manager + `WorkspaceChangeSet` + 13th
  signal `modelChanged`.
* S1.3e: `reset()` + `modelReset()` signal + `_clear_dirty()`.

Validation order in mutation methods (consistent across S1.3c.x):

1. Argument validation / canonicalization (e.g., `_canonical_rotation`,
   `str.strip()`) — raises early on bad inputs, leaves model state
   untouched.
2. Existence check (e.g., `component_id` in `_components`) — raises
   `KeyError` if the target is missing.
3. No-op suppression via ε-tolerance helpers or exact `==` — returns
   silently if the call would not change state.
4. Mutation + `_set_dirty()` + signal emission. `modified_at` is
   bumped on real mutations only; no-ops do NOT bump it (see ADR-020
   §"No-op suppression").

A call with both an invalid argument and a missing id raises the
argument error first (step 1), not the missing-id error (step 2).
This reflects the principle that argument validation precedes
resource lookup.

References:
----------
* `decisions/ADR-003-workspace-ui-data-separation.md`
* `decisions/ADR-005-command-stack-qundostack.md`
* `decisions/ADR-018-signal-payload-contracts.md`
* `decisions/ADR-019-batch-mutation-and-changeset.md`
* `decisions/ADR-020-dirty-tracking-semantics.md`
* `specs/02_workspace_requirements.md` §3 (Source of Truth), §4 (Signals),
  §11.4 (Field Mutability Matrix), §22 / §23 (Phase-1 rotation
  quantization), §14 (Connection System)
* `specs/06_data_flow_and_architecture.md` §4.2
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Final

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
from .equality import approx_equal_float, approx_equal_qpointf
from .id_generator import WorkspaceIdGenerator
from .selection_model import SelectionSnapshot
from .validation_report import ValidationReport

if TYPE_CHECKING:
    from collections.abc import Mapping


# Phase-1 rotation quantization per `02 §22`/`§23`. ADR-018 keeps the
# signal payload type `float` so the contract stays stable if `02`
# later admits free or non-orthogonal rotation; the quantization rule
# is enforced at the mutation API layer via `_canonical_rotation`.
_VALID_ROTATIONS: Final[tuple[float, ...]] = (0.0, 90.0, 180.0, 270.0)


class WorkspaceModel(QObject):
    """Source of truth for workspace state.

    Holds the canonical state of components, connections, and the
    dirty flag for a single workspace document. Per ADR-003 the model
    owns truth and the UI is a pure consumer; per ADR-005 user edits
    enter through `QUndoCommand` subclasses (S1.7 work) that call
    public mutation methods on this model. Per ADR-018 / ADR-019 /
    ADR-020 the model emits 13 signals total once S1.3 is complete.

    Mutation API status:

    * S1.3c.1: `add_component`, `remove_component`, `move_component`
      plus the 12 fine-grained signal definitions and the
      transition-only `_set_dirty()` helper.
    * S1.3c.2a: `rotate_component` plus rotation validation /
      canonicalization on `add_component`.
    * S1.3c.2b (current): `set_parameter`, `set_custom_label`,
      `set_locked`, `set_tags`, `set_annotations` for component
      property edits; `add_connection`, `remove_connection`,
      `update_connection` for connection lifecycle and content edits.
      Per `02 §11.4`, `metadata` and `extensions` have no public
      setter in Phase 1.
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
        `02 §3`, `02 §4`, `02 §11.4`, ADR-003, ADR-018, ADR-019,
        ADR-020.
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
        rotation: float = 0.0,
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
        match `ComponentInstance.position`.

        `rotation` is validated and canonicalized via
        `_canonical_rotation` before any mutation. Sub-ε drift around
        the Phase-1 valid angles is snapped to the canonical value.
        Invalid values raise `ValueError` and the model state remains
        unchanged.

        `metadata` and `extensions` parameters here populate the new
        instance only; per `02 §11.4` they have no public *setter* in
        Phase 1 and cannot be mutated after creation through
        `WorkspaceModel`.

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
            rotation: Initial rotation in degrees. Must be (within ε)
                one of `{0.0, 90.0, 180.0, 270.0}` per `02 §22`/`§23`;
                snapped to the canonical value before storage.
                Defaults to 0.0.
            parameters: Optional parameter mapping. Copied.
            locked: Initial locked state.
            tags: Tuple of free-form tags.
            annotations: Optional annotations mapping. Copied.
            metadata: Optional metadata mapping. Copied. Internal
                container per `02 §11.4`; no public setter.
            extensions: Optional extensions mapping. Copied. Internal
                container per `02 §11.4`; no public setter.

        Returns:
            Internal `component_id` (`cmp_<ULID>`) of the new component.

        Raises:
            ValueError: If `rotation` is not (within ε) a Phase-1
                quantization angle.
        """
        # TODO(S1.B): Replace explicit kwargs with ComponentDefinition
        # lookup once ComponentRegistry is implemented. See `specs/07`
        # §16 and the S1.B grouping in `specs/07` §7.
        canonical_rotation = _canonical_rotation(rotation)
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
            rotation=canonical_rotation,
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

    def rotate_component(self, component_id: str, new_rotation: float) -> None:
        """Rotate a component to a new angle (degrees).

        Phase-1 quantization rule (`02 §22`/`§23`) is enforced at the
        mutation API layer: `new_rotation` must be approximately equal
        (within ε) to one of `{0.0, 90.0, 180.0, 270.0}`. Sub-ε drift
        around those values is **snapped to the canonical exact angle**
        so storage stays canonical and downstream comparisons can use
        `==`.

        Validation order: `new_rotation` is validated and canonicalized
        before the component existence check (see the module
        docstring §"Validation order in mutation methods").

        Applies ε=1e-6 no-op suppression per ADR-020. On a real
        rotation, `componentRotated(id, old, new_canonical)` is emitted
        with both endpoints as `float` per ADR-018.

        Args:
            component_id: Internal `cmp_<ULID>` identifier.
            new_rotation: Target rotation in degrees. Snapped to the
                canonical Phase-1 angle if within ε.

        Raises:
            ValueError: If `new_rotation` is not (within ε) a Phase-1
                quantization angle. Raised before the existence check.
            KeyError: If `component_id` is not present in the
                workspace. Only raised when `new_rotation` is valid.
        """
        canonical = _canonical_rotation(new_rotation)
        current = self._components.get(component_id)
        if current is None:
            raise KeyError(component_id)
        old_rotation = float(current.rotation)
        if approx_equal_float(old_rotation, canonical):
            return
        new_instance = replace(
            current,
            rotation=canonical,
            modified_at=_now_iso8601(),
        )
        self._components[component_id] = new_instance
        self._set_dirty()
        self.componentRotated.emit(component_id, old_rotation, canonical)

    def set_parameter(
        self,
        component_id: str,
        param_name: str,
        value: Any,
    ) -> None:
        """Set or upsert a parameter value on a component.

        Phase 1 behavior: **upsert**. If `param_name` is not already
        in the component's parameters dict, it is added; otherwise it
        is overwritten. ParameterSchemaRegistry (S1.B) and
        parameter-schema-dispatched equality (S1.6) are not yet
        implemented.

        TODO(S1.6): After parameter schema dispatch lands:
            - reject param names not declared in the component
              definition (raise `KeyError` or `ValueError`);
            - dispatch equality per parameter type (float uses
              ε-tolerance per ADR-020, others use exact `==`).

        Until then, upsert + exact `==` no-op suppression is the stub.

        On a real edit, emits `componentChanged(component_id)` (the
        ADR-018 catch-all for parameter / label / tag / lock /
        annotation edits) and bumps `modified_at`.

        Args:
            component_id: Internal `cmp_<ULID>` identifier.
            param_name: Parameter identifier as declared in the
                component definition.
            value: New parameter value.

        Raises:
            KeyError: If `component_id` is not present in the
                workspace.
        """
        current = self._components.get(component_id)
        if current is None:
            raise KeyError(component_id)
        # Phase-1 stub: exact `==` no-op suppression. Replaced in S1.6
        # by parameter-schema-dispatched equality (float → ε-tolerance,
        # others → exact ==).
        if param_name in current.parameters and current.parameters[param_name] == value:
            return
        new_parameters = dict(current.parameters)
        new_parameters[param_name] = value
        new_instance = replace(
            current,
            parameters=new_parameters,
            modified_at=_now_iso8601(),
        )
        self._components[component_id] = new_instance
        self._set_dirty()
        self.componentChanged.emit(component_id)

    def set_custom_label(self, component_id: str, new_label: str) -> None:
        """Set the custom (user-editable) label on a component.

        The label is normalized via `str.strip()` before comparison
        and storage; trailing or leading whitespace is not part of
        the canonical label. This prevents phantom `componentChanged`
        emissions and dirty transitions from typing whitespace that
        the user perceives as unchanged. To clear the label, pass an
        empty string (or any whitespace-only string — both canonicalize
        to "").

        Validation order:
            1. Argument normalization (here: `strip()`).
            2. Existence check.
            3. No-op suppression (canonical-vs-canonical comparison).
            4. Mutation + `componentChanged` emission.

        Args:
            component_id: Internal `cmp_<ULID>` identifier.
            new_label: New label text. Whitespace-trimmed before
                storage.

        Raises:
            KeyError: If `component_id` is not present in the
                workspace.
        """
        canonical_label = new_label.strip()
        current = self._components.get(component_id)
        if current is None:
            raise KeyError(component_id)
        if current.custom_label == canonical_label:
            return
        new_instance = replace(
            current,
            custom_label=canonical_label,
            modified_at=_now_iso8601(),
        )
        self._components[component_id] = new_instance
        self._set_dirty()
        self.componentChanged.emit(component_id)

    def set_locked(self, component_id: str, locked: bool) -> None:
        """Set the locked flag on a component.

        Locked components are protected from accidental edits per
        `02 §38`. This raw mutation simply flips the flag; lock-aware
        editing rules (e.g., refusing move on a locked component) are
        enforced at the command layer (S1.7).

        Args:
            component_id: Internal `cmp_<ULID>` identifier.
            locked: New locked state.

        Raises:
            KeyError: If `component_id` is not present in the
                workspace.
        """
        current = self._components.get(component_id)
        if current is None:
            raise KeyError(component_id)
        if current.locked == locked:
            return
        new_instance = replace(
            current,
            locked=locked,
            modified_at=_now_iso8601(),
        )
        self._components[component_id] = new_instance
        self._set_dirty()
        self.componentChanged.emit(component_id)

    def set_tags(
        self,
        component_id: str,
        new_tags: tuple[str, ...],
    ) -> None:
        """Set the tags tuple on a component (replaces wholesale).

        Tags are stored as a tuple to align with
        `ComponentInstance.tags`. Mypy strict will reject lists or
        other sequences; callers must pass a tuple. Empty tuple
        clears all tags.

        Args:
            component_id: Internal `cmp_<ULID>` identifier.
            new_tags: New tags tuple. Replaces the current tuple
                wholesale.

        Raises:
            KeyError: If `component_id` is not present in the
                workspace.
        """
        current = self._components.get(component_id)
        if current is None:
            raise KeyError(component_id)
        if current.tags == new_tags:
            return
        new_instance = replace(
            current,
            tags=new_tags,
            modified_at=_now_iso8601(),
        )
        self._components[component_id] = new_instance
        self._set_dirty()
        self.componentChanged.emit(component_id)

    def set_annotations(
        self,
        component_id: str,
        new_annotations: Mapping[str, Any],
    ) -> None:
        """Set the annotations dict on a component (replaces wholesale).

        Per `02 §11.4`, `set_*` methods replace the field wholesale.
        To merge, callers must read-merge-write at the call site, or
        use a future `update_annotations` method. The wholesale
        semantics are intentional and documented to avoid silent
        data loss when nested dicts are involved.

        The input mapping is copied to insulate callers from later
        mutations.

        Args:
            component_id: Internal `cmp_<ULID>` identifier.
            new_annotations: New annotations mapping. Replaces the
                current dict wholesale.

        Raises:
            KeyError: If `component_id` is not present in the
                workspace.
        """
        current = self._components.get(component_id)
        if current is None:
            raise KeyError(component_id)
        canonical_annotations = dict(new_annotations)
        if current.annotations == canonical_annotations:
            return
        new_instance = replace(
            current,
            annotations=canonical_annotations,
            modified_at=_now_iso8601(),
        )
        self._components[component_id] = new_instance
        self._set_dirty()
        self.componentChanged.emit(component_id)

    # ------------------------------------------------------------------ #
    # Public mutation API — connections
    # ------------------------------------------------------------------ #

    def add_connection(
        self,
        *,
        source: PortRef,
        target: PortRef,
        routing: ConnectionRouting | None = None,
        label: str = "",
        style: Mapping[str, Any] | None = None,
    ) -> str:
        """Add a connection between two component ports and return its id.

        This is a **low-level raw mutation**. It does NOT perform
        validation: no duplicate detection, no domain compatibility
        check, no self-connection rejection, no port-existence check.
        All such validation is the responsibility of higher layers:

        * **Primary defense (S1.7 command layer):** the
          `AddConnectionCommand` runs the connection validator
          (`02 §20.1`) before invoking this method. If validation
          fails, this method is never called. This is the path all
          UI-initiated edits take per ADR-005.
        * **Secondary defense (S1.4 incremental validator):** runs
          after mutations as a safety net for bypass or corrupt-load
          scenarios. Not the primary check.

        Duplicate detection per `02 §14.3`: a connection between the
        same two ports is a duplicate (commutatively — A→B and B→A
        are the same connection). The command-layer validator uses
        `frozenset({(source.component_id, source.port_id),
        (target.component_id, target.port_id)})` for comparison. This
        raw method does no such check; calling it twice with the same
        ports produces two distinct connections with different ULIDs.

        `metadata` and `extensions` cannot be supplied through the
        public API; per `02 §11.4` they are internal / round-trip
        only and are populated as empty dicts.

        Args:
            source: Endpoint reference at the source side
                (`(component_id, port_id)`).
            target: Endpoint reference at the target side.
            routing: Optional routing specification. Defaults to
                `ConnectionRouting()` (orthogonal style, empty
                waypoints).
            label: Optional wire label. Defaults to "".
            style: Optional visual style overrides per `02 §39`.
                Copied. Defaults to empty dict.

        Returns:
            Internal `connection_id` (`con_<ULID>`) of the new
            connection.
        """
        connection = self._build_connection(
            source=source,
            target=target,
            routing=routing,
            label=label,
            style=style,
        )
        self._connections[connection.id] = connection
        self._set_dirty()
        self.connectionAdded.emit(connection.id)
        return connection.id

    def remove_connection(self, connection_id: str) -> None:
        """Remove a connection from the workspace.

        Args:
            connection_id: Internal `con_<ULID>` identifier.

        Raises:
            KeyError: If `connection_id` is not present in the
                workspace. Command-layer wrappers (S1.7) are expected
                to translate this into a domain error before
                surfacing it to the UI; see ADR-005 and the error
                catalog in `specs/11_error_code_catalog.md`.
        """
        if connection_id not in self._connections:
            raise KeyError(connection_id)
        del self._connections[connection_id]
        self._set_dirty()
        self.connectionRemoved.emit(connection_id)

    def update_connection(
        self,
        connection_id: str,
        *,
        label: str | None = None,
        routing: ConnectionRouting | None = None,
        style: Mapping[str, Any] | None = None,
    ) -> None:
        """Update one or more user-editable fields on a connection.

        Combo updater: each keyword argument is optional; `None`
        means "leave this field unchanged". To clear `label`, pass
        an empty string. To clear `style`, pass an empty mapping.
        (`None` cannot be used as "clear" because it overlaps with
        the "unchanged" sentinel.)

        Per `02 §11.4`, this method does not modify `source` or
        `target`. Endpoint re-targeting (`02 §37`) is a future
        command-layer feature delivered via `ModifyConnectionCommand`.

        No-op suppression: if every keyword argument is `None`, the
        call is a no-op (no signal, no dirty change). Per-field
        no-op detection is intentionally **not** performed at this
        layer; if any argument is non-`None`, the connection is
        considered changed and `connectionChanged(connection_id)` is
        emitted exactly once.

        Args:
            connection_id: Internal `con_<ULID>` identifier.
            label: New label, or `None` to leave unchanged.
            routing: New `ConnectionRouting`, or `None` to leave
                unchanged.
            style: New style mapping (copied), or `None` to leave
                unchanged.

        Raises:
            KeyError: If `connection_id` is not present in the
                workspace.
        """
        current = self._connections.get(connection_id)
        if current is None:
            raise KeyError(connection_id)
        if label is None and routing is None and style is None:
            return
        new_label = label if label is not None else current.label
        new_routing = routing if routing is not None else current.routing
        new_style = dict(style) if style is not None else current.style
        new_instance = replace(
            current,
            label=new_label,
            routing=new_routing,
            style=new_style,
        )
        self._connections[connection_id] = new_instance
        self._set_dirty()
        self.connectionChanged.emit(connection_id)

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
        rotation: float = 0.0,
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
        responsible for insertion and for canonicalizing `rotation`
        via `_canonical_rotation` before invoking this builder.

        Args:
            definition_id: Dotted identifier of the source component
                definition.
            type: Definition type label used for display.
            display_name: Human-readable definition name.
            domain: Physical domain identifier.
            category: Library category from the definition.
            position: Scene-coordinate `(x, y)` of the component
                anchor.
            visual: SVG variant selector.
            physical_attributes: Declared physical-attribute flags.
            custom_label: Optional user-editable label. Defaults to
                "".
            rotation: Rotation in degrees; assumed already
                canonicalized by the caller. Defaults to 0.0.
            parameters: Optional parameter mapping. Copied.
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
        `add_connection`) is responsible for insertion.

        Args:
            source: Endpoint reference at the source side.
            target: Endpoint reference at the target side.
            routing: Optional routing specification. Defaults to a
                fresh `ConnectionRouting()` (orthogonal style, empty
                waypoints).
            label: Optional wire label. Defaults to "".
            style: Optional visual style overrides per `02 §39`.
                Copied.
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


def _canonical_rotation(rotation: float) -> float:
    """Validate a rotation value and return the canonical Phase-1 angle.

    Per ADR-018 the signal payload type is `float`, but the Phase-1
    quantization rule from `02 §22`/`§23` restricts valid values to
    `{0.0, 90.0, 180.0, 270.0}`. This helper enforces that rule and
    **snaps sub-ε drift** to the canonical valid angle, so internal
    storage stays exact and downstream comparisons can use `==`.

    Used by both `add_component` and `rotate_component`. Both methods
    store the returned canonical value, not the caller's drifted
    input, and the signal payload also carries the canonical value.

    Subscribers receive `float` payloads but must not hard-code
    membership in the closed `{0.0, 90.0, 180.0, 270.0}` set —
    Phase 2+ may admit additional angles (e.g., 45°). The contract
    only guarantees a `float` in degrees.

    Args:
        rotation: Candidate rotation value in degrees.

    Returns:
        The matching canonical angle from `_VALID_ROTATIONS`.

    Raises:
        ValueError: If `rotation` is not approximately equal (within
            ε) to any value in `_VALID_ROTATIONS`.
    """
    for valid in _VALID_ROTATIONS:
        if approx_equal_float(rotation, valid):
            return valid
    raise ValueError(f"rotation must be one of {_VALID_ROTATIONS}, got {rotation}")


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
