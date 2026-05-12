"""Unit tests for `WorkspaceReactivityObserver` (S2.B.3).

These tests use a stub QObject as the workspace stand-in so the
observer's behavior can be exercised without booting a real
`WorkspaceModel`. The companion integration test in
`tests/integration/test_workspace_reactivity_observer.py` covers
the real-cross-feature path.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from PySide6.QtCore import QObject, Signal

from features.ControllerDesignModule.model import (
    ConfigurationModel,
    ControllerSettings,
    IOEntry,
    IOSelection,
    IOSourcePortRef,
    SimulationSettings,
)
from features.ControllerDesignModule.observers import WorkspaceReactivityObserver
from shared.graph.port_ref import PortRef

ConfigurationFactory = Callable[..., ConfigurationModel]


class _StubWorkspace(QObject):
    """Minimum duck-typed workspace exposing only `componentRemoved`."""

    componentRemoved = Signal(str)  # noqa: N815 — Qt signal naming


def _make_entry(entry_id: str, component_id: str, port_id: str = "p") -> IOEntry:
    return IOEntry(
        id=entry_id,
        source=IOSourcePortRef(
            port_ref=PortRef(component_id=component_id, port_id=port_id),
            variable="across",
        ),
    )


@pytest.fixture
def configuration_factory() -> ConfigurationFactory:
    """Build a fresh `ConfigurationModel` populated with the given I/O entries."""

    def _factory(
        inputs: tuple[IOEntry, ...] = (),
        outputs: tuple[IOEntry, ...] = (),
    ) -> ConfigurationModel:
        return ConfigurationModel(
            controller_settings=ControllerSettings(),
            io_selection=IOSelection(inputs=inputs, outputs=outputs),
            simulation_settings=SimulationSettings(),
        )

    return _factory


# ====================================================================== #
# Construction + attachment
# ====================================================================== #


@pytest.mark.unit
def test_observer_construction_does_not_attach(configuration_factory: ConfigurationFactory) -> None:
    """Construction is decoupled from subscription per the docstring."""
    config = configuration_factory()
    observer = WorkspaceReactivityObserver(configuration=config)
    assert observer.configuration is config


@pytest.mark.unit
def test_observer_attaches_to_workspace_signal(configuration_factory: ConfigurationFactory) -> None:
    """`attach_to_workspace_signals` wires `componentRemoved` to the slot."""
    config = configuration_factory(inputs=(_make_entry("ioin_X", "cmp_A"),))
    observer = WorkspaceReactivityObserver(configuration=config)
    workspace = _StubWorkspace()
    observer.attach_to_workspace_signals(workspace)
    # Emit and verify reactivity end-to-end through the wired connection.
    workspace.componentRemoved.emit("cmp_A")
    assert config.io_selection.inputs[0].status == "stale"


# ====================================================================== #
# Stale-detection rules
# ====================================================================== #


@pytest.mark.unit
def test_referenced_input_entry_gets_marked_stale(
    configuration_factory: ConfigurationFactory,
) -> None:
    """A single input entry pointing at the removed component → stale."""
    config = configuration_factory(inputs=(_make_entry("ioin_X", "cmp_A"),))
    observer = WorkspaceReactivityObserver(configuration=config)
    workspace = _StubWorkspace()
    observer.attach_to_workspace_signals(workspace)

    workspace.componentRemoved.emit("cmp_A")

    assert config.io_selection.inputs[0].status == "stale"


@pytest.mark.unit
def test_referenced_output_entry_gets_marked_stale(
    configuration_factory: ConfigurationFactory,
) -> None:
    """Output entries are checked symmetrically with inputs."""
    config = configuration_factory(outputs=(_make_entry("ioout_Y", "cmp_B"),))
    observer = WorkspaceReactivityObserver(configuration=config)
    workspace = _StubWorkspace()
    observer.attach_to_workspace_signals(workspace)

    workspace.componentRemoved.emit("cmp_B")

    assert config.io_selection.outputs[0].status == "stale"


@pytest.mark.unit
def test_unreferenced_components_do_not_emit_signal(
    configuration_factory: ConfigurationFactory,
) -> None:
    """A componentRemoved with no matching entry → no mutation, no signal."""
    config = configuration_factory(inputs=(_make_entry("ioin_X", "cmp_A"),))
    observer = WorkspaceReactivityObserver(configuration=config)
    workspace = _StubWorkspace()
    observer.attach_to_workspace_signals(workspace)

    received: list[IOSelection] = []
    config.ioSelectionChanged.connect(received.append)

    workspace.componentRemoved.emit("cmp_UNRELATED")

    assert received == []
    assert config.io_selection.inputs[0].status == "valid"


@pytest.mark.unit
def test_multiple_matching_entries_all_get_flagged(
    configuration_factory: ConfigurationFactory,
) -> None:
    """Every entry pointing at the removed component is flagged."""
    config = configuration_factory(
        inputs=(
            _make_entry("ioin_1", "cmp_A"),
            _make_entry("ioin_2", "cmp_A"),
        ),
        outputs=(_make_entry("ioout_1", "cmp_A"),),
    )
    observer = WorkspaceReactivityObserver(configuration=config)
    workspace = _StubWorkspace()
    observer.attach_to_workspace_signals(workspace)

    workspace.componentRemoved.emit("cmp_A")

    assert all(e.status == "stale" for e in config.io_selection.inputs)
    assert all(e.status == "stale" for e in config.io_selection.outputs)


@pytest.mark.unit
def test_mixed_matching_and_unrelated_entries(configuration_factory: ConfigurationFactory) -> None:
    """Only the matching entries get flagged; unrelated entries stay valid."""
    config = configuration_factory(
        inputs=(
            _make_entry("ioin_A", "cmp_A"),
            _make_entry("ioin_B", "cmp_B"),
        ),
    )
    observer = WorkspaceReactivityObserver(configuration=config)
    workspace = _StubWorkspace()
    observer.attach_to_workspace_signals(workspace)

    workspace.componentRemoved.emit("cmp_A")

    assert config.io_selection.inputs[0].status == "stale"
    assert config.io_selection.inputs[1].status == "valid"


@pytest.mark.unit
def test_already_stale_entry_idempotent(configuration_factory: ConfigurationFactory) -> None:
    """Re-removal of the same component does not fire `ioSelectionChanged`.

    ADR-020 transition-only rule: the second `componentRemoved` event
    finds the entries already stale, produces an equal IOSelection,
    and `set_io_selection` swallows the no-op write.
    """
    config = configuration_factory(inputs=(_make_entry("ioin_X", "cmp_A"),))
    observer = WorkspaceReactivityObserver(configuration=config)
    workspace = _StubWorkspace()
    observer.attach_to_workspace_signals(workspace)

    received: list[IOSelection] = []
    config.ioSelectionChanged.connect(received.append)

    workspace.componentRemoved.emit("cmp_A")
    workspace.componentRemoved.emit("cmp_A")  # second time — already stale

    assert len(received) == 1
    assert config.io_selection.inputs[0].status == "stale"


@pytest.mark.unit
def test_signal_emission_payload_is_full_io_selection(
    configuration_factory: ConfigurationFactory,
) -> None:
    """The emitted signal payload carries the full new IOSelection."""
    config = configuration_factory(
        inputs=(
            _make_entry("ioin_A", "cmp_A"),
            _make_entry("ioin_B", "cmp_B"),
        ),
    )
    observer = WorkspaceReactivityObserver(configuration=config)
    workspace = _StubWorkspace()
    observer.attach_to_workspace_signals(workspace)

    received: list[IOSelection] = []
    config.ioSelectionChanged.connect(received.append)

    workspace.componentRemoved.emit("cmp_A")

    assert len(received) == 1
    payload = received[0]
    assert isinstance(payload, IOSelection)
    assert payload.inputs[0].status == "stale"
    assert payload.inputs[1].status == "valid"


# ====================================================================== #
# Metadata / extensions preservation
# ====================================================================== #


@pytest.mark.unit
def test_metadata_and_extensions_survive_stale_flip(
    configuration_factory: ConfigurationFactory,
) -> None:
    """Stale-flip mutation preserves IOSelection top-level fields."""
    config = ConfigurationModel(
        controller_settings=ControllerSettings(),
        io_selection=IOSelection(
            inputs=(_make_entry("ioin_X", "cmp_A"),),
            metadata={"author": "test"},
            extensions={"future_field": 42},
        ),
        simulation_settings=SimulationSettings(),
    )
    observer = WorkspaceReactivityObserver(configuration=config)
    workspace = _StubWorkspace()
    observer.attach_to_workspace_signals(workspace)

    workspace.componentRemoved.emit("cmp_A")

    assert config.io_selection.metadata == {"author": "test"}
    assert config.io_selection.extensions == {"future_field": 42}
