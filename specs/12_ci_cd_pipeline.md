# 12_ci_cd_pipeline.md

## 1. Purpose

This document defines the Continuous Integration and Continuous Deployment (CI/CD) pipeline for the Engineering System Designer project.

The pipeline exists to:

* prevent broken or unstandardized code from being merged into the main branch
* enforce architectural invariants on every push
* run all automated tests on every change
* verify that the project's contracts (specs, ADRs, schemas, error codes) remain consistent
* produce reproducible builds and distributable artifacts when changes are tagged for release

This document is **not** a feature specification. It is an operational contract that complements `08_codex_execution_rules.md`, `09_coding_standards.md`, `10_logging_conventions.md`, and `11_error_code_catalog.md`.

The pipeline is the **gate** for merging code. AI agents and human contributors alike must pass the pipeline before a pull request is approved.

---

## 2. Scope

### 2.1 In Scope

* GitHub Actions workflow definition
* Five pipeline stages: Setup, Lint, Test, Security, Deploy
* Trigger events (push, pull_request, schedule, workflow_dispatch)
* Caching strategy
* Test segmentation by markers (unit / integration / architecture / gui / slow)
* Coverage reporting
* Security scanning (`safety`, `bandit`)
* Architecture invariant tests
* Deployment to GitHub Releases (Phase 1)
* Deployment to PyPI or Docker registry (Phase 3 future scope)

### 2.2 Out of Scope

* Local pre-commit hooks (see `09_coding_standards.md` §13.4)
* Test authoring guidance (see `09_coding_standards.md` §11)
* Specific feature test design (see each feature spec's "Required Tests" section)

---

## 3. Pipeline Overview

### 3.1 Five Stages

The pipeline runs in five sequential stages. Each stage must pass before the next begins (with parallelization where independent).

```
Stage 1: Setup       → Stage 2: Lint   → Stage 3: Test       → Stage 4: Security    → Stage 5: Deploy
(install deps,         (ruff check,       (unit, integration,    (safety,                (build, publish,
  cache)                ruff format,       architecture, gui,     bandit)                  release)
                        mypy)               coverage)
```

### 3.2 Stage Failure Policy

* if Setup fails, no other stages run
* if Lint fails, Test still runs to surface as many issues as possible (Lint failure blocks merge)
* if Test fails on the main branch, an alert is created (issue or notification)
* if Security finds high-severity vulnerabilities, merge is blocked
* Deploy runs only on tagged releases or main-branch pushes (configurable)

### 3.3 Trigger Events

The pipeline runs on:

* `push` to `main`, `develop`, or any `release/*` branch
* `pull_request` targeting `main` or `develop`
* `schedule`: weekly run on `main` to catch dependency drift (Sundays at 03:00 UTC)
* `workflow_dispatch`: manual trigger from the GitHub Actions UI

---

## 4. Stage 1 — Setup

### 4.1 Purpose

Prepare a clean Python environment with all dependencies installed.

### 4.2 Steps

1. Check out the repository
2. Set up Python 3.11 (and 3.12 in matrix mode)
3. Restore pip cache (if any)
4. Install runtime dependencies from `requirements.txt`
5. Install development dependencies from `requirements-dev.txt`
6. Cache the resulting environment

### 4.3 GitHub Actions Snippet

```yaml
jobs:
  setup:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]
    steps:
      - name: Check out repository
        uses: actions/checkout@v4
      
      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
          cache: pip
      
      - name: Install runtime dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
      
      - name: Install development dependencies
        run: pip install -r requirements-dev.txt
      
      - name: Verify Python version
        run: python --version
      
      - name: List installed packages
        run: pip list
```

### 4.4 Cache Strategy

* `pip` cache is keyed by the hash of `requirements.txt` and `requirements-dev.txt`
* On cache hit, dependencies are restored without re-download
* Cache is invalidated when either requirements file changes

---

## 5. Stage 2 — Lint

### 5.1 Purpose

Verify that the code conforms to project coding standards (`09_coding_standards.md`).

### 5.2 Tools

* **Ruff** for formatting and linting (replaces Black, isort, flake8, pyupgrade, pydocstyle)
* **mypy** for type checking in strict mode

### 5.3 Steps

1. Run `ruff format --check src tests` (no auto-fix; CI verifies, does not modify)
2. Run `ruff check src tests`
3. Run `mypy --config-file pyproject.toml src`

### 5.4 GitHub Actions Snippet

```yaml
  lint:
    needs: setup
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip
      
      - name: Install dev dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt -r requirements-dev.txt
      
      - name: Check formatting
        run: ruff format --check src tests
      
      - name: Lint with Ruff
        run: ruff check src tests
      
      - name: Type-check with mypy
        run: mypy --config-file pyproject.toml src
```

### 5.5 Lint Failure Handling

* if `ruff format --check` fails, the contributor must run `ruff format` locally and re-commit
* if `ruff check` fails, the contributor must fix the violations or add `# noqa: <code>` with justification
* if `mypy` fails, the contributor must fix type errors or add `# type: ignore[code]` with comment

---

## 6. Stage 3 — Test

### 6.1 Purpose

Run all automated tests in the appropriate order to surface failures quickly.

### 6.2 Test Segmentation

Tests are segmented by pytest markers (declared in `pyproject.toml` per `09 §13.3`):

* `unit` — fast tests of single classes or functions
* `integration` — multi-module integration tests
* `architecture` — import-boundary and invariant tests
* `gui` — tests requiring `QApplication` (use `pytest-qt`)
* `slow` — tests that take more than one second

### 6.3 Order of Execution

CI runs tests in waves:

1. **Wave 1**: `architecture` tests — cheap and validate fundamental invariants
2. **Wave 2**: `unit` tests — broad coverage, fast feedback
3. **Wave 3**: `integration` tests
4. **Wave 4**: `gui` tests
5. **Wave 5**: `slow` tests (only on `main` and `release/*` branches)

A failure in an earlier wave aborts later waves to save CI time.

### 6.4 GitHub Actions Snippet

```yaml
  test-architecture:
    needs: setup
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip
      - run: pip install -r requirements.txt -r requirements-dev.txt
      - name: Run architecture tests
        run: pytest -m architecture --strict-markers
  
  test-unit:
    needs: test-architecture
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip
      - run: pip install -r requirements.txt -r requirements-dev.txt
      - name: Run unit tests with coverage
        run: pytest -m unit --cov=src --cov-report=xml --cov-report=term
      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v4
        with:
          files: coverage.xml
          fail_ci_if_error: false
  
  test-integration:
    needs: test-unit
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip
      - run: pip install -r requirements.txt -r requirements-dev.txt
      - name: Run integration tests
        run: pytest -m integration
  
  test-gui:
    needs: test-integration
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip
      - run: pip install -r requirements.txt -r requirements-dev.txt
      - name: Set up Xvfb (virtual display)
        run: |
          sudo apt-get update
          sudo apt-get install -y xvfb libegl1 libxkbcommon0 libdbus-1-3
      - name: Run GUI tests
        run: xvfb-run -a pytest -m gui
  
  test-slow:
    needs: test-gui
    if: github.ref == 'refs/heads/main' || startsWith(github.ref, 'refs/heads/release/')
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip
      - run: pip install -r requirements.txt -r requirements-dev.txt
      - name: Run slow tests
        run: pytest -m slow --timeout=300
```

### 6.5 Architecture Tests

The architecture wave includes tests that verify:

* `tests/architecture/test_engine_isolation.py` — `shared.engine` cannot be imported during Phase 1
* `tests/architecture/test_module_boundaries.py` — `features/<X>/` does not import `features/<Y>/`
* `tests/architecture/test_no_ui_in_model.py` — `model/` subpackages do not import Qt UI modules
* `tests/architecture/test_no_engine_in_features.py` — Phase 1 features do not import `shared.engine`
* `tests/architecture/test_error_catalog.py` — every raised error code is in `11_error_code_catalog.md`
* `tests/architecture/test_logging_events.py` — every `extra["event"]` value is in `shared/utils/logging_events.py`
* `tests/architecture/test_adr_files_present.py` — all 17 ADRs referenced in `06 §19` exist as files in `decisions/`

These tests are cheap and fail fast when invariants are broken.

### 6.6 Coverage Reporting

* Unit tests collect coverage via `pytest-cov`
* Coverage is uploaded to Codecov (or equivalent)
* Coverage threshold: **80% minimum** for the entire codebase, **90% for `model/` subpackages**
* Coverage drops below threshold do not block merge automatically but trigger a comment on the PR

---

## 7. Stage 4 — Security

### 7.1 Purpose

Detect known vulnerabilities in dependencies and unsafe patterns in source code.

### 7.2 Tools

* **safety** — checks installed packages against the PyUp.io vulnerability database
* **bandit** — static analysis for common security issues in Python source code
* **pip-audit** (optional) — alternative to safety, uses the OSV database

### 7.3 Steps

1. Run `safety check --file requirements.txt --output text`
2. Run `bandit -r src -ll` (low-level severity threshold)

### 7.4 GitHub Actions Snippet

```yaml
  security:
    needs: test-architecture
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip
      
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
          pip install safety bandit
      
      - name: Check for known vulnerabilities
        run: safety check --file requirements.txt --output text
        continue-on-error: false
      
      - name: Run bandit
        run: bandit -r src -ll -f txt
        continue-on-error: true
```

### 7.5 Security Failure Handling

* `safety` failures with **high** or **critical** severity block merge
* `safety` failures with **medium** or **low** severity create a warning but do not block
* `bandit` warnings are reviewed manually; no automatic merge block in Phase 1
* if a vulnerability cannot be fixed immediately, an exemption may be added to `.safety-policy.yml` with a comment and a tracking issue

### 7.6 Forbidden Patterns Detected by Bandit

* hardcoded credentials (passwords, tokens, API keys)
* use of `eval()` or `exec()` on untrusted input
* unsafe deserialization (`pickle`, `yaml.load` without `Loader=yaml.SafeLoader`)
* `subprocess` calls with `shell=True` and dynamic arguments
* `assert` statements used for security-critical checks (assertions are stripped in optimized builds)

---

## 8. Stage 5 — Deploy

### 8.1 Purpose

Build and publish release artifacts when changes reach the main branch or a tagged release.

### 8.2 Phase 1 Deployment Targets

* **GitHub Releases** — when a tag matching `v*.*.*` is pushed, build a Python wheel and source distribution and attach to the release
* **Internal artifact retention** — every successful build on `main` produces a wheel uploaded as a CI artifact (retained for 30 days)

### 8.3 Phase 3 Future Targets (Reserved)

* PyPI publishing (requires API token)
* Docker image build and push to a container registry
* Auto-update channel for desktop releases

These are reserved scope; not implemented in Phase 1.

### 8.4 Steps

1. Build source distribution (`python -m build --sdist`)
2. Build wheel (`python -m build --wheel`)
3. Verify wheel installs cleanly in a fresh environment
4. Attach artifacts to GitHub Release (if tagged)

### 8.5 GitHub Actions Snippet

```yaml
  deploy:
    needs: [lint, test-gui, security]
    if: startsWith(github.ref, 'refs/tags/v')
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      
      - name: Install build tooling
        run: |
          python -m pip install --upgrade pip
          pip install build
      
      - name: Build distribution
        run: python -m build
      
      - name: Verify wheel
        run: |
          pip install dist/*.whl
          python -c "import system_designer; print('OK')"
      
      - name: Upload to GitHub Release
        uses: softprops/action-gh-release@v2
        with:
          files: |
            dist/*.whl
            dist/*.tar.gz
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### 8.6 Versioning

The project uses **semantic versioning**:

* `MAJOR.MINOR.PATCH` (e.g., `0.2.0`)
* version stored in `pyproject.toml` `[project]` section
* tags on the main branch follow `v0.2.0` format
* pre-release tags use `v0.2.0-rc.1` format

The `application_version` field in `project.json` (see `02 §29.1`) reflects the version of the application that wrote the file.

---

## 9. Pipeline Performance

### 9.1 Targets

| Stage | Target Duration |
|---|---|
| Setup (with cache hit) | < 30 seconds |
| Lint | < 1 minute |
| Test (architecture wave) | < 30 seconds |
| Test (unit wave) | < 3 minutes |
| Test (integration wave) | < 5 minutes |
| Test (gui wave) | < 5 minutes |
| Test (slow wave, main only) | < 10 minutes |
| Security | < 1 minute |
| Deploy | < 3 minutes |
| **Total (PR pipeline)** | **< 15 minutes** |

### 9.2 Optimization Strategies

* aggressive pip caching (keyed by requirements hash)
* matrix parallelization for Python 3.11 / 3.12
* test segmentation to skip slow tests on PR branches
* `pytest-xdist` for parallel test execution within a wave
* `pytest --lf` (last-failed) is **not** used in CI; CI must always run the full suite

### 9.3 CI Resource Limits

* maximum concurrent jobs per branch: 4
* CI minute budget per month: tracked, alert at 80% consumption
* job timeout: 30 minutes per stage (forces investigation of stuck tests)

---

## 10. Branch Protection

### 10.1 Required Status Checks

The `main` branch must require:

* `lint` job success
* `test-architecture` job success
* `test-unit` job success
* `test-integration` job success
* `test-gui` job success
* `security` job success

### 10.2 Required Reviews

* at least one human reviewer must approve before merge
* PRs authored by AI agents require **explicit human review** verifying ADR compliance per `08 §8`

### 10.3 Merge Strategy

* squash merge for feature branches (clean history)
* rebase merge for `release/*` to `main` (preserve release history)
* never use simple merge commits on `main`

---

## 11. Local Reproduction

Contributors must be able to reproduce CI checks locally:

```bash
# Set up environment
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
pre-commit install

# Run lint locally (Stage 2)
ruff format --check src tests
ruff check src tests
mypy --config-file pyproject.toml src

# Run tests locally (Stage 3)
pytest -m architecture
pytest -m unit
pytest -m integration
pytest -m gui  # may require Xvfb on Linux without a display

# Run security locally (Stage 4)
safety check --file requirements.txt
bandit -r src -ll
```

A `Makefile` or `tox.ini` may be added to wrap these commands in single targets.

---

## 12. Pipeline Files

The CI configuration lives in:

```text
.github/
  workflows/
    ci.yml                  # main pipeline
    nightly.yml             # weekly scheduled run (optional)
    release.yml             # release-specific pipeline
  dependabot.yml            # dependency update automation
```

---

## 13. Forbidden Practices

The agent must never:

1. push code that fails Lint locally
2. disable a CI step without an open issue documenting the reason
3. add `continue-on-error: true` to a status check that should be blocking
4. commit secrets (API keys, tokens) into the repository
5. use `pull_request_target` for PR triggers without security review (allows untrusted code to access secrets)
6. skip the architecture wave even for "small" changes
7. mark a test as `slow` only to bypass its execution on PR branches
8. modify `.github/workflows/*.yml` without reviewing the security implications
9. add a deployment target without a corresponding security review
10. bypass branch protection by merging directly to `main`

---

## 14. Acceptance Criteria

The CI/CD pipeline is acceptable when:

* the five stages run in the documented order
* the `lint`, `test-architecture`, `test-unit`, `test-integration`, `test-gui`, and `security` jobs are required status checks on `main`
* test segmentation by markers works correctly
* coverage is uploaded and visible
* security scans run on every push
* deploy runs only on tags
* total PR pipeline duration stays under 15 minutes
* local reproduction commands match CI behavior
* branch protection blocks merges that fail any required check
* the architecture wave includes the tests listed in §6.5

---

## 15. Final Rule

The CI/CD pipeline is the merge gate.

The agent must:

* run lint and tests locally before pushing
* never disable a status check
* address every CI failure before requesting review
* keep the pipeline fast (< 15 minutes for PRs)
* respect branch protection rules

A green pipeline does not guarantee correctness, but a red pipeline guarantees the code is not ready to merge.
