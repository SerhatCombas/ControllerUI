# Stage S0 Final Cleanup

This document handles the **final two decisions** from the Stage S0
checklist:

1. Delete `app.js`, `styles.css`, `index.html` (PySide6-only project)
2. Move `main.py` from project root to `src/application/main.py`
   with strict spec compliance (`python -m application.main`)

It assumes you have already completed Phase 1–4 of
`STAGE_S0_MIGRATION.md` (the previous package). If not, complete
those first.

---

## Phase 5 — Remove Web Frontend Leftovers

We chose **Option A: delete**. The project is a pure PySide6 desktop
app; the JavaScript/CSS/HTML files are not needed.

### Step 5.1: Delete the files

```bash
cd /Users/serhatcombas/Documents/Pyscripts/Codex_Project

# Remove web frontend files inside SystemDesignerShell:
rm -f src/application/SystemDesignerShell/app.js
rm -f src/application/SystemDesignerShell/styles.css

# Remove the root-level index.html:
rm -f index.html

# Verify:
ls src/application/SystemDesignerShell/
# Expected: __init__.py, main_window.py, __pycache__/ (the latter recreates)
```

### Step 5.2: Verify nothing else references them

```bash
grep -rn "app.js\|styles.css\|index.html" src/ \
    --include="*.py" \
    --include="*.md" \
    --exclude-dir=__pycache__
# Expected: no output. If any references remain, edit those files
# to remove the references.
```

### Step 5.3: Stage deletions

```bash
git add -A
git status
# Confirm the three deletions are listed.
```

---

## Phase 6 — Spec-Pure `main.py` Relocation

We chose **Option A: spec-pure single entry**. The application
entry point will live at `src/application/main.py`, and the launch
command becomes:

```bash
python -m application.main
```

### Step 6.1: Inspect the current `main.py` content

```bash
cat main.py
```

If the file contains real code (QApplication setup, window creation,
etc.), we'll preserve it. If it is empty or trivial, we'll replace it
with the spec-aligned template provided in the package.

### Step 6.2: Choose your migration sub-option

#### Sub-option A: Preserve existing main.py content

If your current `main.py` has code you want to keep:

```bash
# Move the existing file:
git mv main.py src/application/main.py

# Verify it landed correctly:
ls src/application/
# Expected: __init__.py, main.py, SystemDesignerShell/
```

Then make sure `__init__.py` is in place (the previous package
provided one):

```bash
ls src/application/__init__.py
# If missing, copy from the package:
cp stage_s0_final/src/application/__init__.py \
   src/application/__init__.py
```

You may need to adapt imports in your existing `main.py`. Specifically,
update:

* `from SystemDesignerShell import ...` → `from application.SystemDesignerShell import ...`
* Any relative import that assumed `main.py` was at the project root.

#### Sub-option B: Replace with spec-aligned template

If your current `main.py` is trivial or empty:

```bash
# Remove the old file:
rm main.py

# Use the spec-aligned template:
cp stage_s0_final/src/application/main.py \
   src/application/main.py

cp stage_s0_final/src/application/__init__.py \
   src/application/__init__.py
```

The template provides:

* Bootstrap logging configuration (per `specs/10 §9`)
* Standard `QApplication` setup with org/app/version metadata
* Hooks for future registry bootstrap (commented `TODO(stage_s1)`)
* Lifecycle: configure logging → create QApplication → show shell → enter event loop
* `--debug` command-line flag for debug logging

### Step 6.3: Replace `SystemDesignerShell/__init__.py`

The spec-aligned template re-exports `SystemDesignerShell` from
`main_window.py`. Update the existing `__init__.py`:

```bash
cp stage_s0_final/src/application/SystemDesignerShell/__init__.py \
   src/application/SystemDesignerShell/__init__.py
```

This file expects `main_window.py` to define a class named
`SystemDesignerShell`. If your existing `main_window.py` uses a
different class name, either rename the class or adjust the import in
`__init__.py`.

---

## Phase 7 — Update `pyproject.toml` for Editable Install

Replace the existing `pyproject.toml` with the updated version that
adds:

1. `[project.scripts]` — installs a `system-designer` console command
2. Refined `[tool.setuptools.packages.find]` for src/ layout
3. mypy `mypy_path = "src"` (required for src/ layout)
4. pytest `pythonpath = ["src"]` (no manual PYTHONPATH needed)

```bash
cp stage_s0_final/pyproject.toml pyproject.toml
```

### Then perform the editable install:

```bash
source .venv/bin/activate
python -m pip install -e .
```

You should see output similar to:

```
Successfully installed system_designer-0.2.0
```

After this one-time install, the packages `application`, `features`,
and `shared` are importable from anywhere — no PYTHONPATH manipulation
needed.

---

## Phase 8 — Replace `README.md`

The README needs updates to reflect:

* New launch command: `python -m application.main`
* Editable install instructions
* `pyproject.toml` makes `pytest` work without PYTHONPATH

```bash
cp stage_s0_final/README.md README.md
```

---

## Phase 9 — Final Verification

### Step 9.1: Architecture tests

```bash
pytest -m architecture -v
# pyproject.toml's pythonpath setting handles src/ inclusion automatically.
```

Expected: 17 PASSED + 3 SKIPPED (logging events tests are SKIPPED until
Stage S1).

### Step 9.2: Application launches

```bash
python -m application.main
```

The window should appear. If you see import errors, verify:

```bash
python -c "from application.main import main; print('import OK')"
```

If this still fails, the editable install did not register correctly.
Re-run `python -m pip install -e .`.

### Step 9.3: Console script works

```bash
system-designer
```

Should launch the same window.

### Step 9.4: Lint

```bash
ruff check src tests
ruff format --check src tests
```

### Step 9.5: Type-check

```bash
mypy --config-file pyproject.toml src
```

### Step 9.6: Final structure check

```bash
tree -L 3 -I '__pycache__|.venv|*.egg-info|build|dist'
```

The structure should match the diagram in `README.md` § Project Structure.

### Step 9.7: Commit

```bash
git add -A
git status
# Confirm changes are staged correctly.

git commit -m "S0: complete stage S0 architectural baseline

- Add shared/engine ImportError barrier (ADR-001)
- Add model/ and commands/ packages to SystemModelingModule
- Add ComponentInfoPanel and ModelEquationsPanel (moved from ControllerDesignModule)
- Rename ControllerTuningPanel to ConfigurationPanel
- Rename SimulationResultsPanel to ResultsPanel
- Add model/ and builders/ packages to ControllerDesignModule
- Move main.py to src/application/main.py (spec-pure entry point)
- Remove web frontend leftovers (app.js, styles.css, index.html)
- Add assets/locales/en.json with Phase 1 error code translations
- Update pyproject.toml for editable install and src/ layout
- Update README with new launch command

Architecture tests: 17 PASSED, 3 SKIPPED (logging events deferred to S1).
"
```

---

## Stage S0 Final Checklist

When ALL of these are true, Stage S0 is complete:

- [x] `src/shared/engine/__init__.py` raises `ImportError` (Phase 1)
- [x] `src/features/SystemModelingModule/model/` exists with `__init__.py`
- [x] `src/features/SystemModelingModule/commands/` exists with `__init__.py`
- [x] `src/features/SystemModelingModule/panels/ComponentInfoPanel/` exists
- [x] `src/features/SystemModelingModule/panels/ModelEquationsPanel/` exists
- [x] `src/features/ControllerDesignModule/model/` exists with `__init__.py`
- [x] `src/features/ControllerDesignModule/builders/` exists with `__init__.py`
- [x] `ControllerTuningPanel` renamed to `ConfigurationPanel`
- [x] `SimulationResultsPanel` renamed to `ResultsPanel`
- [x] `ModelEquationsPanel` no longer exists under ControllerDesignModule
- [x] `assets/locales/en.json` exists
- [x] All Python package directories have `__init__.py`
- [ ] `app.js`, `styles.css`, `index.html` removed (this phase)
- [ ] `main.py` moved to `src/application/main.py` (this phase)
- [ ] `pyproject.toml` updated for src/ layout + editable install
- [ ] `python -m pip install -e .` succeeded
- [ ] `python -m application.main` launches the app
- [ ] `system-designer` console script launches the app
- [ ] `pytest -m architecture` passes (17 PASSED, 3 SKIPPED acceptable)
- [ ] All changes committed to feature branch
- [ ] Branch merged to main after review

Once everything above is checked, **Stage S0 is officially complete**
and you can begin **Stage S1 (Workspace Foundation)** per
`specs/07_implementation_order.md` §7.

---

## Rollback

If anything goes wrong:

```bash
git checkout main
git branch -D stage-s0-completion  # if your branch is named that
```

Your main branch remains untouched.

---

## What's Next

Stage S1 begins implementation work. The first targets:

1. `WorkspaceModel` in `src/features/SystemModelingModule/model/workspace_model.py`
2. `ComponentInstance` and `Connection` dataclasses
3. `WorkspaceIdGenerator` (ULID + display ID)
4. First QUndoCommand subclasses (`AddComponentCommand`, `MoveComponentCommand`)
5. First UI components (BlockDiagramWorkspace skeleton)

See `specs/07_implementation_order.md` §7 for the full S1 plan.
