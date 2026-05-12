"""I/O selection dataclasses (S2.A scaffold).

Per spec/03 §6 and the S2 sub-commit plan. Phase 1 stores and
round-trips I/O entries, plus a tagged-union `source` discriminator
that today carries one variant (`port_ref`) and reserves the
schema for Phase-2 variants (`probe_ref`, `state_variable_ref`,
`implicit_node_ref`, `expression_ref`, `engine_output_ref`).

Design choices (decisions K2 / K3 from the S2.A pre-scan):

* **Composition over duplication for port references.**
  `IOSourcePortRef` composes a `PortRef` (the canonical
  `(component_id, port_id)` identity from `shared/graph`) with the
  Bond-Graph `variable` discriminator. PortRef validators wired in
  S1.5 (and reused by `AddConnectionCommand`) remain authoritative;
  the JSON serializer flattens the pair to sibling fields to keep
  the on-disk shape from spec/03 §6.2 verbatim.
* **Discriminated union via the `kind` field.** Phase 1's union
  alias `IOSource = IOSourcePortRef` widens in Phase 2 to a
  proper `Union[...]`. `IOSource.from_dict` dispatches on
  `kind`; unknown variants raise so the caller can surface a
  forward-compat warning per spec/03 §10.1.
* **Shared `IOEntry` dataclass for inputs and outputs.** The two
  bucket lists differ only in the id-prefix convention
  (`ioin_<ULID>` vs `ioout_<ULID>`); inlining one dataclass keeps
  serialization symmetric.

References:
----------
* `specs/03_configuration_requirements.md` §6 (I/O Selection)
* `specs/03_configuration_requirements.md` §6.4 (Bond Graph variable)
* `specs/03_configuration_requirements.md` §6.8 (Source Kinds)
* `specs/03_configuration_requirements.md` §11.3 (Forward Compat)
* `decisions/ADR-002-hybrid-ulid-identity-model.md`
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Literal, TypeAlias

from shared.graph.port_ref import PortRef

# Bond-Graph variable kinds per spec/03 §6.4. Stored as `Literal`
# because the spec calls it out as a closed set; unknown values
# loaded from a newer schema raise during `from_dict` so S2.B's
# validator can surface a warning.
BondGraphVariable = Literal["across", "through", "derived"]

# Status enum per spec/03 §6.3. Stale references survive
# persistence (§6.7) so the loader does not drop them silently.
IOEntryStatus = Literal["valid", "stale", "invalid"]


@dataclass(frozen=True)
class IOSourcePortRef:
    """Phase-1 I/O source variant referencing a workspace port.

    Composes a canonical `PortRef` with the Bond-Graph variable
    discriminator. The `kind` field carries the union tag for
    forward-compat dispatch:

        match source.kind:
            case "port_ref": ...
            case "probe_ref": ...        # Phase 2
            case "state_variable_ref": ...  # Phase 2

    JSON serialization flattens `port_ref` into sibling
    `component_id` / `port_id` fields per spec/03 §6.2:

        {
          "kind": "port_ref",
          "component_id": "cmp_...",
          "port_id": "p",
          "variable": "across"
        }
    """

    port_ref: PortRef
    variable: BondGraphVariable
    kind: Literal["port_ref"] = "port_ref"

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the flat-sibling JSON shape from spec/03 §6.2."""
        return {
            "kind": self.kind,
            "component_id": self.port_ref.component_id,
            "port_id": self.port_ref.port_id,
            "variable": self.variable,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> IOSourcePortRef:
        """Inverse of `to_dict`. Required fields missing → `KeyError`.

        `variable` outside `{"across", "through", "derived"}`
        raises `ValueError` so loaders can surface the issue;
        validation severity decisions live in S2.B.
        """
        kind = payload.get("kind", "port_ref")
        if kind != "port_ref":
            raise ValueError(f"IOSourcePortRef.from_dict expected kind='port_ref', got {kind!r}")
        component_id = payload.get("component_id")
        port_id = payload.get("port_id")
        variable = payload.get("variable")
        if not isinstance(component_id, str) or not component_id:
            raise KeyError("IOSourcePortRef payload missing required 'component_id'")
        if not isinstance(port_id, str) or not port_id:
            raise KeyError("IOSourcePortRef payload missing required 'port_id'")
        if variable not in {"across", "through", "derived"}:
            raise ValueError(
                f"IOSourcePortRef.variable must be one of 'across'/'through'"
                f"/'derived'; got {variable!r}"
            )
        return cls(
            port_ref=PortRef(component_id=component_id, port_id=port_id),
            variable=variable,  # narrowed by check above  # type: ignore[arg-type]
        )


# Phase-1 union: a single variant. Phase 2 widens this to
# `IOSourcePortRef | IOSourceProbeRef | IOSourceStateRef | ...`
# without renaming the alias.
IOSource: TypeAlias = IOSourcePortRef


def io_source_from_dict(payload: dict[str, Any]) -> IOSource:
    """Tagged-union dispatcher on `payload['kind']`.

    Phase 1 supports `"port_ref"` only. Unknown kinds raise
    `ValueError` so the loader can surface a warning per
    spec/03 §6.8 and §12.2. (Persistence-layer "preserve raw
    payload" handling for unsupported variants is S2.E's job.)
    """
    kind = payload.get("kind", "port_ref")
    if kind == "port_ref":
        return IOSourcePortRef.from_dict(payload)
    raise ValueError(f"Unknown I/O source kind {kind!r} (Phase 1 supports 'port_ref')")


# Field set that `IOEntry.from_dict` recognizes; anything else
# goes into `extensions` for forward-compat preservation.
_IO_ENTRY_KNOWN_FIELDS: frozenset[str] = frozenset(
    {
        "id",
        "display_name",
        "source",
        "quantity",
        "unit",
        "status",
        "metadata",
        "extensions",
    }
)

_IO_SELECTION_KNOWN_FIELDS: frozenset[str] = frozenset(
    {
        "inputs",
        "outputs",
        "metadata",
        "extensions",
    }
)


@dataclass(frozen=True)
class IOEntry:
    """One input or output entry inside `IOSelection`.

    The same dataclass serves both buckets — input vs output is
    encoded in the id prefix (`ioin_<ULID>` / `ioout_<ULID>`) and
    the parent list (`IOSelection.inputs` vs `.outputs`).
    """

    id: str
    source: IOSource
    display_name: str = ""
    quantity: str = ""
    unit: str = ""
    status: IOEntryStatus = "valid"
    metadata: dict[str, Any] = field(default_factory=dict)
    extensions: dict[str, Any] = field(default_factory=dict)

    def with_updated(self, **changes: Any) -> IOEntry:
        """Return a copy with `changes` applied (immutability-friendly)."""
        return replace(self, **changes)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the spec/03 §6.2 JSON form."""
        return {
            "id": self.id,
            "display_name": self.display_name,
            "source": self.source.to_dict(),
            "quantity": self.quantity,
            "unit": self.unit,
            "status": self.status,
            "metadata": dict(self.metadata),
            "extensions": dict(self.extensions),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> IOEntry:
        """Inverse of `to_dict`. Required: `id` + `source`."""
        raw_id = payload.get("id")
        if not isinstance(raw_id, str) or not raw_id:
            raise KeyError("IOEntry payload missing required 'id' field")
        source_payload = payload.get("source")
        if not isinstance(source_payload, dict):
            raise KeyError("IOEntry payload missing required 'source' object")
        source = io_source_from_dict(source_payload)
        status_raw = payload.get("status", "valid")
        if status_raw not in {"valid", "stale", "invalid"}:
            raise ValueError(
                f"IOEntry.status must be 'valid'/'stale'/'invalid'; got {status_raw!r}"
            )
        carry = {k: v for k, v in payload.items() if k not in _IO_ENTRY_KNOWN_FIELDS}
        extensions_in: dict[str, Any] = (
            dict(payload["extensions"]) if isinstance(payload.get("extensions"), dict) else {}
        )
        extensions_in.update(carry)
        return cls(
            id=raw_id,
            source=source,
            display_name=str(payload.get("display_name", "")),
            quantity=str(payload.get("quantity", "")),
            unit=str(payload.get("unit", "")),
            status=status_raw,  # narrowed above # type: ignore[arg-type]
            metadata=dict(payload.get("metadata", {}) or {}),
            extensions=extensions_in,
        )


@dataclass(frozen=True)
class IOSelection:
    """Top-level I/O selection container (spec/03 §6.2)."""

    inputs: tuple[IOEntry, ...] = ()
    outputs: tuple[IOEntry, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    extensions: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------ #
    # Immutable update helpers
    # ------------------------------------------------------------------ #

    def with_input_added(self, entry: IOEntry) -> IOSelection:
        """Return a copy with `entry` appended to `inputs`."""
        return replace(self, inputs=(*self.inputs, entry))

    def with_input_removed(self, entry_id: str) -> IOSelection:
        """Return a copy with the input matching `entry_id` removed."""
        return replace(self, inputs=tuple(e for e in self.inputs if e.id != entry_id))

    def with_output_added(self, entry: IOEntry) -> IOSelection:
        """Return a copy with `entry` appended to `outputs`."""
        return replace(self, outputs=(*self.outputs, entry))

    def with_output_removed(self, entry_id: str) -> IOSelection:
        """Return a copy with the output matching `entry_id` removed."""
        return replace(self, outputs=tuple(e for e in self.outputs if e.id != entry_id))

    # ------------------------------------------------------------------ #
    # Serialization
    # ------------------------------------------------------------------ #

    def to_dict(self) -> dict[str, Any]:
        """Serialize to the spec/03 §6.2 JSON form."""
        return {
            "inputs": [e.to_dict() for e in self.inputs],
            "outputs": [e.to_dict() for e in self.outputs],
            "metadata": dict(self.metadata),
            "extensions": dict(self.extensions),
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> IOSelection:
        """Inverse of `to_dict`. Missing fields fall back to defaults."""
        inputs_raw = payload.get("inputs", [])
        outputs_raw = payload.get("outputs", [])
        if not isinstance(inputs_raw, list):
            inputs_raw = []
        if not isinstance(outputs_raw, list):
            outputs_raw = []
        inputs = tuple(IOEntry.from_dict(entry) for entry in inputs_raw if isinstance(entry, dict))
        outputs = tuple(
            IOEntry.from_dict(entry) for entry in outputs_raw if isinstance(entry, dict)
        )
        carry = {k: v for k, v in payload.items() if k not in _IO_SELECTION_KNOWN_FIELDS}
        extensions_in: dict[str, Any] = (
            dict(payload["extensions"]) if isinstance(payload.get("extensions"), dict) else {}
        )
        extensions_in.update(carry)
        return cls(
            inputs=inputs,
            outputs=outputs,
            metadata=dict(payload.get("metadata", {}) or {}),
            extensions=extensions_in,
        )


__all__ = [
    "BondGraphVariable",
    "IOEntry",
    "IOEntryStatus",
    "IOSelection",
    "IOSource",
    "IOSourcePortRef",
    "io_source_from_dict",
]
