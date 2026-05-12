"""Project file persistence orchestration (S2.E.2).

The `application/persistence/` package owns the top-level
`save_project` / `load_project` pipeline that combines workspace
and configuration model serialization into one `.systemdesign/`
directory bundle per ADR-012 and spec/02 §29.

Why `application/` and not `features/` or `shared/`:

* The orchestration reads from both `SystemModelingModule` and
  `ControllerDesignModule` — neither feature can host the
  aggregator without violating the feature-to-feature import
  boundary.
* `shared/` houses cross-feature types and utilities, not
  application-level workflows.
* `application/` already composes features (the shell builds
  both models); persistence is the file-I/O cousin of that
  composition.

Phase 1 surface:

* `save_project(bundle_path, workspace_model, configuration_model)`
* `load_project(bundle_path, workspace_model, configuration_model)`
* `ProjectFormatError`

References:
----------
* `decisions/ADR-012-project-package-directory-format.md`
* `specs/02_workspace_requirements.md` §29 (Persistence)
"""

from .project_io import ProjectFormatError, load_project, save_project

__all__ = [
    "ProjectFormatError",
    "load_project",
    "save_project",
]
