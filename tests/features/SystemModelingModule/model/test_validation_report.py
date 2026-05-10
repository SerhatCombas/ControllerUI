"""Unit tests for `ValidationReport` and `ValidationIssue`.

References
----------
* `specs/02_workspace_requirements.md` §20.5 (severity levels)
* `specs/02_workspace_requirements.md` §32.3.3 (status bar summary format)
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from features.SystemModelingModule.model.validation_report import (
    ValidationIssue,
    ValidationReport,
)


def _issue(
    *,
    severity: str,
    issue_id: str = "i",
    code: str = "warning.test.placeholder",
    message: str = "placeholder",
    subject_kind: str = "workspace",
    subject_id: str | None = None,
) -> ValidationIssue:
    return ValidationIssue(
        issue_id=issue_id,
        severity=severity,  # type: ignore[arg-type]
        code=code,
        message=message,
        subject_kind=subject_kind,  # type: ignore[arg-type]
        subject_id=subject_id,
    )


# ---------------------------------------------------------------------- #
# Empty / OK state
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_empty_report_is_ok() -> None:
    report = ValidationReport.empty()
    assert report.issues == ()
    assert not report.has_errors
    assert not report.has_warnings
    assert not report.is_blocking
    assert report.summary() == "Workspace OK"


@pytest.mark.unit
def test_default_constructor_yields_empty_report() -> None:
    assert ValidationReport() == ValidationReport.empty()


# ---------------------------------------------------------------------- #
# Severity flags
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_has_errors_is_true_when_any_issue_is_error() -> None:
    report = ValidationReport(
        issues=(
            _issue(severity="info", issue_id="i1"),
            _issue(severity="error", issue_id="i2"),
        )
    )
    assert report.has_errors
    assert report.is_blocking


@pytest.mark.unit
def test_has_warnings_is_independent_from_errors() -> None:
    report = ValidationReport(issues=(_issue(severity="warning", issue_id="w1"),))
    assert report.has_warnings
    assert not report.has_errors
    assert not report.is_blocking  # warnings do not block simulation (§20.5)


@pytest.mark.unit
def test_info_only_report_is_not_blocking_and_summary_is_ok() -> None:
    """Info entries do not raise the headline summary (`02 §32.3.3`)."""
    report = ValidationReport(
        issues=(
            _issue(severity="info", issue_id="i1"),
            _issue(severity="info", issue_id="i2"),
        )
    )
    assert not report.has_errors
    assert not report.has_warnings
    assert not report.is_blocking
    assert report.summary() == "Workspace OK"


# ---------------------------------------------------------------------- #
# by_severity / for_subject
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_by_severity_filters_and_preserves_order() -> None:
    a = _issue(severity="warning", issue_id="a")
    b = _issue(severity="error", issue_id="b")
    c = _issue(severity="warning", issue_id="c")
    report = ValidationReport(issues=(a, b, c))

    assert report.by_severity("warning") == (a, c)
    assert report.by_severity("error") == (b,)
    assert report.by_severity("info") == ()


@pytest.mark.unit
def test_for_subject_returns_issues_for_that_subject() -> None:
    a = _issue(
        severity="error",
        issue_id="a",
        subject_kind="component",
        subject_id="cmp_x",
    )
    b = _issue(
        severity="warning",
        issue_id="b",
        subject_kind="component",
        subject_id="cmp_y",
    )
    c = _issue(
        severity="info",
        issue_id="c",
        subject_kind="component",
        subject_id="cmp_x",
    )
    report = ValidationReport(issues=(a, b, c))

    assert report.for_subject("cmp_x") == (a, c)
    assert report.for_subject("cmp_y") == (b,)
    assert report.for_subject("cmp_z") == ()


@pytest.mark.unit
def test_for_subject_excludes_workspace_level_issues() -> None:
    """Workspace-level issues (subject_id is None) must never match by id."""
    workspace_issue = _issue(severity="error", issue_id="w", subject_id=None)
    report = ValidationReport(issues=(workspace_issue,))
    assert report.for_subject("anything") == ()


# ---------------------------------------------------------------------- #
# summary() formatting (matches the §32.3.3 examples literally)
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_summary_one_warning_singular() -> None:
    report = ValidationReport(issues=(_issue(severity="warning", issue_id="w1"),))
    assert report.summary() == "1 warning"


@pytest.mark.unit
def test_summary_two_warnings_plural() -> None:
    report = ValidationReport(
        issues=(
            _issue(severity="warning", issue_id="w1"),
            _issue(severity="warning", issue_id="w2"),
        )
    )
    assert report.summary() == "2 warnings"


@pytest.mark.unit
def test_summary_one_error_singular() -> None:
    report = ValidationReport(issues=(_issue(severity="error", issue_id="e1"),))
    assert report.summary() == "1 error"


@pytest.mark.unit
def test_summary_two_warnings_one_error_matches_spec_example() -> None:
    """Spec §32.3.3 explicit example: `2 warnings, 1 error`."""
    report = ValidationReport(
        issues=(
            _issue(severity="warning", issue_id="w1"),
            _issue(severity="warning", issue_id="w2"),
            _issue(severity="error", issue_id="e1"),
        )
    )
    assert report.summary() == "2 warnings, 1 error"


# ---------------------------------------------------------------------- #
# Frozenness
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_validation_issue_is_frozen() -> None:
    issue = _issue(severity="info", issue_id="i")
    with pytest.raises(FrozenInstanceError):
        issue.severity = "error"  # type: ignore[misc]


@pytest.mark.unit
def test_validation_report_is_frozen() -> None:
    report = ValidationReport.empty()
    with pytest.raises(FrozenInstanceError):
        report.issues = ()  # type: ignore[misc]
