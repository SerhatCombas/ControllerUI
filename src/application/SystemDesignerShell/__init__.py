"""SystemDesignerShell — main application window.

`SystemDesignerShell` is the top-level `QMainWindow` that composes:

* the System Modeling area (left side):
  - ModelLibraryPanel
  - BlockDiagramWorkspace (canvas)
  - ComponentInfoPanel (bottom)
  - ModelEquationsPanel (right edge, collapsible)
* the System Controlling area (right side):
  - ConfigurationPanel (Controller / I/O / Simulation / Plot Layout tabs)
  - ResultsPanel (4-slot unified plot grid)
  - Run Simulation button (bottom)
* the global status bar (bottom of window)

References
----------
* `specs/02_workspace_requirements.md` §32.2 (Status Bar)
* `specs/06_data_flow_and_architecture.md` §2.1 (Application Layer)
* `specs/06_data_flow_and_architecture.md` §3 (Module Initialization Order)
"""

from __future__ import annotations

from .main_window import SystemDesignerShell

__all__ = [
    "SystemDesignerShell",
]
