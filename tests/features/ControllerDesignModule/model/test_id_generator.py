"""Unit tests for ControllerDesignModule ULID identity helpers (S2.A)."""

from __future__ import annotations

import pytest

from features.ControllerDesignModule.model import (
    CONTROLLER_ID_PREFIX,
    IO_INPUT_ID_PREFIX,
    IO_OUTPUT_ID_PREFIX,
    is_controller_id,
    is_io_input_id,
    is_io_output_id,
    new_controller_id,
    new_io_input_id,
    new_io_output_id,
)


@pytest.mark.unit
def test_new_controller_id_uses_ctrl_prefix() -> None:
    """A fresh controller id starts with `ctrl_`."""
    assert new_controller_id().startswith(CONTROLLER_ID_PREFIX)


@pytest.mark.unit
def test_new_io_input_id_uses_ioin_prefix() -> None:
    """A fresh I/O input id starts with `ioin_`."""
    assert new_io_input_id().startswith(IO_INPUT_ID_PREFIX)


@pytest.mark.unit
def test_new_io_output_id_uses_ioout_prefix() -> None:
    """A fresh I/O output id starts with `ioout_`."""
    assert new_io_output_id().startswith(IO_OUTPUT_ID_PREFIX)


@pytest.mark.unit
def test_generated_ids_are_unique_across_calls() -> None:
    """Successive generator calls never collide (1000-sample check)."""
    ids = {new_controller_id() for _ in range(1000)}
    assert len(ids) == 1000


@pytest.mark.unit
def test_predicates_accept_valid_ids() -> None:
    """The three `is_*_id` predicates each accept their own prefix's output."""
    assert is_controller_id(new_controller_id())
    assert is_io_input_id(new_io_input_id())
    assert is_io_output_id(new_io_output_id())


@pytest.mark.unit
def test_predicates_reject_cross_prefix_ids() -> None:
    """Each predicate rejects ids carrying any other prefix."""
    cid = new_controller_id()
    iid = new_io_input_id()
    oid = new_io_output_id()
    assert not is_controller_id(iid)
    assert not is_controller_id(oid)
    assert not is_io_input_id(cid)
    assert not is_io_input_id(oid)
    assert not is_io_output_id(cid)
    assert not is_io_output_id(iid)


@pytest.mark.unit
def test_predicates_reject_malformed_strings() -> None:
    """Empty, missing-body, or invalid-ULID strings are rejected."""
    assert not is_controller_id("")
    assert not is_controller_id("ctrl_")
    assert not is_controller_id("ctrl_not_a_valid_ulid_body_x")
    assert not is_controller_id("CTRL_01HV7N9G8K4QZ7R2M6P3A1B9C0")
    assert not is_controller_id("ctrl_01HV7N9G8K4QZ7R2M6P3A1B9C0_extra")
