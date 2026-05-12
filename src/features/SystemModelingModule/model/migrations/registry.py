"""Schema migration framework for project files (S2.E.1).

Per spec/02 §29.3.1, project files carry a `schema_version` and
older versions must be migrated to the current target before
`WorkspaceModel.from_dict` consumes them.

Phase 1 ships the **framework** with **zero registered
migrations**: the project schema started at `0.2.0` and no prior
production format exists. A synthetic migration fixture lives in
the test suite (see `test_workspace_migrations.py`) so the
registry's dispatch path is exercised even though no real
upgrade is needed yet.

When a future schema version (`0.3.0`, ...) lands, the migration
function gets registered here as a single new entry in
`WorkspaceModelMigrations.MIGRATIONS`. The registry pattern keeps
the diff small and the chain testable per migration.

References:
----------
* `specs/02_workspace_requirements.md` §29.3 (Schema Versioning)
* `specs/02_workspace_requirements.md` §29.3.1 (to_dict / from_dict
  Contract)
* `specs/11_error_code_catalog.md` §7.9 (Migration error codes)
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Final

# Current canonical schema version. Bumped whenever the on-disk
# JSON structure for `project.json` changes in a way that needs a
# migration. Compared against `data["schema_version"]` in
# `WorkspaceModel.from_dict`.
CURRENT_SCHEMA_VERSION: Final[str] = "0.2.0"


class SchemaMigrationError(ValueError):
    """Raised when a project file cannot be migrated to the current schema.

    Two top-level causes:

    * The file declares a `schema_version` newer than the current
      application supports (forward incompatibility).
    * The file declares a known older `schema_version` but the
      registered migration chain cannot reach the current
      version (e.g., gap in the migration registry).

    Carries the source and target versions in `context` so
    `error.migration.no_path` / `.target_version_unknown`
    callers can surface them in the UI.
    """

    def __init__(
        self,
        message: str,
        *,
        source_version: str | None = None,
        target_version: str | None = None,
    ) -> None:
        """Build a structured migration failure from explicit version context."""
        super().__init__(message)
        self.source_version = source_version
        self.target_version = target_version


# A migration function takes a project-file dict at version
# `(source)` and returns the equivalent dict at version `(target)`.
# Implementations must be pure: same input → same output, no I/O.
MigrationFn = Callable[[dict[str, Any]], dict[str, Any]]


class WorkspaceModelMigrations:
    """Registry of schema migrations from older versions to current.

    Phase-1 starting state: empty registry. Adding a migration
    when the schema bumps to `0.3.0` is a single dict entry plus
    one pure function; the test suite verifies that the dispatch
    path stays correct via a synthetic 0.1.0 fixture.

    Usage:

        migrated = WorkspaceModelMigrations.migrate(
            data, target_version=CURRENT_SCHEMA_VERSION
        )

    Returns the migrated dict (a new object; never mutates input).
    Raises `SchemaMigrationError` when the chain is broken.
    """

    # `(source_version, next_version)` → migration function.
    # Phase 1 ships an empty registry; future schema bumps add
    # entries here.
    MIGRATIONS: Final[dict[tuple[str, str], MigrationFn]] = {}

    @classmethod
    def migrate(
        cls,
        data: dict[str, Any],
        *,
        target_version: str = CURRENT_SCHEMA_VERSION,
    ) -> dict[str, Any]:
        """Walk the migration chain from `data["schema_version"]` to `target_version`.

        Args:
            data: Project-file dict carrying a `schema_version` key.
            target_version: Desired schema version. Defaults to
                `CURRENT_SCHEMA_VERSION`. Tests pass an alternate
                target to exercise mid-chain stops.

        Returns:
            A new dict at `target_version`. The input is not mutated.

        Raises:
            SchemaMigrationError: `data["schema_version"]` is
                absent / unknown, newer than `target_version`, or
                no migration chain reaches `target_version`.
        """
        if "schema_version" not in data:
            raise SchemaMigrationError(
                "project payload missing 'schema_version'",
                source_version=None,
                target_version=target_version,
            )
        current = str(data["schema_version"])
        if current == target_version:
            return dict(data)
        if cls._version_tuple(current) > cls._version_tuple(target_version):
            raise SchemaMigrationError(
                f"project schema_version {current!r} is newer than the "
                f"application target {target_version!r}; refusing to load",
                source_version=current,
                target_version=target_version,
            )
        # Walk one hop at a time until we reach the target.
        seen: set[str] = {current}
        while current != target_version:
            next_step = cls._find_next_step(current, target_version)
            if next_step is None:
                raise SchemaMigrationError(
                    f"no migration path from {current!r} to " f"{target_version!r}",
                    source_version=current,
                    target_version=target_version,
                )
            migrate_fn = cls.MIGRATIONS[(current, next_step)]
            data = migrate_fn(data)
            current = next_step
            if current in seen:
                # Defensive cycle detection — the registry should
                # be acyclic, but bad entries should raise rather
                # than spin forever.
                raise SchemaMigrationError(
                    f"migration chain cycle detected at {current!r}",
                    source_version=current,
                    target_version=target_version,
                )
            seen.add(current)
        return dict(data)

    @classmethod
    def _find_next_step(cls, current: str, target_version: str) -> str | None:
        """Return the next intermediate version to migrate to, if any.

        Phase-1 implementation: linear lookup over registered
        edges starting at `current`. Acceptable cost for Phase 1
        chain length (≤ a handful of versions). When the chain
        grows, swap for a precomputed graph + BFS without
        changing the call site.
        """
        for source, dest in cls.MIGRATIONS:
            if source == current:
                return dest
        return None

    @staticmethod
    def _version_tuple(version: str) -> tuple[int, ...]:
        """Convert a `'major.minor.patch'` string into a comparable tuple.

        Non-numeric segments collapse to `0` so accidentally
        malformed values still sort deterministically (and a
        migration registry mismatch surfaces as a "no path"
        error rather than a crash).
        """
        parts: list[int] = []
        for chunk in version.split("."):
            try:
                parts.append(int(chunk))
            except ValueError:
                parts.append(0)
        return tuple(parts)


__all__ = [
    "CURRENT_SCHEMA_VERSION",
    "MigrationFn",
    "SchemaMigrationError",
    "WorkspaceModelMigrations",
]
