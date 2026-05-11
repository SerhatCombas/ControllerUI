"""WorkspaceModel: source-of-truth for workspace state.

The single source of truth for placed components, connections, and the
dirty flag. UI subscribes to its signals; widgets never store canonical
data per ADR-003. Per ADR-018 / ADR-019 / ADR-020 the model emits 13
signals total: 12 fine-grained signals for individual mutations and
one coarse-grained `modelChanged` signal for batch operations.

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
* S1.3c.2a: `ComponentInstance.rotation` schema fix (`int → float`),
  `_canonical_rotation` helper, `rotate_component`.
* S1.3c.2b: five component property setters and three connection
  mutations.
* S1.3d: `batch()` context manager + 13th signal
  `modelChanged(WorkspaceChangeSet)` per ADR-019 + minimal `reset()`
  with batch interaction. Mutation methods became batch-aware.
* S1.3e (this commit): `_clear_dirty()` private helper, symmetric
  to `_set_dirty()` (ADR-020 transition-only rule). `reset()` is
  refactored to delegate dirty-clearing to the helper rather than
  setting `self._dirty = False` directly. Per Yorum A, `reset()`
  re-creates the `WorkspaceIdGenerator`, so the next component
  added after a reset receives a display ID counter starting from
  `1` again (blank-slate semantics).

Validation order in mutation methods (consistent across S1.3c.x):

1. Argument validation / canonicalization.
2. Existence check (`KeyError` if the target is missing).
3. No-op suppression.
4. Mutation + `_set_dirty()` + signal emission (or batch-builder
   record).

Validation order in batch context exit (per ADR-019):

1. Build the cumulative `WorkspaceChangeSet` from the builder.
2. If empty, suppress emission and return.
3. Otherwise emit `modelChanged(change_set)`. Subscriber exceptions
   during emission MUST NOT mask a caller exception that triggered
   the exit (Mode B + masking guard per ADR-019 §"Subscriber
   exceptions during emission"); they are logged and the caller
   exception propagates.

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

import logging
from dataclasses import replace
from datetime import UTC, datetime
from types import MappingProxyType, TracebackType
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
from .workspace_change_set import WorkspaceChangeSet

if TYPE_CHECKING:
    from collections.abc import Mapping

    from shared.registry import ComponentRegistry


logger = logging.getLogger(__name__)


# Phase-1 rotation quantization per `02 §22`/`§23`. ADR-018 keeps the
# signal payload type `float` so the contract stays stable if `02`
# later admits free or non-orthogonal rotation; the quantization rule
# is enforced at the mutation API layer via `_canonical_rotation`.
_VALID_ROTATIONS: Final[tuple[float, ...]] = (0.0, 90.0, 180.0, 270.0)


class _ChangeSetBuilder:
    """Internal accumulator for a batch's `WorkspaceChangeSet`.

    Implements the diff-aggregation rules from ADR-019 §"Diff
    aggregation rules": tuples carry net-effect IDs in insertion
    order of first appearance, intermediate add+remove pairs cancel,
    and edits to a removed component are dropped.

    The `signal_reset()` method handles `model.reset()` inside a
    batch: it clears all queued state and sets `reset_required`,
    after which subsequent record calls become no-ops (post-reset
    mutations apply to the model but are not individually reflected
    in the change_set per ADR-019 §"Reset semantics inside a batch").
    """

    def __init__(self) -> None:
        # Internal lists preserve insertion order of first appearance.
        self._added_components: list[str] = []
        self._removed_components: list[str] = []
        self._changed_components: list[str] = []
        self._added_connections: list[str] = []
        self._removed_connections: list[str] = []
        self._changed_connections: list[str] = []
        self._validation_changed: bool = False
        self._dirty_changed: bool = False
        self._reset_required: bool = False

    # ------------------------------------------------------------------ #
    # Component records
    # ------------------------------------------------------------------ #

    def record_component_added(self, cid: str) -> None:
        """Record a component addition; respects reset suppression."""
        if self._reset_required:
            return
        if cid not in self._added_components:
            self._added_components.append(cid)

    def record_component_removed(self, cid: str) -> None:
        """Record a component removal with add/change cancellation."""
        if self._reset_required:
            return
        if cid in self._added_components:
            # add + remove within batch → net zero
            self._added_components.remove(cid)
            while cid in self._changed_components:
                self._changed_components.remove(cid)
            return
        # was pre-batch existing
        if cid not in self._removed_components:
            self._removed_components.append(cid)
        # change is moot once removed
        while cid in self._changed_components:
            self._changed_components.remove(cid)

    def record_component_changed(self, cid: str) -> None:
        """Record a component edit; suppressed if `cid` was added in batch."""
        if self._reset_required:
            return
        if cid in self._added_components:
            return  # added + changed → added only
        if cid in self._removed_components:
            return  # changed + removed unreachable in normal flow
        if cid not in self._changed_components:
            self._changed_components.append(cid)

    # ------------------------------------------------------------------ #
    # Connection records
    # ------------------------------------------------------------------ #

    def record_connection_added(self, conn_id: str) -> None:
        """Record a connection addition; respects reset suppression."""
        if self._reset_required:
            return
        if conn_id not in self._added_connections:
            self._added_connections.append(conn_id)

    def record_connection_removed(self, conn_id: str) -> None:
        """Record a connection removal with add/change cancellation."""
        if self._reset_required:
            return
        if conn_id in self._added_connections:
            self._added_connections.remove(conn_id)
            while conn_id in self._changed_connections:
                self._changed_connections.remove(conn_id)
            return
        if conn_id not in self._removed_connections:
            self._removed_connections.append(conn_id)
        while conn_id in self._changed_connections:
            self._changed_connections.remove(conn_id)

    def record_connection_changed(self, conn_id: str) -> None:
        """Record a connection edit; suppressed if added in batch."""
        if self._reset_required:
            return
        if conn_id in self._added_connections:
            return
        if conn_id in self._removed_connections:
            return
        if conn_id not in self._changed_connections:
            self._changed_connections.append(conn_id)

    # ------------------------------------------------------------------ #
    # Aggregate flags
    # ------------------------------------------------------------------ #

    def mark_dirty_changed(self) -> None:
        """Mark that the dirty bit transitioned during the batch."""
        if self._reset_required:
            return
        self._dirty_changed = True

    def mark_validation_changed(self) -> None:
        """Mark that the validation report changed during the batch.

        Currently unused (validation deferral lands in S1.6); kept
        for API stability so that the validator can call it without
        needing further changes here.
        """
        if self._reset_required:
            return
        self._validation_changed = True

    def signal_reset(self) -> None:
        """Handle `model.reset()` called inside the batch.

        Clears all queued state and sets `reset_required`. After this
        call, all `record_*` and `mark_*` methods become no-ops (per
        ADR-019 §"Reset semantics inside a batch").
        """
        self._added_components.clear()
        self._removed_components.clear()
        self._changed_components.clear()
        self._added_connections.clear()
        self._removed_connections.clear()
        self._changed_connections.clear()
        self._validation_changed = False
        self._dirty_changed = False
        self._reset_required = True

    def build(self) -> WorkspaceChangeSet:
        """Snapshot the current state into a frozen `WorkspaceChangeSet`."""
        return WorkspaceChangeSet(
            added_components=tuple(self._added_components),
            removed_components=tuple(self._removed_components),
            changed_components=tuple(self._changed_components),
            added_connections=tuple(self._added_connections),
            removed_connections=tuple(self._removed_connections),
            changed_connections=tuple(self._changed_connections),
            validation_changed=self._validation_changed,
            dirty_changed=self._dirty_changed,
            reset_required=self._reset_required,
        )


class _Batch:
    """Context manager helper returned by `WorkspaceModel.batch()`.

    Per ADR-019, the model itself implements the batch semantics; this
    class only forwards `__enter__` / `__exit__` to model methods. The
    `__exit__` skeleton implements the subscriber-exception-masking
    guard (Mode B per ADR-019).
    """

    __slots__ = ("_model",)

    def __init__(self, model: WorkspaceModel) -> None:
        self._model = model

    def __enter__(self) -> None:
        self._model._batch_enter()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        # The model's `_batch_exit` may raise (subscriber exception
        # without a caller exception, case 2 of the ADR-019 truth
        # table). It will not mask `exc_val` (case 4) because of the
        # logging guard inside.
        self._model._batch_exit(exc_val)
        # Returning None / False propagates `exc_val` if any.


class WorkspaceModel(QObject):
    """Source of truth for workspace state.

    Holds the canonical state of components, connections, and the
    dirty flag for a single workspace document. Per ADR-003 the model
    owns truth and the UI is a pure consumer; per ADR-005 user edits
    enter through `QUndoCommand` subclasses (S1.7 work) that call
    public mutation methods on this model. Per ADR-018 / ADR-019 /
    ADR-020 the model emits 13 signals total.

    Mutation API status:

    * S1.3c.1: `add_component`, `remove_component`, `move_component`
      plus the 12 fine-grained signal definitions and the
      transition-only `_set_dirty()` helper.
    * S1.3c.2a: `rotate_component` plus rotation validation /
      canonicalization on `add_component`.
    * S1.3c.2b: `set_parameter`, `set_custom_label`, `set_locked`,
      `set_tags`, `set_annotations`, `add_connection`,
      `remove_connection`, `update_connection`.
    * S1.3d (current): `batch()` context manager + `modelChanged`
      signal + minimal `reset()`. Mutation methods are batch-aware:
      inside a batch, individual fine-grained signals are suppressed
      and changes are accumulated into a `_ChangeSetBuilder`; on
      outermost exit, exactly one `modelChanged(change_set)` is
      emitted (suppressed if the change_set is empty).
    * S1.3e: extended `reset()` semantics + `_clear_dirty()`.

    Attributes:
        is_dirty: Read-only dirty flag per ADR-020.
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
        modelChanged(change_set: WorkspaceChangeSet)  # ADR-019, batch only

    See Also:
        `02 §3`, `02 §4`, `02 §11.4`, ADR-003, ADR-018, ADR-019,
        ADR-020.
    """

    # ------------------------------------------------------------------ #
    # Fine-grained signals (ADR-018)
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

    # ------------------------------------------------------------------ #
    # Coarse-grained batch signal (ADR-019)
    # ------------------------------------------------------------------ #
    # Mutually exclusive with the 12 fine-grained signals: outside a
    # batch the fine-grained signals fire; inside a batch they are
    # suppressed and `modelChanged` fires once on outermost exit.
    modelChanged = Signal(WorkspaceChangeSet)

    def __init__(
        self,
        parent: QObject | None = None,
        registry: ComponentRegistry | None = None,
    ) -> None:
        """Initialize an empty, clean workspace model.

        Args:
            parent: Optional Qt parent for ownership.
            registry: Optional `ComponentRegistry` used by
                `add_component_from_definition` to resolve definition
                IDs into `ComponentDefinition` records (S1.B.1d).
                When `None`, the registry-backed entrypoint raises
                `RuntimeError`; the explicit-kwarg
                `add_component` path remains usable regardless.
                Application bootstrap (S1.9) wires the registry; unit
                tests that exercise `add_component` directly may omit
                it.
        """
        super().__init__(parent)
        self._components: dict[str, ComponentInstance] = {}
        self._connections: dict[str, Connection] = {}
        self._dirty: bool = False
        self._id_generator: WorkspaceIdGenerator = WorkspaceIdGenerator()
        self._registry: ComponentRegistry | None = registry
        # Batch state: depth counter for nested batches, builder
        # accumulating diff content for the outermost batch only.
        self._batch_depth: int = 0
        self._batch_builder: _ChangeSetBuilder | None = None

    # ------------------------------------------------------------------ #
    # Read-only views
    # ------------------------------------------------------------------ #

    @property
    def is_dirty(self) -> bool:
        """Current dirty bit per ADR-020."""
        return self._dirty

    @property
    def components(self) -> Mapping[str, ComponentInstance]:
        """Read-only mapping of `component_id` → `ComponentInstance`."""
        return MappingProxyType(self._components)

    @property
    def connections(self) -> Mapping[str, Connection]:
        """Read-only mapping of `connection_id` → `Connection`."""
        return MappingProxyType(self._connections)

    @property
    def registry(self) -> ComponentRegistry | None:
        """The optional `ComponentRegistry` wired at construction time.

        Public read-only accessor for the registry attribute used by
        `add_component_from_definition` (S1.B.1d) and the command
        stack (S1.7.x). When None, registry-backed entrypoints raise
        `RuntimeError` and `set_parameter` falls back to exact `==`
        no-op suppression per S1.B.1e.
        """
        return self._registry

    # ------------------------------------------------------------------ #
    # Batch context manager (ADR-019)
    # ------------------------------------------------------------------ #

    def batch(self) -> _Batch:
        """Return a context manager that coalesces signals over a batch.

        Inside the resulting `with` block, the 12 fine-grained signals
        are suppressed and per-mutation `dirtyChanged` emissions are
        deferred. On the outermost exit, the model emits exactly one
        `modelChanged(change_set: WorkspaceChangeSet)` carrying the
        cumulative diff (provided the change_set is not empty per
        `WorkspaceChangeSet.is_empty`).

        Nested calls increment a depth counter; only the outermost
        exit emits. Mode B exception handling: completed mutations
        remain in the model and are reflected in the change_set;
        the exception still propagates after emission.

        Subscriber exceptions during `modelChanged` emission MUST NOT
        mask a caller exception that triggered the exit. The
        `_batch_exit` implementation logs subscriber exceptions when
        a caller exception is present and otherwise re-raises.

        See ADR-019 for the full contract.
        """
        return _Batch(self)

    def _batch_enter(self) -> None:
        """Open a batch; allocate the builder on the outermost open."""
        self._batch_depth += 1
        if self._batch_depth == 1:
            self._batch_builder = _ChangeSetBuilder()

    def _batch_exit(self, exc_val: BaseException | None) -> None:
        """Close a batch; on outermost close, emit `modelChanged`.

        Per ADR-019 §"Subscriber exceptions during emission":

        * If `exc_val is not None` and a subscriber raises, the
          subscriber exception is logged and the caller exception
          (`exc_val`) is allowed to propagate (case 4 of the truth
          table).
        * If `exc_val is None` and a subscriber raises, the
          subscriber exception propagates (case 2).
        * Otherwise (cases 1 and 3) the caller exception (or none)
          propagates normally.
        """
        self._batch_depth -= 1
        if self._batch_depth != 0:
            return  # nested exit: no-op until outermost
        builder = self._batch_builder
        # Clear builder reference before emitting so subscribers that
        # introspect the model see "not in a batch" while reacting.
        self._batch_builder = None
        if builder is None:
            return  # defensive: shouldn't happen given matched enter/exit
        change_set = builder.build()
        if change_set.is_empty():
            return
        # NOTE: Under PySide6's default signal dispatch, subscriber
        # exceptions raised in `modelChanged` slots are caught by the
        # Qt event loop and routed to `sys.excepthook` rather than
        # propagating back here. This `try/except` is structurally
        # retained per ADR-019 §"Subscriber exceptions during
        # emission" (truth table cases 2 and 4) but is runtime-
        # inactive in Phase 1: the `except` branch never fires
        # because the subscriber exception is intercepted upstream
        # by Qt. See
        # `decisions/2026-05-10_pyside6-signal-exception-dispatch.md`
        # for the finding and candidate resolution paths.
        try:
            self.modelChanged.emit(change_set)
        except Exception:
            if exc_val is not None:
                # Case 4 (defensive; runtime-inactive per the NOTE
                # above): a caller exception is propagating; do not
                # mask it. Log the subscriber exception and let the
                # caller exception flow.
                logger.exception(
                    "subscriber raised during batched modelChanged "
                    "emission; original mutation exception preserved"
                )
            else:
                # Case 2 (defensive; runtime-inactive): no caller
                # exception; let the subscriber exception propagate.
                raise

    # ------------------------------------------------------------------ #
    # Reset (S1.3d minimal; full semantics in S1.3e)
    # ------------------------------------------------------------------ #

    def reset(self) -> None:
        """Reset the workspace to an empty, clean state.

        Clears components, connections, the dirty flag, and the ID
        generator. The ID generator is **re-created** rather than
        reused (Yorum A: blank-slate semantics) — the next component
        added after a reset receives a display-ID counter starting
        from `1` again, regardless of how many components were
        present before the reset.

        Dirty clearing is delegated to `_clear_dirty()` (symmetric to
        `_set_dirty()`); per ADR-020 transition-only rule, a
        `dirtyChanged(False)` emission only occurs if the model was
        actually dirty before the reset.

        Outside a batch, emits `modelReset()` (always, regardless of
        prior dirty state) and `dirtyChanged(False)` (only on dirty→
        clean transition).

        Inside a batch, per ADR-019 §"Reset semantics inside a
        batch": all queued mutations are discarded from the
        change_set, `change_set.reset_required = True`, and post-
        reset mutations apply to the model normally but are NOT
        individually reflected in the change_set. The fine-grained
        `modelReset` signal is NOT emitted inside a batch — the
        single `modelChanged(change_set)` with `reset_required=True`
        on outermost exit is the canonical notification.
        `_clear_dirty()` is called inside a batch as well; its
        `mark_dirty_changed()` write to the builder is a no-op once
        `signal_reset()` has set `reset_required=True`, so the
        change_set's `dirty_changed` flag stays `False` (consistent
        with ADR-019's "reset_required wins; other diff fields
        empty" rule).
        """
        self._components.clear()
        self._connections.clear()
        self._id_generator = WorkspaceIdGenerator()

        if self._batch_builder is not None:
            # Inside a batch: nuke queued state first, then clear
            # dirty (which is a no-op on the builder due to
            # reset_required). Do NOT emit modelReset; outermost
            # batch exit will carry the reset notification.
            self._batch_builder.signal_reset()
            self._clear_dirty()
            return

        # Outside a batch: clear dirty (transition emits if needed)
        # then emit modelReset.
        self._clear_dirty()
        self.modelReset.emit()

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
        """Add a new component and return its id.

        See S1.3c.1 / S1.3c.2a for the full contract; S1.3d adds
        batch awareness (the `componentAdded` signal is suppressed
        inside a batch and the addition is recorded into the
        change_set instead).

        Note:
            Since S1.B.1d the registry-backed entrypoint
            `add_component_from_definition` is the preferred way to
            create instances from library definitions. This
            explicit-kwarg method is retained for low-level test use
            and for paths (e.g., project load, migrations) that
            already carry the resolved fields.
        """
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
        if self._batch_builder is not None:
            self._batch_builder.record_component_added(instance.id)
        else:
            self.componentAdded.emit(instance.id)
        return instance.id

    def add_component_from_definition(
        self,
        definition_id: str,
        position: QPointF,
        *,
        custom_label: str = "",
        rotation: float = 0.0,
        parameters: Mapping[str, Any] | None = None,
        locked: bool = False,
        tags: tuple[str, ...] = (),
        annotations: Mapping[str, Any] | None = None,
    ) -> str:
        """Add a component sourced from a library `ComponentDefinition`.

        Registry-backed companion to `add_component` introduced in
        S1.B.1d (decision B1 — new method rather than overloading
        `add_component`). Resolves `definition_id` through the
        `ComponentRegistry` supplied at model construction, copies
        the definition-derived fields (`type`, `display_name`,
        `domain`, `category`, `visual`, `physical_attributes`) into
        the new instance per `02 §11.3`, and delegates the rest of
        the addition flow to the existing `_build_component_instance`
        path so the dirty flag, batch builder, and `componentAdded`
        signal behavior remain identical to `add_component`.

        Parameter handling: by default an empty `parameters` mapping
        is stored on the instance, which per
        `ComponentInstance.parameters` means "use definition defaults
        at runtime." Callers that want to set explicit user-edited
        values at creation time can pass them through the
        `parameters` kwarg (e.g., for project-load and copy/paste
        flows in later stages). Parameter validation against the
        definition schema is the responsibility of `set_parameter`
        (S1.B.1e); this entrypoint accepts whatever the caller
        supplies.

        Validation order (consistent with the rest of the mutation
        API, `02 §3` / `02 §4`):

        1. Argument validation: registry availability (`RuntimeError`
           if no registry was wired at construction) and rotation
           canonicalization (raises `ValueError` for off-grid
           rotations per `_canonical_rotation`).
        2. Definition lookup: `registry.get(definition_id)` raises
           `KeyError` for unknown ids.
        3. Mutation + `_set_dirty()` + signal emission (or batch
           record), identical to `add_component`.

        Args:
            definition_id: Dotted-namespace definition id from a
                registered `ComponentDefinition` (e.g.,
                `"electrical.analog.components.resistor"`).
            position: Scene-coordinate placement; canonicalized to a
                `tuple[float, float]` on the instance per
                `ComponentInstance.position`.
            custom_label: Optional user-editable label.
            rotation: Initial rotation in degrees; restricted to
                `{0.0, 90.0, 180.0, 270.0}` in Phase 1 per `02 §22`
                and ADR-018.
            parameters: Optional explicit per-instance parameter
                overrides; defaults to empty (definition defaults
                resolved at runtime).
            locked: Initial locked flag.
            tags: Initial tag tuple.
            annotations: Initial annotations mapping.

        Returns:
            The newly minted `cmp_<ULID>` instance id.

        Raises:
            RuntimeError: No `ComponentRegistry` was supplied at
                construction time.
            KeyError: `definition_id` is not registered.
            ValueError: `rotation` is off-grid per `_canonical_rotation`.

        See Also:
            `01 §6`, `02 §11.3`, ADR-021.
        """
        if self._registry is None:
            raise RuntimeError(
                "add_component_from_definition requires a ComponentRegistry; "
                "pass `registry=...` to WorkspaceModel(...)"
            )
        definition = self._registry.get(definition_id)
        canonical_rotation = _canonical_rotation(rotation)
        instance = self._build_component_instance(
            definition_id=definition.id,
            type=definition.display_name,
            display_name=definition.display_name,
            domain=definition.domain,
            category=definition.category,
            position=(position.x(), position.y()),
            visual=VisualSpec(
                svg_id=definition.visual.svg_id,
                variant=definition.visual.default_variant,
            ),
            physical_attributes=definition.physical_attributes,
            custom_label=custom_label,
            rotation=canonical_rotation,
            parameters=parameters,
            locked=locked,
            tags=tags,
            annotations=annotations,
        )
        self._components[instance.id] = instance
        self._set_dirty()
        if self._batch_builder is not None:
            self._batch_builder.record_component_added(instance.id)
        else:
            self.componentAdded.emit(instance.id)
        return instance.id

    def remove_component(self, component_id: str) -> None:
        """Remove a component (low-level; cascade is the command's job)."""
        if component_id not in self._components:
            raise KeyError(component_id)
        del self._components[component_id]
        self._set_dirty()
        if self._batch_builder is not None:
            self._batch_builder.record_component_removed(component_id)
        else:
            self.componentRemoved.emit(component_id)

    def restore_component(self, instance: ComponentInstance) -> None:
        """Re-insert a previously-removed component verbatim.

        Used by the command stack (S1.7) to support undo/redo of
        component additions and deletions: the command captures the
        full `ComponentInstance` on first redo (after
        `add_component_from_definition` mints the id) and re-inserts
        it on subsequent redos via this method. Because the captured
        instance is frozen and carries its original `cmp_<ULID>` id,
        undo → redo cycles preserve identity — which is the
        prerequisite for stable connection references and
        cross-feature linking (`02 §8.3`, `08 §5.6`).

        Validation order:

        1. Argument validation: `instance.id` must not already exist
           in the model (collision indicates a logic bug in the
           command sequencing — typically a missing `undo()` between
           two `redo()` calls).
        2. Mutation + `_set_dirty()` + signal emission (or batch
           record), identical to `add_component`.

        Args:
            instance: A previously-captured `ComponentInstance` with
                its original id. The dataclass is frozen, so this
                method does not need to defensively copy it.

        Raises:
            ValueError: `instance.id` collides with an existing
                component in the model.

        See Also:
            ADR-002 (id stability), ADR-005 (command stack),
            `02 §29.3` (round-trip identity rule).
        """
        if instance.id in self._components:
            raise ValueError(f"component id collision on restore: '{instance.id}'")
        self._components[instance.id] = instance
        self._set_dirty()
        if self._batch_builder is not None:
            self._batch_builder.record_component_added(instance.id)
        else:
            self.componentAdded.emit(instance.id)

    def move_component(self, component_id: str, new_pos: QPointF) -> None:
        """Move a component; ε no-op suppression (ADR-020)."""
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
        if self._batch_builder is not None:
            self._batch_builder.record_component_changed(component_id)
        else:
            self.componentMoved.emit(component_id, current_pos, new_pos)

    def rotate_component(self, component_id: str, new_rotation: float) -> None:
        """Rotate a component; canonicalize, ε no-op, validation order rule."""
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
        if self._batch_builder is not None:
            self._batch_builder.record_component_changed(component_id)
        else:
            self.componentRotated.emit(component_id, old_rotation, canonical)

    def set_parameter(
        self,
        component_id: str,
        param_name: str,
        value: Any,
    ) -> None:
        """Set or upsert a parameter value with schema-dispatched no-op rule.

        S1.B.1e closes the TODO(S1.6) marker: the per-type no-op
        suppression now consults the `ComponentRegistry` (wired at
        `WorkspaceModel(registry=...)` time per S1.B.1d) to discover
        the parameter's declared type and dispatch the equality check
        accordingly:

        * `float` parameters: ε-tolerance equality (`approx_equal_float`)
          per ADR-020. Suppresses spurious `componentChanged`
          emissions from sub-ε numeric drift (e.g., a slider that
          re-emits a slightly different float each tick).
        * `int`, `bool`, `string`, `enum`, `expression` parameters:
          exact `==`. These types are discrete or syntactic; sub-ε
          tolerance does not apply.

        When the registry cannot resolve the type — no registry
        wired, the component's `definition_id` is not registered, or
        the parameter is not declared in the definition — the method
        falls back to exact `==`. This keeps backwards compatibility
        with the pre-S1.B.1d code path (used by all existing S1.3
        tests, which construct `WorkspaceModel()` without a registry)
        and avoids changing semantics for parameters that the
        registry cannot describe.

        Insertion semantics: when `param_name` is not present on the
        instance, this method always inserts (no comparison runs).
        Parameter-id validation against the definition schema (i.e.,
        rejecting parameters that the definition does not declare) is
        not enforced here — that is the Phase 1.5+ command-stack
        layer's responsibility and would break the upsert-friendly
        contract used by project-load and copy/paste flows.

        Validation order (consistent with `add_component`,
        `add_component_from_definition`, etc., `02 §3`/`§4`):

        1. Existence check (`KeyError` if `component_id` is missing).
        2. Schema lookup (best-effort; None falls back to `==`).
        3. No-op suppression by dispatched equality.
        4. Mutation + `_set_dirty()` + signal emission (or batch
           record).

        Args:
            component_id: Target component instance id.
            param_name: Parameter id (matches `ParameterDefinition.id`
                when registered).
            value: New value; type is the caller's responsibility.
                Value-level validation against `ParameterDefinition`
                bounds / enum / unit is the command-stack layer's
                responsibility (Phase 1.5+).

        Raises:
            KeyError: `component_id` is unknown.

        See Also:
            `02 §11.4` (Field Mutability Matrix), ADR-020 (ε no-op),
            ADR-021 (registry-backed parameter discovery).
        """
        current = self._components.get(component_id)
        if current is None:
            raise KeyError(component_id)
        if param_name in current.parameters:
            existing = current.parameters[param_name]
            param_type = self._lookup_parameter_type(current.definition_id, param_name)
            if _parameter_values_equal(existing, value, param_type):
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
        if self._batch_builder is not None:
            self._batch_builder.record_component_changed(component_id)
        else:
            self.componentChanged.emit(component_id)

    def unset_parameter(self, component_id: str, param_name: str) -> None:
        """Remove a parameter entry from a component (no-op if absent).

        Symmetric counterpart to `set_parameter`. Introduced in S1.7.2
        for `ChangeParameterCommand`'s undo path: when the command's
        first redo INSERTED a parameter (the entry was absent before
        the edit), undo must REMOVE the entry rather than restore
        `None` as a value. Removing the entry returns the instance to
        the "use definition default at runtime" semantic per
        `02 §11.3` / `ComponentInstance.parameters`.

        Validation order (consistent with the rest of the mutation
        API):

        1. Existence check (`KeyError` if `component_id` is missing).
        2. No-op suppression: if `param_name` is not in the instance
           parameters dict, return early.
        3. Mutation + `_set_dirty()` + signal emission (or batch
           record). The emitted signal is `componentChanged` (the
           catch-all for parameter edits), identical to
           `set_parameter`.

        Args:
            component_id: Target component instance id.
            param_name: Parameter id to remove. Absence is a no-op.

        Raises:
            KeyError: `component_id` is unknown.

        See Also:
            `set_parameter` (S1.B.1e),
            `02 §11.3` (parameter defaults at runtime),
            `02 §11.4` (Field Mutability Matrix).
        """
        current = self._components.get(component_id)
        if current is None:
            raise KeyError(component_id)
        if param_name not in current.parameters:
            return
        new_parameters = dict(current.parameters)
        del new_parameters[param_name]
        new_instance = replace(
            current,
            parameters=new_parameters,
            modified_at=_now_iso8601(),
        )
        self._components[component_id] = new_instance
        self._set_dirty()
        if self._batch_builder is not None:
            self._batch_builder.record_component_changed(component_id)
        else:
            self.componentChanged.emit(component_id)

    def _lookup_parameter_type(
        self,
        definition_id: str,
        param_id: str,
    ) -> str | None:
        """Return the declared `ParameterType`, or None if unresolvable.

        Resolution order (any miss returns `None`):

        1. A `ComponentRegistry` must be wired at construction.
        2. `definition_id` must be registered.
        3. `param_id` must be declared on that definition.

        `None` callers treat as "use exact `==`" so that the pre-
        S1.B.1d code path (no registry) stays semantically identical
        and parameters that are not in the definition schema (e.g.,
        legacy upserts, future user-defined extra params) keep their
        upsert-friendly behavior.
        """
        if self._registry is None:
            return None
        if not self._registry.has(definition_id):
            return None
        definition = self._registry.get(definition_id)
        for param_def in definition.parameters:
            if param_def.id == param_id:
                return param_def.type
        return None

    def set_custom_label(self, component_id: str, new_label: str) -> None:
        """Set the custom label; whitespace strip canonicalization."""
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
        if self._batch_builder is not None:
            self._batch_builder.record_component_changed(component_id)
        else:
            self.componentChanged.emit(component_id)

    def set_locked(self, component_id: str, locked: bool) -> None:
        """Set the locked flag; exact bool == no-op."""
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
        if self._batch_builder is not None:
            self._batch_builder.record_component_changed(component_id)
        else:
            self.componentChanged.emit(component_id)

    def set_tags(
        self,
        component_id: str,
        new_tags: tuple[str, ...],
    ) -> None:
        """Set the tags tuple wholesale; exact `==` no-op."""
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
        if self._batch_builder is not None:
            self._batch_builder.record_component_changed(component_id)
        else:
            self.componentChanged.emit(component_id)

    def set_annotations(
        self,
        component_id: str,
        new_annotations: Mapping[str, Any],
    ) -> None:
        """Set the annotations dict wholesale (replace, not merge)."""
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
        if self._batch_builder is not None:
            self._batch_builder.record_component_changed(component_id)
        else:
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
        """Add a connection (raw mutation; validation at command layer)."""
        connection = self._build_connection(
            source=source,
            target=target,
            routing=routing,
            label=label,
            style=style,
        )
        self._connections[connection.id] = connection
        self._set_dirty()
        if self._batch_builder is not None:
            self._batch_builder.record_connection_added(connection.id)
        else:
            self.connectionAdded.emit(connection.id)
        return connection.id

    def remove_connection(self, connection_id: str) -> None:
        """Remove a connection."""
        if connection_id not in self._connections:
            raise KeyError(connection_id)
        del self._connections[connection_id]
        self._set_dirty()
        if self._batch_builder is not None:
            self._batch_builder.record_connection_removed(connection_id)
        else:
            self.connectionRemoved.emit(connection_id)

    def restore_connection(self, connection: Connection) -> None:
        """Re-insert a previously-removed connection verbatim.

        Symmetric counterpart to `restore_component` (S1.7.1).
        Introduced in S1.7.3 for `DeleteComponentCommand`'s undo
        path: the command captures the full `Connection` instances
        cascaded out by a component deletion and re-inserts them on
        undo with their original `con_<ULID>` ids — so downstream
        references (validation reports, future graph caches) keep
        the same identity across delete/undo cycles per ADR-002 /
        `02 §8`.

        Validation order:

        1. Argument validation: `connection.id` must not collide
           with an existing connection (collisions indicate a
           command-sequencing logic bug, same as
           `restore_component`).
        2. Mutation + `_set_dirty()` + signal emission (or batch
           record), identical to `add_connection`.

        Args:
            connection: A previously-captured `Connection` with its
                original id. The dataclass is frozen, so this method
                does not need to defensively copy.

        Raises:
            ValueError: `connection.id` collides with an existing
                connection.

        See Also:
            `restore_component` (S1.7.1), ADR-002 (id stability),
            `02 §29.3` (round-trip identity).
        """
        if connection.id in self._connections:
            raise ValueError(f"connection id collision on restore: '{connection.id}'")
        self._connections[connection.id] = connection
        self._set_dirty()
        if self._batch_builder is not None:
            self._batch_builder.record_connection_added(connection.id)
        else:
            self.connectionAdded.emit(connection.id)

    def connections_for_component(self, component_id: str) -> tuple[Connection, ...]:
        """Return all connections referencing `component_id` on either endpoint.

        Used by `DeleteComponentCommand` to discover the cascade
        set; will also serve future validators and project export.
        Iteration order matches the connections dict (Python dict
        insertion order per the 3.7+ guarantee), so callers get a
        stable replay order on undo.

        Does NOT validate that `component_id` exists in the model —
        an unknown id simply yields an empty tuple. Callers that
        need an existence check should perform it separately
        (`component_id in model.components`).

        Args:
            component_id: Target component id.

        Returns:
            Tuple of `Connection` records whose `source.component_id`
            or `target.component_id` equals `component_id`. Frozen
            dataclasses are safe to share; callers may store the
            tuple for replay without defensive copying.
        """
        return tuple(
            conn
            for conn in self._connections.values()
            if conn.source.component_id == component_id or conn.target.component_id == component_id
        )

    def update_connection(
        self,
        connection_id: str,
        *,
        label: str | None = None,
        routing: ConnectionRouting | None = None,
        style: Mapping[str, Any] | None = None,
    ) -> None:
        """Combo update (label / routing / style); all-None → no-op."""
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
        if self._batch_builder is not None:
            self._batch_builder.record_connection_changed(connection_id)
        else:
            self.connectionChanged.emit(connection_id)

    # ------------------------------------------------------------------ #
    # Internal builders
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
        """Mint a fresh `ComponentInstance` (no insert; caller commits)."""
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
        """Mint a fresh `Connection` (no insert; caller commits)."""
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
        """Transition dirty `False → True`; batch-aware emission.

        Per ADR-020 transition-only rule: if already dirty, no-op.
        Outside a batch, emits `dirtyChanged(True)`. Inside a batch,
        marks the change_set's `dirty_changed` aggregate flag instead;
        no individual `dirtyChanged` emission until outermost exit
        (and even then, only the change_set carries the transition;
        subscribers query `model.is_dirty` for the actual state).

        TODO(S1.7): Replace with `QUndoStack.cleanChanged` binding.
        """
        if self._dirty:
            return
        self._dirty = True
        if self._batch_builder is not None:
            self._batch_builder.mark_dirty_changed()
        else:
            self.dirtyChanged.emit(True)

    def _clear_dirty(self) -> None:
        """Transition dirty `True → False`; batch-aware emission.

        Symmetric to `_set_dirty`. Per ADR-020 transition-only rule:
        if already clean, no-op (no extra emission). Outside a batch,
        emits `dirtyChanged(False)`. Inside a batch, marks the
        change_set's `dirty_changed` aggregate flag (which is itself
        a no-op once `signal_reset()` has set `reset_required=True`
        on the builder, so reset-clear sequences leave
        `change_set.dirty_changed=False` per ADR-019's
        "reset_required wins; other diff fields empty" rule).

        Used by `reset()` (S1.3e), and (in S2) the save path. In
        S1.7 this helper will be replaced by a
        `QUndoStack.cleanChanged` binding per ADR-020 §"QUndoStack
        integration"; until then, this is the only public-API path
        that flips the flag back to clean.

        TODO(S1.7): Bind to `QUndoStack.cleanChanged` so the command
        stack is the canonical clean-state authority.
        """
        if not self._dirty:
            return
        self._dirty = False
        if self._batch_builder is not None:
            self._batch_builder.mark_dirty_changed()
        else:
            self.dirtyChanged.emit(False)


def _canonical_rotation(rotation: float) -> float:
    """Validate a rotation and return the canonical Phase-1 angle."""
    for valid in _VALID_ROTATIONS:
        if approx_equal_float(rotation, valid):
            return valid
    raise ValueError(f"rotation must be one of {_VALID_ROTATIONS}, got {rotation}")


def _parameter_values_equal(
    existing: Any,
    value: Any,
    param_type: str | None,
) -> bool:
    """Type-dispatched parameter equality for `set_parameter` no-op suppression.

    Float parameters use ε-tolerance per ADR-020 to suppress spurious
    `componentChanged` emissions from sub-ε numeric drift. All other
    declared types (`int`, `bool`, `string`, `enum`, `expression`)
    and the `None` "unknown / unregistered" sentinel fall back to
    exact `==` so the pre-S1.B.1d behavior is preserved when the
    registry cannot resolve the parameter type.

    The ε-tolerance branch only fires when both sides are numeric
    (`int` or `float`). This guards against bool-vs-float traps and
    unexpected non-numeric values flowing through a parameter declared
    as `float` — in those edge cases we conservatively fall back to
    `==` so the mutation path (and any downstream validator) still
    runs.

    Args:
        existing: The value currently stored on the instance.
        value: The candidate new value.
        param_type: Declared `ParameterType` per `01 §6`, or `None`
            when the registry cannot resolve the parameter.

    Returns:
        `True` if the values should be treated as equal (no-op
        suppression fires); `False` otherwise (mutation proceeds).
    """
    if (
        param_type == "float"
        and not isinstance(existing, bool)
        and not isinstance(value, bool)
        and isinstance(existing, int | float)
        and isinstance(value, int | float)
    ):
        return approx_equal_float(float(existing), float(value))
    return bool(existing == value)


def _now_iso8601() -> str:
    """Return current UTC time as an ISO-8601 string."""
    return datetime.now(UTC).isoformat(timespec="microseconds")


__all__ = [
    "WorkspaceModel",
]
