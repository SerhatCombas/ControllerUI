"""Architecture test: feature module boundaries.

Verifies that feature modules do not import from each other directly.
Cross-feature communication must go through `shared/` or through the
application layer's orchestration (per `06_data_flow_and_architecture.md`
§4 and `08_codex_execution_rules.md` §6).

Specifically:
* `features/SystemModelingModule/**` must not import `features/ControllerDesignModule/**`
* `features/ControllerDesignModule/**` must not import `features/SystemModelingModule/**`
* feature modules may import from `shared/` and from `application/` is forbidden
* `shared/` must not import from `features/` or `application/`
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest


FEATURE_MODULES = {
    "system_modeling": Path("src/features/SystemModelingModule"),
    "controller_design": Path("src/features/ControllerDesignModule"),
}

SHARED_ROOT = Path("src/shared")
APPLICATION_ROOT = Path("src/application")


@pytest.mark.architecture
def test_system_modeling_does_not_import_controller_design() -> None:
    """SystemModelingModule must not import from ControllerDesignModule."""
    violations = _find_cross_module_imports(
        source_root=FEATURE_MODULES["system_modeling"],
        forbidden_prefix="features.ControllerDesignModule",
    )
    _assert_no_violations(violations, "SystemModelingModule → ControllerDesignModule")


@pytest.mark.architecture
def test_controller_design_does_not_import_system_modeling() -> None:
    """ControllerDesignModule must not import from SystemModelingModule.
    
    ControllerDesignModule consumes artifacts (ODEArtifact) produced by
    SystemModelingModule, but those artifacts are passed through method
    arguments or via shared types — not by importing SystemModelingModule
    directly.
    """
    violations = _find_cross_module_imports(
        source_root=FEATURE_MODULES["controller_design"],
        forbidden_prefix="features.SystemModelingModule",
    )
    _assert_no_violations(violations, "ControllerDesignModule → SystemModelingModule")


@pytest.mark.architecture
def test_shared_does_not_import_features() -> None:
    """`shared/` must not import any feature module.
    
    Shared layer is a foundation; features depend on shared, not the
    other way around (per `06 §2.3`).
    """
    if not SHARED_ROOT.exists():
        return
    
    violations: list[tuple[Path, int, str]] = []
    for py_file in SHARED_ROOT.rglob("*.py"):
        violations.extend(
            _find_imports_matching(py_file, prefix="features.")
        )
    
    _assert_no_violations(violations, "shared/ → features/")


@pytest.mark.architecture
def test_shared_does_not_import_application() -> None:
    """`shared/` must not import the application layer."""
    if not SHARED_ROOT.exists():
        return
    
    violations: list[tuple[Path, int, str]] = []
    for py_file in SHARED_ROOT.rglob("*.py"):
        violations.extend(
            _find_imports_matching(py_file, prefix="application.")
        )
    
    _assert_no_violations(violations, "shared/ → application/")


@pytest.mark.architecture
def test_features_do_not_import_application() -> None:
    """Feature modules must not import the application layer.
    
    The application layer composes features; features must remain
    independent of the shell so they can be tested in isolation.
    """
    violations: list[tuple[Path, int, str]] = []
    for source_root in FEATURE_MODULES.values():
        if not source_root.exists():
            continue
        for py_file in source_root.rglob("*.py"):
            violations.extend(
                _find_imports_matching(py_file, prefix="application.")
            )
    
    _assert_no_violations(violations, "features/ → application/")


def _find_cross_module_imports(
    source_root: Path,
    forbidden_prefix: str,
) -> list[tuple[Path, int, str]]:
    """Return violations under `source_root` that import `forbidden_prefix`."""
    if not source_root.exists():
        return []
    
    violations: list[tuple[Path, int, str]] = []
    for py_file in source_root.rglob("*.py"):
        violations.extend(_find_imports_matching(py_file, prefix=forbidden_prefix))
    return violations


def _find_imports_matching(
    py_file: Path,
    prefix: str,
) -> list[tuple[Path, int, str]]:
    """Return imports under `py_file` matching the given prefix."""
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
                if _module_matches(alias.name, prefix):
                    violations.append(
                        (py_file, node.lineno, f"import {alias.name}")
                    )
        elif isinstance(node, ast.ImportFrom):
            if node.module and _module_matches(node.module, prefix):
                violations.append(
                    (py_file, node.lineno, f"from {node.module} import ...")
                )
    return violations


def _module_matches(module_name: str, prefix: str) -> bool:
    """Return True if `module_name` is or descends from `prefix`."""
    if prefix.endswith("."):
        return module_name.startswith(prefix) or module_name == prefix.rstrip(".")
    return module_name == prefix or module_name.startswith(f"{prefix}.")


def _assert_no_violations(
    violations: list[tuple[Path, int, str]],
    direction: str,
) -> None:
    """Fail the test if any violations were found, with a clear report."""
    if violations:
        report_lines = [
            f"  {path}:{lineno}: {statement}"
            for path, lineno, statement in violations
        ]
        pytest.fail(
            f"Cross-module import violation ({direction}):\n"
            + "\n".join(report_lines)
        )
