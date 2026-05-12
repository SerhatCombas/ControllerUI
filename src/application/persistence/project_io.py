"""Top-level project save/load — `.systemdesign/` bundle orchestration.

Combines `WorkspaceModel.to_dict / from_dict` and
`ConfigurationModel.to_dict / from_dict` (S2.E.1) into one
project file at `bundle_path/project.json` plus the
`results/`, `exports/`, `recovery/` subdirectories from ADR-012.

Phase-1 design choices (locked in the S2.E pre-scan, PD1-PD9):

* PD1 — legacy single-file format intentionally not supported.
  An input path that is a regular file raises
  `ProjectFormatError` with a clear message rather than a
  generic `IsADirectoryError`.
* PD4 — atomic file write via `Path.replace` (temp-and-rename).
  Temp file lives in the same directory so the rename is atomic
  on POSIX and best-effort on Windows.
* PD6 — UTF-8 encoding, LF line endings, `indent=2`,
  `ensure_ascii=False` for human-diffable JSON output (spec §29.3.1
  "deterministic, human-diff-friendly").
* PD7 — `application_version` sourced from
  `importlib.metadata.version` so the canonical
  `pyproject.toml` value is the single source of truth.
* PD9 — module location: `application/persistence/`. Cross-feature
  reads (both `WorkspaceModel` and `ConfigurationModel`) only
  happen at the application composition layer.

Cross-model atomicity for `load_project`:

  Phase-1 implementation uses snapshot + rollback: before
  invoking the second model's `from_dict`, the first model's
  state is captured via its own `to_dict`. If the second load
  raises, the first model is rolled back by re-calling
  `from_dict` with the snapshot. This is pragmatic — it relies
  on the existing per-model atomic API and avoids exposing a
  parse-only phase publicly. A proper two-phase commit (parse
  both → apply both) is a Phase-2 cleanup if cross-model load
  performance becomes load-bearing.

References:
----------
* `decisions/ADR-012-project-package-directory-format.md`
* `specs/02_workspace_requirements.md` §29 (Persistence)
* `specs/02_workspace_requirements.md` §29.3.1 (to_dict/from_dict)
* `specs/02_workspace_requirements.md` §29.4 (Unknown field preservation)
"""

from __future__ import annotations

import json
import logging
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _package_version
from typing import TYPE_CHECKING, Any, Final

from features.SystemModelingModule.model.migrations import (
    CURRENT_SCHEMA_VERSION,
    WorkspaceModelMigrations,
)
from shared.utils import logging_events as events

if TYPE_CHECKING:
    from pathlib import Path

    from features.ControllerDesignModule.model.configuration_model import (
        ConfigurationModel,
    )
    from features.SystemModelingModule.model.workspace_model import (
        WorkspaceModel,
    )


logger = logging.getLogger(__name__)

# Bundle layout per ADR-012 + spec §29.1. `recovery/` is consumed
# by S2.F autosave (if implemented); `results/` and `exports/` are
# Phase-2 simulation/export targets. Phase-1 saves an empty
# subdirectory for each — content lands later.
_BUNDLE_SUBDIRS: Final[tuple[str, ...]] = ("results", "exports", "recovery")

# Canonical project-file name inside the bundle.
_PROJECT_JSON_NAME: Final[str] = "project.json"

# Temp suffix used for atomic write. Same-directory placement is
# required for `Path.replace` to be atomic on POSIX.
_TMP_SUFFIX: Final[str] = ".tmp"


class ProjectFormatError(ValueError):
    """Raised when a path is not a valid `.systemdesign/` bundle.

    Distinct from `FileNotFoundError` (path absent) and
    `SchemaMigrationError` (bundle exists, payload version is
    incompatible). Carries the offending path in `context` so
    UI surfaces can render a helpful "expected a directory,
    got file" message per spec/03 §29.5.
    """


def save_project(
    bundle_path: Path,
    *,
    workspace_model: WorkspaceModel,
    configuration_model: ConfigurationModel,
) -> None:
    """Save the two models into a `.systemdesign/` directory bundle.

    Atomically writes `bundle_path/project.json` via temp-and-rename
    so an interrupted save leaves either the prior file or the new
    file fully written — never half. Ensures the three subdirectory
    placeholders (`results/`, `exports/`, `recovery/`) exist.

    Args:
        bundle_path: Target directory. Created if absent. If it
            exists as a regular file, raises `ProjectFormatError`
            rather than refusing silently or clobbering.
        workspace_model: The workspace model providing the
            `components` + `connections` section.
        configuration_model: The configuration model providing the
            `controller_settings` / `io_selection` /
            `simulation_settings` / `plot_layout` sections.

    Raises:
        ProjectFormatError: `bundle_path` exists and is a regular
            file (not a directory).
    """
    logger.info(
        "Starting project save",
        extra={
            "event": events.PROJECT_SAVE_STARTED,
            "bundle_path": str(bundle_path),
        },
    )
    if bundle_path.exists() and bundle_path.is_file():
        logger.error(
            "Project save target is a regular file",
            extra={
                "event": events.PROJECT_SAVE_FAILED,
                "bundle_path": str(bundle_path),
                "reason": "regular_file",
            },
        )
        raise ProjectFormatError(
            f"Cannot save: '{bundle_path}' is a regular file. "
            f"Project bundles must be directories per ADR-012."
        )
    bundle_path.mkdir(parents=True, exist_ok=True)
    _ensure_bundle_subdirs(bundle_path)

    payload = _build_project_payload(
        workspace_model=workspace_model,
        configuration_model=configuration_model,
    )
    try:
        _atomic_write_json(bundle_path / _PROJECT_JSON_NAME, payload)
    except OSError as exc:
        logger.error(
            "Project save failed: %s",
            exc,
            extra={
                "event": events.PROJECT_SAVE_FAILED,
                "bundle_path": str(bundle_path),
                "reason": type(exc).__name__,
            },
        )
        raise
    logger.info(
        "Saved project to %s",
        bundle_path,
        extra={
            "event": events.PROJECT_SAVE_COMPLETED,
            "bundle_path": str(bundle_path),
            "schema_version": payload["schema_version"],
        },
    )


def load_project(
    bundle_path: Path,
    *,
    workspace_model: WorkspaceModel,
    configuration_model: ConfigurationModel,
) -> None:
    """Load a project bundle into the two existing model instances.

    Replaces both models' state with the bundle's contents,
    applying schema migrations if needed and triggering each
    model's `loaded` signal so the bound command stacks clear.

    Cross-model atomicity: the workspace model is loaded first;
    its post-load state is captured for rollback. If the
    configuration load then raises, the workspace is restored by
    re-applying the snapshot. Either both models load, or both
    stay at their prior state.

    Args:
        bundle_path: Path to a `.systemdesign/` directory.
        workspace_model: The model that receives the workspace
            section. Caller is responsible for re-binding any
            subscribers; the model emits `loaded` + `modelReset`
            after a successful load.
        configuration_model: The model that receives the
            configuration sections. Emits `loaded` plus the
            per-section change signals after a successful load.

    Raises:
        ProjectFormatError: `bundle_path` is a file (PD1), the
            bundle's `project.json` is missing, or the payload
            is structurally invalid (e.g., the top-level isn't
            a JSON object).
        FileNotFoundError: `bundle_path` doesn't exist at all.
        SchemaMigrationError: The project's `schema_version` is
            newer than this application or no migration path
            exists.
        KeyError / ValueError: A component / connection / config
            entry is malformed. Atomicity holds at the per-model
            level via S2.E.1 + at the cross-model level via the
            snapshot-rollback in this function.
    """
    logger.info(
        "Starting project load",
        extra={
            "event": events.PROJECT_LOAD_STARTED,
            "bundle_path": str(bundle_path),
        },
    )
    try:
        if bundle_path.is_file():
            raise ProjectFormatError(
                f"Expected a .systemdesign/ directory bundle; got file "
                f"'{bundle_path}'. Legacy single-file format is not "
                f"supported in Phase 1."
            )
        if not bundle_path.is_dir():
            raise FileNotFoundError(f"Project bundle not found: {bundle_path}")

        project_json_path = bundle_path / _PROJECT_JSON_NAME
        if not project_json_path.is_file():
            raise ProjectFormatError(
                f"Bundle '{bundle_path}' is missing the required " f"'{_PROJECT_JSON_NAME}' file."
            )

        raw = project_json_path.read_text(encoding="utf-8")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ProjectFormatError(
                f"Bundle '{bundle_path}' contains malformed JSON: {exc}"
            ) from exc
        if not isinstance(payload, dict):
            raise ProjectFormatError(
                f"Bundle '{bundle_path}' project.json top-level must be a "
                f"JSON object; got {type(payload).__name__}."
            )

        # Run the migration chain (Phase-1 registry is empty, so this
        # is a pass-through for current-version files and a clear
        # error for newer/unknown versions).
        migrated = WorkspaceModelMigrations.migrate(payload)

        # Cross-model atomic load via snapshot-rollback. Capture
        # the workspace's prior state BEFORE mutation so the
        # rollback path has somewhere to return.
        workspace_snapshot = workspace_model.to_dict()
        workspace_model.from_dict(migrated)
        try:
            configuration_model.from_dict(migrated)
        except Exception:
            # Config load failed — restore workspace to its prior
            # snapshot before propagating. The model's internal
            # atomic from_dict makes this restoration safe
            # (parse-then-apply).
            workspace_model.from_dict(workspace_snapshot)
            raise
    except Exception as exc:
        logger.error(
            "Project load failed: %s",
            exc,
            extra={
                "event": events.PROJECT_LOAD_FAILED,
                "bundle_path": str(bundle_path),
                "reason": type(exc).__name__,
            },
        )
        raise

    logger.info(
        "Loaded project from %s",
        bundle_path,
        extra={
            "event": events.PROJECT_LOAD_COMPLETED,
            "bundle_path": str(bundle_path),
            "schema_version": migrated.get("schema_version"),
        },
    )


# ====================================================================== #
# Internal helpers
# ====================================================================== #


def _build_project_payload(
    *,
    workspace_model: WorkspaceModel,
    configuration_model: ConfigurationModel,
) -> dict[str, Any]:
    """Compose the project.json dict from both models + project metadata.

    Field order matches spec/02 §29.1 for human-diffable output;
    the leading `schema_version` lets external tools sniff
    compatibility without parsing the full body.
    """
    payload: dict[str, Any] = {
        "schema_version": CURRENT_SCHEMA_VERSION,
        "application_version": _resolve_application_version(),
    }
    payload.update(workspace_model.to_dict())
    payload.update(configuration_model.to_dict())
    return payload


def _atomic_write_json(target_path: Path, payload: dict[str, Any]) -> None:
    """Write `payload` to `target_path` atomically.

    Writes to a same-directory `.tmp` file first, then
    `Path.replace`s into place. POSIX guarantees atomic rename on
    the same filesystem; Windows performs a best-effort
    `MoveFileEx` with `REPLACE_EXISTING`. Either the prior file
    survives intact or the new file fully lands — never a
    half-written file.
    """
    tmp_path = target_path.with_suffix(target_path.suffix + _TMP_SUFFIX)
    body = json.dumps(
        payload,
        indent=2,
        ensure_ascii=False,
        sort_keys=False,
    )
    # `newline="\n"` prevents Windows from translating "\n" to
    # CRLF on write, keeping the on-disk file byte-identical across
    # platforms (spec §29.3.1 deterministic output).
    tmp_path.write_text(body + "\n", encoding="utf-8", newline="\n")
    tmp_path.replace(target_path)


def _ensure_bundle_subdirs(bundle_path: Path) -> None:
    """Create the three Phase-1 subdirectories if any are missing.

    Lenient policy per the S2.E pre-scan: subdirectories are
    runtime artifacts, not part of the project's data integrity.
    A user (or external cleanup process) deleting `results/` does
    not corrupt the project — we just recreate the placeholder on
    next save. `mkdir(exist_ok=True)` is idempotent.
    """
    for subdir_name in _BUNDLE_SUBDIRS:
        (bundle_path / subdir_name).mkdir(exist_ok=True)


def _resolve_application_version() -> str:
    """Return the installed application version per PD7.

    Sources the version from `pyproject.toml` via
    `importlib.metadata`. Raises `RuntimeError` rather than
    silently returning a placeholder — if the package isn't
    installed, the test environment is misconfigured and we
    should fail loudly.
    """
    try:
        return _package_version("system_designer")
    except PackageNotFoundError as exc:
        raise RuntimeError(
            "system_designer package version cannot be resolved via "
            "importlib.metadata. Ensure 'pip install -e .' has been "
            "run per CLAUDE.md."
        ) from exc
