"""Architecture invariant: Phase 1 immutable fields have no public setter.

Per `02 §11.4 Field Mutability Matrix`, certain fields on
`ComponentInstance` are immutable in Phase 1:

* Definition-inherited (`02 §11.3`): `visual`, `physical_attributes`.
  These come from the source `ComponentDefinition` and the user
  cannot edit them in Phase 1.
* Forward-compatibility containers (`02 §29.1`, §29.3.1, §39):
  `metadata`, `extensions`. Round-trip preservation slots only;
  populated via `_build_*` (new instance) and `from_dict` (load
  preservation). No public mutation path.
* Identity / lifecycle timestamps: `created_at` (immutable),
  `modified_at` (auto-managed by mutation methods, not externally
  settable).

This test guards against regressions: if someone adds a public
`set_*` method for any of these fields, the matrix in `02 §11.4`
must be updated first, and for definition-inherited fields a new
ADR justifying the policy change is required.

Negative shape testing belongs in the architecture wave, not the
behavioral unit suite — the assertion is structural ("model exposes
no method named X"), not behavioral ("method X does Y").

References
----------
* `specs/02_workspace_requirements.md` §11.3 (Physical Attributes
  Origin), §11.4 (Field Mutability Matrix), §29.1 (project JSON
  field semantics), §29.3.1 (from_dict round-trip), §39 (Bond Graph
  preparation).
* `decisions/ADR-003-workspace-ui-data-separation.md` (mutation API
  as the only sanctioned write path).
* `decisions/ADR-020-dirty-tracking-semantics.md` (modified_at
  auto-management).
"""

from __future__ import annotations

import pytest

from features.SystemModelingModule.model.workspace_model import WorkspaceModel

# Setter names that MUST NOT exist on `WorkspaceModel` in Phase 1.
# Adding any of these requires updating `02 §11.4` first.
_PHASE1_IMMUTABLE_SETTERS: tuple[str, ...] = (
    "set_physical_attributes",
    "set_visual",
    "set_metadata",
    "set_extensions",
    "set_created_at",
    "set_modified_at",
)


@pytest.mark.architecture
@pytest.mark.parametrize("attr", _PHASE1_IMMUTABLE_SETTERS)
def test_phase1_immutable_fields_have_no_public_setter(attr: str) -> None:
    """Phase 1 §11.3 / §11.4: immutable fields have no public setter.

    Regression guard. If this test fails because a setter was added
    for one of the listed fields, the spec amendment in `02 §11.4`
    must be updated first; for definition-inherited fields (`visual`,
    `physical_attributes`), a new ADR justifying the policy change
    is also required before re-running.
    """
    model = WorkspaceModel()
    assert not hasattr(model, attr), (
        f"{attr} should not exist in Phase 1 per `02 §11.4` "
        f"Field Mutability Matrix. If this setter is intentional, "
        f"update the matrix and (for definition-inherited fields) "
        f"add an ADR justifying the change before re-running."
    )
