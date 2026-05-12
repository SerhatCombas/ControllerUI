"""ConfigurationModel: QObject host for the three Phase-1 config sections.

Parallels `SystemModelingModule.WorkspaceModel` in role: a single
QObject owning the canonical configuration state and emitting the
Qt signals that spec/03 §9 + spec/06 §4.3.1 mandate. The three
S2.A dataclass families (ControllerSettings, IOSelection,
SimulationSettings) are frozen value types — they cannot carry
signals — so this class is the source of truth and signal
producer.

Phase-1 scope at S2.B.3 (this commit):

* Holds the three dataclasses by reference.
* Emits `ioSelectionChanged(IOSelection)` on mutation.
* Provides `set_io_selection(new)` mutation that no-ops on equal
  values (matches the WorkspaceModel transition-only contract
  per ADR-020).

Deferred to S2.D (user-driven mutation commands):

* `controllerSettingsChanged()`, `simulationSettingsChanged()`,
  and `plotLayoutChanged()` signals.
* Setter API for the remaining sections.

The class name is permanent: adding the other three signals + setters
in S2.D is a non-breaking widening of the API surface, not a rename.

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

from .io_selection import IOSelection
from .plot_layout import PlotLayout

if TYPE_CHECKING:
    from .controller_settings import ControllerSettings
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

    # S2.B.3 + S2.C signals. The remaining two spec/03 §9 signals
    # (controllerSettingsChanged, simulationSettingsChanged) land
    # in S2.D when user-driven mutation commands arrive.
    ioSelectionChanged = Signal(IOSelection)
    plotLayoutChanged = Signal(PlotLayout)

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


__all__ = ["ConfigurationModel"]
