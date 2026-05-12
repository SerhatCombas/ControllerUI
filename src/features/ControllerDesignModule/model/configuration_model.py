"""ConfigurationModel: QObject host for the three Phase-1 config sections.

Parallels `SystemModelingModule.WorkspaceModel` in role: a single
QObject owning the canonical configuration state and emitting the
Qt signals that spec/03 §9 + spec/06 §4.3.1 mandate. The three
S2.A dataclass families (ControllerSettings, IOSelection,
SimulationSettings) are frozen value types — they cannot carry
signals — so this class is the source of truth and signal
producer.

Phase-1 incremental landing per the S2 plan:

* S2.B.3 — `ioSelectionChanged(IOSelection)` signal +
  `set_io_selection(new)` setter.
* S2.C — `plotLayoutChanged(PlotLayout)` signal +
  `set_plot_layout(new)` setter.
* S2.D.1 — `controllerSettingsChanged(ControllerSettings)` signal +
  `set_controller_settings(new)` setter; `is_dirty` + `dirtyChanged(bool)`
  signal + internal `_set_dirty`/`_clear_dirty` for the
  `ConfigurationCommandStack` clean-binding.
* S2.D.3 — `simulationSettingsChanged(SimulationSettings)` signal +
  `set_simulation_settings(new)` setter (the only remaining spec/03 §9
  signal after S2.D.1).

All mutations honor the ADR-020 transition-only emission rule: a
setter that receives a value-equal object is a no-op and emits no
signal, preventing subscriber storms under reactive feedback loops
and matching `WorkspaceModel`'s contract one-for-one.

References:
----------
* `specs/03_configuration_requirements.md` §9 (Configuration Signals)
* `specs/06_data_flow_and_architecture.md` §4.3.1 (Module Signals)
* `decisions/ADR-018-signal-payload-contracts.md`
* `decisions/ADR-020-clean-changed-dirty-tracking.md` (transition-only rule)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Signal

from .controller_settings import ControllerSettings
from .io_selection import IOSelection
from .plot_layout import PlotLayout

if TYPE_CHECKING:
    from .simulation_settings import SimulationSettings


class ConfigurationModel(QObject):
    """QObject host owning the three Phase-1 configuration sections.

    Args:
        controller_settings: Initial `ControllerSettings` value (frozen
            dataclass). The model retains a reference; replacement via
            S2.D setters will produce new value instances.
        io_selection: Initial `IOSelection` value. Mutated via
            `set_io_selection` (S2.B.3) when reactive stale-detection
            flips an entry's status.
        simulation_settings: Initial `SimulationSettings` value.
        parent: Optional Qt parent. Matches `WorkspaceModel`'s
            signature so application bootstrap can compose both
            uniformly.

    Signals:
        ioSelectionChanged: Fires whenever `set_io_selection`
            installs a new value that differs from the current one.
            The payload is the new `IOSelection` instance (carries
            full state per ADR-018 "self-contained payloads where
            cheap").
    """

    # S2.B.3 / S2.C / S2.D.1 signals. The last remaining spec/03 §9
    # signal (`simulationSettingsChanged`) lands in S2.D.3 alongside
    # its setter.
    ioSelectionChanged = Signal(IOSelection)
    plotLayoutChanged = Signal(PlotLayout)
    controllerSettingsChanged = Signal(ControllerSettings)
    # S2.D.1 — module-level dirty bit. Mirrors `WorkspaceModel.dirtyChanged`
    # so the shell's title-bar dirty indicator can OR both signals
    # into a single project-level "dirty" view (spec/03 §9).
    dirtyChanged = Signal(bool)

    def __init__(
        self,
        *,
        controller_settings: ControllerSettings,
        io_selection: IOSelection,
        simulation_settings: SimulationSettings,
        plot_layout: PlotLayout,
        parent: QObject | None = None,
    ) -> None:
        """Construct the model with starting values for every section."""
        super().__init__(parent)
        self._controller_settings: ControllerSettings = controller_settings
        self._io_selection: IOSelection = io_selection
        self._simulation_settings: SimulationSettings = simulation_settings
        self._plot_layout: PlotLayout = plot_layout
        self._dirty: bool = False

    # ------------------------------------------------------------------ #
    # Read-only accessors
    # ------------------------------------------------------------------ #

    @property
    def controller_settings(self) -> ControllerSettings:
        """The current `ControllerSettings` (frozen value)."""
        return self._controller_settings

    @property
    def io_selection(self) -> IOSelection:
        """The current `IOSelection` (frozen value)."""
        return self._io_selection

    @property
    def simulation_settings(self) -> SimulationSettings:
        """The current `SimulationSettings` (frozen value)."""
        return self._simulation_settings

    @property
    def plot_layout(self) -> PlotLayout:
        """The current `PlotLayout` (frozen value)."""
        return self._plot_layout

    @property
    def is_dirty(self) -> bool:
        """Module-level dirty bit per ADR-020.

        `True` after any mutation pushed via the command stack
        until the stack returns to its clean index (or the model
        is explicitly cleared by a persistence-layer save).
        """
        return self._dirty

    # ------------------------------------------------------------------ #
    # Mutations
    # ------------------------------------------------------------------ #

    def set_io_selection(self, new: IOSelection) -> None:
        """Install a new `IOSelection` and emit `ioSelectionChanged`.

        Transition-only emission per ADR-020: when `new` is value-
        equal to the current selection, the call is a no-op and the
        signal does NOT fire. This keeps subscriber storms small
        under reactive feedback loops (e.g., observer marks already-
        stale entries again on repeated `componentRemoved` events).
        """
        if new == self._io_selection:
            return
        self._io_selection = new
        self.ioSelectionChanged.emit(new)

    def set_plot_layout(self, new: PlotLayout) -> None:
        """Install a new `PlotLayout` and emit `plotLayoutChanged`.

        Same transition-only contract as `set_io_selection`. The
        Phase-1 API is deliberately a full-replacement setter only:
        partial mutations (per-slot plot_type, per-slot
        channel_selection) are produced on the caller side using
        `PlotSlotConfig.with_plot_type` + `PlotLayout.with_slot_replaced`
        and pushed through this single entry point. S2.D
        `ChangePlotTypeCommand` will follow the same shape; no
        per-slot setter is added here so the API stays narrow.
        """
        if new == self._plot_layout:
            return
        self._plot_layout = new
        self.plotLayoutChanged.emit(new)

    def set_controller_settings(self, new: ControllerSettings) -> None:
        """Install a new `ControllerSettings` and emit `controllerSettingsChanged`.

        Full-replacement setter matching the S2.B.3 / S2.C pattern.
        Per-controller mutations (add, remove, type change, parameter
        edit) are produced caller-side via
        `ControllerSettings.with_controller_added/removed/replaced`
        and pushed through this entry point by the matching S2.D.1
        commands. Transition-only emission per ADR-020.
        """
        if new == self._controller_settings:
            return
        self._controller_settings = new
        self.controllerSettingsChanged.emit(new)

    # ------------------------------------------------------------------ #
    # Internal dirty helpers (called by ConfigurationCommandStack)
    # ------------------------------------------------------------------ #

    def _set_dirty(self) -> None:
        """Mark the model dirty; emit `dirtyChanged(True)` on transition.

        Internal helper, called by `ConfigurationCommandStack` when
        a command pushes the underlying QUndoStack away from its
        clean index. Transition-only emission per ADR-020: redundant
        calls while already dirty are silent no-ops.
        """
        if self._dirty:
            return
        self._dirty = True
        self.dirtyChanged.emit(True)

    def _clear_dirty(self) -> None:
        """Mark the model clean; emit `dirtyChanged(False)` on transition.

        Called by the command stack on `cleanChanged(True)` (stack
        index returned to its clean baseline) and by persistence
        layer's save flow (S2.E). Transition-only per ADR-020.
        """
        if not self._dirty:
            return
        self._dirty = False
        self.dirtyChanged.emit(False)


__all__ = ["ConfigurationModel"]
