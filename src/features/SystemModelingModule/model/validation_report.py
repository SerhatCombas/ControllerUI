"""ValidationReport: structured workspace-validation result.

The validation pipeline (`02 §20`) emits structured reports rather than
free-form strings. Reports flow through `WorkspaceModel.validationChanged`
into three coordinated UI surfaces (`02 §32.3`): workspace highlights,
component info panel status field, and the status bar summary.

Severity levels for validation are limited to `info | warning | error`
(`02 §20.5`). The four-level severity in `02 §32.1` (which adds `fatal`)
is for runtime/system failures, not validation, and is intentionally
**not** included here.

Each `ValidationIssue` carries a stable `issue_id` (`02 §20.6`) so the
UI and tests can diff reports across debounced revalidations. The
`code` field is a dotted error-catalog reference per
`11_error_code_catalog.md` §3.1; it is also the localization key.

This module is data-layer-only. It must not import any Qt UI classes.

References:
----------
* `specs/02_workspace_requirements.md` §20 (Validation Strategy)
* `specs/02_workspace_requirements.md` §32.3 (Validation Indicators)
* `specs/11_error_code_catalog.md` §3 (Naming Convention)
* `decisions/ADR-003-workspace-ui-data-separation.md`
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

# Validation severity levels per `02 §20.5`. The four-level scheme in
# `02 §32.1` is **not** the validation severity scheme.
ValidationSeverity = Literal["info", "warning", "error"]

# What kind of entity an issue is attached to. Workspace-level issues
# (e.g., "no electrical ground") use `"workspace"` and leave `subject_id`
# as `None`.
SubjectKind = Literal["component", "connection", "workspace"]


@dataclass(frozen=True)
class ValidationIssue:
    """A single validation finding.

    Issues are immutable. Their `issue_id` is stable across reports
    referring to the same logical problem on the same subject, which
    lets subscribers diff reports across debounced revalidations
    (`02 §20.6`). The caller is responsible for choosing a stable
    `issue_id` — typically derived from `(code, subject_id)` plus any
    distinguishing field stored in `context`.

    Attributes:
        issue_id: Stable identifier for this logical issue. Same
            problem on same subject must produce the same id across
            revalidations.
        severity: Severity level (`02 §20.5`).
        code: Error catalog reference following the dotted namespace
            of `11 §3.1` (e.g.,
            `"error.connection.incompatible_domains"`).
        message: Human-readable English-baseline message. The `code`
            is the localization key; this field carries the resolved
            text for display in Phase 1.
        subject_kind: What kind of entity the issue is attached to.
            Defaults to `"workspace"` for cross-cutting issues.
        subject_id: Internal ULID of the component/connection the
            issue refers to. `None` for workspace-level issues.
        context: Free-form key/value bag for templating and
            disambiguating issues during ID generation. Not
            interpreted by the report itself.
    """

    issue_id: str
    severity: ValidationSeverity
    code: str
    message: str
    subject_kind: SubjectKind = "workspace"
    subject_id: str | None = None
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ValidationReport:
    """Snapshot of all currently active validation issues.

    The empty report is the "OK" state: no issues. Reports are frozen
    so subscribers can hold references without defensive copies.
    Tuple-typed `issues` keeps the dataclass shallowly hashable (the
    tuple itself is hashable; `ValidationIssue.context` dicts are not,
    so report hashing should not be relied on — entity identity is
    the right comparison).

    Attributes:
        issues: Ordered tuple of `ValidationIssue` instances. Order
            is producer-defined; UI may resort by severity for display.
    """

    issues: tuple[ValidationIssue, ...] = ()

    @classmethod
    def empty(cls) -> ValidationReport:
        """Return the canonical empty (OK) report."""
        return cls()

    @property
    def has_errors(self) -> bool:
        """Return True if any issue has severity `"error"`."""
        return any(issue.severity == "error" for issue in self.issues)

    @property
    def has_warnings(self) -> bool:
        """Return True if any issue has severity `"warning"`."""
        return any(issue.severity == "warning" for issue in self.issues)

    @property
    def is_blocking(self) -> bool:
        """Return True if the report blocks simulation (`02 §20.5`).

        Errors block simulation in later phases; warnings and info
        do not. Aliased onto `has_errors` for readability at call
        sites that care about blocking semantics.
        """
        return self.has_errors

    def by_severity(
        self,
        severity: ValidationSeverity,
    ) -> tuple[ValidationIssue, ...]:
        """Return issues filtered to a single severity level.

        Args:
            severity: Severity to filter on.

        Returns:
            Tuple of issues with the requested severity, preserving
            input order.
        """
        return tuple(issue for issue in self.issues if issue.severity == severity)

    def for_subject(self, subject_id: str) -> tuple[ValidationIssue, ...]:
        """Return issues attached to a specific component or connection.

        Args:
            subject_id: Internal ULID of the component or connection.

        Returns:
            Tuple of issues whose `subject_id` matches, preserving
            input order. Workspace-level issues (which have
            `subject_id is None`) are never returned here.
        """
        return tuple(issue for issue in self.issues if issue.subject_id == subject_id)

    def summary(self) -> str:
        """Return a one-line summary suitable for the status bar.

        Format per `02 §32.3.3`:

        * `"Workspace OK"` when there are no errors and no warnings
        * `"1 error"`, `"2 errors"` when only errors exist
        * `"1 warning"`, `"2 warnings"` when only warnings exist
        * `"2 warnings, 1 error"` when both exist (warnings then
          errors, matching the spec example wording)

        Info-only reports also produce `"Workspace OK"`: info entries
        are tracked but do not raise the headline summary.

        Returns:
            A short, human-readable summary string.
        """
        n_warn = len(self.by_severity("warning"))
        n_err = len(self.by_severity("error"))
        if n_warn == 0 and n_err == 0:
            return "Workspace OK"
        parts: list[str] = []
        if n_warn:
            parts.append(f"{n_warn} warning{'s' if n_warn != 1 else ''}")
        if n_err:
            parts.append(f"{n_err} error{'s' if n_err != 1 else ''}")
        return ", ".join(parts)


__all__ = [
    "SubjectKind",
    "ValidationIssue",
    "ValidationReport",
    "ValidationSeverity",
]
