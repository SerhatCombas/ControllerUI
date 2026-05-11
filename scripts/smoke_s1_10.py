"""S1.10 programmatic smoke harness.

Builds the real `SystemDesignerShell`, walks the 7-scenario manual-
smoke checklist (3 positive + 1 round-trip + 1 param edit + 2
negatives) via the public API, and reports observations as either
plain text (default) or structured JSON (`--json`).

This is NOT a pytest test — it is a one-shot diagnostic harness
preserved so subsequent stages (S2 persistence onwards) can re-run
it as a regression check after each substantive change.

Exit codes:
  0  every scenario passed its built-in expectation
  1  at least one scenario failed (printed in the structured
     report under `findings`)

Usage:
  python scripts/smoke_s1_10.py                # human-readable
  python scripts/smoke_s1_10.py --json         # machine-readable
  python scripts/smoke_s1_10.py --json | tee smoke_results.json
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

    from PySide6.QtCore import QPointF
    from PySide6.QtWidgets import QApplication

    from application.SystemDesignerShell.main_window import SystemDesignerShell
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
