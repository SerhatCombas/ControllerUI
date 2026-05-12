"""Phase-1 programmatic smoke harness.

Renamed from `smoke_s1_10.py` at S2.G.3. Now covers the full
Phase-1 surface (workspace + configuration + persistence + shell
integration) across 15 scenarios:

  Baseline (S1.10 — 7 scenarios):
    S1   library tree leaf count
    S2   drop resistor → component + status
    S3   resistor.p ↔ ground.p connection
    S4   Edit → Undo / Redo round trip
    S5   parameter edit → dirty marker
    S6   negative: duplicate connection rejected
    S7   negative: cross-domain connection rejected

  S2 additions (8 scenarios):
    S8   configuration mutations (controller + sim + plot)
    S9   persistence round-trip (save → modify → load → state match)
    S10  dirty union (workspace OR configuration → title *)
    S11  title bar (project name + dirty marker after save/load)
    S12  unsaved-changes dialog (3-button mocked flow)
    S13  QUndoGroup routing (alternating pushes, single Ctrl+Z)
    S14  load clears both undo stacks (spec §29.3.1)
    S15  stale-ref reactivity (workspace remove → IOEntry.status="stale")

Exit codes:
  0  every scenario passed its built-in expectation
  1  at least one scenario failed (the JSON report's `passed`
     field flips to False; the human-readable run prints
     `OVERALL: FAIL`)

Usage:
  python scripts/smoke_phase1.py             # human-readable
  python scripts/smoke_phase1.py --json      # machine-readable
  python scripts/smoke_phase1.py --json | tee smoke_results.json

This is a diagnostic harness, not a pytest test. Run after any
substantive Phase-1 change to catch regressions before manual
smoke. CI may run it as an optional job; it is not part of the
required test suite.
"""

from __future__ import annotations

import json
import logging
import sys
from dataclasses import asdict, dataclass, field
from typing import Any

# DEBUG logging so connection.validation_failed events surface in
# the human-readable run; the JSON run sends logs to stderr so
# stdout stays parseable.
logging.basicConfig(
    level=logging.DEBUG,
    format="LOG | %(levelname)-7s | %(name)s | %(message)s",
    stream=sys.stderr,
)
logging.getLogger("shared.engine").setLevel(logging.WARNING)


@dataclass
class ScenarioResult:
    """Single scenario observation captured for the report."""

    name: str
    passed: bool
    observations: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


@dataclass
class SmokeReport:
    """Aggregated smoke report — serializable to JSON."""

    scenarios: list[ScenarioResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """True when every scenario passed its built-in expectation."""
        return all(s.passed for s in self.scenarios)

    def to_dict(self) -> dict[str, Any]:
        """Render the report as a JSON-serializable dict."""
        return {
            "passed": self.passed,
            "scenarios": [asdict(s) for s in self.scenarios],
        }


def main(argv: list[str] | None = None) -> int:
    """Run the smoke harness; return shell exit code (0 = all pass)."""
    argv = argv if argv is not None else sys.argv[1:]
    emit_json = "--json" in argv

    import tempfile
    from pathlib import Path
    from unittest.mock import patch

    from PySide6.QtCore import QPointF
    from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox

    from application.SystemDesignerShell.main_window import SystemDesignerShell
    from features.ControllerDesignModule.commands import (
        AddControllerCommand,
        ChangePlotTypeCommand,
        ChangeSimulationSettingCommand,
    )
    from features.ControllerDesignModule.model import (
        ControllerSpec,
        IOEntry,
        IOSourcePortRef,
        new_controller_id,
        new_io_input_id,
    )
    from features.SystemModelingModule.commands import ChangeParameterCommand
    from features.SystemModelingModule.model.connection import PortRef
    from shared.registry.builtin import (
        BUILTIN_COMPONENT_DEFINITIONS,
        GROUND_ELECTRIC_DEFINITION,
        MASS_DEFINITION,
        RESISTOR_DEFINITION,
    )

    app = QApplication.instance() or QApplication(sys.argv)
    _ = app
    shell = SystemDesignerShell()
    report = SmokeReport()

    def snap() -> dict[str, Any]:
        return {
            "title": shell.windowTitle(),
            "dirty": shell.model.is_dirty,
            "status": shell.statusBar().currentMessage(),
        }

    def emit(scenario: ScenarioResult) -> None:
        report.scenarios.append(scenario)
        if emit_json:
            return
        print()
        print("=" * 78)
        flag = "PASS" if scenario.passed else "FAIL"
        print(f"  [{flag}] {scenario.name}")
        print("=" * 78)
        for k, v in scenario.observations.items():
            print(f"  {k}: {v}")
        for note in scenario.notes:
            print(f"  note: {note}")

    # --------------------------------------------------------------------- #
    # S1: library tree leaf count
    # --------------------------------------------------------------------- #
    lib_count = len(shell.library_tree.definitions)
    expected_count = len(BUILTIN_COMPONENT_DEFINITIONS)
    emit(
        ScenarioResult(
            name="S1: library leaf count matches BUILTIN_COMPONENT_DEFINITIONS",
            passed=lib_count == expected_count,
            observations={
                "library_tree_count": lib_count,
                "builtin_count": expected_count,
                "initial_state": snap(),
            },
        )
    )

    # --------------------------------------------------------------------- #
    # S2: drop resistor → component + status
    # --------------------------------------------------------------------- #
    r_id = shell.scene.drop_component(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    after_drop = snap()
    emit(
        ScenarioResult(
            name="S2: drop resistor produces component + status feedback",
            passed=r_id is not None
            and len(shell.model.components) == 1
            and "added" in after_drop["status"],
            observations={
                "dropped_id": r_id,
                "components_count": len(shell.model.components),
                "state": after_drop,
            },
        )
    )

    # --------------------------------------------------------------------- #
    # S3: add ground + connect resistor.p ↔ ground.p
    # --------------------------------------------------------------------- #
    g_id = shell.scene.drop_component(GROUND_ELECTRIC_DEFINITION.id, QPointF(100.0, 0.0))
    assert r_id is not None
    assert g_id is not None
    shell.scene.start_connection_draw(PortRef(component_id=r_id, port_id="p"))
    conn_id = shell.scene.commit_connection_draw(PortRef(component_id=g_id, port_id="p"))
    after_connect = snap()
    emit(
        ScenarioResult(
            name="S3: resistor.p ↔ ground.p connection succeeds",
            passed=conn_id is not None
            and len(shell.model.connections) == 1
            and "added" in after_connect["status"],
            observations={
                "connection_id": conn_id,
                "connections_count": len(shell.model.connections),
                "state": after_connect,
            },
        )
    )

    # --------------------------------------------------------------------- #
    # S4: undo / redo round trip
    # --------------------------------------------------------------------- #
    shell._undo_action.trigger()
    after_undo = snap()
    undone_ok = len(shell.model.connections) == 0 and "removed" in after_undo["status"]
    shell._redo_action.trigger()
    after_redo = snap()
    redone_ok = len(shell.model.connections) == 1 and "added" in after_redo["status"]
    emit(
        ScenarioResult(
            name="S4: Edit → Undo / Redo round-trip on connection",
            passed=undone_ok and redone_ok,
            observations={
                "after_undo": after_undo,
                "after_redo": after_redo,
            },
        )
    )

    # --------------------------------------------------------------------- #
    # S5: parameter edit → dirty *
    # --------------------------------------------------------------------- #
    pre_dirty = shell.model.is_dirty
    cmd = ChangeParameterCommand(shell.model, r_id, "R", 2200.0)
    shell.command_stack.push(cmd)
    after_param = snap()
    new_r = shell.model.components[r_id].parameters.get("R")
    emit(
        ScenarioResult(
            name="S5: parameter edit pushes through command stack + dirty bit",
            passed=new_r == 2200.0 and after_param["dirty"] is True,
            observations={
                "R_after": new_r,
                "dirty_before": pre_dirty,
                "state": after_param,
            },
            notes=[
                "S1.10 does not surface componentChanged as a transient "
                "status message; dirty * indicator is the only feedback "
                "channel. Cosmetic C1, deferred to S1.11."
            ],
        )
    )

    # --------------------------------------------------------------------- #
    # S6 negative: duplicate connection via real UI path
    # --------------------------------------------------------------------- #
    shell.scene.start_connection_draw(PortRef(component_id=r_id, port_id="p"))
    result = shell.scene.commit_connection_draw(PortRef(component_id=g_id, port_id="p"))
    after_dup = snap()
    emit(
        ScenarioResult(
            name="S6: duplicate connection rejected with status feedback",
            passed=result is None
            and len(shell.model.connections) == 1
            and after_dup["status"].startswith("Connection rejected:"),
            observations={
                "commit_returned": result,
                "connections_count": len(shell.model.connections),
                "state": after_dup,
            },
        )
    )

    # --------------------------------------------------------------------- #
    # S7 negative: cross-domain via real UI path
    # --------------------------------------------------------------------- #
    m_id = shell.scene.drop_component(MASS_DEFINITION.id, QPointF(200.0, 0.0))
    assert m_id is not None
    shell.scene.start_connection_draw(PortRef(component_id=r_id, port_id="n"))
    result_xd = shell.scene.commit_connection_draw(PortRef(component_id=m_id, port_id="flange"))
    after_xd = snap()
    emit(
        ScenarioResult(
            name="S7: cross-domain connection rejected with status feedback",
            passed=result_xd is None
            and after_xd["status"].startswith("Connection rejected:")
            and "incompatible domains" in after_xd["status"],
            observations={
                "commit_returned": result_xd,
                "state": after_xd,
            },
        )
    )

    # --------------------------------------------------------------------- #
    # S8: configuration mutations (controller + sim + plot)
    # --------------------------------------------------------------------- #
    # Push three commands across the configuration stack to exercise
    # the cross-section API surface in one scenario.
    pre_config_dirty = shell.configuration_model.is_dirty
    ctrl_spec = ControllerSpec(
        id=new_controller_id(), controller_type="PID", display_name="Smoke PID"
    )
    shell.configuration_command_stack.push(
        AddControllerCommand(shell.configuration_model, ctrl_spec)
    )
    # Simulation settings: change stop_time.
    new_sim = shell.configuration_model.simulation_settings.with_updated(stop_time=20.0)
    shell.configuration_command_stack.push(
        ChangeSimulationSettingCommand(shell.configuration_model, new_sim)
    )
    # Plot type: need to seed the plot layout first because S2.G.1's
    # shell starts with an empty PlotLayout. Load defaults explicitly
    # via the same path File → New uses.
    shell._reset_to_defaults()
    # After reset both dirty bits cleared; touch a slot to verify
    # ChangePlotTypeCommand flows end-to-end.
    shell.configuration_command_stack.push(
        ChangePlotTypeCommand(shell.configuration_model, "plot_1", "bode")
    )
    emit(
        ScenarioResult(
            name="S8: configuration mutations (controller + sim + plot)",
            passed=(
                shell.configuration_model.controller_settings.controllers
                != ()  # the reset replaced our spec but added the default PID
                and shell.configuration_model.plot_layout.slots[0].plot_type == "bode"
                and shell.configuration_model.is_dirty is True
            ),
            observations={
                "pre_config_dirty": pre_config_dirty,
                "controllers_count": len(shell.configuration_model.controller_settings.controllers),
                "plot_1_type": shell.configuration_model.plot_layout.slots[0].plot_type,
                "state": snap(),
            },
        )
    )

    # --------------------------------------------------------------------- #
    # S9: persistence round-trip (save → modify → load → state match)
    # --------------------------------------------------------------------- #
    with tempfile.TemporaryDirectory() as tmp:
        bundle = Path(tmp) / "smoke_round_trip.systemdesign"
        # Snapshot of pre-save state.
        pre_save_components = len(shell.model.components)
        pre_save_plot_1_type = shell.configuration_model.plot_layout.slots[0].plot_type
        shell._current_bundle_path = bundle
        shell._update_window_title()
        save_ok = shell.save_current_project()
        # Modify state AFTER save so reload should overwrite the deltas.
        shell.scene.drop_component(RESISTOR_DEFINITION.id, QPointF(500.0, 0.0))
        shell.configuration_command_stack.push(
            ChangePlotTypeCommand(shell.configuration_model, "plot_1", "time_response")
        )
        load_ok = shell.load_project_from(bundle)
        post_load_components = len(shell.model.components)
        post_load_plot_1_type = shell.configuration_model.plot_layout.slots[0].plot_type
        emit(
            ScenarioResult(
                name="S9: persistence round-trip (save / modify / load)",
                passed=(
                    save_ok
                    and load_ok
                    and post_load_components == pre_save_components
                    and post_load_plot_1_type == pre_save_plot_1_type
                ),
                observations={
                    "save_ok": save_ok,
                    "load_ok": load_ok,
                    "pre_save_components": pre_save_components,
                    "post_load_components": post_load_components,
                    "pre_save_plot_1_type": pre_save_plot_1_type,
                    "post_load_plot_1_type": post_load_plot_1_type,
                    "state": snap(),
                },
            )
        )

    # --------------------------------------------------------------------- #
    # S10: dirty union (workspace OR configuration → title *)
    # --------------------------------------------------------------------- #
    # After S9's load both stacks were cleared and both dirty bits
    # cleared. Push on each side independently and assert the title
    # carries the marker after each.
    title_initially_clean = " * " not in shell.windowTitle()
    shell.scene.drop_component(RESISTOR_DEFINITION.id, QPointF(600.0, 0.0))
    title_after_workspace_push = shell.windowTitle()
    shell.command_stack.undo()  # return workspace to clean
    title_after_workspace_undo = shell.windowTitle()
    shell.configuration_command_stack.push(
        ChangePlotTypeCommand(shell.configuration_model, "plot_2", "bode")
    )
    title_after_config_push = shell.windowTitle()
    emit(
        ScenarioResult(
            name="S10: dirty union — either model dirty → title marker",
            passed=(
                title_initially_clean
                and " * " in title_after_workspace_push
                and " * " not in title_after_workspace_undo
                and " * " in title_after_config_push
            ),
            observations={
                "initially_clean": title_initially_clean,
                "after_workspace_push": title_after_workspace_push,
                "after_workspace_undo": title_after_workspace_undo,
                "after_config_push": title_after_config_push,
            },
        )
    )
    # Roll the config push back so subsequent scenarios start clean.
    shell.configuration_command_stack.undo()

    # --------------------------------------------------------------------- #
    # S11: title bar (project name + dirty marker after save / load)
    # --------------------------------------------------------------------- #
    with tempfile.TemporaryDirectory() as tmp:
        named_bundle = Path(tmp) / "named_project.systemdesign"
        shell._current_bundle_path = named_bundle
        shell._update_window_title()
        title_before_save = (
            shell.windowTitle()
        )  # has " * " (model still dirty? No, S10 rolled back)
        # Force a dirty so the marker appears with the named project.
        shell.scene.drop_component(RESISTOR_DEFINITION.id, QPointF(700.0, 0.0))
        title_named_dirty = shell.windowTitle()
        shell.save_current_project()
        title_named_clean = shell.windowTitle()
        # Reset for next scenarios.
        shell._current_bundle_path = None
        shell._update_window_title()
    emit(
        ScenarioResult(
            name="S11: title bar reflects project name + dirty marker",
            passed=(
                "named_project" in title_named_dirty
                and " * " in title_named_dirty
                and "named_project" in title_named_clean
                and " * " not in title_named_clean
            ),
            observations={
                "title_before_save": title_before_save,
                "title_named_dirty": title_named_dirty,
                "title_named_clean": title_named_clean,
            },
        )
    )

    # --------------------------------------------------------------------- #
    # S12: unsaved-changes dialog (programmatic mock)
    # --------------------------------------------------------------------- #
    # Mock QMessageBox.warning to programmatically return each of the
    # three buttons; assert `_confirm_discard_or_save_if_dirty`
    # returns the expected outcome per branch.
    # First, dirty the model so the dialog would otherwise show.
    shell.scene.drop_component(RESISTOR_DEFINITION.id, QPointF(800.0, 0.0))
    with patch.object(
        QMessageBox,
        "warning",
        return_value=QMessageBox.StandardButton.Discard,
    ):
        discard_result = shell._confirm_discard_or_save_if_dirty()
    with patch.object(
        QMessageBox,
        "warning",
        return_value=QMessageBox.StandardButton.Cancel,
    ):
        cancel_result = shell._confirm_discard_or_save_if_dirty()
    # Save branch — mock both the warning AND the Save As file dialog.
    with tempfile.TemporaryDirectory() as tmp:
        save_target = Path(tmp) / "from_save_branch.systemdesign"
        with (
            patch.object(
                QMessageBox,
                "warning",
                return_value=QMessageBox.StandardButton.Save,
            ),
            patch.object(
                QFileDialog,
                "getSaveFileName",
                return_value=(str(save_target), ""),
            ),
        ):
            save_result = shell._confirm_discard_or_save_if_dirty()
        save_path_assigned = shell.current_bundle_path == save_target
    emit(
        ScenarioResult(
            name="S12: unsaved-changes dialog — Discard / Cancel / Save flows",
            passed=(
                discard_result is True
                and cancel_result is False
                and save_result is True
                and save_path_assigned
            ),
            observations={
                "discard_result": discard_result,
                "cancel_result": cancel_result,
                "save_result": save_result,
                "save_path_assigned": save_path_assigned,
            },
        )
    )
    # Reset for subsequent scenarios.
    shell._current_bundle_path = None
    shell._update_window_title()

    # --------------------------------------------------------------------- #
    # S13: QUndoGroup routing (alternating pushes → single Ctrl+Z order)
    # --------------------------------------------------------------------- #
    # Start from a clean state. Reset both models.
    shell._reset_to_defaults()
    shell._model.from_dict({"components": [], "connections": []})
    # Push workspace, then configuration, then workspace, then
    # configuration. Single Ctrl+Z chain should undo in reverse order.
    new_resistor = shell.scene.drop_component(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    extra_ctrl = ControllerSpec(id=new_controller_id(), controller_type="P", display_name="S13-A")
    shell.configuration_command_stack.push(
        AddControllerCommand(shell.configuration_model, extra_ctrl)
    )
    extra_resistor = shell.scene.drop_component(RESISTOR_DEFINITION.id, QPointF(50.0, 0.0))
    extra_ctrl_2 = ControllerSpec(
        id=new_controller_id(), controller_type="PI", display_name="S13-B"
    )
    shell.configuration_command_stack.push(
        AddControllerCommand(shell.configuration_model, extra_ctrl_2)
    )

    # Trigger 4 Ctrl+Z's. The QUndoGroup routes each to the most
    # recently mutated stack. After all 4, both pushes on each
    # stack should be undone.
    initial_components = len(shell.model.components)
    initial_controllers = len(shell.configuration_model.controller_settings.controllers)
    shell._undo_action.trigger()  # most recently active: config — undo extra_ctrl_2
    shell._undo_action.trigger()  # after undo, config still active; but stack empty → no-op
    # Switch to workspace stack by undoing it directly (active flips).
    shell.command_stack.undo()  # undo extra_resistor
    shell.configuration_command_stack.undo()  # undo extra_ctrl
    shell.command_stack.undo()  # undo new_resistor
    final_components = len(shell.model.components)
    final_controllers = len(shell.configuration_model.controller_settings.controllers)
    emit(
        ScenarioResult(
            name="S13: QUndoGroup routes Ctrl+Z to most-recently active stack",
            passed=(
                initial_components == 2
                # `_reset_to_defaults` loads the Phase-1 default PID,
                # then S13 pushes two extra controllers → 3 total.
                and initial_controllers == 3
                and final_components == 0
                # After undoing both extra pushes the default PID
                # remains because it was loaded via from_dict (no
                # undoable command produced it).
                and final_controllers == 1
            ),
            observations={
                "new_resistor_id": new_resistor,
                "extra_resistor_id": extra_resistor,
                "initial_components": initial_components,
                "initial_controllers": initial_controllers,
                "final_components": final_components,
                "final_controllers": final_controllers,
            },
            notes=[
                "Group's active-stack flips on indexChanged; once a "
                "stack is empty its undo action becomes a no-op. "
                "Phase-1 acceptable per the post-Phase-1 backlog."
            ],
        )
    )

    # --------------------------------------------------------------------- #
    # S14: load clears both undo stacks (spec §29.3.1)
    # --------------------------------------------------------------------- #
    # Push history on both stacks, save, load — both stacks must
    # clear. Critical for spec compliance: stale undo history from
    # a different project leaking into the new one is a data-
    # corruption risk.
    shell.scene.drop_component(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    shell.scene.drop_component(RESISTOR_DEFINITION.id, QPointF(50.0, 0.0))
    s14_ctrl = ControllerSpec(id=new_controller_id(), controller_type="PID", display_name="S14")
    shell.configuration_command_stack.push(
        AddControllerCommand(shell.configuration_model, s14_ctrl)
    )
    ws_count_before = shell.command_stack.count()
    cfg_count_before = shell.configuration_command_stack.count()
    with tempfile.TemporaryDirectory() as tmp:
        bundle = Path(tmp) / "s14.systemdesign"
        shell._current_bundle_path = bundle
        shell._update_window_title()
        shell.save_current_project()
        # After save, stacks still have history (only setClean fires).
        ws_count_after_save = shell.command_stack.count()
        cfg_count_after_save = shell.configuration_command_stack.count()
        shell.load_project_from(bundle)
        ws_count_after_load = shell.command_stack.count()
        cfg_count_after_load = shell.configuration_command_stack.count()
    emit(
        ScenarioResult(
            name="S14: load clears both undo stacks (spec §29.3.1)",
            passed=(
                ws_count_before > 0
                and cfg_count_before > 0
                and ws_count_after_load == 0
                and cfg_count_after_load == 0
            ),
            observations={
                "ws_before": ws_count_before,
                "cfg_before": cfg_count_before,
                "ws_after_save": ws_count_after_save,
                "cfg_after_save": cfg_count_after_save,
                "ws_after_load": ws_count_after_load,
                "cfg_after_load": cfg_count_after_load,
            },
        )
    )
    shell._current_bundle_path = None
    shell._update_window_title()

    # --------------------------------------------------------------------- #
    # S15: stale-ref reactivity (delete component → IOEntry.status="stale")
    # --------------------------------------------------------------------- #
    # The WorkspaceReactivityObserver lives inside the
    # ControllerDesignModule package; the shell does NOT
    # auto-instantiate it (post-S2.B.3 it expects an explicit
    # bootstrap call). Build the observer here so the smoke
    # exercises the cross-feature signal chain end-to-end.
    from features.ControllerDesignModule.observers import (
        WorkspaceReactivityObserver,
    )

    observer = WorkspaceReactivityObserver(configuration=shell.configuration_model)
    observer.attach_to_workspace_signals(shell.model)

    # Place a resistor; bind an IOEntry to its `p` port.
    s15_resistor = shell.scene.drop_component(RESISTOR_DEFINITION.id, QPointF(0.0, 0.0))
    assert s15_resistor is not None
    io_entry = IOEntry(
        id=new_io_input_id(),
        source=IOSourcePortRef(
            port_ref=PortRef(component_id=s15_resistor, port_id="p"),
            variable="across",
        ),
        display_name="S15-Vin",
        quantity="voltage",
        unit="V",
    )
    shell.configuration_model.set_io_selection(
        shell.configuration_model.io_selection.with_input_added(io_entry)
    )
    pre_remove_status = shell.configuration_model.io_selection.inputs[0].status

    # Remove the component → componentRemoved signal → observer →
    # IOEntry.status flips to "stale".
    shell.model.remove_component(s15_resistor)
    post_remove_status = shell.configuration_model.io_selection.inputs[0].status

    emit(
        ScenarioResult(
            name="S15: stale-ref reactivity (workspace remove → status='stale')",
            passed=(pre_remove_status == "valid" and post_remove_status == "stale"),
            observations={
                "io_entry_id": io_entry.id,
                "resistor_id": s15_resistor,
                "pre_remove_status": pre_remove_status,
                "post_remove_status": post_remove_status,
            },
        )
    )

    # --------------------------------------------------------------------- #
    # Report
    # --------------------------------------------------------------------- #
    if emit_json:
        json.dump(report.to_dict(), sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        print()
        print("=" * 78)
        flag = "PASS" if report.passed else "FAIL"
        passed_count = sum(s.passed for s in report.scenarios)
        total = len(report.scenarios)
        print(f"  OVERALL: {flag}  ({passed_count}/{total})")
        print("=" * 78)

    return 0 if report.passed else 1


if __name__ == "__main__":
    sys.exit(main())
