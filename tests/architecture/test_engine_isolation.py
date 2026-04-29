"""Architecture test: Phase 1 engine isolation (ADR-001).

Verifies that `shared.engine` cannot be imported during Phase 1, and
that no Phase 1 source files attempt to import it.

Per ADR-001 (`decisions/ADR-001-phase1-engine-isolation.md`) and
`08_codex_execution_rules.md` §6.1.
"""

from __future__ import annotations

import ast
import importlib
import importlib.util
from pathlib import Path

import pytest


# Roots scanned for forbidden imports during Phase 1.
PHASE_1_SOURCE_ROOTS = [
    Path("src/application"),
    Path("src/features/SystemModelingModule"),
    Path("src/features/ControllerDesignModule"),
    Path("src/shared/components"),
    Path("src/shared/registry"),
    Path("src/shared/graph"),
    Path("src/shared/types"),
    Path("src/shared/probes"),
    Path("src/shared/utils"),
]

# Forbidden import patterns (Phase 1 may not import these).
FORBIDDEN_PATTERNS = (
    "shared.engine",
    "src.shared.engine",
)


@pytest.mark.architecture
def test_shared_engine_raises_import_error_in_phase_1() -> None:
    """`shared.engine` must raise ImportError when imported during Phase 1.
    
    The `shared/engine/__init__.py` is configured to raise ImportError
    until Stage S4 entry, when the barrier is removed and the package
    is replaced with normal exports.
    """
    spec = importlib.util.find_spec("shared.engine")
    if spec is None:
        # Package does not exist yet (very early development); that
        # also satisfies isolation.
        return
    
    with pytest.raises(ImportError) as exc_info:
        importlib.import_module("shared.engine")
    
    assert "Phase 1" in str(exc_info.value), (
        "ImportError message must reference Phase 1 to make the "
        "isolation rationale clear (see ADR-001)."
    )


@pytest.mark.architecture
def test_no_phase_1_source_imports_shared_engine() -> None:
    """No Phase 1 source file may import `shared.engine` or any submodule.
    
    Walks the Phase 1 source tree, parses each .py file as AST, and
    asserts that no `import` statement targets `shared.engine` or a
    submodule.
    """
    violations: list[tuple[Path, int, str]] = []
    
    for root in PHASE_1_SOURCE_ROOTS:
        if not root.exists():
            continue
        for py_file in root.rglob("*.py"):
            violations.extend(_find_engine_imports(py_file))
    
    if violations:
        report_lines = [
            f"  {path}:{lineno}: {statement}"
            for path, lineno, statement in violations
        ]
        pytest.fail(
            "shared.engine imports detected in Phase 1 source files "
            "(see ADR-001):\n" + "\n".join(report_lines)
        )


def _find_engine_imports(py_file: Path) -> list[tuple[Path, int, str]]:
    """Return a list of (path, lineno, statement) tuples for forbidden imports."""
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
                if _is_forbidden(alias.name):
                    violations.append(
                        (py_file, node.lineno, f"import {alias.name}")
                    )
        elif isinstance(node, ast.ImportFrom):
            if node.module and _is_forbidden(node.module):
                violations.append(
                    (py_file, node.lineno, f"from {node.module} import ...")
                )
    
    return violations


def _is_forbidden(module_name: str) -> bool:
    """Return True if the dotted module name is a forbidden Phase 1 import."""
    return any(
        module_name == pattern or module_name.startswith(f"{pattern}.")
        for pattern in FORBIDDEN_PATTERNS
    )
