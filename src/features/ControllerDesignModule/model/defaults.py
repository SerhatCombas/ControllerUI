"""Default configuration loader for ControllerDesignModule (S2.B.1).

Materializes `shared/registry/default_config.json` into the S2.A
dataclass families. Used by:

* "New Project" flow — every section gets fresh defaults
* Partial project load — `spec/03 §11.4` "missing sections fall back
  to defaults from `default_config.json`"

The defaults JSON intentionally omits the `id` field on default
controller entries. The loader injects a fresh
`new_controller_id()` so every "New Project" action produces a
unique controller id per ADR-002 (ULIDs are never reused). This
keeps the JSON file usable as a template across projects without
relying on the never-reused promise.

The PlotLayout default section (S2.C) is read alongside the
three S2.B.1 sections; the JSON file now carries all four. The
`DefaultConfiguration` aggregator exposes `plot_layout` as a
fourth field.

References:
----------
* `specs/03_configuration_requirements.md` §13 (Default Configuration)
* `specs/03_configuration_requirements.md` §11.4 (Partial Load Safety)
* `decisions/ADR-002-hybrid-ulid-identity-model.md`
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib.resources import files
from typing import Any

from .controller_settings import ControllerSettings
from .id_generator import new_controller_id
from .io_selection import IOSelection
from .plot_layout import PlotLayout
from .simulation_settings import SimulationSettings

# Resource path inside the installed package. `importlib.resources`
# resolves this to a real filesystem path in editable installs and
# to a packaged-data entry in regular installs (the
# `[tool.setuptools.package-data]` entry in `pyproject.toml`
# ensures both modes work).
_DEFAULT_CONFIG_PACKAGE = "shared.registry"
_DEFAULT_CONFIG_RESOURCE = "default_config.json"


@dataclass(frozen=True)
class DefaultConfiguration:
    """Aggregated Phase-1 defaults from `default_config.json`.

    Returned by `load_default_configuration()`. Each field carries
    a fresh instance — re-calling the loader produces new dataclass
    instances with new generated ULIDs where applicable, so callers
    do not accidentally share mutable state between projects.
    """

    controller_settings: ControllerSettings
    io_selection: IOSelection
    simulation_settings: SimulationSettings
    plot_layout: PlotLayout


def _read_default_payload() -> dict[str, Any]:
    """Read and parse the bundled `default_config.json`."""
    raw = (files(_DEFAULT_CONFIG_PACKAGE) / _DEFAULT_CONFIG_RESOURCE).read_text(encoding="utf-8")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError(
            f"{_DEFAULT_CONFIG_RESOURCE} top-level must be a JSON object; "
            f"got {type(payload).__name__}"
        )
    return payload


def load_default_controller_settings() -> ControllerSettings:
    """Return a fresh `ControllerSettings` from `default_config.json`.

    The default template omits the `id` field on each controller
    entry; the loader injects a freshly generated
    `ctrl_<ULID>` so every call returns distinct controller
    identities. This makes "New Project" safe under ADR-002's
    "never reused" rule.
    """
    payload = _read_default_payload()
    section = payload.get("controller_settings", {})
    if not isinstance(section, dict):
        section = {}
    controllers = section.get("controllers", [])
    if not isinstance(controllers, list):
        controllers = []
    section = dict(section)
    section["controllers"] = [
        {**entry, "id": entry.get("id") or new_controller_id()}
        for entry in controllers
        if isinstance(entry, dict)
    ]
    return ControllerSettings.from_dict(section)


def load_default_io_selection() -> IOSelection:
    """Return a fresh `IOSelection` from `default_config.json`."""
    payload = _read_default_payload()
    section = payload.get("io_selection", {})
    if not isinstance(section, dict):
        section = {}
    return IOSelection.from_dict(section)


def load_default_simulation_settings() -> SimulationSettings:
    """Return a fresh `SimulationSettings` from `default_config.json`."""
    payload = _read_default_payload()
    section = payload.get("simulation_settings", {})
    if not isinstance(section, dict):
        section = {}
    return SimulationSettings.from_dict(section)


def load_default_plot_layout() -> PlotLayout:
    """Return a fresh `PlotLayout` from `default_config.json` (spec §13)."""
    payload = _read_default_payload()
    section = payload.get("plot_layout", {})
    if not isinstance(section, dict):
        section = {}
    return PlotLayout.from_dict(section)


def load_default_configuration() -> DefaultConfiguration:
    """Return all four Phase-1 default sections in one call.

    Convenience aggregator for the "New Project" bootstrap path.
    Each call reads the JSON file once and produces fresh
    dataclass instances; no caching is performed so per-call
    ULID freshness is guaranteed.
    """
    return DefaultConfiguration(
        controller_settings=load_default_controller_settings(),
        io_selection=load_default_io_selection(),
        simulation_settings=load_default_simulation_settings(),
        plot_layout=load_default_plot_layout(),
    )


__all__ = [
    "DefaultConfiguration",
    "load_default_configuration",
    "load_default_controller_settings",
    "load_default_io_selection",
    "load_default_plot_layout",
    "load_default_simulation_settings",
]
