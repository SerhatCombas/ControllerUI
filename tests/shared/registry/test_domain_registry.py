"""Unit tests for `shared.registry.DomainRegistry` (S1.B.1b).

Covers per `02 §13.2`:

* construction preserves insertion order
* duplicate domain at construction raises `ValueError`
* `supported()` returns the registered tuple
* `is_supported()` accepts arbitrary strings (safe boolean)
* `are_compatible()` Phase 1: same-domain only
"""

from __future__ import annotations

import pytest

from shared.registry import DomainRegistry


@pytest.mark.unit
def test_construction_preserves_insertion_order() -> None:
    """`supported()` reflects insertion order."""
    registry = DomainRegistry(["electrical_analog", "mechanical_translational"])

    assert registry.supported() == ("electrical_analog", "mechanical_translational")


@pytest.mark.unit
def test_duplicate_domain_raises_valueerror() -> None:
    """A duplicate domain at construction fails fast."""
    with pytest.raises(ValueError, match="duplicate domain id"):
        DomainRegistry(["electrical_analog", "electrical_analog"])


@pytest.mark.unit
def test_is_supported_accepts_arbitrary_string_input() -> None:
    """`is_supported` returns False for unknown strings (no TypeError)."""
    registry = DomainRegistry(["electrical_analog"])

    assert registry.is_supported("electrical_analog") is True
    assert registry.is_supported("hydraulic") is False
    assert registry.is_supported("") is False


@pytest.mark.unit
def test_are_compatible_same_domain_returns_true() -> None:
    """Phase 1 rule: same-domain ports are compatible."""
    registry = DomainRegistry(["electrical_analog", "mechanical_translational"])

    assert registry.are_compatible("electrical_analog", "electrical_analog") is True
    assert registry.are_compatible("mechanical_translational", "mechanical_translational") is True


@pytest.mark.unit
def test_are_compatible_different_domain_returns_false() -> None:
    """Phase 1 rule per `02 §13.2`: cross-domain pairs are incompatible."""
    registry = DomainRegistry(["electrical_analog", "mechanical_translational"])

    assert registry.are_compatible("electrical_analog", "mechanical_translational") is False
    assert registry.are_compatible("mechanical_translational", "electrical_analog") is False
