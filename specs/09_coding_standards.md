# 09_coding_standards.md

## 1. Purpose

This document defines mandatory coding standards for the Engineering System Designer project.

It exists to ensure that:

* code style remains consistent across all stages and contributors (human or AI agent)
* style decisions are encoded as tooling configuration, not informal habits
* AI coding agents have a single authoritative reference for naming, formatting, type hints, and structural conventions
* code review can focus on architecture and correctness rather than formatting debates

This document is **not** a feature specification. It is a code-quality contract that complements `08_codex_execution_rules.md`.

The agent must treat coding standards as enforceable rules, not as preferences.

---

## 2. Scope

### 2.1 In Scope

* Python language conventions (3.11+)
* Code formatting (line length, indentation, quotes)
* Type hint policy
* Docstring format
* Import ordering
* Naming conventions
* PySide6-specific conventions (signals, slots, QObject hierarchy)
* File and module structure
* Test code style
* Linting and formatting tool configuration

### 2.2 Out of Scope

* Architecture decisions (see `06_data_flow_and_architecture.md`)
* Module ownership (see `06` and ADR-003, ADR-004, ADR-006)
* Logging conventions (see `10_logging_conventions.md`)
* Error code conventions (see `11_error_code_catalog.md`)
* CI pipeline (see `12_ci_cd_pipeline.md`)

---

## 3. Python Version

The project targets **Python 3.11** as the minimum supported version.

Required because:

* `match` statements are used freely
* improved error messages help diagnostics
* `tomllib` is in the standard library (used for `pyproject.toml` parsing)
* better type variance and `Self` type are stable

Forbidden:

* Python 3.10 or earlier syntax-only features
* Python 3.13+ features that break 3.11 compatibility (e.g., PEP 695 `type Alias = X` syntax is forbidden until 3.11 is dropped)

The Python version is enforced in `pyproject.toml`:

```toml
[project]
requires-python = ">=3.11,<3.13"
```

---

## 4. Code Formatting

### 4.1 Line Length

Maximum line length: **100 characters**.

100 is the modern compromise between 80 (too tight for type-hinted Python) and 120 (hurts side-by-side review).

Long expressions must be broken using:

* parenthesized continuation (preferred)
* trailing commas in multi-line collections
* line continuation with `\` only as a last resort

### 4.2 Indentation

* 4 spaces per indent level
* never tabs
* continuation lines align with opening delimiter or use 4-space hanging indent

### 4.3 Quotes

* double quotes `"` for strings (default)
* single quotes `'` allowed only when the string contains double quotes
* triple double quotes `"""` for docstrings (always)
* raw strings `r"..."` for regex patterns and Windows paths in tests

### 4.4 Trailing Commas

Multi-line collections must use trailing commas:

```python
items = [
    "first",
    "second",
    "third",
]
```

This produces clean diffs when items are added or removed.

### 4.5 Blank Lines

* two blank lines between top-level functions and classes
* one blank line between methods inside a class
* one blank line to group logically related blocks within a function (sparingly)
* no blank lines at the start or end of a function body

### 4.6 Formatter

The project uses **Ruff** as the canonical formatter and linter.

Ruff replaces:

* Black (formatting)
* isort (import sorting)
* flake8 (linting)
* pyupgrade (modernization)
* pydocstyle (docstring linting)

Ruff configuration lives in `pyproject.toml` (see §13.1).

Forbidden:

* running Black separately from Ruff
* committing code that has not been formatted with `ruff format`
* disabling individual Ruff rules without justification in a code comment

---

## 5. Type Hints

### 5.1 Mandatory Type Hints

Type hints are **mandatory** for:

* all function and method signatures (parameters and return types)
* all module-level constants
* all class attributes (using `: type` declaration)
* all dataclass field declarations

Type hints are **optional** but recommended for:

* local variables when the type is non-obvious from the right-hand side
* lambda parameters (only if the lambda is non-trivial)

### 5.2 Type Hint Style

Use modern Python 3.11 syntax:

```python
# Preferred:
def add_component(
    self,
    definition_id: str,
    position: QPointF,
    parameters: dict[str, Any] | None = None,
) -> str:
    ...

# Allowed but not preferred:
from typing import Optional, Dict
def add_component(
    self,
    definition_id: str,
    position: QPointF,
    parameters: Optional[Dict[str, Any]] = None,
) -> str:
    ...
```

Specifically:

* `list[T]`, `dict[K, V]`, `tuple[T, ...]`, `set[T]` instead of `List`, `Dict`, `Tuple`, `Set`
* `T | None` instead of `Optional[T]`
* `T1 | T2` instead of `Union[T1, T2]`
* `Callable[[Args], Ret]` from `collections.abc`, not `typing`

### 5.3 Forward References

When a class references itself or a class defined later in the same file:

```python
from __future__ import annotations  # at the top of the file

class WorkspaceModel(QObject):
    def merge(self, other: WorkspaceModel) -> WorkspaceModel:
        ...
```

`from __future__ import annotations` should be the first import in every module.

### 5.4 Generic Types

Use `TypeVar` and `Generic` for genuinely generic code. Avoid `Any` where a more specific type is feasible.

```python
from typing import TypeVar, Generic

T = TypeVar("T")

class Registry(Generic[T]):
    def get(self, key: str) -> T | None:
        ...
    
    def register(self, key: str, value: T) -> None:
        ...
```

### 5.5 Type Checking Tool

The project uses **mypy** in strict mode for type checking.

mypy configuration lives in `pyproject.toml` (see §13.2).

CI must run mypy on every push (see `12_ci_cd_pipeline.md`).

Forbidden:

* committing code with mypy errors unless suppressed with explicit `# type: ignore[error-code]` and a comment explaining why
* using `Any` as a way to bypass mypy
* using `# type: ignore` without an error code

### 5.6 Pydantic and Dataclasses

For data structures:

* use `@dataclass` for simple POPO data
* use `@dataclass(frozen=True)` for immutable artifacts (e.g., `ODEArtifact`, `SimulationResultArtifact`)
* use Pydantic v2 only when validation, JSON serialization, or schema generation is needed

```python
from dataclasses import dataclass, field

@dataclass(frozen=True)
class ComponentInstance:
    id: str
    display_id: str
    definition_id: str
    domain: str
    position: tuple[float, float]
    rotation: int = 0
    parameters: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
```

---

## 6. Docstrings

### 6.1 Mandatory Docstrings

Docstrings are **mandatory** for:

* every public module
* every public class
* every public function or method
* every public dataclass field with non-obvious semantics

Docstrings are **optional** for:

* private functions (`_underscore_prefix`) when the name and signature are self-explanatory
* one-line lambda or trivial helper functions
* test functions (test names should be descriptive enough)

### 6.2 Docstring Format

The project uses **Google-style** docstrings:

```python
def add_component(
    self,
    definition_id: str,
    position: QPointF,
    parameters: dict[str, Any] | None = None,
) -> str:
    """Add a component instance to the workspace model.
    
    Resolves the component definition through the registry, generates
    a fresh internal ULID and display ID, and applies default parameters
    from the definition unless overridden.
    
    Args:
        definition_id: Namespace-style identifier of the component
            definition to instantiate (e.g., 
            "electrical.analog.components.resistor").
        position: Position in scene coordinates where the component
            should be placed.
        parameters: Optional parameter override mapping. Keys must
            match parameter IDs from the component definition. If
            None, definition defaults are used.
    
    Returns:
        The internal ULID-based component ID of the newly created
        instance (e.g., "cmp_01HV7N9G8K4QZ7R2M6P3A1B9C0").
    
    Raises:
        ComponentDefinitionNotFoundError: If `definition_id` is not
            registered in `ComponentRegistry`.
        InvalidParameterError: If `parameters` contains keys not
            declared in the component definition or values that fail
            schema validation.
    
    See Also:
        `02_workspace_requirements.md` §10 for placement rules.
        `06_data_flow_and_architecture.md` §7.1 for placement flow.
    """
    ...
```

Required sections (in order):

1. **Summary line** — one-line imperative description, ending with a period
2. **Extended description** — optional, separated from summary by blank line
3. **Args** — every parameter except `self` and `cls`
4. **Returns** — except for `__init__` and functions returning `None`
5. **Raises** — every exception type explicitly raised by the function
6. **See Also** — optional, cross-references to spec sections or other code

### 6.3 Module Docstrings

Every module must start with a module-level docstring:

```python
"""WorkspaceModel: source of truth for the visual modeling canvas.

This module owns the authoritative state of components, connections,
and validation status. UI components subscribe to its signals and
render derived visuals; they do not store independent state.

See `02_workspace_requirements.md` §3 for the source-of-truth rules
and ADR-003 for the UI/data separation decision.
"""
```

### 6.4 Class Docstrings

Class docstrings describe what the class is responsible for, including signal API for QObject classes.

### 6.5 Forbidden Docstring Practices

* one-word docstrings (`"""Init."""`, `"""Get."""`)
* docstrings that just repeat the function name (`"""Add component."""` for `add_component`)
* misleading docstrings (description does not match implementation)
* docstrings with `TODO` or `FIXME` markers without an issue link
* docstrings claiming behavior that the function does not implement

---

## 7. Naming Conventions

### 7.1 General Naming

| Element | Convention | Example |
|---|---|---|
| modules | `lower_snake_case` | `workspace_model.py` |
| packages | `lower_snake_case` | `system_modeling_module/` |
| classes | `UpperCamelCase` | `WorkspaceModel` |
| functions | `lower_snake_case` | `add_component` |
| methods | `lower_snake_case` | `to_dict` |
| variables | `lower_snake_case` | `component_id` |
| constants | `UPPER_SNAKE_CASE` | `DEFAULT_GRID_SIZE` |
| type variables | `UpperCamelCase` short | `T`, `ComponentT` |
| enums (values) | `UPPER_SNAKE_CASE` | `ValidationSeverity.ERROR` |
| private | `_leading_underscore` | `_internal_state` |
| name-mangled | `__double_leading` (rare) | `__truly_private` |

### 7.2 Project-Specific Naming

#### 7.2.1 Component IDs

* internal ID: ULID with prefix → `cmp_01HV7N9G8K4QZ7R2M6P3A1B9C0`
* display ID: lowercase + counter → `resistor_3`
* definition ID: dotted namespace → `electrical.analog.components.resistor`
* custom label: free-form Unicode (user input)

(See `01_library_requirements.md` §6.2.1 for the full identity model.)

#### 7.2.2 Signals (Exception to snake_case)

PySide6 Qt signals use `lowerCamelCase` (matching Qt's own convention):

```python
class WorkspaceModel(QObject):
    componentAdded = Signal(str)
    componentRemoved = Signal(str)
    validationChanged = Signal(object)
    dirtyChanged = Signal(bool)
    modelReset = Signal()
```

This is the **single exception** to snake_case in this project. Rationale: consistency with Qt API (`textChanged`, `clicked`, `valueChanged`).

Ruff rule N802 is suppressed only for Signal declarations (see §13.1).

#### 7.2.3 Slots

Slot methods that handle signals use the prefix `on_` followed by the signal name in snake_case:

```python
class BlockDiagramWorkspaceScene(QGraphicsScene):
    def on_component_added(self, component_id: str) -> None:
        ...
    
    def on_validation_changed(self, report: ValidationReport) -> None:
        ...
```

Connection wiring:

```python
self.workspace_model.componentAdded.connect(self.on_component_added)
```

#### 7.2.4 Commands

`QUndoCommand` subclasses end with `Command`:

* `AddComponentCommand`
* `MoveComponentCommand`
* `DeleteConnectionCommand`

Command files match: `add_component_command.py`.

#### 7.2.5 Artifacts

Phase 2 artifact classes end with `Artifact`:

* `ODEArtifact`
* `SimulationResultArtifact`
* `StabilityAnalysisArtifact`

#### 7.2.6 Adapters

Backend adapters end with `Adapter`:

* `CasadiSolverAdapter`
* `ScipySolverAdapter`
* `PIDRuntimeAdapter`

### 7.3 Forbidden Naming

* abbreviations that are not domain-specific (`tmp`, `val`, `obj`, `mgr`)
* single-letter variables outside of `i`, `j`, `k` for loop counters or mathematical contexts (`x`, `y`, `t`, `dt`, `u`)
* Hungarian notation (`strName`, `intCount`)
* names that shadow Python builtins (`list`, `dict`, `id`, `type`, `filter`, `map`)
* names ending with numeric suffixes for unrelated purposes (`process2`, `handler3`)

For component instance identifiers, `id` shadowing is acceptable in dataclass fields because the field name `id` is part of the public schema:

```python
@dataclass
class ComponentInstance:
    id: str  # Acceptable: schema-mandated field name
    display_id: str
```

---

## 8. Imports

### 8.1 Import Ordering

Imports are grouped in this order, with one blank line between groups:

1. `from __future__ import annotations` (always first if present)
2. Standard library imports
3. Third-party imports (PySide6, CasADi, NumPy, etc.)
4. First-party imports (`shared`, `features`, `application`)
5. Local relative imports (`.sibling_module`)

Within each group, imports are alphabetically sorted by module path.

```python
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QGraphicsScene

from shared.components import ComponentDefinition
from shared.graph import SystemGraph
from shared.types import DomainId

from .component_instance import ComponentInstance
from .id_generator import WorkspaceIdGenerator
```

Ruff enforces this order automatically.

### 8.2 Forbidden Import Patterns

* `from module import *` (star imports)
* mixing relative and absolute imports for the same package
* circular imports (resolve by extracting shared dependencies)
* `import shared.engine` or any submodule during Phase 1 (enforced by `shared/engine/__init__.py` ImportError, see ADR-001)
* importing UI modules (`PySide6.QtWidgets`, `PySide6.QtGui`) inside `model/` subfolders or `shared/` packages
* importing from `application/` inside `features/` or `shared/`
* importing from `features/<other_module>/` inside `features/<this_module>/` (cross-feature imports go through `shared/`)

### 8.3 Lazy Imports

Lazy imports (inside functions) are allowed only for:

* breaking circular dependencies that cannot be resolved structurally
* importing optional dependencies
* importing heavy modules that are needed only in rare code paths

Every lazy import must have a comment explaining why it is lazy:

```python
def linearize(self) -> StateSpaceMatrices:
    # Lazy import: CasADi is a heavyweight dependency loaded only when
    # linearization is actually requested.
    import casadi as ca
    ...
```

---

## 9. Project Structure Conventions

### 9.1 File Layout

* one class per file when the class is non-trivial (>50 lines)
* small dataclasses, enums, and protocol classes may be grouped in a single file by topic
* `__init__.py` files explicitly declare the public API via `__all__`

```python
# features/SystemModelingModule/model/__init__.py
"""Data layer for SystemModelingModule.

Re-exports the public API of the model subpackage. UI code imports
from this package, not from individual files.
"""

from .component_instance import ComponentInstance
from .connection import Connection
from .id_generator import WorkspaceIdGenerator
from .selection_model import SelectionModel
from .validation_report import ValidationReport, ValidationSeverity
from .workspace_model import WorkspaceModel

__all__ = [
    "ComponentInstance",
    "Connection",
    "SelectionModel",
    "ValidationReport",
    "ValidationSeverity",
    "WorkspaceIdGenerator",
    "WorkspaceModel",
]
```

### 9.2 File Length

* preferred: under 400 lines per file
* hard limit: 800 lines per file
* if a file exceeds 400 lines, consider whether it should be split

This is a soft guideline, not a strict rule. Some files (large registry definitions, full migration scripts) legitimately exceed 400 lines.

### 9.3 Function Length

* preferred: under 40 lines per function
* hard limit: 80 lines per function
* prefer extraction of helpers over deep nesting

### 9.4 Class Length

* preferred: under 300 lines per class
* hard limit: 500 lines per class
* if a class exceeds 300 lines, consider whether responsibilities can be split

---

## 10. PySide6 Conventions

### 10.1 QObject Inheritance

Classes that emit signals must inherit from `QObject`:

```python
from PySide6.QtCore import QObject, Signal

class WorkspaceModel(QObject):
    componentAdded = Signal(str)
    
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._components: dict[str, ComponentInstance] = {}
```

The `parent` parameter in `__init__` is mandatory (defaults to `None`) for correct Qt object tree management.

### 10.2 Signal Connections

Connect signals in `__init__` or in dedicated `_connect_signals()` methods, not scattered through arbitrary methods:

```python
def __init__(self, model: WorkspaceModel, parent: QObject | None = None) -> None:
    super().__init__(parent)
    self._model = model
    self._connect_signals()

def _connect_signals(self) -> None:
    self._model.componentAdded.connect(self.on_component_added)
    self._model.componentRemoved.connect(self.on_component_removed)
    self._model.validationChanged.connect(self.on_validation_changed)
```

### 10.3 Signal Disconnection

Long-lived objects must explicitly disconnect signals when destroyed if Qt's automatic cleanup is not sufficient (e.g., when connecting to a longer-lived object's signal):

```python
def cleanup(self) -> None:
    """Disconnect signals before destruction."""
    self._model.componentAdded.disconnect(self.on_component_added)
```

### 10.4 Threading

Per `06 §17`:

* `WorkspaceModel` and all model mutations run on the main thread
* UI updates run on the main thread
* expensive operations (Phase 2 simulation) run in worker threads
* worker → UI communication uses queued Qt signals

Forbidden:

* mutating `WorkspaceModel` from a worker thread
* calling `QWidget` methods from a worker thread
* using Python `threading` primitives where Qt's `QThread` and signals would suffice

### 10.5 Forbidden PySide6 Patterns

* using `QApplication.processEvents()` to "make UI responsive" — use proper threading instead
* connecting the same signal to the same slot multiple times without explicit reason
* storing `QWidget` references inside `model/` classes
* using `QTimer.singleShot(0, ...)` as a generic deferral mechanism

---

## 11. Test Code Style

### 11.1 Test File Layout

Test files mirror the source structure under `tests/`:

```
src/features/SystemModelingModule/model/workspace_model.py
tests/features/SystemModelingModule/model/test_workspace_model.py
```

### 11.2 Test Naming

Test files: `test_<module_name>.py`

Test functions: `test_<behavior_under_test>`:

```python
def test_add_component_returns_ulid_id() -> None: ...
def test_add_component_emits_component_added_signal() -> None: ...
def test_add_component_increments_display_id_counter() -> None: ...
def test_add_component_raises_on_unknown_definition_id() -> None: ...
```

Test names describe **what is being tested**, not **what is being done**:

* good: `test_delete_component_also_removes_attached_connections`
* bad: `test_delete_then_check_connections`

### 11.3 Test Structure

Each test follows the **Arrange-Act-Assert** pattern with optional comments:

```python
def test_add_component_emits_component_added_signal(
    workspace_model: WorkspaceModel,
    qtbot: QtBot,
) -> None:
    # Arrange
    definition_id = "electrical.analog.components.resistor"
    position = QPointF(100.0, 200.0)
    
    # Act
    with qtbot.waitSignal(workspace_model.componentAdded, timeout=1000) as blocker:
        component_id = workspace_model.add_component(definition_id, position)
    
    # Assert
    assert blocker.args == [component_id]
    assert component_id.startswith("cmp_")
```

### 11.4 Fixtures

Reusable fixtures live in:

* `tests/conftest.py` for project-wide fixtures
* `tests/<package>/conftest.py` for package-scoped fixtures

Common fixtures:

* `workspace_model` — fresh `WorkspaceModel` instance
* `component_registry` — populated `ComponentRegistry` with MVP components
* `temp_project_dir` — temporary directory shaped like `.systemdesign/`

### 11.5 Test Categories

Tests are organized by category, marked with pytest markers:

```python
import pytest

@pytest.mark.unit
def test_workspace_model_add_component(): ...

@pytest.mark.integration
def test_save_and_load_round_trip(): ...

@pytest.mark.architecture
def test_no_engine_imports_in_phase1(): ...

@pytest.mark.gui
def test_block_diagram_workspace_renders_component(qtbot): ...

@pytest.mark.slow
def test_load_1000_components_under_5_seconds(): ...
```

CI runs categories in waves (see `12_ci_cd_pipeline.md`).

### 11.6 Forbidden Test Patterns

* tests that depend on the order of execution
* tests that share mutable state across functions
* tests that use real network, real filesystem outside `tmp_path`, or real time delays > 100ms
* tests that test multiple unrelated behaviors in one function
* tests with conditional assertions inside `if` branches
* mocking the system under test (mock collaborators only)

---

## 12. Comments

### 12.1 When to Comment

* explain **why**, not **what** (the code shows what)
* document non-obvious algorithmic choices
* link to specification sections for architectural rules
* note `TODO(name)` with a tracking issue reference
* warn about subtle edge cases

### 12.2 Comment Style

* `#` followed by a single space, then sentence-case prose
* full sentences with terminal punctuation when comments span multiple lines
* short noun phrases acceptable for inline comments

```python
# Phase 1 forbids importing shared.engine; this is verified at startup
# by tests/architecture/test_engine_isolation.py.
from shared.registry import ComponentRegistry

count = 0  # number of currently selected components
```

### 12.3 Forbidden Comment Patterns

* commented-out code (delete it; version control remembers)
* `# This is obvious` style noise
* date stamps in comments (use git blame)
* author attributions in comments (use git blame)
* `# noqa` without an error code

---

## 13. Tool Configuration

### 13.1 Ruff Configuration

The full configuration lives in `pyproject.toml`. Key settings:

```toml
[tool.ruff]
line-length = 100
target-version = "py311"
src = ["src", "tests"]

[tool.ruff.lint]
select = [
    "E",      # pycodestyle errors
    "W",      # pycodestyle warnings
    "F",      # pyflakes
    "I",      # isort
    "N",      # pep8-naming
    "UP",     # pyupgrade
    "B",      # flake8-bugbear
    "C4",     # flake8-comprehensions
    "D",      # pydocstyle
    "PT",     # flake8-pytest-style
    "RUF",    # Ruff-specific rules
    "SIM",    # flake8-simplify
    "TID",    # flake8-tidy-imports
    "TCH",    # flake8-type-checking
]
ignore = [
    "D100",   # missing docstring in public module
    "D104",   # missing docstring in public package
    "D203",   # 1 blank line before class docstring (conflicts with D211)
    "D213",   # multi-line summary on second line (conflicts with D212)
]

[tool.ruff.lint.per-file-ignores]
# PySide6 signals use lowerCamelCase by convention (see §7.2.2)
"**/model/*.py" = ["N815"]
"**/widgets/*.py" = ["N815"]
# Tests do not require docstrings
"tests/**/*.py" = ["D"]
# Allow unused imports for re-export
"**/__init__.py" = ["F401"]

[tool.ruff.lint.isort]
known-first-party = ["application", "features", "shared"]

[tool.ruff.lint.pydocstyle]
convention = "google"

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
```

### 13.2 mypy Configuration

```toml
[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
disallow_untyped_decorators = true
no_implicit_optional = true
warn_redundant_casts = true
warn_unused_ignores = true
warn_no_return = true
warn_unreachable = true
strict_equality = true

[[tool.mypy.overrides]]
module = ["casadi.*", "scipy.*"]
ignore_missing_imports = true
```

### 13.3 pytest Configuration

```toml
[tool.pytest.ini_options]
minversion = "7.0"
addopts = [
    "--strict-markers",
    "--strict-config",
    "-ra",
]
testpaths = ["tests"]
markers = [
    "unit: fast unit tests (default)",
    "integration: integration tests across modules",
    "architecture: architecture and import-boundary tests",
    "gui: tests requiring QApplication",
    "slow: tests that take > 1 second",
]
```

### 13.4 Pre-commit Hooks

The project uses `pre-commit` to enforce standards before commit:

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.7.0
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.13.0
    hooks:
      - id: mypy
        args: [--config-file=pyproject.toml]
        additional_dependencies: [pyside6, types-toml]
```

Contributors must install hooks before their first commit:

```bash
pip install pre-commit
pre-commit install
```

---

## 14. Code Review Standards

### 14.1 Required Review Checks

Every pull request must verify:

* `ruff check` passes with no violations
* `ruff format --check` passes
* `mypy` passes with no errors
* all tests pass
* new code has accompanying tests
* schema changes have migration tests (see `02 §29.3.1`)
* architecture tests still pass (see `08 §10`)
* commit messages follow the convention from `08 §13.2`

### 14.2 Review Etiquette

* prefer concrete suggestions over open-ended questions
* link to the relevant specification section when requesting changes
* distinguish between blocking issues and nice-to-haves
* approve only when the architecture, correctness, and standards are all satisfied

### 14.3 AI Agent Reviews

When the author is an AI agent:

* the human reviewer must verify ADR compliance per the stage's checklist (see `08 §8`)
* the human reviewer must verify no shortcut anti-patterns from `08 §6.5` were used
* the human reviewer must verify cross-document consistency (specs ↔ code)

---

## 15. Forbidden Practices

The agent must never:

1. commit unformatted code (must run `ruff format` first)
2. commit code with `mypy` errors (must add `# type: ignore[code]` with comment if necessary)
3. add `# noqa` without a specific error code and a comment
4. use `from x import *`
5. import `shared.engine` during Phase 1
6. import Qt UI modules inside `model/` or `shared/` packages
7. mutate `WorkspaceModel` from a worker thread
8. use Python builtins as variable names (`list`, `dict`, `id`, `type`)
9. write tests that depend on execution order
10. write functions over 80 lines or files over 800 lines without extraction
11. commit commented-out code
12. write docstrings that are misleading or stale
13. silently downgrade type hints to `Any`
14. shadow signal names with method names

Violation of any rule above blocks merge.

---

## 16. Acceptance Criteria

The coding standards are acceptable when:

* `ruff check` exits zero on the entire codebase
* `ruff format --check` exits zero on the entire codebase
* `mypy --strict` exits zero on the entire codebase
* every public module, class, and function has a Google-style docstring
* import order is enforced by Ruff isort rules
* PySide6 signal naming follows `lowerCamelCase` convention
* test markers are declared and used consistently
* pre-commit hooks are installed and pass
* CI pipeline (see `12_ci_cd_pipeline.md`) verifies all of the above on every push

---

## 17. Final Rule

Code style is a contract, not a preference.

The contract is enforced by:

* Ruff (formatting and most linting)
* mypy (type checking)
* pytest (test correctness)
* pre-commit hooks (local enforcement)
* CI pipeline (gate enforcement)
* code review (architectural correctness)

The agent must respect this contract on every commit. Style violations block merge regardless of feature correctness.
