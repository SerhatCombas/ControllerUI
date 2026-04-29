# 10_logging_conventions.md

## 1. Purpose

This document defines mandatory logging conventions for the Engineering System Designer project.

It exists to ensure that:

* logs are useful for debugging, support, and post-mortem analysis
* log output is consistent across modules and contributors
* AI coding agents follow a single authoritative reference for logger naming, levels, and formatting
* logs do not become a vehicle for leaking sensitive information or for replacing proper error handling
* log volume scales sensibly across Phase 1, Phase 2, and Phase 3

This document is **not** a feature specification. It is an operational contract complementing `08_codex_execution_rules.md`, `09_coding_standards.md`, and `11_error_code_catalog.md`.

---

## 2. Scope

### 2.1 In Scope

* Logger hierarchy and naming
* Log level usage (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`)
* Log formatter specification
* Structured logging (key-value extras)
* Logging during application bootstrap
* Logging from `WorkspaceModel`, `SystemGraph`, registries, commands
* Logging from Qt slots and signal handlers
* Logging in tests
* Forbidden logging patterns

### 2.2 Out of Scope

* Error code definitions (see `11_error_code_catalog.md`)
* User-facing status bar messages (see `02 §32.2`)
* Telemetry, analytics, or remote log shipping (Phase 3+)

---

## 3. Logging Library

The project uses the **Python standard library** `logging` module.

Forbidden:

* `print()` statements anywhere in production code (allowed only in `examples/`, `scripts/`, and test debug output)
* third-party loggers like `loguru` or `structlog` in Phase 1 (may be reconsidered in Phase 3)
* writing logs by directly opening files

Rationale:

* `logging` is universally available
* it integrates with Qt's logging via `QtMsgHandler`
* downstream tools (CI log parsers, IDE consoles) expect standard `logging` output

---

## 4. Logger Hierarchy

Loggers follow Python's dotted-name hierarchy, mirroring the package structure under `src/`.

### 4.1 Top-Level Logger

The project root logger is named `system_designer`.

It is configured in `application/bootstrap.py` once at application startup and serves as the parent of all module-level loggers.

```python
# application/bootstrap.py
import logging

logger = logging.getLogger("system_designer")
logger.setLevel(logging.INFO)
```

### 4.2 Module Loggers

Every module that emits log messages must create a module-local logger using the module's dotted path:

```python
# features/SystemModelingModule/model/workspace_model.py
import logging

logger = logging.getLogger(__name__)
# __name__ resolves to "features.SystemModelingModule.model.workspace_model"
```

### 4.3 Logger Naming Examples

| Source File | Logger Name |
|---|---|
| `application/main.py` | `application.main` |
| `application/bootstrap.py` | `application.bootstrap` |
| `features/SystemModelingModule/model/workspace_model.py` | `features.SystemModelingModule.model.workspace_model` |
| `features/SystemModelingModule/commands/add_component_command.py` | `features.SystemModelingModule.commands.add_component_command` |
| `shared/registry/component_registry.py` | `shared.registry.component_registry` |
| `shared/engine/solvers/casadi_solver_adapter.py` | `shared.engine.solvers.casadi_solver_adapter` |

### 4.4 Logger Configuration

The bootstrap step configures:

* root level: `INFO` for production, `DEBUG` for development
* `system_designer.shared.engine` level: `WARNING` in Phase 1 (since the package is dormant)
* `features.SystemModelingModule.model` level: matches root in Phase 1

```python
# application/bootstrap.py
def configure_logging(debug: bool = False) -> None:
    """Configure project loggers at application startup.
    
    Args:
        debug: If True, set root level to DEBUG; otherwise INFO.
    """
    root_level = logging.DEBUG if debug else logging.INFO
    logging.getLogger("system_designer").setLevel(root_level)
    
    # Engine is dormant in Phase 1; suppress chatty initialization warnings.
    logging.getLogger("shared.engine").setLevel(logging.WARNING)
    
    # Configure handler with project formatter (see §6).
    handler = logging.StreamHandler()
    handler.setFormatter(get_project_formatter())
    logging.getLogger("system_designer").addHandler(handler)
```

---

## 5. Log Levels

The project uses the five standard Python log levels, each with a specific meaning.

### 5.1 DEBUG

Detailed information useful only for development.

Examples:

* `Connection candidate evaluated: source=cmp_01HV..., target=cmp_01HX..., domain_match=True`
* `Display ID counter incremented: resistor 3 -> 4`
* `Hash cache miss: workspace_hash=abc123, recomputing`

DEBUG messages must:

* not appear in production logs
* contain enough detail to reconstruct a failure scenario
* never be the primary control flow signal (use return values for that)

### 5.2 INFO

Routine but significant events. Useful for understanding what the application is doing.

Examples:

* `Project loaded: path=/path/to/project.systemdesign, components=42, connections=53`
* `Component added: id=cmp_01HV..., display=resistor_3, definition=electrical.analog.components.resistor`
* `Validation completed: errors=0, warnings=1, duration_ms=12`
* `Simulation started: request_id=sim_01HV..., backend=casadi, duration=10.0s`

INFO messages must:

* describe a meaningful state change or completed action
* be readable to a human supporting the user
* not appear at a rate that drowns out other levels in normal use

### 5.3 WARNING

Recoverable problems that may affect correctness but allow the application to continue.

Examples:

* `Validation found unresolved port reference: component=cmp_01HV..., port=p2`
* `Schema migration applied: 0.1.0 -> 0.2.0, with 3 unknown fields preserved`
* `Result reference points to missing HDF5 file: path=results/sim_01HV.h5; marking status=file_missing`
* `Plot type "experimental_phase_plot" not recognized; placed in Unknown group`

WARNING messages must:

* describe an actual problem, not just an unusual but expected event
* include enough context for the user or developer to act
* be paired with a structured error code (see §7) when applicable

### 5.4 ERROR

Failures that prevent an operation from completing but do not crash the application.

Examples:

* `Failed to load project: schema_version 0.0.5 has no migration path`
* `Connection rejected: incompatible domains (electrical_analog -> mechanical_translational)`
* `Component definition not found in registry: definition_id=electrical.analog.unknown`
* `Simulation aborted: solver returned non-finite result at t=2.3`

ERROR messages must:

* describe a failed operation, not a failed application
* include a structured error code (see `11_error_code_catalog.md`)
* be visible to the user through the status bar or an info panel (see `02 §32`)

### 5.5 CRITICAL

Failures that may compromise the application's integrity or risk data loss.

Examples:

* `Project save failed mid-write; recovery file may be corrupt`
* `Architecture invariant violated: shared.engine import detected at runtime in Phase 1`
* `Component registry corruption detected: duplicate definition_id`
* `Unhandled exception in main event loop`

CRITICAL messages must:

* be rare in normal operation
* trigger user-visible alerts (modal dialog or persistent error banner)
* include a stack trace via `logger.critical(..., exc_info=True)`

### 5.6 Level Selection Rules

When deciding between levels:

* if the user does not need to know → DEBUG
* if the user benefits from knowing but no action is needed → INFO
* if the user should be aware and possibly act → WARNING
* if an operation failed → ERROR
* if the application's integrity is at risk → CRITICAL

---

## 6. Log Format

### 6.1 Production Formatter

The standard production formatter is:

```text
2026-04-28 14:23:45.123 | INFO     | features.SystemModelingModule.model.workspace_model | Component added: id=cmp_01HV7N9G8K4QZ7R2M6P3A1B9C0, display=resistor_3
```

Format string:

```python
"%(asctime)s.%(msecs)03d | %(levelname)-8s | %(name)s | %(message)s"
```

Fields:

* timestamp with millisecond precision in ISO-like format
* level name padded to 8 characters for alignment
* logger name (the module path)
* message

The formatter implementation:

```python
# shared/utils/logging_helpers.py
import logging

def get_project_formatter() -> logging.Formatter:
    """Return the canonical project log formatter."""
    return logging.Formatter(
        fmt="%(asctime)s.%(msecs)03d | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
```

### 6.2 Development Formatter

Optional: a richer formatter may be enabled in development with `--debug` to include source location:

```text
2026-04-28 14:23:45.123 | INFO     | features.SystemModelingModule.model.workspace_model:add_component:142 | Component added
```

The development formatter is selected by `bootstrap.configure_logging(debug=True)`.

### 6.3 Forbidden Format Practices

* timestamps without timezone or millisecond precision
* level names not padded (alignment matters in scanning)
* mixing different formatters across handlers
* including the entire logger name path in the user-facing status bar (use the message only, see `02 §32.2`)

---

## 7. Structured Logging

While the project uses standard `logging`, key-value context must be passed via `extra` to enable downstream parsing.

### 7.1 Using `extra`

Pass structured context as a dictionary:

```python
logger.info(
    "Component added",
    extra={
        "component_id": component_id,
        "display_id": display_id,
        "definition_id": definition_id,
        "domain": domain,
    },
)
```

The standard formatter ignores `extra` keys, but downstream log processors (in Phase 3+) can index them.

### 7.2 Structured Logging via Helpers

For frequently-emitted events, define helpers in `shared/utils/logging_helpers.py`:

```python
def log_component_added(
    logger: logging.Logger,
    component: ComponentInstance,
) -> None:
    """Emit a standardized component-added log entry."""
    logger.info(
        "Component added: id=%s, display=%s, definition=%s",
        component.id,
        component.display_id,
        component.definition_id,
        extra={
            "event": "workspace.component_added",
            "component_id": component.id,
            "display_id": component.display_id,
            "definition_id": component.definition_id,
            "domain": component.domain,
        },
    )
```

Standard event names (see §8) belong here for consistency.

### 7.3 Error Codes in Structured Logs

When logging WARNING, ERROR, or CRITICAL, include the error code from `11_error_code_catalog.md`:

```python
logger.error(
    "Connection rejected: incompatible domains",
    extra={
        "event": "workspace.connection_rejected",
        "error_code": "error.connection.incompatible_domains",
        "source_domain": source.domain,
        "target_domain": target.domain,
        "source_id": source.id,
        "target_id": target.id,
    },
)
```

Error codes are defined in `11_error_code_catalog.md`. Logging without the corresponding error code is forbidden for ERROR and CRITICAL.

---

## 8. Standard Event Names

The following event names are reserved for use in `extra["event"]` to enable consistent log parsing.

### 8.1 Workspace Events

* `workspace.component_added`
* `workspace.component_removed`
* `workspace.component_moved`
* `workspace.component_rotated`
* `workspace.component_changed`
* `workspace.connection_added`
* `workspace.connection_removed`
* `workspace.connection_modified`
* `workspace.connection_rejected`
* `workspace.parameter_changed`
* `workspace.selection_changed`
* `workspace.validation_changed`
* `workspace.validation_errors`

### 8.2 Project Lifecycle Events

* `project.new`
* `project.opened`
* `project.saved`
* `project.closed`
* `project.autosave`
* `project.recovery_loaded`
* `project.migration_applied`
* `project.migration_failed`

### 8.3 Registry Events

* `registry.bootstrap_started`
* `registry.bootstrap_completed`
* `registry.definition_registered`
* `registry.definition_lookup_failed`

### 8.4 Command Events

* `command.redo`
* `command.undo`
* `command.merged`

### 8.5 Phase 2+ Events

* `engine.simulation_requested`
* `engine.simulation_completed`
* `engine.simulation_failed`
* `engine.solver_selected`
* `analysis.linearization_completed`
* `analysis.stability_artifact_produced`
* `controller.runtime_started`
* `controller.runtime_step_failed`

### 8.6 System Events

* `system.startup`
* `system.shutdown`
* `system.unhandled_exception`
* `system.architecture_invariant_violated`

The full event list is maintained in `shared/utils/logging_events.py` as constants:

```python
# shared/utils/logging_events.py
WORKSPACE_COMPONENT_ADDED = "workspace.component_added"
WORKSPACE_COMPONENT_REMOVED = "workspace.component_removed"
# ...
```

---

## 9. Bootstrap Logging

Application startup must produce a clear sequence of INFO messages tracing the initialization order:

```text
2026-04-28 14:00:00.001 | INFO  | system_designer | Application starting
2026-04-28 14:00:00.005 | INFO  | application.bootstrap | Logging configured: level=INFO
2026-04-28 14:00:00.012 | INFO  | application.bootstrap | Settings loaded: path=~/.config/system_designer/settings.json
2026-04-28 14:00:00.045 | INFO  | shared.registry.domain_registry | DomainRegistry loaded: 4 domains
2026-04-28 14:00:00.087 | INFO  | shared.registry.component_registry | ComponentRegistry loaded: 23 components
2026-04-28 14:00:00.092 | INFO  | shared.registry.svg_registry | SvgRegistry loaded: 23 SVG assets
2026-04-28 14:00:00.130 | INFO  | features.SystemModelingModule.module | SystemModelingModule initialized
2026-04-28 14:00:00.155 | INFO  | features.ControllerDesignModule.module | ControllerDesignModule initialized
2026-04-28 14:00:00.180 | INFO  | application.shell | SystemDesignerShell created
2026-04-28 14:00:00.220 | INFO  | system_designer | Application ready
```

This sequence aids debugging when the application fails to start.

---

## 10. Logging in Specific Contexts

### 10.1 Logging in `WorkspaceModel`

Every state-affecting public method must emit at least one INFO log on success:

```python
def add_component(self, definition_id: str, position: QPointF) -> str:
    component = self._build_component(definition_id, position)
    self._components[component.id] = component
    self.componentAdded.emit(component.id)
    self._mark_dirty()
    
    logger.info(
        "Component added",
        extra={
            "event": "workspace.component_added",
            "component_id": component.id,
            "display_id": component.display_id,
            "definition_id": definition_id,
        },
    )
    return component.id
```

Validation failures within `WorkspaceModel` use WARNING:

```python
if existing_connection := self._find_duplicate_connection(source, target):
    logger.warning(
        "Duplicate connection rejected",
        extra={
            "event": "workspace.connection_rejected",
            "error_code": "error.connection.duplicate",
            "existing_connection_id": existing_connection.id,
            "source_id": source.id,
            "target_id": target.id,
        },
    )
    raise DuplicateConnectionError(...)
```

### 10.2 Logging in Commands

`QUndoCommand` subclasses must log on `redo` (initial execution) and `undo`:

```python
class AddComponentCommand(QUndoCommand):
    def redo(self) -> None:
        self._component_id = self._model.add_component(
            self._definition_id, self._position
        )
        logger.debug(
            "Command executed: AddComponent",
            extra={
                "event": "command.redo",
                "command_type": "AddComponent",
                "component_id": self._component_id,
            },
        )
    
    def undo(self) -> None:
        self._model.remove_component(self._component_id)
        logger.debug(
            "Command undone: AddComponent",
            extra={
                "event": "command.undo",
                "command_type": "AddComponent",
                "component_id": self._component_id,
            },
        )
```

Note: Commands use DEBUG (not INFO) because the underlying model methods already emit INFO. Double-logging the same event would be noisy.

### 10.3 Logging in Qt Slots

Slots that handle signals should log only when the slot's behavior is non-trivial:

```python
def on_component_added(self, component_id: str) -> None:
    component = self._model.get_component(component_id)
    self._create_graphics_item(component)
    # No log here: the model already logged the addition.
```

```python
def on_validation_changed(self, report: ValidationReport) -> None:
    self._update_visual_indicators(report)
    if report.has_errors():
        logger.warning(
            "Validation errors present",
            extra={
                "event": "workspace.validation_errors",
                "error_count": len(report.errors),
                "warning_count": len(report.warnings),
            },
        )
```

### 10.4 Logging in Tests

Tests should not emit logs to stdout by default. Use `caplog` to assert on log content:

```python
import logging
import pytest

def test_add_component_logs_info(workspace_model, caplog):
    with caplog.at_level(logging.INFO, logger="features.SystemModelingModule"):
        workspace_model.add_component("electrical.analog.components.resistor", QPointF(0, 0))
    
    assert any(
        record.levelname == "INFO" 
        and "Component added" in record.message
        for record in caplog.records
    )
```

### 10.5 Logging Exceptions

When catching and re-raising or transforming an exception, include `exc_info=True`:

```python
try:
    self._migration_registry.migrate(data, target_version)
except SchemaMigrationError:
    logger.error(
        "Schema migration failed",
        extra={
            "event": "project.migration_failed",
            "error_code": "error.project.migration_failed",
            "from_version": data["schema_version"],
            "to_version": target_version,
        },
        exc_info=True,
    )
    raise
```

For unhandled exceptions in the Qt event loop, install a handler:

```python
def install_unhandled_exception_handler() -> None:
    """Install a logging handler for uncaught exceptions."""
    def handler(exc_type, exc_value, exc_traceback):
        logger.critical(
            "Unhandled exception",
            extra={"event": "system.unhandled_exception"},
            exc_info=(exc_type, exc_value, exc_traceback),
        )
    
    sys.excepthook = handler
```

---

## 11. Performance Considerations

### 11.1 Lazy Message Construction

Use `%` formatting in log calls so that the formatter is only invoked when the level is enabled:

```python
# Good: lazy formatting
logger.debug("Component %s moved to (%s, %s)", component_id, x, y)

# Bad: eager formatting (str interpolation happens regardless of level)
logger.debug(f"Component {component_id} moved to ({x}, {y})")
```

For complex objects, guard with `isEnabledFor`:

```python
if logger.isEnabledFor(logging.DEBUG):
    logger.debug("State snapshot: %s", json.dumps(model.to_dict()))
```

### 11.2 High-Frequency Paths

Logging inside per-frame Qt paint events, mouse-move handlers, or solver step callbacks must be DEBUG-only and rate-limited:

```python
class GhostConnectionItem(QGraphicsItem):
    def update_position(self, scene_pos: QPointF) -> None:
        # Do not log: this fires on every mouse-move event.
        self._end_pos = scene_pos
        self.update()
```

For Phase 2 simulation step callbacks, log only milestones (every 1000 steps, every 1 second of simulated time, or on completion).

### 11.3 Forbidden Performance Patterns

* logging inside tight loops without level guards
* serializing large objects (full model snapshots, simulation arrays) at INFO or higher
* logging every paint event
* logging from inside `__hash__` or `__eq__`
* logging from inside Qt's `event()` handler

---

## 12. Sensitive Information

### 12.1 Forbidden Content

Logs must never contain:

* user credentials (passwords, API keys, tokens)
* full file paths that include user home directories or usernames (use anonymized paths in logs)
* personally identifiable information beyond what is in component custom labels (which the user explicitly typed)
* contents of `.systemdesign/` recovery files (may contain unsaved sensitive content)

### 12.2 Path Anonymization

When logging file paths, anonymize the user portion:

```python
from pathlib import Path

def anonymize_path(path: Path) -> str:
    """Replace the user's home directory with ~ in log output."""
    home = Path.home()
    try:
        return f"~/{path.relative_to(home)}"
    except ValueError:
        return str(path)
```

### 12.3 Custom Label Logging

Component custom labels are user-typed and may be logged at DEBUG or INFO. They are not considered sensitive in this context, but Phase 3+ may add a privacy mode that suppresses them.

---

## 13. Forbidden Logging Patterns

The agent must never:

1. use `print()` in production code
2. configure logging outside `application/bootstrap.py` (no per-module `logging.basicConfig()` calls)
3. emit ERROR or CRITICAL without an `error_code` in `extra`
4. emit logs from inside high-frequency paths without level guards
5. include sensitive content (credentials, raw home paths)
6. use eager `f-string` formatting in log calls without level guards
7. emit duplicate logs for the same event (e.g., both Command and Model logging the same addition at INFO)
8. swallow exceptions silently (no try-except without at least a DEBUG log)
9. log at INFO level for every paint or mouse event
10. instantiate loggers via `logging.Logger(name)` directly (use `getLogger(name)`)
11. use a hardcoded string for `event` instead of the constants from `shared/utils/logging_events.py`
12. mix log levels inconsistently (e.g., emit ERROR for an expected validation message)

---

## 14. Test Requirements

The logging configuration is acceptable when:

* every public state-affecting method emits at least one log entry
* every WARNING / ERROR / CRITICAL log includes a structured `error_code`
* the standard event names are used for `extra["event"]`
* tests verify INFO-level events for key state transitions
* tests verify that ERROR-level events include `error_code`
* the bootstrap sequence produces the expected initialization log lines
* no log emits from high-frequency Qt event handlers
* no production code uses `print()` (enforced by Ruff rule T201)
* logs do not contain unanonymized home directory paths

---

## 15. Acceptance Criteria

Logging is acceptable when:

* `system_designer` root logger is configured exactly once in `application/bootstrap.py`
* every module uses `logger = logging.getLogger(__name__)`
* the production formatter produces messages matching the format in §6.1
* structured `extra` keys are used for all non-trivial log events
* error codes from `11_error_code_catalog.md` are used in WARNING/ERROR/CRITICAL logs
* the standard event names from §8 are used consistently
* high-frequency paths are DEBUG-only with level guards
* sensitive paths are anonymized
* tests assert on log content for critical events
* CI pipeline includes a test that exercises the bootstrap log sequence (see `12_ci_cd_pipeline.md`)

---

## 16. Final Rule

Logging is the application's diagnostic backbone. It must be precise, structured, and disciplined.

The agent must:

* use `logging.getLogger(__name__)` in every module
* select the correct level for each message
* include `extra["event"]` and `extra["error_code"]` where applicable
* never use `print()`
* never emit ERROR or CRITICAL without an error code
* respect performance constraints in high-frequency paths

Logs are written for the user, the developer, and the future post-mortem. Treat them with the same rigor as production code.
