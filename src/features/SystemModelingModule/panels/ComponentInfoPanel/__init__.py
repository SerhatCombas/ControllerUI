"""Component Info Panel — bottom-of-window properties panel.

Shows properties of the current selection. Reads from `WorkspaceModel`
and `SelectionModel`; never mutates either directly.

Visible fields per `specs/02_workspace_requirements.md` §28:

* Selected (display name)
* Component ID (display ID)
* Custom Label
* Domain
* Category
* Position, Rotation
* Ports (count)
* Boundary, Motion, Directional, Source, Source Type (from physical_attributes)
* Parameters (with units)
* Status (validation result, see §32.3.2)

References
----------
* `specs/02_workspace_requirements.md` §28 (Component Info Panel Integration)
* `specs/02_workspace_requirements.md` §11 (Component Data Model)
"""

__all__: list[str] = []
