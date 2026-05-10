"""Unit tests for `equality` ε-tolerance helpers (S1.3b).

Covers:

* `EPSILON` is exactly `1e-6` (load-bearing constant per ADR-020)
* `approx_equal_float`:
    - exact equality (incl. `0.0` vs `-0.0`)
    - sub-ε differences treated as equal
    - exact-ε boundary treated as not-equal (strict `<`)
    - super-ε differences treated as not-equal
    - `NaN` returns False for any pair
    - infinities behave consistently with subtraction semantics
    - grid-snap drift (`grid * round(x / grid)` round-trip) suppressed
* `approx_equal_qpointf`:
    - exact equality at origin and away from origin
    - sub-ε on x or y axis treated as equal
    - exact-ε squared-distance boundary treated as not-equal
    - diagonal sub-ε case (combined `dx`, `dy` whose `dx² + dy²` < ε²)
    - super-ε rejected (smallest grid step = 1.0 per `02 §5.2`)
    - `NaN` in either coordinate returns False

References
----------
* `decisions/ADR-020-dirty-tracking-semantics.md` §"Equality semantics"
* `specs/02_workspace_requirements.md` §5.2 (Grid units)
"""

from __future__ import annotations

import math

import pytest
from PySide6.QtCore import QPointF

from features.SystemModelingModule.model.equality import (
    EPSILON,
    approx_equal_float,
    approx_equal_qpointf,
)

# ---------------------------------------------------------------------- #
# Constant
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_epsilon_is_one_micron() -> None:
    """ε is the load-bearing 1e-6 constant per ADR-020."""
    assert EPSILON == 1e-6


# ---------------------------------------------------------------------- #
# `approx_equal_float`
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_float_equal_returns_true_for_exact_match() -> None:
    """Identical floats are equal."""
    assert approx_equal_float(1.0, 1.0) is True


@pytest.mark.unit
def test_float_equal_treats_positive_and_negative_zero_as_equal() -> None:
    """`0.0` and `-0.0` differ in sign bit but compare equal here."""
    assert approx_equal_float(0.0, -0.0) is True


@pytest.mark.unit
def test_float_equal_returns_true_for_sub_epsilon_difference() -> None:
    """A sub-ε difference is treated as a no-op."""
    assert approx_equal_float(1.0, 1.0 + 5e-7) is True
    assert approx_equal_float(1.0, 1.0 - 5e-7) is True


@pytest.mark.unit
def test_float_equal_returns_false_for_exactly_epsilon_difference() -> None:
    """The boundary is strict `<`; exact ε is not equal."""
    assert approx_equal_float(0.0, EPSILON) is False
    assert approx_equal_float(0.0, -EPSILON) is False


@pytest.mark.unit
def test_float_equal_returns_false_for_super_epsilon_difference() -> None:
    """Differences larger than ε are not equal."""
    assert approx_equal_float(1.0, 2.0) is False
    assert approx_equal_float(1.0, 1.0 + 1e-3) is False


@pytest.mark.unit
def test_float_equal_returns_false_for_any_nan_pair() -> None:
    """`NaN` is never equal — including `NaN` to itself."""
    nan = float("nan")
    assert approx_equal_float(nan, nan) is False
    assert approx_equal_float(nan, 0.0) is False
    assert approx_equal_float(0.0, nan) is False


@pytest.mark.unit
def test_float_equal_handles_infinities() -> None:
    """`inf - inf` is `NaN`, so two infinities are not equal here."""
    assert approx_equal_float(math.inf, math.inf) is False
    assert approx_equal_float(math.inf, -math.inf) is False
    assert approx_equal_float(math.inf, 0.0) is False


@pytest.mark.unit
def test_float_equal_suppresses_grid_snap_drift() -> None:
    """`grid * round(x / grid)` round-trip drift falls within ε.

    This is the motivating drag-snap case from ADR-020 §"Equality
    semantics": the snapped position is numerically distinct from the
    pre-snap position by a few ULPs, but the user perceives no move.
    """
    grid = 20.0
    raw = 100.000000_0001
    snapped = grid * round(raw / grid)
    # `snapped` is exactly `100.0`; `raw` differs by sub-ULP-style drift.
    assert approx_equal_float(snapped, raw) is True


# ---------------------------------------------------------------------- #
# `approx_equal_qpointf`
# ---------------------------------------------------------------------- #


@pytest.mark.unit
def test_qpointf_equal_returns_true_for_exact_origin() -> None:
    """Two origin points are equal."""
    assert approx_equal_qpointf(QPointF(0.0, 0.0), QPointF(0.0, 0.0)) is True


@pytest.mark.unit
def test_qpointf_equal_returns_true_for_exact_off_origin() -> None:
    """Two identical off-origin points are equal."""
    assert approx_equal_qpointf(QPointF(123.5, -42.0), QPointF(123.5, -42.0)) is True


@pytest.mark.unit
def test_qpointf_equal_returns_true_for_sub_epsilon_x_axis() -> None:
    """A sub-ε difference on x with exact y is treated as a no-op."""
    a = QPointF(1.0, 1.0)
    b = QPointF(1.0 + 5e-7, 1.0)
    assert approx_equal_qpointf(a, b) is True


@pytest.mark.unit
def test_qpointf_equal_returns_true_for_sub_epsilon_y_axis() -> None:
    """A sub-ε difference on y with exact x is treated as a no-op."""
    a = QPointF(1.0, 1.0)
    b = QPointF(1.0, 1.0 + 5e-7)
    assert approx_equal_qpointf(a, b) is True


@pytest.mark.unit
def test_qpointf_equal_returns_true_for_sub_epsilon_diagonal() -> None:
    """`dx² + dy² < ε²` even when each axis component is non-zero.

    Choosing `dx = dy = ε / 2` gives `dx² + dy² = ε² / 2 < ε²`.
    """
    a = QPointF(0.0, 0.0)
    b = QPointF(EPSILON / 2.0, EPSILON / 2.0)
    assert approx_equal_qpointf(a, b) is True


@pytest.mark.unit
def test_qpointf_equal_returns_false_at_exactly_epsilon_squared_distance() -> None:
    """The boundary is strict `<`; squared distance == ε² is not equal.

    A pure-x offset of exactly `EPSILON` gives `dx² + dy² = ε²`, which
    is not strictly less than `ε²`.
    """
    a = QPointF(0.0, 0.0)
    b = QPointF(EPSILON, 0.0)
    assert approx_equal_qpointf(a, b) is False


@pytest.mark.unit
def test_qpointf_equal_returns_false_at_smallest_grid_step() -> None:
    """A 1.0-unit move (smallest grid step per `02 §5.2`) is not a no-op."""
    a = QPointF(0.0, 0.0)
    b = QPointF(1.0, 0.0)
    assert approx_equal_qpointf(a, b) is False


@pytest.mark.unit
def test_qpointf_equal_returns_false_for_nan_in_any_coordinate() -> None:
    """`NaN` in either coordinate causes inequality."""
    nan = float("nan")
    origin = QPointF(0.0, 0.0)
    assert approx_equal_qpointf(QPointF(nan, 0.0), origin) is False
    assert approx_equal_qpointf(QPointF(0.0, nan), origin) is False
    assert approx_equal_qpointf(origin, QPointF(nan, nan)) is False


@pytest.mark.unit
def test_qpointf_equal_suppresses_grid_snap_drift() -> None:
    """Grid-snap round-trip drift on a 2D point is suppressed.

    Mirrors `test_float_equal_suppresses_grid_snap_drift` but in the
    `QPointF` form that mutation methods (S1.3c) will use directly.
    """
    grid = 20.0

    def snap(p: QPointF) -> QPointF:
        return QPointF(grid * round(p.x() / grid), grid * round(p.y() / grid))

    raw = QPointF(100.000000_0001, 80.000000_0002)
    snapped = snap(raw)
    assert approx_equal_qpointf(snapped, raw) is True
