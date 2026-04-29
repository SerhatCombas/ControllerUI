"""Architecture test: logging event name consistency.

Verifies that every value used as `extra["event"]` in the codebase
is declared as a constant in `shared/utils/logging_events.py`.

Per `10_logging_conventions.md` §8 and `12_ci_cd_pipeline.md` §6.5.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest


SOURCE_ROOT = Path("src")
EVENTS_FILE = Path("src/shared/utils/logging_events.py")

# Event names follow `<category>.<specific>` (lowercase, dots, underscores).
EVENT_PATTERN = re.compile(r"^[a-z_]+\.[a-z0-9_]+$")


@pytest.mark.architecture
def test_logging_events_module_exists() -> None:
    """The `shared/utils/logging_events.py` module must exist.
    
    This file is the single source of truth for `extra["event"]` values.
    """
    if not EVENTS_FILE.exists():
        pytest.skip(
            f"Events module not yet present: {EVENTS_FILE}. "
            "Will be enforced once Stage S0 logging scaffolding is in place."
        )


@pytest.mark.architecture
def test_event_values_match_constants() -> None:
    """Every literal `extra={"event": "..."}` value is declared in events module."""
    if not EVENTS_FILE.exists():
        pytest.skip("Events module not yet present.")
    if not SOURCE_ROOT.exists():
        pytest.skip(f"Source root not found: {SOURCE_ROOT}.")
    
    declared = _extract_declared_events(EVENTS_FILE)
    used = _extract_used_events(SOURCE_ROOT)
    
    missing = used - declared
    if missing:
        pytest.fail(
            "Event values used in extra={'event': ...} but not declared "
            "as constants in `shared/utils/logging_events.py` "
            "(see `10 §8`):\n"
            + "\n".join(f"  {name}" for name in sorted(missing))
        )


@pytest.mark.architecture
def test_declared_events_match_naming_convention() -> None:
    """All declared event constants must follow `<category>.<specific>` format."""
    if not EVENTS_FILE.exists():
        pytest.skip("Events module not yet present.")
    
    declared = _extract_declared_events(EVENTS_FILE)
    invalid = [name for name in declared if not EVENT_PATTERN.match(name)]
    
    if invalid:
        pytest.fail(
            "Event constants violate naming convention "
            "(see `10 §8`, format `<category>.<specific>`):\n"
            + "\n".join(f"  {name}" for name in sorted(invalid))
        )


def _extract_declared_events(events_file: Path) -> set[str]:
    """Extract string values assigned to module-level constants."""
    try:
        source = events_file.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(events_file))
    except (OSError, UnicodeDecodeError, SyntaxError):
        return set()
    
    declared: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if (
                isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)
            ):
                declared.add(node.value.value)
    return declared


def _extract_used_events(source_root: Path) -> set[str]:
    """Find string literals used as the `event` key inside `extra={}`."""
    used: set[str] = set()
    for py_file in source_root.rglob("*.py"):
        if py_file.resolve() == EVENTS_FILE.resolve():
            continue
        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(py_file))
        except (OSError, UnicodeDecodeError, SyntaxError):
            continue
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Dict):
                # Looking for {"event": "<literal>", ...}
                for key, value in zip(node.keys, node.values, strict=False):
                    if (
                        isinstance(key, ast.Constant)
                        and key.value == "event"
                        and isinstance(value, ast.Constant)
                        and isinstance(value.value, str)
                    ):
                        used.add(value.value)
    return used
