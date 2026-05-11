"""GraphValidator: pre-mutation validation for workspace graph candidates.

Owned by `SystemModelingModule` per `02 §2.2` ("Data Layer" core objects)
and `06 §4.2` ("run graph-level validation"). The validator is the
primary defense of the connection-creation pipeline per ADR-005: the
S1.7 `AddConnectionCommand` will call
`validate_connection_candidate` **before** invoking
`WorkspaceModel.add_connection`; if the report has errors, the raw
mutator is never called.

Scope progression across stages:

* S1.4 (current, Step Group D): `validate_connection_candidate` —
  real-time pre-mutation validation for a single connection per
  `02 §14.3` and `§20.1`. Covers self-connection, missing
  component / port, cross-domain, and duplicate detection
  (commutative).
* S1.5 (Step Group E, future): implicit node assembly validation +
  mixed-domain detection at the node level (`02 §18.1`).
* S1.6+ (Step Group F, future): full graph-level validation —
  dangling required ports, missing domain reference (e.g., ground,
  fixed), stale I/O references, debouncing strategy per `02 §20.6`.

All methods are state-free; the validator instance carries no
configuration in Phase 1. Future config (e.g., relaxed mode for
import scenarios) would be added via constructor parameters in
later stages.

The validator does **not** depend on `WorkspaceModel`. The caller
supplies the workspace snapshot via `components`,
`existing_connections`, and a `port_lookup` callable. This keeps
the validator unit-testable in isolation and avoids coupling
between the validator and the source-of-truth model.

References:
----------
* `decisions/ADR-005-command-stack-qundostack.md` (validator chain
  at the command layer)
* `specs/02_workspace_requirements.md` §14 (Connection System),
  §14.3 (validation before creation), §20 (validation strategy),
  §20.1 (real-time validation)
* `specs/06_data_flow_and_architecture.md` §4.2 (SystemModelingModule
  responsibilities)
* `specs/11_error_code_catalog.md` §7.1 (Connection Errors)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from shared.registry.parameter_validator import ParameterValidator

from .validation_report import ValidationIssue, ValidationReport

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping

    from shared.registry import ComponentRegistry

    from .component_instance import ComponentInstance
    from .connection import Connection, PortRef


class GraphValidator:
    """Validates workspace-graph operations against `02 §20.1` rules.

    Stateless in Phase 1; the class exists for future extension
    (configuration, plugin-supplied rules, profiling hooks) without
    forcing call-site changes.

    The S1.4 surface is the single method
    `validate_connection_candidate`. Future S1.5 / S1.6+ stages will
    add `validate_graph` and other methods to this class.
    """

    def validate_connection_candidate(
        self,
        *,
        source: PortRef,
        target: PortRef,
        existing_connections: Iterable[Connection],
        components: Mapping[str, ComponentInstance],
        port_lookup: Callable[[PortRef], str | None],
    ) -> ValidationReport:
        """Validate a candidate connection before mutation.

        Implements the real-time validation rules from `02 §20.1`:

        1. **Self-connection** — `source == target` (same component,
           same port) is rejected per `02 §14.3`.
        2. **Missing component** — `source.component_id` or
           `target.component_id` not present in `components`.
        3. **Missing port** — `port_lookup` returns `None`, meaning
           the port does not exist on the component (only checked
           when the component itself exists).
        4. **Cross-domain** — `port_lookup(source)` and
           `port_lookup(target)` return different domain strings.
        5. **Duplicate** — an existing connection already connects
           the same two `(component_id, port_id)` endpoints. Checked
           commutatively via `frozenset`: A→B and B→A are the same
           connection per `02 §14.3`.

        Checks short-circuit when a prerequisite fails (e.g., a
        missing component skips the port and domain checks for that
        side). When both sides fail independently (e.g., both
        components missing), both issues are reported in one
        report.

        The validator returns a `ValidationReport`. Empty issues
        (`report.is_blocking == False`) means the candidate may be
        committed by the caller. Any error-severity issue means the
        candidate must be rejected; the command layer is responsible
        for surfacing the issues to the UI per ADR-005.

        Args:
            source: Endpoint reference at the source side.
            target: Endpoint reference at the target side.
            existing_connections: Snapshot of the connections that
                already exist in the workspace (used only for the
                duplicate check). Iterated once.
            components: Snapshot of `component_id` →
                `ComponentInstance`. Used only for existence checks;
                the validator does not inspect component fields.
            port_lookup: Callable that maps a `PortRef` to the
                domain string of the port, or `None` if the port
                does not exist on its component. Phase 1 uses the
                domain string only; future stages may extend this
                to return a `PortDefinition` (S1.B) — the imza
                will be widened in a backwards-compatible way.

        Returns:
            `ValidationReport` carrying any `ValidationIssue`s
            found. An empty report means the candidate is valid and
            may be committed.
        """
        issues: list[ValidationIssue] = []

        # 1. Self-connection — short-circuit; nothing else matters
        #    if source and target are the same port.
        if source.component_id == target.component_id and source.port_id == target.port_id:
            issues.append(_issue_self_connection(source))
            return ValidationReport(issues=tuple(issues))

        # 2. Missing component — collect both sides independently.
        source_component_exists = source.component_id in components
        target_component_exists = target.component_id in components
        if not source_component_exists:
            issues.append(_issue_missing_source_component(source))
        if not target_component_exists:
            issues.append(_issue_missing_target_component(target))
        if not (source_component_exists and target_component_exists):
            return ValidationReport(issues=tuple(issues))

        # 3. Missing port — port_lookup returns None.
        source_domain = port_lookup(source)
        target_domain = port_lookup(target)
        if source_domain is None:
            issues.append(_issue_missing_source_port(source))
        if target_domain is None:
            issues.append(_issue_missing_target_port(target))
        if source_domain is None or target_domain is None:
            return ValidationReport(issues=tuple(issues))

        # 4. Cross-domain — incompatible domain pair.
        if source_domain != target_domain:
            issues.append(
                _issue_incompatible_domains(
                    source=source,
                    target=target,
                    source_domain=source_domain,
                    target_domain=target_domain,
                )
            )
            return ValidationReport(issues=tuple(issues))

        # 5. Duplicate — commutative frozenset comparison per
        #    `02 §14.3`. A→B and B→A are the same connection.
        candidate_endpoints = frozenset(
            (
                (source.component_id, source.port_id),
                (target.component_id, target.port_id),
            )
        )
        for connection in existing_connections:
            existing_endpoints = frozenset(
                (
                    (connection.source.component_id, connection.source.port_id),
                    (connection.target.component_id, connection.target.port_id),
                )
            )
            if existing_endpoints == candidate_endpoints:
                issues.append(_issue_duplicate(connection.id, source, target))
                break  # one duplicate is enough; spec doesn't require enumerating all

        return ValidationReport(issues=tuple(issues))

    def validate_workspace(
        self,
        *,
        components: Mapping[str, ComponentInstance],
        connections: Iterable[Connection],
        registry: ComponentRegistry | None,
    ) -> ValidationReport:
        """Validate the full workspace state.

        Implements the Phase-1 workspace-level rules from
        `02 §20`:

        1. **Required ports must be connected** (`02 §20.1`):
           every `PortDefinition` with `required=True` on a
           placed component must appear as either endpoint of
           at least one connection. Missing connection → warning
           (`02 §20.5`: warnings do not block editing).
        2. **Domain reference rule** (`02 §20.4`): each domain
           that has any placed component must have at least one
           reference component:
             * `electrical_analog` → `Ground Electric`
             * `mechanical_translational` → `Fixed`
           Missing reference → error.
        3. **Parameter validation** (`02 §9.4`): each placed
           component's parameters must satisfy the rules from
           `ParameterValidator` (type, required, min/max, enum,
           unit). Each `ParameterValidator` error becomes one
           error-severity `ValidationIssue`.

        Empty workspace returns an empty report — no rules
        apply when there are no components.

        Args:
            components: Snapshot of `component_id` →
                `ComponentInstance`. Read-only iteration.
            connections: Snapshot of `Connection` records.
                Iterated once for the required-port check.
            registry: `ComponentRegistry` used to resolve each
                component's `PortDefinition` and
                `ParameterDefinition` tuples. When `None`, the
                required-port and parameter rules cannot run
                (no definitions available) and are silently
                skipped — the domain-reference rule still runs
                because it reads instance fields directly.

        Returns:
            `ValidationReport` carrying every issue discovered.
            Empty when the workspace is clean (no required-port
            warnings, all domain references present, all
            parameters valid).
        """
        issues: list[ValidationIssue] = []
        connection_tuple = tuple(connections)

        # Rule 1: required ports must be connected (registry-dependent).
        if registry is not None:
            for component_id, instance in components.items():
                if not registry.has(instance.definition_id):
                    continue
                definition = registry.get(instance.definition_id)
                for port_def in definition.ports:
                    if not port_def.required:
                        continue
                    if not _port_is_connected(component_id, port_def.id, connection_tuple):
                        issues.append(
                            _issue_dangling_required_port(
                                component_id, port_def.id, instance.display_name
                            )
                        )

        # Rule 2: domain reference (registry-independent — reads
        # instance.domain and instance.definition_id directly).
        domains_present: set[str] = {inst.domain for inst in components.values()}
        if "electrical_analog" in domains_present and not _has_definition(
            components, _GROUND_DEFINITION_ID
        ):
            issues.append(_issue_missing_ground_reference())
        if "mechanical_translational" in domains_present and not _has_definition(
            components, _FIXED_DEFINITION_ID
        ):
            issues.append(_issue_missing_fixed_reference())

        # Rule 3: parameter validation (registry-dependent).
        if registry is not None:
            param_validator = ParameterValidator()
            for component_id, instance in components.items():
                if not registry.has(instance.definition_id):
                    continue
                definition = registry.get(instance.definition_id)
                for param_def in definition.parameters:
                    # Use the instance value if present; otherwise
                    # validate the definition default (catches
                    # invalid defaults at schema-load time too).
                    value = instance.parameters.get(param_def.id, param_def.default)
                    errors = param_validator.validate(param_def, value)
                    for index, error_text in enumerate(errors):
                        issues.append(
                            _issue_invalid_parameter(component_id, param_def.id, index, error_text)
                        )

        return ValidationReport(issues=tuple(issues))


# ---------------------------------------------------------------------- #
# Workspace-rule constants
# ---------------------------------------------------------------------- #


_GROUND_DEFINITION_ID = "electrical.analog.components.ground"
_FIXED_DEFINITION_ID = "mechanics.translational.components.fixed"


def _has_definition(
    components: Mapping[str, ComponentInstance],
    definition_id: str,
) -> bool:
    """Return True if any placed component matches `definition_id`."""
    return any(inst.definition_id == definition_id for inst in components.values())


def _port_is_connected(
    component_id: str,
    port_id: str,
    connections: Iterable[Connection],
) -> bool:
    """Return True if `(component_id, port_id)` is either endpoint of any connection."""
    for conn in connections:
        if (conn.source.component_id == component_id and conn.source.port_id == port_id) or (
            conn.target.component_id == component_id and conn.target.port_id == port_id
        ):
            return True
    return False


# ---------------------------------------------------------------------- #
# Issue factories — keep the validator method body readable and the
# error-catalog reference strings in one place.
#
# `issue_id` format: `<code>:<distinguishing-fields>`. Stable across
# debounced revalidations per `02 §20.6` so subscribers can diff
# reports against prior emissions.
# ---------------------------------------------------------------------- #


def _issue_dangling_required_port(
    component_id: str,
    port_id: str,
    display_name: str,
) -> ValidationIssue:
    """Build the issue for `02 §20.1` dangling required port (warning).

    Code is `warning.validation.unused_port` per `11 §7.7`.
    """
    return ValidationIssue(
        issue_id=f"warning.validation.unused_port:{component_id}:{port_id}",
        severity="warning",
        code="warning.validation.unused_port",
        message=(f"required port '{port_id}' on '{display_name}' is not connected"),
        subject_kind="component",
        subject_id=component_id,
        context={"port_id": port_id},
    )


def _issue_missing_ground_reference() -> ValidationIssue:
    """Build the issue for `02 §20.4` missing electrical ground reference.

    Code is `error.validation.missing_ground` per `11 §7.7`.
    """
    return ValidationIssue(
        issue_id="error.validation.missing_ground",
        severity="error",
        code="error.validation.missing_ground",
        message=("electrical model requires at least one Ground Electric component"),
        subject_kind="workspace",
        subject_id=None,
        context={"domain": "electrical_analog"},
    )


def _issue_missing_fixed_reference() -> ValidationIssue:
    """Build the issue for `02 §20.4` missing mechanical fixed reference.

    Code is `error.validation.missing_fixed_reference` per `11 §7.7`.
    """
    return ValidationIssue(
        issue_id="error.validation.missing_fixed_reference",
        severity="error",
        code="error.validation.missing_fixed_reference",
        message=("mechanical translational model requires at least one Fixed component"),
        subject_kind="workspace",
        subject_id=None,
        context={"domain": "mechanical_translational"},
    )


# Map `ParameterValidator`'s plain-text errors back to the
# `11 §7.3` catalog codes. The mapping is message-pattern based —
# a structured ParameterValidator return would be cleaner but is
# scope-creep for S1.6a; the patterns are stable text fragments
# from `parameter_validator.py`'s issue strings.
#
# TODO(S1.6.future): refactor `ParameterValidator.validate` to
# return `(code, message)` tuples so this mapping table goes
# away.


def _classify_parameter_error(text: str) -> str:
    """Map a `ParameterValidator` error string to a `11 §7.3` code."""
    if "is required but no value was provided" in text:
        return "error.parameter.required_missing"
    if "expects type" in text:
        return "error.parameter.type_mismatch"
    if "below minimum" in text or "above maximum" in text:
        return "error.parameter.out_of_range"
    if "is not in" in text and "allowed values" in text:
        return "error.parameter.invalid_enum"
    if "unit" in text and "does not match" in text:
        return "error.parameter.unit_mismatch"
    return "error.parameter.type_mismatch"


def _issue_invalid_parameter(
    component_id: str,
    param_id: str,
    rule_index: int,
    detail: str,
) -> ValidationIssue:
    """Build the issue for `02 §9.4` parameter validation failure.

    Code classification follows `11 §7.3` based on message pattern.
    `rule_index` disambiguates multiple issues on the same param.
    """
    code = _classify_parameter_error(detail)
    return ValidationIssue(
        issue_id=f"{code}:{component_id}:{param_id}:{rule_index}",
        severity="error",
        code=code,
        message=detail,
        subject_kind="component",
        subject_id=component_id,
        context={"param_id": param_id, "rule_index": rule_index},
    )


def _issue_self_connection(ref: PortRef) -> ValidationIssue:
    """Build the issue for `02 §14.3` self-connection rejection."""
    return ValidationIssue(
        issue_id=f"error.connection.self_connection:{ref.component_id}.{ref.port_id}",
        severity="error",
        code="error.connection.self_connection",
        message=(f"Cannot connect port '{ref.component_id}.{ref.port_id}' to itself."),
        subject_kind="workspace",
        subject_id=None,
        context={
            "component_id": ref.component_id,
            "port_id": ref.port_id,
        },
    )


def _issue_missing_source_component(ref: PortRef) -> ValidationIssue:
    """Build the issue for a candidate whose source component is absent."""
    return ValidationIssue(
        issue_id=f"error.connection.missing_source_component:{ref.component_id}",
        severity="error",
        code="error.connection.missing_source_component",
        message=(f"Source component '{ref.component_id}' does not exist in the workspace."),
        subject_kind="workspace",
        subject_id=None,
        context={"component_id": ref.component_id, "port_id": ref.port_id},
    )


def _issue_missing_target_component(ref: PortRef) -> ValidationIssue:
    """Build the issue for a candidate whose target component is absent."""
    return ValidationIssue(
        issue_id=f"error.connection.missing_target_component:{ref.component_id}",
        severity="error",
        code="error.connection.missing_target_component",
        message=(f"Target component '{ref.component_id}' does not exist in the workspace."),
        subject_kind="workspace",
        subject_id=None,
        context={"component_id": ref.component_id, "port_id": ref.port_id},
    )


def _issue_missing_source_port(ref: PortRef) -> ValidationIssue:
    """Build the issue for a missing source port on an existing component."""
    return ValidationIssue(
        issue_id=f"error.connection.missing_source_port:{ref.component_id}.{ref.port_id}",
        severity="error",
        code="error.connection.missing_source_port",
        message=(
            f"Source port '{ref.port_id}' does not exist on component " f"'{ref.component_id}'."
        ),
        subject_kind="workspace",
        subject_id=None,
        context={"component_id": ref.component_id, "port_id": ref.port_id},
    )


def _issue_missing_target_port(ref: PortRef) -> ValidationIssue:
    """Build the issue for a missing target port on an existing component."""
    return ValidationIssue(
        issue_id=f"error.connection.missing_target_port:{ref.component_id}.{ref.port_id}",
        severity="error",
        code="error.connection.missing_target_port",
        message=(
            f"Target port '{ref.port_id}' does not exist on component " f"'{ref.component_id}'."
        ),
        subject_kind="workspace",
        subject_id=None,
        context={"component_id": ref.component_id, "port_id": ref.port_id},
    )


def _issue_incompatible_domains(
    *,
    source: PortRef,
    target: PortRef,
    source_domain: str,
    target_domain: str,
) -> ValidationIssue:
    """Build the issue for `02 §14.3` cross-domain rejection."""
    return ValidationIssue(
        issue_id=(
            f"error.connection.incompatible_domains:"
            f"{source.component_id}.{source.port_id}->"
            f"{target.component_id}.{target.port_id}"
        ),
        severity="error",
        code="error.connection.incompatible_domains",
        message=(f"Cannot connect {source_domain} to {target_domain}: incompatible domains."),
        subject_kind="workspace",
        subject_id=None,
        context={
            "source_component_id": source.component_id,
            "source_port_id": source.port_id,
            "source_domain": source_domain,
            "target_component_id": target.component_id,
            "target_port_id": target.port_id,
            "target_domain": target_domain,
        },
    )


def _issue_duplicate(
    existing_connection_id: str,
    source: PortRef,
    target: PortRef,
) -> ValidationIssue:
    """Build the issue for `02 §14.3` duplicate-connection rejection.

    `issue_id` is keyed on the existing connection's id so that the
    same logical duplicate (A→B vs B→A) produces a stable
    `issue_id` across both orderings (the existing connection's id
    is invariant under the candidate's orientation).
    """
    return ValidationIssue(
        issue_id=f"error.connection.duplicate:{existing_connection_id}",
        severity="error",
        code="error.connection.duplicate",
        message=(
            f"A connection between '{source.component_id}.{source.port_id}' "
            f"and '{target.component_id}.{target.port_id}' already exists "
            f"(connection {existing_connection_id})."
        ),
        subject_kind="connection",
        subject_id=existing_connection_id,
        context={
            "existing_connection_id": existing_connection_id,
            "source_component_id": source.component_id,
            "source_port_id": source.port_id,
            "target_component_id": target.component_id,
            "target_port_id": target.port_id,
        },
    )


__all__ = [
    "GraphValidator",
]
