"""Configuration-side validator (S2.B.2).

Parallels `SystemModelingModule.GraphValidator`: stateless class,
explicit-snapshot args, one public `validate` entry, one private
helper per rule. The validator is a *reporter*; it never mutates
the dataclasses it inspects. Reactive state updates (e.g., flipping
`IOEntry.status` to `"stale"` when a referenced workspace component
is removed) live in S2.B.3.

Boundary between S2.B.2 and S2.B.3:

* **S2.B.2** (this file): pure function from snapshot →
  `ValidationReport`. On-demand. The caller supplies the
  configuration sections and the workspace snapshot
  (`components` mapping + `ComponentRegistry`) at the moment of
  the call. Output is read-only; no models are touched.
* **S2.B.3** (next sub-commit): signal-driven coordinator that
  observes `WorkspaceModel.componentRemoved` /
  `componentChanged` and mutates `IOSelection`'s `status` field
  in place. The validator in this file may be invoked by the
  coordinator to compute the new report; the coordinator owns
  the mutation.

Rule set (spec/03 §10.1, Phase 1 subset):

1. **Simulation time bounds** — `stop_time > start_time`,
   `sample_time > 0`, `max_step > 0` if set. Errors.
2. **Unsupported controller_type** — anything outside the Phase-1
   `{P, PI, PD, PID}` set. Warning per spec §10.2 and §12.2.
3. **Unsupported solver** — anything outside the Phase-1
   `{auto, fixed_step, variable_step}` set. Warning per spec §7.5.
4. **Stale controller I/O linkage** — `input_ref` / `output_ref`
   on an *enabled* controller points to an id absent from
   `IOSelection.inputs` / `.outputs`. Warning per spec §5.5.
5. **Stale I/O workspace reference** — `IOSourcePortRef.port_ref`
   targets a missing component (component_id absent from
   snapshot) or a missing port (port_id absent from the
   component's definition ports). Warning per spec §6.7;
   becomes error before simulation in Phase 2.

References:
----------
* `specs/03_configuration_requirements.md` §10 (Validation)
* `specs/11_error_code_catalog.md` §7.7 (Validation category)
* `decisions/ADR-018-signal-payload-contracts.md` (ValidationReport payload)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from shared.types import ValidationIssue, ValidationReport

from .plot_layout import PLOT_TYPE_KIND_MAP

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from shared.registry import ComponentRegistry
    from shared.types import ComponentInstanceLike

    from .controller_settings import ControllerSettings, ControllerSpec
    from .io_selection import IOEntry, IOSelection
    from .plot_layout import PlotLayout, PlotSlotConfig
    from .simulation_settings import SimulationSettings


# Phase-1 closed sets. Unknown values are loaded but flagged as
# warnings per spec/03 §10.2 + §12.2 — the validator surfaces the
# warning; the loader preserves the raw string in the dataclass.
_PHASE1_CONTROLLER_TYPES: Final[frozenset[str]] = frozenset({"P", "PI", "PD", "PID"})
_PHASE1_SOLVERS: Final[frozenset[str]] = frozenset({"auto", "fixed_step", "variable_step"})


class ConfigurationValidator:
    """Stateless validator for the three Phase-1 configuration sections.

    Mirrors `GraphValidator` in shape: instances carry no state, all
    inputs flow through method arguments, and individual rules live in
    private helpers that yield `ValidationIssue` instances. Tests
    target the public `validate` method; helpers are implementation
    detail.
    """

    def validate(
        self,
        controller_settings: ControllerSettings,
        io_selection: IOSelection,
        simulation_settings: SimulationSettings,
        *,
        components: Mapping[str, ComponentInstanceLike],
        registry: ComponentRegistry,
        plot_layout: PlotLayout | None = None,
    ) -> ValidationReport:
        """Run every Phase-1 rule and return the aggregated report.

        Args:
            controller_settings: Controller list to validate.
            io_selection: I/O entries to validate (and to cross-check
                against controller references).
            simulation_settings: Simulation parameters to validate.
            components: Workspace snapshot — `component_id` →
                `ComponentInstance`. Used by the stale-reference
                rule only; the validator never mutates it.
            registry: `ComponentRegistry` resolving each component's
                `definition_id` to its `PortDefinition` list. Used
                for the missing-port check.
            plot_layout: Optional `PlotLayout` to validate. Defaults
                to an empty layout (no plot-side issues raised). Made
                optional so pre-S2.C call sites keep working without
                churn; S2.C+ callers pass it explicitly.

        Returns:
            `ValidationReport` carrying every issue produced by all
            rules. An empty report means the configuration is
            internally consistent and consistent with the supplied
            workspace snapshot.
        """
        # Local import keeps the module import-time cost low and
        # avoids forcing `PlotLayout` into the TYPE_CHECKING-only
        # signature when the caller omits the argument.
        from .plot_layout import PlotLayout as _PlotLayout

        effective_layout: PlotLayout = plot_layout if plot_layout is not None else _PlotLayout()
        issues: list[ValidationIssue] = []
        issues.extend(self._check_simulation_time_bounds(simulation_settings))
        issues.extend(self._check_unsupported_solver(simulation_settings))
        issues.extend(self._check_unsupported_controller_type(controller_settings))
        issues.extend(self._check_controller_io_linkage(controller_settings, io_selection))
        issues.extend(self._check_io_workspace_references(io_selection, components, registry))
        issues.extend(self._check_plot_type_known(effective_layout))
        issues.extend(self._check_channel_selection_kind_match(effective_layout))
        return ValidationReport(issues=tuple(issues))

    # ------------------------------------------------------------------ #
    # Rule 1 — simulation time bounds (spec/03 §7.3)
    # ------------------------------------------------------------------ #

    def _check_simulation_time_bounds(self, sim: SimulationSettings) -> Iterable[ValidationIssue]:
        """Per spec §7.3: stop > start, sample > 0, max_step > 0."""
        if sim.stop_time <= sim.start_time:
            yield _issue_simulation_stop_le_start(sim)
        if sim.sample_time <= 0:
            yield _issue_simulation_sample_time_non_positive(sim)
        if sim.max_step is not None and sim.max_step <= 0:
            yield _issue_simulation_max_step_non_positive(sim)

    # ------------------------------------------------------------------ #
    # Rule 2 — unsupported controller_type (spec/03 §10.2 + §12.2)
    # ------------------------------------------------------------------ #

    def _check_unsupported_controller_type(
        self, controller_settings: ControllerSettings
    ) -> Iterable[ValidationIssue]:
        """Warn for any controller whose type is outside the Phase-1 set."""
        for spec in controller_settings.controllers:
            if spec.controller_type not in _PHASE1_CONTROLLER_TYPES:
                yield _issue_unsupported_controller_type(spec)

    # ------------------------------------------------------------------ #
    # Rule 3 — unsupported solver (spec/03 §7.5)
    # ------------------------------------------------------------------ #

    def _check_unsupported_solver(self, sim: SimulationSettings) -> Iterable[ValidationIssue]:
        """Warn when `solver` is outside the Phase-1 supported set."""
        if sim.solver not in _PHASE1_SOLVERS:
            yield _issue_unsupported_solver(sim.solver)

    # ------------------------------------------------------------------ #
    # Rule 4 — stale controller I/O linkage (spec/03 §5.5)
    # ------------------------------------------------------------------ #

    def _check_controller_io_linkage(
        self,
        controller_settings: ControllerSettings,
        io_selection: IOSelection,
    ) -> Iterable[ValidationIssue]:
        """Per spec §5.5: enabled controller's input/output ref must resolve."""
        input_ids = {e.id for e in io_selection.inputs}
        output_ids = {e.id for e in io_selection.outputs}
        for spec in controller_settings.controllers:
            if not spec.enabled:
                # Disabled controllers don't warn (spec §5.5).
                continue
            if spec.input_ref is not None and spec.input_ref not in input_ids:
                yield _issue_stale_controller_input_ref(spec)
            if spec.output_ref is not None and spec.output_ref not in output_ids:
                yield _issue_stale_controller_output_ref(spec)

    # ------------------------------------------------------------------ #
    # Rule 5 — stale I/O workspace references (spec/03 §6.7)
    # ------------------------------------------------------------------ #

    def _check_io_workspace_references(
        self,
        io_selection: IOSelection,
        components: Mapping[str, ComponentInstanceLike],
        registry: ComponentRegistry,
    ) -> Iterable[ValidationIssue]:
        """Per spec §6.7: source.port_ref must resolve in the workspace."""
        for entry in (*io_selection.inputs, *io_selection.outputs):
            # Phase 1 `IOSource` is the single-variant alias
            # `IOSourcePortRef`; mypy narrows accordingly. When
            # Phase 2 widens the union (probe_ref, state_variable_ref,
            # ...), this loop body becomes a `match source.kind:`
            # dispatch and each variant adds its own helper.
            port_ref = entry.source.port_ref
            component = components.get(port_ref.component_id)
            if component is None:
                yield _issue_stale_io_component_ref(entry, port_ref.component_id)
                continue
            # Port existence check via the registry. Unknown
            # definition_id is treated as out-of-scope here (the
            # registry should already have warned at bootstrap);
            # we skip the port check to avoid noisy double-reports.
            try:
                definition = registry.get(component.definition_id)
            except KeyError:
                continue
            if not any(p.id == port_ref.port_id for p in definition.ports):
                yield _issue_stale_io_port_ref(entry, port_ref.port_id)

    # ------------------------------------------------------------------ #
    # Rule 6 — unknown plot_type (spec/03 §8.4 + §12.2)
    # ------------------------------------------------------------------ #

    def _check_plot_type_known(self, plot_layout: PlotLayout) -> Iterable[ValidationIssue]:
        """Warn for any slot whose `plot_type` is not in the Phase-1+2 map."""
        for slot in plot_layout.slots:
            if slot.plot_type not in PLOT_TYPE_KIND_MAP:
                yield _issue_unknown_plot_type(slot)

    # ------------------------------------------------------------------ #
    # Rule 7 — channel_selection.kind ↔ plot_type compatibility
    # (spec/03 §8.6 + §10.1)
    # ------------------------------------------------------------------ #

    def _check_channel_selection_kind_match(
        self, plot_layout: PlotLayout
    ) -> Iterable[ValidationIssue]:
        """Error when a slot's `channel_selection.kind` doesn't match its `plot_type`.

        Unknown plot_types are skipped here (no canonical kind to
        compare against); rule 6 already surfaces them as warnings.
        """
        for slot in plot_layout.slots:
            expected_kind = PLOT_TYPE_KIND_MAP.get(slot.plot_type)
            if expected_kind is None:
                continue
            if slot.channel_selection.kind != expected_kind:
                yield _issue_channel_selection_kind_mismatch(slot, expected_kind)


# ====================================================================== #
# Issue constructors
# ====================================================================== #
#
# Following the GraphValidator pattern: each rule has a dedicated
# constructor function so the rule body stays at a single level of
# abstraction (yield issue or continue). Codes are namespaced under
# `error.validation.*` / `warning.validation.*` per spec/11 §7.7.


def _issue_simulation_stop_le_start(sim: SimulationSettings) -> ValidationIssue:
    code = "error.validation.simulation_stop_time_le_start_time"
    return ValidationIssue(
        issue_id=f"{code}|workspace",
        severity="error",
        code=code,
        message=(
            f"simulation stop_time ({sim.stop_time}) must be greater than "
            f"start_time ({sim.start_time})."
        ),
        subject_kind="workspace",
        subject_id=None,
        context={"start_time": sim.start_time, "stop_time": sim.stop_time},
    )


def _issue_simulation_sample_time_non_positive(
    sim: SimulationSettings,
) -> ValidationIssue:
    code = "error.validation.simulation_sample_time_non_positive"
    return ValidationIssue(
        issue_id=f"{code}|workspace",
        severity="error",
        code=code,
        message=f"simulation sample_time ({sim.sample_time}) must be positive.",
        subject_kind="workspace",
        subject_id=None,
        context={"sample_time": sim.sample_time},
    )


def _issue_simulation_max_step_non_positive(
    sim: SimulationSettings,
) -> ValidationIssue:
    code = "error.validation.simulation_max_step_non_positive"
    return ValidationIssue(
        issue_id=f"{code}|workspace",
        severity="error",
        code=code,
        message=(
            f"simulation max_step ({sim.max_step}) must be positive when "
            f"provided; pass None to disable the cap."
        ),
        subject_kind="workspace",
        subject_id=None,
        context={"max_step": sim.max_step},
    )


def _issue_unsupported_controller_type(spec: ControllerSpec) -> ValidationIssue:
    code = "warning.validation.unsupported_controller_type"
    return ValidationIssue(
        issue_id=f"{code}|{spec.id}",
        severity="warning",
        code=code,
        message=(
            f"controller {spec.id!r} has controller_type "
            f"{spec.controller_type!r}, which is outside the Phase-1 set "
            f"(P, PI, PD, PID). The value is preserved on save."
        ),
        subject_kind="workspace",
        subject_id=spec.id,
        context={"controller_type": spec.controller_type},
    )


def _issue_unsupported_solver(solver: str) -> ValidationIssue:
    code = "warning.validation.unsupported_solver"
    return ValidationIssue(
        issue_id=f"{code}|workspace",
        severity="warning",
        code=code,
        message=(
            f"solver {solver!r} is outside the Phase-1 supported set "
            f"(auto, fixed_step, variable_step). The value is preserved "
            f"on save."
        ),
        subject_kind="workspace",
        subject_id=None,
        context={"solver": solver},
    )


def _issue_stale_controller_input_ref(spec: ControllerSpec) -> ValidationIssue:
    code = "warning.validation.stale_controller_input_ref"
    return ValidationIssue(
        issue_id=f"{code}|{spec.id}",
        severity="warning",
        code=code,
        message=(
            f"enabled controller {spec.id!r} references input "
            f"{spec.input_ref!r}, which is not present in "
            f"io_selection.inputs."
        ),
        subject_kind="workspace",
        subject_id=spec.id,
        context={"input_ref": spec.input_ref},
    )


def _issue_stale_controller_output_ref(spec: ControllerSpec) -> ValidationIssue:
    code = "warning.validation.stale_controller_output_ref"
    return ValidationIssue(
        issue_id=f"{code}|{spec.id}",
        severity="warning",
        code=code,
        message=(
            f"enabled controller {spec.id!r} references output "
            f"{spec.output_ref!r}, which is not present in "
            f"io_selection.outputs."
        ),
        subject_kind="workspace",
        subject_id=spec.id,
        context={"output_ref": spec.output_ref},
    )


def _issue_stale_io_component_ref(entry: IOEntry, component_id: str) -> ValidationIssue:
    code = "warning.validation.stale_io_component_ref"
    return ValidationIssue(
        issue_id=f"{code}|{entry.id}",
        severity="warning",
        code=code,
        message=(
            f"I/O entry {entry.id!r} references component "
            f"{component_id!r}, which is not present in the workspace."
        ),
        subject_kind="component",
        subject_id=component_id,
        context={"io_entry_id": entry.id, "component_id": component_id},
    )


def _issue_stale_io_port_ref(entry: IOEntry, port_id: str) -> ValidationIssue:
    code = "warning.validation.stale_io_port_ref"
    return ValidationIssue(
        issue_id=f"{code}|{entry.id}",
        severity="warning",
        code=code,
        message=(
            f"I/O entry {entry.id!r} references port {port_id!r}, "
            f"which is not declared on the target component's definition."
        ),
        subject_kind="component",
        subject_id=None,
        context={"io_entry_id": entry.id, "port_id": port_id},
    )


def _issue_unknown_plot_type(slot: PlotSlotConfig) -> ValidationIssue:
    code = "warning.validation.unknown_plot_type"
    return ValidationIssue(
        issue_id=f"{code}|{slot.slot_id}",
        severity="warning",
        code=code,
        message=(
            f"plot slot {slot.slot_id!r} has plot_type "
            f"{slot.plot_type!r}, which is outside the known set. "
            f"The value is preserved on save and rendered as a "
            f"placeholder per spec/03 §12.2."
        ),
        subject_kind="workspace",
        subject_id=None,
        context={"slot_id": slot.slot_id, "plot_type": slot.plot_type},
    )


def _issue_channel_selection_kind_mismatch(
    slot: PlotSlotConfig, expected_kind: str
) -> ValidationIssue:
    code = "error.validation.channel_selection_kind_mismatch"
    return ValidationIssue(
        issue_id=f"{code}|{slot.slot_id}",
        severity="error",
        code=code,
        message=(
            f"plot slot {slot.slot_id!r} uses plot_type "
            f"{slot.plot_type!r} (kind {expected_kind!r}) but its "
            f"channel_selection.kind is "
            f"{slot.channel_selection.kind!r}."
        ),
        subject_kind="workspace",
        subject_id=None,
        context={
            "slot_id": slot.slot_id,
            "plot_type": slot.plot_type,
            "expected_kind": expected_kind,
            "actual_kind": slot.channel_selection.kind,
        },
    )


__all__ = ["ConfigurationValidator"]
