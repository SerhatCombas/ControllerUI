"""Application layer for Engineering System Designer.

Hosts the desktop application entry point, the `SystemDesignerShell`
main window, application bootstrap, and project lifecycle coordination.

The application layer composes feature modules and shared services. It
must not implement component physics, graph assembly, equation
extraction, controller design, or simulation logic. See feature
modules under `features/` for those responsibilities.

References
----------
* `specs/06_data_flow_and_architecture.md` §2.1 (Application Layer)
"""

__all__: list[str] = []
