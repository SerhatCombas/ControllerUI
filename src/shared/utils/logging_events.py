"""Canonical event-name constants for structured logging.

Per `specs/10_logging_conventions.md` §8. Every value passed as
`extra["event"]` in a `logger.{info,warning,error,...}` call must
come from this module — the architecture test
`tests/architecture/test_logging_events.py` enforces the
constraint by scanning source for literal
`{"event": "<string>"}` dict entries and asserting each string
has a matching constant declared here.

Naming convention (`10 §8`): `<category>.<specific>`, lowercase
with underscores. The category groups the event domain
(workspace, project, registry, command, system, ...) so log
consumers can filter by prefix. Spec/10 §8.1–§8.6 lists
"standard" reserved categories; module-specific categories
(e.g., `id_generator.*`) are permitted as long as they follow
the same naming pattern.

Phase 1 scope:

* §8.1 Workspace events (13 constants)
* §8.2 Project lifecycle events (8 constants)
* §8.3 Registry events (4 constants)
* §8.4 Command events (3 constants)
* §8.6 System events (4 constants)
* Module-scope: `id_generator.*` (2 constants — pre-S1.8
  events from `WorkspaceIdGenerator` malformed-input
  recovery paths)

Phase 2+ deferred per §8.5 (engine simulation, analysis,
controller runtime — 8 entries). They will be added to this
module when the corresponding modules land.

Note on style: constants are written as bare `NAME = "value"`
assignments (no `: str` annotation) so the AST-walking
architecture test detects them via `ast.Assign` — matches the
spec/10 §8 example and avoids the `AnnAssign` blind spot.

References:
----------
* `specs/10_logging_conventions.md` §7 (Structured Logging),
  §8 (Standard Event Names), §10 (Logging in Specific Contexts)
* `specs/12_ci_cd_pipeline.md` §6.5 (event-name CI check)
"""

from __future__ import annotations

# ---------------------------------------------------------------------- #
# §8.1 Workspace events
# ---------------------------------------------------------------------- #

WORKSPACE_COMPONENT_ADDED = "workspace.component_added"
WORKSPACE_COMPONENT_REMOVED = "workspace.component_removed"
WORKSPACE_COMPONENT_MOVED = "workspace.component_moved"
WORKSPACE_COMPONENT_ROTATED = "workspace.component_rotated"
WORKSPACE_COMPONENT_CHANGED = "workspace.component_changed"
WORKSPACE_CONNECTION_ADDED = "workspace.connection_added"
WORKSPACE_CONNECTION_REMOVED = "workspace.connection_removed"
WORKSPACE_CONNECTION_MODIFIED = "workspace.connection_modified"
WORKSPACE_CONNECTION_REJECTED = "workspace.connection_rejected"
WORKSPACE_PARAMETER_CHANGED = "workspace.parameter_changed"
WORKSPACE_SELECTION_CHANGED = "workspace.selection_changed"
WORKSPACE_VALIDATION_CHANGED = "workspace.validation_changed"
WORKSPACE_VALIDATION_ERRORS = "workspace.validation_errors"

# ---------------------------------------------------------------------- #
# §8.2 Project lifecycle events
# ---------------------------------------------------------------------- #

PROJECT_NEW = "project.new"
PROJECT_OPENED = "project.opened"
PROJECT_SAVED = "project.saved"
PROJECT_CLOSED = "project.closed"
PROJECT_AUTOSAVE = "project.autosave"
PROJECT_RECOVERY_LOADED = "project.recovery_loaded"
PROJECT_MIGRATION_APPLIED = "project.migration_applied"
PROJECT_MIGRATION_FAILED = "project.migration_failed"

# S2.E.2 + S2.G.2 — explicit lifecycle events for the
# `application/persistence/project_io.py` save / load orchestrator
# and the shell's File menu slots. Distinct from the older
# `project.saved` / `project.opened` constants (kept for autosave
# in S2.F where they describe a different lifecycle pattern).
PROJECT_SAVE_STARTED = "project.save_started"
PROJECT_SAVE_COMPLETED = "project.save_completed"
PROJECT_SAVE_FAILED = "project.save_failed"
PROJECT_LOAD_STARTED = "project.load_started"
PROJECT_LOAD_COMPLETED = "project.load_completed"
PROJECT_LOAD_FAILED = "project.load_failed"

# ---------------------------------------------------------------------- #
# §8.3 Registry events
# ---------------------------------------------------------------------- #

REGISTRY_BOOTSTRAP_STARTED = "registry.bootstrap_started"
REGISTRY_BOOTSTRAP_COMPLETED = "registry.bootstrap_completed"
REGISTRY_DEFINITION_REGISTERED = "registry.definition_registered"
REGISTRY_DEFINITION_LOOKUP_FAILED = "registry.definition_lookup_failed"

# ---------------------------------------------------------------------- #
# §8.4 Command events
# ---------------------------------------------------------------------- #

COMMAND_REDO = "command.redo"
COMMAND_UNDO = "command.undo"
COMMAND_MERGED = "command.merged"

# ---------------------------------------------------------------------- #
# §8.6 System events
# ---------------------------------------------------------------------- #

SYSTEM_STARTUP = "system.startup"
SYSTEM_SHUTDOWN = "system.shutdown"
SYSTEM_UNHANDLED_EXCEPTION = "system.unhandled_exception"
SYSTEM_ARCHITECTURE_INVARIANT_VIOLATED = "system.architecture_invariant_violated"

# ---------------------------------------------------------------------- #
# Module-scope events — pre-S1.8 usages that the catalog now
# documents. `WorkspaceIdGenerator` emits these from its
# malformed-input recovery paths (`02 §8.2`).
# ---------------------------------------------------------------------- #

ID_GENERATOR_MALFORMED_DISPLAY_ID = "id_generator.malformed_display_id"
ID_GENERATOR_UNEXPECTED_CONNECTION_PREFIX = "id_generator.unexpected_connection_prefix"

# ---------------------------------------------------------------------- #
# §8.5 Phase 2+ events — intentionally NOT declared here.
#
# These constants will be added when the corresponding Phase 2+
# modules land:
#   * engine.simulation_requested / completed / failed
#   * engine.solver_selected
#   * analysis.linearization_completed
#   * analysis.stability_artifact_produced
#   * controller.runtime_started / step_failed
#
# Adding them prematurely would create dead names that drift out
# of sync with whatever the Phase 2 producer actually emits.
# ---------------------------------------------------------------------- #


__all__ = [
    # §8.4 Command
    "COMMAND_MERGED",
    "COMMAND_REDO",
    "COMMAND_UNDO",
    # Module-scope: id_generator
    "ID_GENERATOR_MALFORMED_DISPLAY_ID",
    "ID_GENERATOR_UNEXPECTED_CONNECTION_PREFIX",
    # §8.2 Project
    "PROJECT_AUTOSAVE",
    "PROJECT_CLOSED",
    "PROJECT_LOAD_COMPLETED",
    "PROJECT_LOAD_FAILED",
    "PROJECT_LOAD_STARTED",
    "PROJECT_MIGRATION_APPLIED",
    "PROJECT_MIGRATION_FAILED",
    "PROJECT_NEW",
    "PROJECT_OPENED",
    "PROJECT_RECOVERY_LOADED",
    "PROJECT_SAVE_COMPLETED",
    "PROJECT_SAVE_FAILED",
    "PROJECT_SAVE_STARTED",
    "PROJECT_SAVED",
    # §8.3 Registry
    "REGISTRY_BOOTSTRAP_COMPLETED",
    "REGISTRY_BOOTSTRAP_STARTED",
    "REGISTRY_DEFINITION_LOOKUP_FAILED",
    "REGISTRY_DEFINITION_REGISTERED",
    # §8.6 System
    "SYSTEM_ARCHITECTURE_INVARIANT_VIOLATED",
    "SYSTEM_SHUTDOWN",
    "SYSTEM_STARTUP",
    "SYSTEM_UNHANDLED_EXCEPTION",
    # §8.1 Workspace
    "WORKSPACE_COMPONENT_ADDED",
    "WORKSPACE_COMPONENT_CHANGED",
    "WORKSPACE_COMPONENT_MOVED",
    "WORKSPACE_COMPONENT_REMOVED",
    "WORKSPACE_COMPONENT_ROTATED",
    "WORKSPACE_CONNECTION_ADDED",
    "WORKSPACE_CONNECTION_MODIFIED",
    "WORKSPACE_CONNECTION_REJECTED",
    "WORKSPACE_CONNECTION_REMOVED",
    "WORKSPACE_PARAMETER_CHANGED",
    "WORKSPACE_SELECTION_CHANGED",
    "WORKSPACE_VALIDATION_CHANGED",
    "WORKSPACE_VALIDATION_ERRORS",
]
