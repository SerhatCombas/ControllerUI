"""shared/graph: cross-feature read-only graph value types.

Per `06 §5.3`: derived graph structures and vertex / node value
types that may be read by both `SystemModelingModule` (producer)
and `ControllerDesignModule` (consumer, Phase 2+). Canonical
workspace storage and validation logic live in
`features/SystemModelingModule/model/` per `06 §4.2`.

Public surface:

* `PortRef` — vertex reference value type (re-exported by
  `features/SystemModelingModule/model/connection.py` for
  backwards compatibility).
* `ImplicitNode` — connected port-group node per `02 §17` / `§18`.
* `SystemGraph` — frozen snapshot of an assembled workspace graph
  (Phase 1 minimal: identifier sets + implicit nodes).

The producing class `GraphAssembler` lives in
`features/SystemModelingModule/model/graph_assembler.py` per
`06 §4.2`; this package contains only the value types.
"""

from .implicit_node import ImplicitNode
from .port_ref import PortRef
from .system_graph import SystemGraph

__all__ = [
    "ImplicitNode",
    "PortRef",
    "SystemGraph",
]
