# Stage S0 Migration Guide

This document is your step-by-step guide to bringing the existing
project structure into compliance with the Stage S0 acceptance
criteria from `specs/07_implementation_order.md` §6.

It assumes:

* you are at `/Users/serhatcombas/Documents/Pyscripts/Codex_Project`
* you have downloaded the `stage_s0/` package from this conversation
* your virtual environment is active (`source .venv/bin/activate`)

---

## Pre-flight Check

Before starting, verify your current state:

```bash
cd /Users/serhatcombas/Documents/Pyscripts/Codex_Project
git status
git stash    # if you have uncommitted work
git checkout -b stage-s0-completion
```

Working on a branch makes it safe to roll back if anything goes wrong.

---

## Phase 1 — Add Missing Files (Safe, no deletion)

### Step 1: Place `shared/engine/__init__.py`

This is **the most critical file**. ADR-001 (Phase 1 Engine Isolation)
is enforced here. Architecture tests verify it.

```bash
# From the downloaded stage_s0/ folder, copy:
cp stage_s0/src/shared/engine/__init__.py \
   src/shared/engine/__init__.py
```

Verify:

```bash
python -c "import sys; sys.path.insert(0, 'src'); from shared import engine"
# Expected output:
# ImportError: shared.engine is not available in Phase 1...
```

If the import succeeds (no error), the barrier is not active. Re-check
the file content.

### Step 2: Add `model/` and `commands/` Folders to SystemModelingModule

```bash
mkdir -p src/features/SystemModelingModule/model/migrations
mkdir -p src/features/SystemModelingModule/commands

# Copy __init__.py files from stage_s0/:
cp stage_s0/src/features/SystemModelingModule/model/__init__.py \
   src/features/SystemModelingModule/model/__init__.py

cp stage_s0/src/features/SystemModelingModule/model/migrations/__init__.py \
   src/features/SystemModelingModule/model/migrations/__init__.py

cp stage_s0/src/features/SystemModelingModule/commands/__init__.py \
   src/features/SystemModelingModule/commands/__init__.py
```

### Step 3: Add `ComponentInfoPanel/` and `ModelEquationsPanel/` to SystemModelingModule

```bash
mkdir -p src/features/SystemModelingModule/panels/ComponentInfoPanel
mkdir -p src/features/SystemModelingModule/panels/ModelEquationsPanel

cp stage_s0/src/features/SystemModelingModule/panels/ComponentInfoPanel/__init__.py \
   src/features/SystemModelingModule/panels/ComponentInfoPanel/__init__.py

cp stage_s0/src/features/SystemModelingModule/panels/ModelEquationsPanel/__init__.py \
   src/features/SystemModelingModule/panels/ModelEquationsPanel/__init__.py
```

### Step 4: Add `model/` and `builders/` Folders to ControllerDesignModule

```bash
mkdir -p src/features/ControllerDesignModule/model
mkdir -p src/features/ControllerDesignModule/builders

cp stage_s0/src/features/ControllerDesignModule/model/__init__.py \
   src/features/ControllerDesignModule/model/__init__.py

cp stage_s0/src/features/ControllerDesignModule/builders/__init__.py \
   src/features/ControllerDesignModule/builders/__init__.py
```

### Step 5: Add `assets/locales/en.json`

```bash
mkdir -p assets/locales
cp stage_s0/assets/locales/en.json assets/locales/en.json
```

---

## Phase 2 — Rename and Move (Destructive, do in order)

### Step 6: Move `ModelEquationsPanel` from ControllerDesignModule to SystemModelingModule

`ModelEquationsPanel` is currently misplaced. It belongs to
SystemModelingModule per ADR-004 (Equation Builder Ownership).

```bash
# The contents of ControllerDesignModule/panels/ModelEquationsPanel
# (if any) should move to SystemModelingModule/panels/ModelEquationsPanel.
# If the folder is empty (only __pycache__), just remove it:

# Check what's inside:
ls src/features/ControllerDesignModule/panels/ModelEquationsPanel/

# If it only has __init__.py and __pycache__/:
rm -rf src/features/ControllerDesignModule/panels/ModelEquationsPanel

# If it has actual code (.py files), move them first:
# cp src/features/ControllerDesignModule/panels/ModelEquationsPanel/*.py \
#    src/features/SystemModelingModule/panels/ModelEquationsPanel/
# rm -rf src/features/ControllerDesignModule/panels/ModelEquationsPanel
```

### Step 7: Rename `ControllerTuningPanel` to `ConfigurationPanel`

Per `specs/03_configuration_requirements.md`, the configuration panel
holds four tabs (Controller, I/O Selection, Simulation Settings, Plot
Layout). The name `ConfigurationPanel` reflects this multi-tab nature.

```bash
# Rename:
git mv src/features/ControllerDesignModule/panels/ControllerTuningPanel \
       src/features/ControllerDesignModule/panels/ConfigurationPanel

# Replace __init__.py with the spec-aligned version:
cp stage_s0/src/features/ControllerDesignModule/panels/ConfigurationPanel/__init__.py \
   src/features/ControllerDesignModule/panels/ConfigurationPanel/__init__.py

# Update any internal imports (search for ControllerTuningPanel references):
grep -r "ControllerTuningPanel" src/ --include="*.py"
# Replace each occurrence with ConfigurationPanel.
```

### Step 8: Rename `SimulationResultsPanel` to `ResultsPanel`

Per `specs/05_simulation_and_results_requirements.md`, the result
panel renders both simulation results AND stability analysis (per
ADR-015 Result Panel Unified With Grouped Dropdown). The name
`ResultsPanel` reflects this unified scope.

```bash
git mv src/features/ControllerDesignModule/panels/SimulationResultsPanel \
       src/features/ControllerDesignModule/panels/ResultsPanel

cp stage_s0/src/features/ControllerDesignModule/panels/ResultsPanel/__init__.py \
   src/features/ControllerDesignModule/panels/ResultsPanel/__init__.py

# Update imports:
grep -r "SimulationResultsPanel" src/ --include="*.py"
# Replace each occurrence with ResultsPanel.
```

---

## Phase 3 — Verify Every Package Has `__init__.py`

A common Python packaging pitfall: a folder is treated as a package
only if it has `__init__.py`. Verify every Python package directory:

```bash
# Find directories under src/ that contain .py files but no __init__.py:
find src -type d ! -path '*/__pycache__*' -exec sh -c '
    if ls "$1"/*.py 1>/dev/null 2>&1 && ! [ -f "$1/__init__.py" ]; then
        echo "MISSING __init__.py in: $1"
    fi
' _ {} \;
```

For each missing one, create:

```bash
touch src/path/to/missing/__init__.py
```

---

## Phase 4 — Run the Architecture Tests

This is the **acceptance gate** for Stage S0. All tests must pass.

```bash
# Run from project root, with src on PYTHONPATH:
PYTHONPATH=src pytest tests/architecture -v
```

Expected output:

```
tests/architecture/test_engine_isolation.py::test_shared_engine_raises_import_error_in_phase_1 PASSED
tests/architecture/test_engine_isolation.py::test_no_phase_1_source_imports_shared_engine PASSED
tests/architecture/test_module_boundaries.py::test_system_modeling_does_not_import_controller_design PASSED
tests/architecture/test_module_boundaries.py::test_controller_design_does_not_import_system_modeling PASSED
tests/architecture/test_module_boundaries.py::test_shared_does_not_import_features PASSED
tests/architecture/test_module_boundaries.py::test_shared_does_not_import_application PASSED
tests/architecture/test_module_boundaries.py::test_features_do_not_import_application PASSED
tests/architecture/test_no_ui_in_model.py::test_data_layer_packages_have_no_ui_imports PASSED
tests/architecture/test_error_catalog.py::test_all_codes_in_catalog_match_naming_convention PASSED
tests/architecture/test_error_catalog.py::test_all_codes_in_catalog_have_locale_entry PASSED
tests/architecture/test_error_catalog.py::test_no_undocumented_codes_raised_in_source PASSED
tests/architecture/test_logging_events.py::test_logging_events_module_exists SKIPPED
tests/architecture/test_logging_events.py::test_event_values_match_constants SKIPPED
tests/architecture/test_logging_events.py::test_declared_events_match_naming_convention SKIPPED
tests/architecture/test_adr_files_present.py::test_decisions_folder_exists PASSED
tests/architecture/test_adr_files_present.py::test_decisions_readme_exists PASSED
tests/architecture/test_adr_files_present.py::test_decisions_template_exists PASSED
tests/architecture/test_adr_files_present.py::test_all_canonical_adrs_present PASSED
tests/architecture/test_adr_files_present.py::test_adr_files_have_required_sections PASSED
```

`SKIPPED` is acceptable for `test_logging_events.py` because the
`shared/utils/logging_events.py` module is not yet created (it is
populated during Stage S1 / S2 along with the actual logging code).

If any test FAILS, see the failure message — it will pinpoint the
violation. Common fixes:

* `test_engine_isolation` fails → `shared/engine/__init__.py` is
  missing or does not raise ImportError
* `test_module_boundaries` fails → a feature module imports another
  feature module (audit imports)
* `test_no_ui_in_model` fails → a `model/` subfolder imports
  `PySide6.QtWidgets` or `QtGui`
* `test_error_catalog` fails → an error code is raised in code but
  not present in `specs/11_error_code_catalog.md` or `assets/locales/en.json`
* `test_adr_files_present` fails → an ADR file is missing or lacks a
  required section

---

## Phase 5 — Decide About `app.js`, `styles.css`, `index.html`

These files are not part of the spec'd PySide6 architecture. Three
options:

### Option A: Delete (recommended if they were exploration leftovers)

```bash
rm src/application/SystemDesignerShell/app.js
rm src/application/SystemDesignerShell/styles.css
rm index.html
```

### Option B: Keep as Qt WebEngine assets

If you intend to use `QWebEngineView` to embed HTML/CSS/JS UI
fragments inside the PySide6 app, document this choice as a new ADR:

```bash
cp decisions/_template.md decisions/ADR-018-web-engine-hybrid-ui.md
# Edit the new file to explain the decision.
```

Then update `specs/06_data_flow_and_architecture.md` §19 to add
ADR-018 to the canonical list and update
`tests/architecture/test_adr_files_present.py` accordingly.

### Option C: Move to a separate prototype folder

If you want to keep the files for reference but exclude them from the
production tree:

```bash
mkdir -p prototypes/web-frontend-exploration
git mv src/application/SystemDesignerShell/app.js \
       prototypes/web-frontend-exploration/
git mv src/application/SystemDesignerShell/styles.css \
       prototypes/web-frontend-exploration/
git mv index.html prototypes/web-frontend-exploration/
```

Add `prototypes/` to `.gitignore` if you don't want to commit it, or
keep it tracked as exploration history.

**Recommendation: Option A** unless you have a clear plan for hybrid
UI. The spec-aligned PySide6 architecture is fully self-sufficient.

---

## Phase 6 — Decide About `main.py` Location

Currently `main.py` is at the project root. Per
`specs/06_data_flow_and_architecture.md` §2.1, the entry point lives
at `src/application/main.py`.

### Option A: Spec-pure (single entry)

Move `main.py` to its proper location:

```bash
git mv main.py src/application/main.py
```

Update README to use:

```bash
python -m application.main
# or
python src/application/main.py
```

### Option B: Pragmatic wrapper (recommended)

Keep a thin wrapper at root that calls the spec-located entry:

```bash
# Move the real implementation:
git mv main.py src/application/main.py

# Create a thin wrapper at root:
cat > main.py <<'EOF'
"""Project root entry-point wrapper.

Forwards to `src.application.main:main()`. Allows users to run
`python main.py` from the project root without setting PYTHONPATH.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add src/ to sys.path so absolute imports work.
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from application.main import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
EOF
```

This way `python main.py` works locally, and `python -m application.main`
works from CI/IDE configurations.

**Recommendation: Option B**.

---

## Phase 7 — Final Verification

After all the above:

```bash
# 1. Architecture tests pass
PYTHONPATH=src pytest tests/architecture -v

# 2. Project structure matches spec
tree -d -L 4 -I '__pycache__|.venv'

# 3. Lint and type-check (if you have any code)
ruff check src tests
ruff format --check src tests
mypy --config-file pyproject.toml src

# 4. Application still launches
python main.py
```

---

## Rollback Plan

If anything breaks:

```bash
git checkout main
git branch -D stage-s0-completion
```

You haven't merged anything yet, so the main branch is untouched.

---

## Stage S0 Completion Checklist

When ALL of these are true, Stage S0 is complete:

- [ ] `src/shared/engine/__init__.py` raises `ImportError`
- [ ] `src/features/SystemModelingModule/model/` exists with `__init__.py`
- [ ] `src/features/SystemModelingModule/commands/` exists with `__init__.py`
- [ ] `src/features/SystemModelingModule/panels/ComponentInfoPanel/` exists
- [ ] `src/features/SystemModelingModule/panels/ModelEquationsPanel/` exists
- [ ] `src/features/ControllerDesignModule/model/` exists with `__init__.py`
- [ ] `src/features/ControllerDesignModule/builders/` exists with `__init__.py`
- [ ] `ControllerTuningPanel` renamed to `ConfigurationPanel`
- [ ] `SimulationResultsPanel` renamed to `ResultsPanel`
- [ ] `ModelEquationsPanel` no longer exists under ControllerDesignModule
- [ ] `assets/locales/en.json` exists
- [ ] All Python package directories have `__init__.py`
- [ ] `pytest tests/architecture -v` passes (skipped tests acceptable)
- [ ] `app.js`, `styles.css`, `index.html` decision is final and documented
- [ ] `main.py` location decision is final
- [ ] All changes committed to a feature branch
- [ ] Branch merged to main after review

Once the checklist is complete, you have a clean Stage S0 baseline
and can begin Stage S1 (Workspace Foundation) per
`specs/07_implementation_order.md` §7.
