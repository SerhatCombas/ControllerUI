# ADR-012: Project Package Directory Format

**Status:** Accepted  
**Date:** 2026-04-28  
**Deciders:** Serhat Combas  
**Stage:** S2  
**Supersedes:** —  
**Superseded by:** —

## Context

Project files need to store:

* the workspace model (components, connections, validation state)
* configuration data (controller settings, I/O selection, simulation settings, plot layout)
* simulation results (in Phase 2, potentially large numerical arrays)
* stability analysis artifacts (in Phase 2)
* recovery/autosave snapshots
* exports (in Phase 2)

A single JSON file becomes unwieldy:

* large simulation results bloat git diffs
* binary numerical data (HDF5) cannot live in JSON
* recovery files conflict with the main file
* sharing requires sending many files

A directory bundle solves these problems while remaining inspectable.

## Decision

Projects are stored as **directory bundles** with `.systemdesign/` extension:

```
quarter_car.systemdesign/
  project.json              # workspace + configuration (human-diffable JSON)
  schema_version.txt        # quick version check without parsing JSON
  results/                  # simulation results (HDF5, Phase 2)
    sim_01HV...h5
    sim_01HX...h5
  exports/                  # user exports (Phase 2)
  recovery/                 # autosave snapshots (rotating)
    recovery_2026-04-28T14-23-45.json
  metadata.json             # minimal index for fast load preview
```

Rules:

* `project.json` contains workspace and configuration; it is the human-readable, diff-friendly source
* `results/` and `exports/` contain large or binary data
* `recovery/` is rotating (e.g., last 5 snapshots, capped at 50 MB)
* the `.systemdesign/` directory itself is what the user opens; the OS treats it as a folder
* legacy single-file `.json` projects are auto-migrated to the directory format on load

The format is versioned via `schema_version` in `project.json` (currently `0.2.0`). Schema migrations follow `02 §29.3.1`.

## Alternatives Considered

### Alternative 1: Single JSON file

Keep everything in one file.

**Rejected because:**

* Large simulation results destroy diffs
* Binary HDF5 cannot be embedded
* Recovery files conflict with the main file

### Alternative 2: ZIP bundle

Use a ZIP file as the project container (like `.docx`, `.pptx`, `.fdx`).

**Rejected because:**

* Diff-unfriendly (binary)
* Requires unpacking for inspection
* Save operations require atomic ZIP rewrites
* Git LFS unfriendly for collaborative workflows

### Alternative 3: Multiple loose files

Store project as a collection of files in a chosen directory without a wrapper.

**Rejected because:**

* No clear project boundary
* Easy to lose track of which files belong together
* OS file managers cannot show the project as a single entity

## Consequences

### Positive

* `project.json` is git-friendly (text, diffable)
* Large data stays out of git via `.gitignore` patterns on `results/`
* Recovery is isolated from the main file
* Inspectable: users can browse the directory if needed
* Cross-platform (macOS shows `.systemdesign/` as a regular folder unless the application bundles it)

### Negative

* Multi-file save operations need atomicity (write to temp, rename)
* Some users may accidentally enter the directory and modify files
* Sharing requires zipping the directory (handled by `Export Project` action)

### Risks

* External modification during a session
* Mitigation: `error.persistence.external_modification_detected` raised when checksum mismatches
* Recovery file growth
* Mitigation: rotating policy with hard cap

## Related ADRs

- ADR-002 Hybrid ULID Identity Model (referenced in `project.json`)
- ADR-016 channel_selection.kind Schema (used in plot configuration)

## References

- `02_workspace_requirements.md` §29.1 (Project Package Format)
- `06_data_flow_and_architecture.md` §11 (Persistence)
- `07_implementation_order.md` §16.12 (S2 verification)
- `11_error_code_catalog.md` §7.8 (Persistence Errors)
