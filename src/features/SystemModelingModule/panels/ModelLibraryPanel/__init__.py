"""Model Equations Panel — collapsible equation display panel.

Lives in the right edge of the application window, attached to the
System Modeling area. Three visual states: collapsed, expanded, pinned.

Phase 1 content: workspace summary, component count, connection count,
active domains, validation status.

Phase 2 content: human-readable equations, state vector, input/output
vector, DAE/ODE representation, warnings.

The panel reads from `WorkspaceModel` (Phase 1) and `ODEArtifact`
(Phase 2). It must not mutate any model state.

References
----------
* `specs/06_data_flow_and_architecture.md` §13 (Model Equations Panel Flow)
* `specs/06_data_flow_and_architecture.md` §13.1 (Panel Visibility and Pinning)
* `specs/04_model_equations_requirements.md` §20 (Phase 2 panel detail)

Note
----
This panel is owned by **SystemModelingModule**, not ControllerDesignModule.
The panel's data source is the workspace model (Phase 1) and the ODE
artifact (Phase 2), both of which belong to SystemModelingModule per
ADR-004 (Equation Builder Ownership).
"""

__all__: list[str] = []
