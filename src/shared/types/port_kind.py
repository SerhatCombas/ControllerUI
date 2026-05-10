"""PortKind: port-direction enumeration.

Per `02 §13.1`:

* Phase 1 allowed kind: `bidirectional`
* Future kinds (Phase 1.5+, not active): `signal_input`,
  `signal_output`, `physical_conservative`, `probe_output`

All five values are declared in the `PortKind` Literal so the
type system can already model future definitions, but the
registry-side `PortDefinition` schema validation accepts only
`"bidirectional"` in Phase 1. Future kinds become active when a
new ADR opens them; the change is additive at the validator
level, not a schema change.

References:
----------
* `specs/02_workspace_requirements.md` §13 (Port System),
  §13.1 (Port Kinds)
* `specs/06_data_flow_and_architecture.md` §5.5 (shared/types)
"""

from __future__ import annotations

from typing import Literal

# All currently-named port kinds across Phase 1 and the named
# future kinds. Phase 1 active set is just `"bidirectional"`;
# additional kinds are reserved values, not currently accepted by
# the registry validator.
PortKind = Literal[
    "bidirectional",
    "signal_input",
    "signal_output",
    "physical_conservative",
    "probe_output",
]


__all__ = ["PortKind"]
