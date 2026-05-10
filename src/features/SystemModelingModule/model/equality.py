"""ε-tolerance equality helpers for `WorkspaceModel` no-op suppression.

These pure functions implement the equality rules defined in ADR-020
§"Equality semantics" for use by mutation methods (S1.3c) when
deciding whether a call is a no-op and should suppress the dirty
transition and the corresponding fine-grained signal.

Two helpers are provided:

* `approx_equal_float(a, b)` — absolute-difference tolerance, used for
  rotation (per ADR-018, rotation is `float`) and for individual float
  parameter values (S1.6 dispatch).
* `approx_equal_qpointf(a, b)` — squared-distance tolerance, used for
  position comparisons. Squared distance avoids a `sqrt()` call and
  gives the same boundary as a Euclidean tolerance.

Both helpers use a strict less-than: `< ε` (or `< ε²` for the squared
form). A pair of values whose difference is *exactly* ε is **not**
considered equal — this matches ADR-020's literal wording and makes
the boundary symmetric and well-defined.

`NaN` propagates through subtraction and comparison so any pair
involving `NaN` returns `False`. This is intentional: `NaN`-valued
positions or parameters are invalid state, and treating them as
distinct prevents accidental no-op suppression that would mask the
invalid value.

This module is part of the data layer; it does not import any Qt UI
classes. `QPointF` from `PySide6.QtCore` is permitted because it is
the canonical scene-coordinate type used by the data layer (see
ADR-018 signal payload table).

References:
----------
* `decisions/ADR-020-dirty-tracking-semantics.md` §"Equality semantics"
* `decisions/ADR-018-signal-payload-contracts.md` (`QPointF` rationale)
* `specs/02_workspace_requirements.md` §5.2 (Grid units; smallest grid
  step is 1.0 logical unit, well above ε=1e-6)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtCore import QPointF

# Tolerance constant in scene units (one micron). Per ADR-020:
#
# * one micron is well below any user-perceivable difference
# * it is well above any plausible accumulation error from grid-snap
#   rounding in 64-bit float arithmetic
# * it is small enough that two intentionally-distinct positions
#   (smallest grid step ≥ 1.0 per `02 §5.2`) are never collapsed
#
# Changing this value is a backwards-incompatible behavior change;
# treat it as load-bearing and amend ADR-020 if it ever needs to move.
EPSILON: float = 1e-6


def approx_equal_float(a: float, b: float) -> bool:
    """Return True when two floats are within ε=1e-6 absolute difference.

    The comparison is strict: `abs(a - b) < EPSILON`. A pair of values
    whose absolute difference is exactly `EPSILON` returns `False`.

    `NaN` returns `False` for any pair involving a `NaN` because
    `NaN < EPSILON` is `False`.

    Args:
        a: First scalar.
        b: Second scalar.

    Returns:
        True when `abs(a - b) < EPSILON`, False otherwise (including
        when either operand is `NaN`).

    See Also:
        ADR-020 §"Equality semantics".
    """
    return abs(a - b) < EPSILON


def approx_equal_qpointf(a: QPointF, b: QPointF) -> bool:
    """Return True when two `QPointF` values are within ε=1e-6 distance.

    Uses squared-distance tolerance: `dx² + dy² < EPSILON²`. This is
    equivalent to `sqrt(dx² + dy²) < EPSILON` but avoids the square
    root and is therefore both faster and free of `sqrt`-related
    rounding error.

    The comparison is strict: a pair of points exactly `EPSILON`
    apart returns `False` (because `EPSILON² < EPSILON²` is `False`).

    `NaN` in any coordinate returns `False` because `NaN < EPSILON²`
    is `False`.

    Args:
        a: First point in scene coordinates.
        b: Second point in scene coordinates.

    Returns:
        True when the Euclidean distance between `a` and `b` is
        strictly less than `EPSILON`, False otherwise.

    See Also:
        ADR-020 §"Equality semantics" (`QPointF` row).
    """
    dx = a.x() - b.x()
    dy = a.y() - b.y()
    return (dx * dx + dy * dy) < (EPSILON * EPSILON)


__all__ = [
    "EPSILON",
    "approx_equal_float",
    "approx_equal_qpointf",
]
