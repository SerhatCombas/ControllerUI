"""Architecture test: no Qt UI imports inside data-layer subpackages.

Verifies the UI/data separation defined by ADR-003. The data layer
(`model/` subfolders, `shared/` non-UI packages) does not import
Qt UI modules. The command layer (`commands/`) sits between UI and
data per ADR-005; it must not import widget code but is allowed to
use `PySide6.QtGui.QUndoCommand` / `QUndoStack`, the canonical Qt
command-pattern primitives.

Per-layer rules:

Data layer (`model/`, `shared/components`, `shared/registry`,
`shared/graph`, `shared/types`, `shared/probes`, `shared/utils`):

* Allowed: `PySide6.QtCore` (for `QObject`, `Signal`, `QPointF`).
* Forbidden: `PySide6.QtWidgets`, `PySide6.QtGui`,
  `PySide6.QtMultimedia`, `PySide6.QtQuick`, `PySide6.QtQml`,
  `PySide6.QtCharts`, `PySide6.QtSvgWidgets`.

Command layer (`features/SystemModelingModule/commands/`):

* Allowed: `PySide6.QtCore`, `PySide6.QtGui` (per ADR-005 — the
  command stack mandates `QUndoCommand` which lives in
  `PySide6.QtGui` in Qt6+; commands stay widget-free by design).
* Forbidden: `PySide6.QtWidgets`, `PySide6.QtMultimedia`,
  `PySide6.QtQuick`, `PySide6.QtQml`, `PySide6.QtCharts`,
  `PySide6.QtSvgWidgets`.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

# Subdirectories that must remain UI-free (data layer per ADR-003).
DATA_LAYER_PATTERNS = [
    "src/features/SystemModelingModule/model",
    "src/features/ControllerDesignModule/model",
    "src/features/ControllerDesignModule/builders",
    "src/shared/components",
    "src/shared/registry",
    "src/shared/graph",
    "src/shared/types",
    "src/shared/probes",
    "src/shared/utils",
]

# Subdirectories that may use `PySide6.QtGui` (for QUndoCommand /
# QUndoStack per ADR-005) but must not import widget modules.
COMMAND_LAYER_PATTERNS = [
    "src/features/SystemModelingModule/commands",
]

# UI modules forbidden everywhere in the data layer.
FORBIDDEN_QT_MODULES_DATA_LAYER = (
    "PySide6.QtWidgets",
    "PySide6.QtGui",
    "PySide6.QtMultimedia",
    "PySide6.QtQuick",
    "PySide6.QtQml",
    "PySide6.QtCharts",
    "PySide6.QtSvgWidgets",
    "PyQt5.QtWidgets",
    "PyQt5.QtGui",
    "PyQt6.QtWidgets",
    "PyQt6.QtGui",
)

# UI modules forbidden in the command layer (QtGui is allowed there
# for QUndoCommand / QUndoStack per ADR-005, so it is NOT on this list).
FORBIDDEN_QT_MODULES_COMMAND_LAYER = (
    "PySide6.QtWidgets",
    "PySide6.QtMultimedia",
    "PySide6.QtQuick",
    "PySide6.QtQml",
    "PySide6.QtCharts",
    "PySide6.QtSvgWidgets",
    "PyQt5.QtWidgets",
    "PyQt6.QtWidgets",
)


@pytest.mark.architecture
def test_data_layer_packages_have_no_ui_imports() -> None:
    """Data-layer packages must not import Qt UI modules (per ADR-003)."""
    violations = _collect_violations(DATA_LAYER_PATTERNS, FORBIDDEN_QT_MODULES_DATA_LAYER)
    if violations:
        _fail(
            "Qt UI imports detected in data-layer packages "
            "(see ADR-003 Workspace UI/Data Separation)",
            violations,
        )


@pytest.mark.architecture
def test_command_layer_does_not_import_widget_modules() -> None:
    """Command-layer packages must not import Qt widget modules.

    Per ADR-005 the command layer uses `QUndoCommand` / `QUndoStack`
    from `PySide6.QtGui` — the canonical Qt command primitives, not
    widget code. Importing actual widget modules (`QtWidgets`,
    `QtCharts`, etc.) into commands would invert the layering: UI
    constructs commands and pushes them, never the other way
    around.
    """
    violations = _collect_violations(COMMAND_LAYER_PATTERNS, FORBIDDEN_QT_MODULES_COMMAND_LAYER)
    if violations:
        _fail(
            "Qt widget imports detected in command-layer packages "
            "(see ADR-005 Command Stack with QUndoStack — commands "
            "may use QtGui's QUndoCommand/QUndoStack but not widget modules)",
            violations,
        )


def _collect_violations(
    patterns: list[str],
    forbidden: tuple[str, ...],
) -> list[tuple[Path, int, str]]:
    """Scan the given patterns and return forbidden-import violations."""
    violations: list[tuple[Path, int, str]] = []
    for pattern in patterns:
        root = Path(pattern)
        if not root.exists():
            continue
        for py_file in root.rglob("*.py"):
            violations.extend(_find_qt_ui_imports(py_file, forbidden))
    return violations


def _find_qt_ui_imports(
    py_file: Path,
    forbidden: tuple[str, ...],
) -> list[tuple[Path, int, str]]:
    """Return forbidden Qt imports detected in the given file."""
    try:
        source = py_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []

    try:
        tree = ast.parse(source, filename=str(py_file))
    except SyntaxError:
        return []

    violations: list[tuple[Path, int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _is_forbidden_qt_module(alias.name, forbidden):
                    violations.append((py_file, node.lineno, f"import {alias.name}"))
        elif (
            isinstance(node, ast.ImportFrom)
            and node.module
            and _is_forbidden_qt_module(node.module, forbidden)
        ):
            violations.append((py_file, node.lineno, f"from {node.module} import ..."))
    return violations


def _is_forbidden_qt_module(module_name: str, forbidden: tuple[str, ...]) -> bool:
    """Return True if the module is in the forbidden list."""
    return any(module_name == entry or module_name.startswith(f"{entry}.") for entry in forbidden)


def _fail(prefix: str, violations: list[tuple[Path, int, str]]) -> None:
    """Format and raise a pytest failure with the violations list."""
    report_lines = [f"  {path}:{lineno}: {statement}" for path, lineno, statement in violations]
    pytest.fail(prefix + ":\n" + "\n".join(report_lines))
