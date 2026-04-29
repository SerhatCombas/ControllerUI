# 11_error_code_catalog.md

## 1. Purpose

This document defines the canonical error code catalog for the Engineering System Designer project.

Error codes serve four purposes:

* **stable identifiers** for errors across the entire codebase, independent of human-readable message wording
* **localization keys** for translating user-facing messages
* **log event tags** linking structured logs to specific failure modes
* **support and diagnostics anchors** for post-mortem analysis and bug reports

This document is **not** a feature specification. It is a catalog that complements `10_logging_conventions.md` and `02_workspace_requirements.md` §32 (Error Handling and Status Reporting).

The agent must use codes from this catalog when emitting WARNING, ERROR, or CRITICAL logs and when raising exceptions that surface to the user.

---

## 2. Scope

### 2.1 In Scope

* Error code naming convention
* Error code hierarchy and namespacing
* Structured error format (Python exception subclasses, dictionary representation)
* Severity mapping
* Localization key relationship
* Phase 1 error codes for workspace, configuration, library, and persistence
* Phase 2+ reserved error codes for engine, simulation, controller runtime
* Adding new error codes (governance)

### 2.2 Out of Scope

* Logging mechanics (see `10_logging_conventions.md`)
* User-facing UI styling for errors (see `02 §32.3`)
* Translation strings themselves (managed in a separate localization resource)

---

## 3. Naming Convention

### 3.1 Format

Error codes use **lowercase dotted namespacing**:

```
<severity>.<category>.<specific_code>
```

Where:

* `<severity>` is one of `info`, `warning`, `error`, `fatal`
* `<category>` is the functional area (e.g., `connection`, `parameter`, `migration`)
* `<specific_code>` is a snake_case description of the failure

Examples:

* `error.connection.incompatible_domains`
* `warning.parameter.out_of_range`
* `fatal.system.architecture_invariant_violated`

### 3.2 Severity Prefix Rules

The severity prefix corresponds to the **default** log level when this code is emitted, not necessarily the level used in every context:

* `info.*` — INFO logs, no user-visible alert, typically used for graceful degradation that the user should be aware of
* `warning.*` — WARNING logs, visible in status bar and validation summary, does not block operation
* `error.*` — ERROR logs, visible in status bar with persistent banner, blocks the specific operation
* `fatal.*` — CRITICAL logs, visible in modal dialog, may compromise application integrity

A specific occurrence may be logged at a different level if context warrants. However, the severity prefix sets the default expectation.

### 3.3 Category Vocabulary

The following categories are reserved:

| Category | Domain |
|---|---|
| `connection` | port-to-port connections, validation, retargeting |
| `component` | component instances, parameters, lifecycle |
| `port` | port definitions, port references, port resolution |
| `domain` | domain registry, domain compatibility |
| `parameter` | parameter values, validation, units |
| `library` | component library, registry loading, drag/drop |
| `validation` | workspace-level validation reports |
| `persistence` | save, load, project package |
| `migration` | schema migrations, version mismatches |
| `recovery` | autosave, recovery files |
| `id` | ID generation, ID conflicts, ID resolution |
| `selection` | selection model, multi-selection |
| `command` | undo/redo, command merging |
| `equation` | equation extraction, DAE pipeline (Phase 2) |
| `solver` | numerical solvers, integration (Phase 2) |
| `simulation` | simulation requests, results (Phase 2) |
| `analysis` | linearization, stability analysis (Phase 2) |
| `controller` | controller design, runtime execution |
| `plot` | plot rendering, plot configuration |
| `system` | system-level invariants, architecture violations |
| `io` | file system, HDF5 storage |
| `signal` | Qt signal/slot wiring issues |

### 3.4 Forbidden Code Patterns

* uppercase letters anywhere in the code
* hyphens (use underscores: `incompatible_domains`, not `incompatible-domains`)
* spaces or non-ASCII characters
* numeric suffixes for related codes (`error.parameter.invalid1`, `error.parameter.invalid2`)
* generic codes without categorization (`error.something_went_wrong`, `error.bad_input`)
* duplicate codes for different errors

---

## 4. Structured Error Format

### 4.1 Python Exception Hierarchy

The project defines a base exception class with structured fields:

```python
# shared/utils/errors.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class StructuredError(Exception):
    """Base exception for all project errors.
    
    Carries a stable error code, user-facing message, and contextual
    metadata for logging and diagnostics.
    
    Attributes:
        code: Stable error code from the catalog.
        message: Human-readable English message.
        context: Structured key-value context for logging and display.
        cause: Optional underlying exception that triggered this error.
    """
    
    code: str
    message: str
    context: dict[str, Any] = field(default_factory=dict)
    cause: Exception | None = None
    
    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize to a structured dictionary for logging or transport."""
        return {
            "code": self.code,
            "message": self.message,
            "context": self.context,
            "cause": str(self.cause) if self.cause else None,
        }
```

Specific subclasses live near the code that raises them, but always inherit from `StructuredError`:

```python
# features/SystemModelingModule/model/errors.py
from shared.utils.errors import StructuredError


class IncompatibleDomainsError(StructuredError):
    """Raised when a connection is attempted between incompatible domain ports."""
    
    @classmethod
    def create(
        cls,
        source_domain: str,
        target_domain: str,
        source_id: str,
        target_id: str,
    ) -> IncompatibleDomainsError:
        return cls(
            code="error.connection.incompatible_domains",
            message=(
                f"Cannot connect {source_domain} to {target_domain}: "
                f"incompatible domains."
            ),
            context={
                "source_domain": source_domain,
                "target_domain": target_domain,
                "source_id": source_id,
                "target_id": target_id,
            },
        )
```

### 4.2 Dictionary Representation

When errors are logged, sent to the UI, or persisted (in validation reports), they use this dictionary shape:

```json
{
    "code": "error.connection.incompatible_domains",
    "message": "Cannot connect electrical_analog to mechanical_translational: incompatible domains.",
    "context": {
        "source_domain": "electrical_analog",
        "target_domain": "mechanical_translational",
        "source_id": "cmp_01HV...",
        "target_id": "cmp_01HX..."
    },
    "cause": null
}
```

### 4.3 Validation Report Integration

`ValidationReport` (see `02 §20`) stores a list of structured issues:

```python
@dataclass
class ValidationIssue:
    code: str
    severity: ValidationSeverity  # INFO, WARNING, ERROR
    message: str
    context: dict[str, Any]
    component_id: str | None = None  # If issue is component-scoped
    connection_id: str | None = None  # If issue is connection-scoped
```

The `code` field draws from this catalog. The Component Info Panel (`02 §28`) renders the `message` field by default but can fall back to looking up a localized string via the `code` (see §6).

---

## 5. Severity Mapping

The default log level for each severity prefix:

| Prefix | Default Log Level | UI Surface | Action Expected |
|---|---|---|---|
| `info.*` | INFO | status bar | none |
| `warning.*` | WARNING | status bar + validation summary + visual highlight | optional |
| `error.*` | ERROR | status bar + validation summary + visual highlight + persistent banner | required |
| `fatal.*` | CRITICAL | modal dialog + log + force-stop | immediate |

When the same logical event occurs in different contexts, different severity prefixes may be used:

* `warning.validation.unresolved_port` (during normal workspace validation)
* `error.persistence.save_blocked_by_unresolved_port` (when the user tries to save and the unresolved port blocks it)

These are distinct codes pointing to related but contextually different errors.

---

## 6. Localization Keys

Each error code doubles as the localization key for translation tables.

### 6.1 Translation Table Format

Translation tables live under `assets/locales/<lang>.json`:

```json
{
    "error.connection.incompatible_domains": "Cannot connect {source_domain} to {target_domain}: incompatible domains.",
    "error.connection.duplicate": "Connection between {source_id} and {target_id} already exists.",
    "warning.parameter.out_of_range": "Parameter {parameter_id} value {value} is outside the recommended range [{min}, {max}]."
}
```

Placeholders use Python `str.format` style. The `context` dictionary supplies the values.

### 6.2 Translation Lookup

The translation lookup function lives in `shared/utils/localization.py`:

```python
def localize(code: str, context: dict[str, Any], language: str = "en") -> str:
    """Return a localized message for the given error code."""
    table = load_locale(language)
    template = table.get(code, FALLBACK_TABLE.get(code, code))
    try:
        return template.format(**context)
    except KeyError:
        return template  # Missing placeholder values: return unformatted
```

If a code is missing from the localization table, the system falls back to the English table, then to the bare code.

### 6.3 Phase 1 Localization

Phase 1 ships with English only. Localization tables exist as scaffolding but are not actively translated. Phase 3+ may add additional languages.

---

## 7. Phase 1 Error Code Catalog

The following codes are defined for Phase 1.

### 7.1 Connection Errors

| Code | Severity | Description |
|---|---|---|
| `error.connection.incompatible_domains` | error | Source and target ports belong to different domains |
| `error.connection.self_connection` | error | A connection cannot have the same source and target port |
| `error.connection.duplicate` | error | A connection between these two ports already exists |
| `error.connection.missing_source_component` | error | The source component does not exist in the workspace model |
| `error.connection.missing_target_component` | error | The target component does not exist in the workspace model |
| `error.connection.missing_source_port` | error | The source port does not exist on its component |
| `error.connection.missing_target_port` | error | The target port does not exist on its component |
| `error.connection.locked_component` | error | Cannot modify a connection attached to a locked component |
| `warning.connection.dangling_after_delete` | warning | A connection became dangling after a component was deleted |
| `warning.connection.routing_invalid` | warning | Connection routing waypoints are invalid; falling back to default |

### 7.2 Component Errors

| Code | Severity | Description |
|---|---|---|
| `error.component.definition_not_found` | error | The requested `definition_id` is not registered |
| `error.component.id_conflict` | error | Internal ID collision (extremely rare with ULID) |
| `error.component.locked` | error | Cannot modify a locked component |
| `error.component.locked_delete` | error | Cannot delete a locked component without explicit unlock |
| `warning.component.display_id_collision` | warning | Two components have the same display ID (load time only) |
| `warning.component.unknown_field_preserved` | warning | Component data contains unknown fields; preserved for forward compat |

### 7.3 Parameter Errors

| Code | Severity | Description |
|---|---|---|
| `error.parameter.required_missing` | error | A required parameter has no value |
| `error.parameter.type_mismatch` | error | Parameter value type does not match schema |
| `error.parameter.out_of_range` | error | Parameter value is outside hard min/max bounds |
| `error.parameter.invalid_enum` | error | Parameter value is not in the allowed enum set |
| `error.parameter.unit_mismatch` | error | Parameter unit is incompatible with the canonical unit |
| `error.parameter.expression_parse_failed` | error | Parameter expression could not be parsed |
| `warning.parameter.out_of_recommended_range` | warning | Parameter value is outside soft recommended range but within hard bounds |
| `warning.parameter.unit_normalized` | warning | Parameter unit was normalized to canonical form (e.g., kΩ → ohm) |

### 7.4 Port Errors

| Code | Severity | Description |
|---|---|---|
| `error.port.definition_not_found` | error | The requested port ID does not exist on the component definition |
| `error.port.kind_unsupported` | error | Port kind is not supported in current Phase |

### 7.5 Domain Errors

| Code | Severity | Description |
|---|---|---|
| `error.domain.not_registered` | error | Domain ID is not in the DomainRegistry |
| `error.domain.cross_domain_node` | error | Implicit node contains ports from multiple domains |
| `warning.domain.deferred_domain` | warning | Component belongs to a deferred domain (rotational/digital in Phase 1) |

### 7.6 Library Errors

| Code | Severity | Description |
|---|---|---|
| `error.library.svg_not_found` | error | Referenced SVG asset does not exist |
| `error.library.svg_parse_failed` | error | SVG file is malformed |
| `error.library.attribution_missing` | error | Third-party SVG has no attribution metadata |
| `error.library.license_file_missing` | error | Attribution references a license file that does not exist |
| `error.library.drag_payload_invalid` | error | Drag payload from library panel is malformed |
| `warning.library.optional_component_skipped` | warning | An optional component was skipped during library load |

### 7.7 Validation Errors

| Code | Severity | Description |
|---|---|---|
| `error.validation.missing_ground` | error | Electrical model has no Ground reference |
| `error.validation.missing_fixed_reference` | error | Mechanical model has no Fixed reference |
| `warning.validation.disconnected_component` | warning | Component has no valid connections |
| `warning.validation.unused_port` | warning | A required port is unused |
| `warning.validation.unresolved_port` | warning | A port reference cannot be resolved |
| `info.validation.workspace_empty` | info | The workspace is empty |

### 7.8 Persistence Errors

| Code | Severity | Description |
|---|---|---|
| `error.persistence.save_failed` | error | Project save failed (file system error) |
| `error.persistence.load_failed` | error | Project load failed (file system or parse error) |
| `error.persistence.invalid_package_structure` | error | `.systemdesign/` directory is missing required files |
| `error.persistence.project_json_invalid` | error | `project.json` is malformed |
| `error.persistence.external_modification_detected` | error | Project package was modified externally during the session |
| `error.persistence.save_blocked_by_unresolved_port` | error | Save was blocked due to unresolved port references |
| `warning.persistence.unknown_field_preserved` | warning | Project file contains unknown fields; preserved for forward compat |
| `warning.persistence.legacy_format_migrated` | warning | Legacy single-file project was migrated to package format |
| `fatal.persistence.save_corrupted_recovery` | fatal | Save failed mid-write; recovery file may be corrupt |

### 7.9 Migration Errors

| Code | Severity | Description |
|---|---|---|
| `error.migration.no_path` | error | No migration path exists from source to target version |
| `error.migration.failed` | error | Migration failed during execution |
| `error.migration.target_version_unknown` | error | Project file uses a schema version newer than the application |
| `warning.migration.field_dropped` | warning | A field was dropped during migration |
| `warning.migration.field_renamed` | warning | A field was renamed during migration |

### 7.10 Recovery Errors

| Code | Severity | Description |
|---|---|---|
| `info.recovery.available` | info | A recovery file is available for this project |
| `warning.recovery.outdated` | warning | Recovery file is older than the last saved state |
| `error.recovery.load_failed` | error | Recovery file could not be loaded |

### 7.11 ID Generation Errors

| Code | Severity | Description |
|---|---|---|
| `error.id.ulid_generation_failed` | error | ULID generation produced an invalid result |
| `warning.id.display_counter_reconstructed` | warning | Display ID counters were rebuilt from existing data |
| `warning.id.display_counter_collision` | warning | Two components have the same display ID due to legacy data |

### 7.12 Command Errors

| Code | Severity | Description |
|---|---|---|
| `warning.command.merge_conflict` | warning | Two undoable commands could not be merged due to conflicting state |
| `error.command.invalid_state` | error | Command attempted to apply to a model in an unexpected state |

### 7.13 System Errors

| Code | Severity | Description |
|---|---|---|
| `fatal.system.unhandled_exception` | fatal | An exception escaped the main event loop |
| `fatal.system.architecture_invariant_violated` | fatal | An architectural invariant (e.g., Phase 1 engine isolation) was violated |
| `fatal.system.registry_corruption` | fatal | A registry contains conflicting or duplicate definitions |
| `error.system.bootstrap_failed` | error | Application bootstrap failed before reaching the main window |

---

## 8. Phase 2+ Reserved Error Codes

The following codes are reserved for Phase 2+. They are not yet emitted in Phase 1 but must not be reused for other purposes.

### 8.1 Equation Pipeline (Stage S3)

| Code | Severity | Description |
|---|---|---|
| `error.equation.extraction_failed` | error | Equation extraction failed for the given graph |
| `error.equation.dae_index_too_high` | error | DAE index exceeds supported reduction depth |
| `error.equation.algebraic_loop` | error | Algebraic loop detected in graph |
| `error.equation.singular_system` | error | System is singular (insufficient ground or constraints) |
| `error.equation.causality_conflict` | error | Bond Graph causality assignment failed |
| `warning.equation.linearity_unknown` | warning | Could not determine linearity hint |

### 8.2 Solver and Simulation (Stage S4)

| Code | Severity | Description |
|---|---|---|
| `error.solver.backend_unavailable` | error | The requested solver backend (e.g., CasADi) is not installed |
| `error.solver.integration_failed` | error | Numerical integration failed at runtime |
| `error.solver.non_finite_result` | error | Solver produced non-finite values (NaN, Inf) |
| `error.solver.timeout` | error | Solver exceeded configured timeout |
| `error.simulation.invalid_request` | error | Simulation request validation failed |
| `error.simulation.aborted_by_user` | error | User aborted a running simulation |
| `warning.simulation.fallback_to_scipy` | warning | CasADi backend unavailable; fell back to SciPy |

### 8.3 Analysis (Stage S5)

| Code | Severity | Description |
|---|---|---|
| `error.analysis.linearization_failed` | error | Linearization failed (e.g., singular Jacobian) |
| `error.analysis.operating_point_invalid` | error | Operating point is invalid for analysis |
| `error.analysis.equilibrium_not_found` | error | Auto-equilibrium solver did not converge |
| `warning.analysis.nonlinear_warning` | warning | Linearization performed on a nonlinear system; results are approximate |

### 8.4 Controller Runtime (Stage S7)

| Code | Severity | Description |
|---|---|---|
| `error.controller.runtime_step_failed` | error | Controller runtime step computation failed |
| `error.controller.output_saturated` | error | Controller output saturated against output limit |
| `warning.controller.output_at_limit` | warning | Controller output is near the output limit |

### 8.5 Plot Errors (Stage S6)

| Code | Severity | Description |
|---|---|---|
| `error.plot.artifact_missing` | error | Required artifact for the selected plot type is missing |
| `error.plot.channel_not_found` | error | Selected channel does not exist in the artifact |
| `error.plot.io_pair_invalid` | error | Selected I/O pair is not valid for the artifact |
| `error.plot.render_failed` | error | Plot rendering failed |
| `warning.plot.unknown_plot_type` | warning | Plot type from project file is not recognized; placed in Unknown group |

### 8.6 IO and Storage (Stage S4)

| Code | Severity | Description |
|---|---|---|
| `error.io.hdf5_write_failed` | error | Failed to write simulation result to HDF5 |
| `error.io.hdf5_read_failed` | error | Failed to read HDF5 file |
| `warning.io.hdf5_file_missing` | warning | Result reference points to a missing HDF5 file |

---

## 9. Adding New Error Codes

### 9.1 Governance

New error codes are added under the following rules:

1. The code must use the format from §3.1.
2. The category must come from the vocabulary in §3.3, or a new category must be proposed.
3. The code must not duplicate an existing code's meaning.
4. The code must include a localization key entry in `assets/locales/en.json` at the same time it is added.
5. A test must be added that exercises the failure path and asserts the code is emitted.
6. This document must be updated to include the new code in §7 or §8.

### 9.2 Adding a New Category

Adding a new category requires:

* a clear functional area boundary
* updating §3.3
* adding the category prefix to the linting check (see §10)

### 9.3 Deprecating an Error Code

Codes may be deprecated but not removed:

* mark the code as `[deprecated]` in this catalog
* keep the localization key in the table
* if the code is replaced by a new code, document the mapping
* remove the code only after at least one major version where it was deprecated

---

## 10. Validation and Linting

### 10.1 Catalog Consistency Test

A test in `tests/architecture/test_error_catalog.py` verifies that:

* every error code raised in the codebase appears in this catalog
* every code in this catalog has a corresponding entry in `assets/locales/en.json`
* every code follows the naming convention from §3.1
* no duplicate codes exist
* the severity prefix matches the actual severity used in raise sites

### 10.2 Localization Test

A test verifies that:

* all placeholders in localization templates can be satisfied by the documented `context` keys
* missing placeholders fall back gracefully

### 10.3 CI Enforcement

CI must run the catalog consistency test on every push (see `12_ci_cd_pipeline.md`).

---

## 11. Forbidden Practices

The agent must never:

1. emit a WARNING, ERROR, or CRITICAL log without an `error_code` in `extra`
2. invent ad-hoc error codes outside this catalog
3. use a `fatal.*` code for a recoverable error
4. use an `info.*` code for a failure
5. duplicate an existing code with a different meaning
6. remove a code from the catalog without going through deprecation
7. raise a `StructuredError` without setting both `code` and `message`
8. include sensitive data in `context` (passwords, raw paths)
9. use the same code at two different severity levels in the same release
10. translate a code itself (codes are stable identifiers, not user-facing text)

---

## 12. Acceptance Criteria

The error code catalog is acceptable when:

* every error code raised in code appears in §7 (Phase 1) or §8 (Phase 2+)
* every code in this catalog has an entry in `assets/locales/en.json`
* `tests/architecture/test_error_catalog.py` passes
* `StructuredError` and its subclasses are used for all surfaced errors
* WARNING/ERROR/CRITICAL logs always include `error_code` in `extra`
* the catalog is referenced from `02 §32`, `08 §6`, `10 §7.3` consistently
* no duplicate codes exist
* deprecated codes are clearly marked

---

## 13. Final Rule

Error codes are stable contracts.

The agent must:

* select the correct code from this catalog for every surfaced error
* never invent codes outside the catalog
* include error codes in WARNING, ERROR, and CRITICAL logs
* use `StructuredError` subclasses for raised exceptions
* keep this catalog and the localization table in sync

Codes are the bridge between the user, the developer, the support engineer, and the AI agent. Treat them as a stable API.
