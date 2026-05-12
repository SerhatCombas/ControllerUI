"""Schema migration registry for project file format.

Migrations run in `WorkspaceModel.from_dict()` when the input data
has an older `schema_version` than the current target.

The S2.E.1 commit lands the framework in `registry.py`; Phase 1
ships with zero registered migrations (the project schema started
at `0.2.0` and no prior format exists). Future bumps add entries
to `WorkspaceModelMigrations.MIGRATIONS`.

References:
----------
* `specs/02_workspace_requirements.md` §29.3.1 (to_dict / from_dict contract)
* `specs/06_data_flow_and_architecture.md` §4.2.2 (WorkspaceModel serialization)
"""

from .registry import (
    CURRENT_SCHEMA_VERSION,
    MigrationFn,
    SchemaMigrationError,
    WorkspaceModelMigrations,
)

__all__: list[str] = [
    "CURRENT_SCHEMA_VERSION",
    "MigrationFn",
    "SchemaMigrationError",
    "WorkspaceModelMigrations",
]
