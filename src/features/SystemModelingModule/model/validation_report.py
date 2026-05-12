"""Re-export shim — `ValidationReport`'s canonical home is `shared/types`.

The validation-result type family was relocated to
`shared/types/validation_report.py` in the pre-S2.B.2 refactor so it
can serve both `SystemModelingModule.GraphValidator` and
`ControllerDesignModule.ConfigurationValidator` without crossing the
features → features import boundary.

This module preserves the original import path so the 30+ existing
imports inside `SystemModelingModule` keep working without churn.
New code should import from `shared.types.validation_report`
directly. A follow-up cleanup commit (S1.11 backlog: "consolidate
validation_report imports") will migrate the callers and delete this
shim.
"""

from __future__ import annotations

from shared.types.validation_report import (
    SubjectKind,
    ValidationIssue,
    ValidationReport,
    ValidationSeverity,
)

__all__ = [
    "SubjectKind",
    "ValidationIssue",
    "ValidationReport",
    "ValidationSeverity",
]
