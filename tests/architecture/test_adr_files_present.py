"""Architecture test: 20 canonical ADR files present.

Verifies that all 20 ADRs referenced in `06_data_flow_and_architecture.md`
§19 exist as files in `decisions/` with matching filenames.

Per `decisions/README.md`, `08_codex_execution_rules.md` §8, and
`12_ci_cd_pipeline.md` §6.5.
"""

from __future__ import annotations

from pathlib import Path

import pytest


DECISIONS_ROOT = Path("decisions")

# The canonical 20 ADRs from `06 §19`.
CANONICAL_ADRS = [
    "ADR-001-phase1-engine-isolation.md",
    "ADR-002-hybrid-ulid-identity-model.md",
    "ADR-003-workspace-ui-data-separation.md",
    "ADR-004-equation-builder-ownership.md",
    "ADR-005-command-stack-qundostack.md",
    "ADR-006-controller-owns-transfer-function-builder.md",
    "ADR-007-symbolic-backend-casadi.md",
    "ADR-008-bond-graph-causality.md",
    "ADR-009-dae-reduction-strategy.md",
    "ADR-010-linearization-ownership.md",
    "ADR-011-dimensional-analysis-policy.md",
    "ADR-012-project-package-directory-format.md",
    "ADR-013-stability-analysis-artifact.md",
    "ADR-014-controller-wrapper-shared-engine.md",
    "ADR-015-result-panel-unified-with-grouped-dropdown.md",
    "ADR-016-channel-selection-kind-schema.md",
    "ADR-017-mirror-sync-plot-dropdowns.md",
    "ADR-018-signal-payload-contracts.md",
    "ADR-019-batch-mutation-and-changeset.md",
    "ADR-020-dirty-tracking-semantics.md",
]

REQUIRED_HEADERS = ("Status:", "Date:", "Context", "Decision", "Consequences")


@pytest.mark.architecture
def test_decisions_folder_exists() -> None:
    """The `decisions/` folder must exist at the project root."""
    assert DECISIONS_ROOT.is_dir(), (
        "decisions/ folder is missing. ADRs must live in this folder. "
        "See `decisions/README.md`."
    )


@pytest.mark.architecture
def test_decisions_readme_exists() -> None:
    """The `decisions/README.md` index must exist."""
    readme = DECISIONS_ROOT / "README.md"
    assert readme.is_file(), (
        "decisions/README.md is missing. It contains the ADR index "
        "and authoring guide."
    )


@pytest.mark.architecture
def test_decisions_template_exists() -> None:
    """The `decisions/_template.md` file must exist for new ADRs."""
    template = DECISIONS_ROOT / "_template.md"
    assert template.is_file(), (
        "decisions/_template.md is missing. New ADRs must be created "
        "by copying this template."
    )


@pytest.mark.architecture
def test_all_canonical_adrs_present() -> None:
    """All 20 canonical ADRs from `06 §19` exist in `decisions/`."""
    if not DECISIONS_ROOT.is_dir():
        pytest.skip("decisions/ folder not yet present.")
    
    missing = [
        name for name in CANONICAL_ADRS
        if not (DECISIONS_ROOT / name).is_file()
    ]
    
    if missing:
        pytest.fail(
            "Canonical ADRs missing from `decisions/`:\n"
            + "\n".join(f"  {name}" for name in missing)
        )


@pytest.mark.architecture
def test_adr_files_have_required_sections() -> None:
    """Each ADR file must contain Status, Date, Context, Decision, Consequences."""
    if not DECISIONS_ROOT.is_dir():
        pytest.skip("decisions/ folder not yet present.")
    
    incomplete: dict[str, list[str]] = {}
    for name in CANONICAL_ADRS:
        path = DECISIONS_ROOT / name
        if not path.is_file():
            continue  # missing file already reported by the previous test
        
        text = path.read_text(encoding="utf-8")
        missing_headers = [
            header for header in REQUIRED_HEADERS
            if header not in text
        ]
        if missing_headers:
            incomplete[name] = missing_headers
    
    if incomplete:
        report_lines = [
            f"  {name}: missing {', '.join(headers)}"
            for name, headers in incomplete.items()
        ]
        pytest.fail(
            "ADR files missing required sections:\n" + "\n".join(report_lines)
        )
