"""Unit tests for `GraphValidator.validate_connection_candidate` (S1.4).

Covers `02 §14.3` and `§20.1` real-time connection validation rules:

* self-connection rejected (one test)
* missing source / target component rejected (independent + combined)
* missing source / target port rejected (only after component exists)
* cross-domain rejected
* duplicate rejected (basic + commutative A->B vs B->A; existing
  connection id is the stable issue_id key)
* valid same-domain candidate returns an empty (non-blocking) report
* integration: validator OK plus raw `add_connection` succeeds
* error catalog reference: every issue.code starts with
  `error.connection.` per `11_error_code_catalog.md` §7.1
* `port_lookup` returning `None` for an existing component's missing
  port is handled as `missing_*_port`, not as a TypeError

Spec §36.2 mandates eight connection tests; S1.4 covers the first
five at the validator layer. Tests #6 (component delete cascades
to connections) and #7/#8 (endpoint re-target preserves id and is
undoable) are command-layer concerns delivered by `DeleteComponentCommand`
and `ModifyConnectionCommand` in S1.7 — see `02 §37` and ADR-005. The
raw-mutator non-cascading behavior for #6 is already verified by
`test_remove_component_does_not_cascade_to_attached_connections` in
`tests/features/SystemModelingModule/model/test_workspace_model.py`.

References
----------
* `decisions/ADR-005-command-stack-qundostack.md`
* `specs/02_workspace_requirements.md` §14 (Connection System),
  §14.3 (validation before creation), §20.1 (real-time validation),
  §36.2 (Connection Tests)
* `specs/11_error_code_catalog.md` §7.1 (Connection Errors)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from PySide6.QtCore import QPointF

from features.SystemModelingModule.model.component_instance import (
    PhysicalAttributes,
    VisualSpec,
)
from features.SystemModelingModule.model.connection import PortRef
from features.SystemModelingModule.model.graph_validator import GraphValidator
from features.SystemModelingModule.model.workspace_model import WorkspaceModel

if TYPE_CHECKING:
    from collections.abc import Callable

# ---------------------------------------------------------------------- #
# Helpers
# ---------------------------------------------------------------------- #


def _add_kwargs(**overrides: Any) -> dict[str, Any]:
    """Default `add_component` kwargs."""
    base: dict[str, Any] = {
        "definition_id": "electrical.analog.components.resistor",
        "type": "Resistor",
        "display_name": "Resistor",
        "domain": "electrical_analog",
        "category": "component",
        "position": QPointF(0.0, 0.0),
        "visual": VisualSpec(svg_id="resistor_default"),
        "physical_attributes": PhysicalAttributes(),
    }
    base.update(overrides)
    return base


def _make_port_lookup(
    domains: dict[tuple[str, str], str],
) -> Callable[[PortRef], str | None]:
    """Build a port_lookup callable that maps `(component_id, port_id)` to
    a domain string, or `None` for unknown keys.

    The Phase-1 contract is "return the port's domain string or None
    if the port does not exist on its component" (see
    `GraphValidator.validate_connection_candidate`). Tests register
    every port that should resolve and omit ports that should appear
    missing.
    """

    def lookup(ref: PortRef) -> str | None:
        return domains.get((ref.component_id, ref.port_id))

    return lookup


# ---------------------------------------------------------------------- #
# Self-connection (§14.3)
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_self_connection_is_rejected() -> None:
    """`source == target` (same component, same port) is rejected."""
    validator = GraphValidator()
    ref = PortRef(component_id="cmp_A", port_id="p")

    report = validator.validate_connection_candidate(
        source=ref,
        target=ref,
        existing_connections=(),
        components={"cmp_A": object()},  # type: ignore[dict-item]
        port_lookup=_make_port_lookup({("cmp_A", "p"): "electrical_analog"}),
    )

    assert report.is_blocking is True
    assert len(report.issues) == 1
    issue = report.issues[0]
    assert issue.code == "error.connection.self_connection"
    assert issue.severity == "error"
    assert "cmp_A" in issue.context["component_id"]


# ---------------------------------------------------------------------- #
# Missing component (§14.3)
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_missing_source_component_is_rejected() -> None:
    """A source component absent from `components` produces an error."""
    validator = GraphValidator()

    report = validator.validate_connection_candidate(
        source=PortRef(component_id="cmp_MISSING", port_id="p"),
        target=PortRef(component_id="cmp_B", port_id="p"),
        existing_connections=(),
        components={"cmp_B": object()},  # type: ignore[dict-item]
        port_lookup=_make_port_lookup({("cmp_B", "p"): "electrical_analog"}),
    )

    assert report.is_blocking is True
    codes = [issue.code for issue in report.issues]
    assert "error.connection.missing_source_component" in codes


@pytest.mark.unit
def test_missing_target_component_is_rejected() -> None:
    """A target component absent from `components` produces an error."""
    validator = GraphValidator()

    report = validator.validate_connection_candidate(
        source=PortRef(component_id="cmp_A", port_id="p"),
        target=PortRef(component_id="cmp_MISSING", port_id="p"),
        existing_connections=(),
        components={"cmp_A": object()},  # type: ignore[dict-item]
        port_lookup=_make_port_lookup({("cmp_A", "p"): "electrical_analog"}),
    )

    assert report.is_blocking is True
    codes = [issue.code for issue in report.issues]
    assert "error.connection.missing_target_component" in codes


@pytest.mark.unit
def test_both_components_missing_reports_both_issues() -> None:
    """Independent collection: both missing sides produce both issues."""
    validator = GraphValidator()

    report = validator.validate_connection_candidate(
        source=PortRef(component_id="cmp_MISSING_A", port_id="p"),
        target=PortRef(component_id="cmp_MISSING_B", port_id="p"),
        existing_connections=(),
        components={},
        port_lookup=_make_port_lookup({}),
    )

    codes = [issue.code for issue in report.issues]
    assert "error.connection.missing_source_component" in codes
    assert "error.connection.missing_target_component" in codes


# ---------------------------------------------------------------------- #
# Missing port (§14.3)
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_missing_source_port_is_rejected() -> None:
    """An existing component with a missing port is rejected."""
    validator = GraphValidator()

    report = validator.validate_connection_candidate(
        source=PortRef(component_id="cmp_A", port_id="missing_port"),
        target=PortRef(component_id="cmp_B", port_id="p"),
        existing_connections=(),
        components={"cmp_A": object(), "cmp_B": object()},  # type: ignore[dict-item]
        port_lookup=_make_port_lookup({("cmp_B", "p"): "electrical_analog"}),
    )

    assert report.is_blocking is True
    codes = [issue.code for issue in report.issues]
    assert "error.connection.missing_source_port" in codes


@pytest.mark.unit
def test_missing_target_port_is_rejected() -> None:
    """An existing component with a missing port is rejected."""
    validator = GraphValidator()

    report = validator.validate_connection_candidate(
        source=PortRef(component_id="cmp_A", port_id="p"),
        target=PortRef(component_id="cmp_B", port_id="missing_port"),
        existing_connections=(),
        components={"cmp_A": object(), "cmp_B": object()},  # type: ignore[dict-item]
        port_lookup=_make_port_lookup({("cmp_A", "p"): "electrical_analog"}),
    )

    assert report.is_blocking is True
    codes = [issue.code for issue in report.issues]
    assert "error.connection.missing_target_port" in codes


# ---------------------------------------------------------------------- #
# Cross-domain (§14.3)
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_cross_domain_connection_is_rejected() -> None:
    """Ports from different domains cannot be connected."""
    validator = GraphValidator()

    report = validator.validate_connection_candidate(
        source=PortRef(component_id="cmp_A", port_id="p"),
        target=PortRef(component_id="cmp_B", port_id="flange"),
        existing_connections=(),
        components={"cmp_A": object(), "cmp_B": object()},  # type: ignore[dict-item]
        port_lookup=_make_port_lookup(
            {
                ("cmp_A", "p"): "electrical_analog",
                ("cmp_B", "flange"): "mechanical_translational",
            }
        ),
    )

    assert report.is_blocking is True
    assert len(report.issues) == 1
    issue = report.issues[0]
    assert issue.code == "error.connection.incompatible_domains"
    assert issue.context["source_domain"] == "electrical_analog"
    assert issue.context["target_domain"] == "mechanical_translational"


# ---------------------------------------------------------------------- #
# Duplicate detection (§14.3, commutative)
# ---------------------------------------------------------------------- #


def _make_model_with_connection() -> tuple[WorkspaceModel, str, str, str]:
    """Set up two components plus one connection between their `p` ports.

    Returns `(model, component_a_id, component_b_id, connection_id)`.
    """
    model = WorkspaceModel()
    a = model.add_component(**_add_kwargs())
    b = model.add_component(**_add_kwargs())
    conn_id = model.add_connection(
        source=PortRef(component_id=a, port_id="p"),
        target=PortRef(component_id=b, port_id="p"),
    )
    return model, a, b, conn_id


@pytest.mark.unit
def test_duplicate_connection_is_rejected_same_orientation() -> None:
    """Re-adding the same A->B candidate is reported as duplicate."""
    model, a, b, existing_id = _make_model_with_connection()
    validator = GraphValidator()

    report = validator.validate_connection_candidate(
        source=PortRef(component_id=a, port_id="p"),
        target=PortRef(component_id=b, port_id="p"),
        existing_connections=tuple(model.connections.values()),
        components=dict(model.components),
        port_lookup=_make_port_lookup(
            {(a, "p"): "electrical_analog", (b, "p"): "electrical_analog"}
        ),
    )

    assert report.is_blocking is True
    assert len(report.issues) == 1
    issue = report.issues[0]
    assert issue.code == "error.connection.duplicate"
    assert issue.subject_id == existing_id
    assert issue.context["existing_connection_id"] == existing_id


@pytest.mark.unit
def test_duplicate_connection_is_rejected_commutatively() -> None:
    """`A->B` existing, candidate `B->A` is the same connection per §14.3."""
    model, a, b, existing_id = _make_model_with_connection()
    validator = GraphValidator()

    # Reversed orientation: candidate is B->A, existing is A->B.
    report = validator.validate_connection_candidate(
        source=PortRef(component_id=b, port_id="p"),
        target=PortRef(component_id=a, port_id="p"),
        existing_connections=tuple(model.connections.values()),
        components=dict(model.components),
        port_lookup=_make_port_lookup(
            {(a, "p"): "electrical_analog", (b, "p"): "electrical_analog"}
        ),
    )

    assert report.is_blocking is True
    assert len(report.issues) == 1
    issue = report.issues[0]
    assert issue.code == "error.connection.duplicate"
    # issue_id keyed on existing connection's id, stable across orientations.
    assert issue.issue_id == f"error.connection.duplicate:{existing_id}"


# ---------------------------------------------------------------------- #
# Valid same-domain
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_valid_same_domain_candidate_returns_empty_report() -> None:
    """A clean same-domain candidate has no issues; report is non-blocking."""
    validator = GraphValidator()
    components: dict[str, Any] = {"cmp_A": object(), "cmp_B": object()}

    report = validator.validate_connection_candidate(
        source=PortRef(component_id="cmp_A", port_id="p"),
        target=PortRef(component_id="cmp_B", port_id="p"),
        existing_connections=(),
        components=components,
        port_lookup=_make_port_lookup(
            {
                ("cmp_A", "p"): "electrical_analog",
                ("cmp_B", "p"): "electrical_analog",
            }
        ),
    )

    assert report.is_blocking is False
    assert report.issues == ()


# ---------------------------------------------------------------------- #
# Integration: validator OK + raw `add_connection` succeeds
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_validator_pass_followed_by_add_connection_succeeds() -> None:
    """End-to-end: validator passes; raw `add_connection` then succeeds.

    Simulates the S1.7 command-layer orchestration: command runs the
    validator first, then calls the raw mutator only when the report
    is non-blocking.
    """
    model = WorkspaceModel()
    a = model.add_component(**_add_kwargs())
    b = model.add_component(**_add_kwargs())
    validator = GraphValidator()

    source = PortRef(component_id=a, port_id="p")
    target = PortRef(component_id=b, port_id="p")

    report = validator.validate_connection_candidate(
        source=source,
        target=target,
        existing_connections=tuple(model.connections.values()),
        components=dict(model.components),
        port_lookup=_make_port_lookup(
            {(a, "p"): "electrical_analog", (b, "p"): "electrical_analog"}
        ),
    )

    assert report.is_blocking is False

    # Validator OK → caller commits via raw mutator.
    conn_id = model.add_connection(source=source, target=target)
    assert conn_id in model.connections


# ---------------------------------------------------------------------- #
# Catalog reference + report ergonomics
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_every_issue_code_is_under_error_connection_namespace() -> None:
    """All connection-validator issue codes live under
    `error.connection.*` per `11_error_code_catalog.md` §7.1."""
    validator = GraphValidator()
    # Self-connection triggers one issue.
    report_self = validator.validate_connection_candidate(
        source=PortRef(component_id="cmp_A", port_id="p"),
        target=PortRef(component_id="cmp_A", port_id="p"),
        existing_connections=(),
        components={"cmp_A": object()},  # type: ignore[dict-item]
        port_lookup=_make_port_lookup({("cmp_A", "p"): "electrical_analog"}),
    )
    # Both components missing triggers two.
    report_missing = validator.validate_connection_candidate(
        source=PortRef(component_id="cmp_X", port_id="p"),
        target=PortRef(component_id="cmp_Y", port_id="p"),
        existing_connections=(),
        components={},
        port_lookup=_make_port_lookup({}),
    )
    all_codes = [issue.code for report in (report_self, report_missing) for issue in report.issues]
    assert all_codes, "expected at least one issue to assert against"
    for code in all_codes:
        assert code.startswith(
            "error.connection."
        ), f"unexpected code namespace: {code} — see 11 §7.1"


@pytest.mark.unit
def test_short_circuit_self_connection_does_not_check_other_rules() -> None:
    """When `source == target`, only the self-connection issue is reported.

    Subsequent rules (missing component, cross-domain, duplicate) are
    short-circuited because they all assume distinct endpoints.
    """
    validator = GraphValidator()
    ref = PortRef(component_id="cmp_MISSING", port_id="p")

    # Component is missing AND it's a self-connection. Self-connection
    # check fires first and short-circuits.
    report = validator.validate_connection_candidate(
        source=ref,
        target=ref,
        existing_connections=(),
        components={},
        port_lookup=_make_port_lookup({}),
    )

    assert len(report.issues) == 1
    assert report.issues[0].code == "error.connection.self_connection"


@pytest.mark.unit
def test_short_circuit_missing_component_skips_port_and_domain_checks() -> None:
    """If both components are missing, neither port nor domain checks fire."""
    validator = GraphValidator()

    report = validator.validate_connection_candidate(
        source=PortRef(component_id="cmp_X", port_id="p"),
        target=PortRef(component_id="cmp_Y", port_id="p"),
        existing_connections=(),
        components={},
        port_lookup=_make_port_lookup({}),
    )

    codes = [issue.code for issue in report.issues]
    # Only missing-component issues should appear; no missing-port or
    # cross-domain noise.
    assert "error.connection.missing_source_component" in codes
    assert "error.connection.missing_target_component" in codes
    assert "error.connection.missing_source_port" not in codes
    assert "error.connection.missing_target_port" not in codes
    assert "error.connection.incompatible_domains" not in codes


@pytest.mark.unit
def test_existing_connections_can_be_empty_iterable() -> None:
    """An empty `existing_connections` is the trivial duplicate-free case."""
    validator = GraphValidator()

    report = validator.validate_connection_candidate(
        source=PortRef(component_id="cmp_A", port_id="p"),
        target=PortRef(component_id="cmp_B", port_id="p"),
        existing_connections=[],
        components={"cmp_A": object(), "cmp_B": object()},  # type: ignore[dict-item]
        port_lookup=_make_port_lookup(
            {
                ("cmp_A", "p"): "electrical_analog",
                ("cmp_B", "p"): "electrical_analog",
            }
        ),
    )

    assert report.is_blocking is False
    assert report.issues == ()
