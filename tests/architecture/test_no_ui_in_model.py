"""Architecture test: no Qt UI imports inside model/ subpackages.

Verifies that data-layer code (`model/` subfolders and `shared/`
non-UI packages) does not import Qt UI modules. This enforces the
UI/data separation defined by ADR-003.

Allowed Qt imports inside model/:
* PySide6.QtCore — for QObject, Signal, QPointF, QObject

Forbidden Qt imports inside model/:
* PySide6.QtWidgets
* PySide6.QtGui
* PySide6.QtMultimedia
* PySide6.QtQuick
* PySide6.QtQml
* PySide6.QtCharts
* PySide6.QtSvgWidgets
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest


# Subdirectories that must remain UI-free.
DATA_LAYER_PATTERNS = [
    "src/features/SystemModelingModule/model",
    "src/features/SystemModelingModule/commands",
    "src/features/ControllerDesignModule/model",
    "src/features/ControllerDesignModule/builders",
    "src/shared/components",
    "src/shared/registry",
    "src/shared/graph",
    "src/shared/types",
    "src/shared/probes",
    "src/shared/utils",
]

FORBIDDEN_QT_MODULES = (
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


@pytest.mark.architecture
def test_data_layer_packages_have_no_ui_imports() -> None:
    """Data-layer packages must not import Qt UI modules (per ADR-003)."""
    violations: list[tuple[Path, int, str]] = []
    
    for pattern in DATA_LAYER_PATTERNS:
        root = Path(pattern)
        if not root.exists():
            continue
        for py_file in root.rglob("*.py"):
            violations.extend(_find_qt_ui_imports(py_file))
    
    if violations:
        report_lines = [
            f"  {path}:{lineno}: {statement}"
            for path, lineno, statement in violations
        ]
        pytest.fail(
            "Qt UI imports detected in data-layer packages "
            "(see ADR-003 Workspace UI/Data Separation):\n"
            + "\n".join(report_lines)
        )


def _find_qt_ui_imports(py_file: Path) -> list[tuple[Path, int, str]]:
    """Return Qt UI imports detected in the given file."""
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
                if _is_forbidden_qt_module(alias.name):
                    violations.append(
                        (py_file, node.lineno, f"import {alias.name}")
                    )
        elif isinstance(node, ast.ImportFrom):
            if node.module and _is_forbidden_qt_module(node.module):
                violations.append(
                    (py_file, node.lineno, f"from {node.module} import ...")
                )
    return violations


def _is_forbidden_qt_module(module_name: str) -> bool:
    """Return True if the module is a forbidden Qt UI module."""
    return any(
        module_name == forbidden or module_name.startswith(f"{forbidden}.")
        for forbidden in FORBIDDEN_QT_MODULES
    )
