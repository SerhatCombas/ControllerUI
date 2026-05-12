"""ULID identity generators for ControllerDesignModule artifacts.

Free functions (not a class-bound generator) because controller-side
artifacts have no display-counter equivalent — `display_name` is a
user-edited string, not an auto-incremented label. Counter-bound
identity stays in `SystemModelingModule` per ADR-002.

Phase 1 internal-ID prefixes:

* `ctrl_<ULID>` — controller specs (spec/03 §5.3)
* `ioin_<ULID>` — I/O selection inputs (spec/03 §6.2)
* `ioout_<ULID>` — I/O selection outputs (spec/03 §6.2)

These follow the prefix-then-ULID convention of `cmp_<ULID>` /
`con_<ULID>` from `SystemModelingModule`. The prefix is fixed; the
ULID body is lexicographically sortable and never reused per
ADR-002.

References:
----------
* `decisions/ADR-002-hybrid-ulid-identity-model.md`
* `specs/03_configuration_requirements.md` §5.3, §6.2
* `specs/09_coding_standards.md` §7.2.1
"""

from __future__ import annotations

from typing import Final

from ulid import ULID

# Internal-ID prefixes per spec/03 §5.3, §6.2.
CONTROLLER_ID_PREFIX: Final[str] = "ctrl_"
IO_INPUT_ID_PREFIX: Final[str] = "ioin_"
IO_OUTPUT_ID_PREFIX: Final[str] = "ioout_"


def new_controller_id() -> str:
    """Return a fresh ULID-suffixed controller id (`ctrl_<ULID>`)."""
    return f"{CONTROLLER_ID_PREFIX}{ULID()}"


def new_io_input_id() -> str:
    """Return a fresh ULID-suffixed I/O input id (`ioin_<ULID>`)."""
    return f"{IO_INPUT_ID_PREFIX}{ULID()}"


def new_io_output_id() -> str:
    """Return a fresh ULID-suffixed I/O output id (`ioout_<ULID>`)."""
    return f"{IO_OUTPUT_ID_PREFIX}{ULID()}"


def is_controller_id(candidate: str) -> bool:
    """Return True when `candidate` matches the `ctrl_<ULID>` shape."""
    return _has_prefix_and_ulid(candidate, CONTROLLER_ID_PREFIX)


def is_io_input_id(candidate: str) -> bool:
    """Return True when `candidate` matches the `ioin_<ULID>` shape."""
    return _has_prefix_and_ulid(candidate, IO_INPUT_ID_PREFIX)


def is_io_output_id(candidate: str) -> bool:
    """Return True when `candidate` matches the `ioout_<ULID>` shape."""
    return _has_prefix_and_ulid(candidate, IO_OUTPUT_ID_PREFIX)


def _has_prefix_and_ulid(candidate: str, prefix: str) -> bool:
    """Strict format check: `<prefix><26-char Crockford Base32 ULID>`."""
    if not candidate.startswith(prefix):
        return False
    body = candidate[len(prefix) :]
    if len(body) != 26:
        return False
    try:
        ULID.from_str(body)
    except (ValueError, TypeError):
        return False
    return True


__all__ = [
    "CONTROLLER_ID_PREFIX",
    "IO_INPUT_ID_PREFIX",
    "IO_OUTPUT_ID_PREFIX",
    "is_controller_id",
    "is_io_input_id",
    "is_io_output_id",
    "new_controller_id",
    "new_io_input_id",
    "new_io_output_id",
]
