"""DomainId: physical domain identifier.

Per `02 §13.2` Phase 1 supports two domains:

* `electrical_analog`
* `mechanical_translational`

Future Phase 1.5+ domains (`rotational`, `digital`, `hydraulic`,
`thermal`, signal) are reserved via spec `02 §35` but not added
to the `DomainId` Literal until a future ADR admits them. AI
agents must not silently extend this Literal.

The `DomainId` type is a string alias (Literal) rather than an
enum to ease serialization to JSON `project.json` and to match
the on-the-wire convention in spec examples.

References:
----------
* `specs/02_workspace_requirements.md` §13.2 (Domain Rule)
* `specs/02_workspace_requirements.md` §35 (Domain Extensibility)
* `specs/06_data_flow_and_architecture.md` §5.5 (shared/types)
"""

from __future__ import annotations

from typing import Literal

# Phase-1 supported domains. Future domains live in `02 §35` and
# require a domain-extension ADR before being added here.
DomainId = Literal["electrical_analog", "mechanical_translational"]


__all__ = ["DomainId"]
