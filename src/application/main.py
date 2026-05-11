"""Application entry point.

Boots the Engineering System Designer desktop application:

1. Configures logging (per `specs/10_logging_conventions.md` §4)
2. Creates the `QApplication` instance
3. Bootstraps registries (`shared/registry/`)
4. Constructs `SystemDesignerShell` (the main `QMainWindow`)
5. Enters the Qt event loop

Run with:

    python -m application.main

Or directly:

    python src/application/main.py

References:
----------
* `specs/06_data_flow_and_architecture.md` §2.1 (Application Layer)
* `specs/06_data_flow_and_architecture.md` §3 (Module Initialization Order)
* `specs/10_logging_conventions.md` §9 (Bootstrap Logging)
"""

from __future__ import annotations

import logging
import sys

# Logger is created at module load. Configuration is applied in main().
logger = logging.getLogger("system_designer")


def main() -> int:
    """Boot the Engineering System Designer application.

    Returns:
        Exit code from the Qt event loop.
    """
    # Logging is configured before any other imports that may emit
    # log entries. This ensures the bootstrap sequence is recorded.
    _configure_logging(debug=_is_debug_mode())
    logger.info("Application starting", extra={"event": "system.startup"})

    # Imports are performed inside main() rather than at module top to:
    # 1. keep the module importable for testing without side effects
    # 2. allow logging to be configured before Qt and registry modules
    #    emit their own bootstrap messages
    from PySide6.QtWidgets import QApplication

    from application.SystemDesignerShell import SystemDesignerShell

    app = QApplication(sys.argv)
    app.setOrganizationName("Engineering System Designer")
    app.setApplicationName("System Designer")
    app.setApplicationVersion("0.2.0")

    # SystemDesignerShell.__init__ bootstraps the full Phase-1
    # dependency chain in deterministic order:
    #   ComponentRegistry → WorkspaceModel →
    #   WorkspaceValidatorController → WorkspaceCommandStack →
    #   WorkspaceScene → WorkspaceView → library tree +
    #   info panel docks → status bar + menus.
    # The legacy `(stage_s1)` TODO is closed at S1.10 — registry
    # construction lives inside the shell so tests can wire
    # alternate registries without touching this module.
    shell = SystemDesignerShell()
    shell.show()

    logger.info("Application ready", extra={"event": "system.startup"})
    return app.exec()


def _configure_logging(debug: bool = False) -> None:
    """Configure project loggers per `specs/10_logging_conventions.md` §4.4.

    Args:
        debug: If True, set the root level to DEBUG; otherwise INFO.
    """
    root_level = logging.DEBUG if debug else logging.INFO
    logging.getLogger("system_designer").setLevel(root_level)

    # Engine is dormant in Phase 1; suppress its WARNING-level output
    # since the package itself raises ImportError on access (ADR-001).
    logging.getLogger("shared.engine").setLevel(logging.WARNING)

    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s.%(msecs)03d | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    root_logger = logging.getLogger("system_designer")
    # Avoid duplicate handlers if main() is called more than once
    # (e.g., from tests).
    if not root_logger.handlers:
        root_logger.addHandler(handler)


def _is_debug_mode() -> bool:
    """Return True if `--debug` was passed on the command line."""
    return "--debug" in sys.argv


if __name__ == "__main__":
    sys.exit(main())
