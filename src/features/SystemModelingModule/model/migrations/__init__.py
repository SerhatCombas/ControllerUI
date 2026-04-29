"""Schema migration registry for project file format.

Migrations run in `WorkspaceModel.from_dict()` when the input data
has an older `schema_version` than the current target.

References
----------
* `specs/02_workspace_requirements.md` §29.3.1 (to_dict / from_dict contract)
* `specs/06_data_flow_and_architecture.md` §4.2.2 (WorkspaceModel serialization)
"""

__all__: list[str] = []
