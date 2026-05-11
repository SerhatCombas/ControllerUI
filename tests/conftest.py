"""Project-level pytest fixtures.

Ensures a `QApplication` exists for the entire test session.
`QGraphicsScene`, `QGraphicsView`, `QGraphicsItem`, and most Qt
widget construction segfaults without a live `QApplication`;
pytest-qt only auto-creates one when the `qtbot` fixture is
requested, but many of our UI tests do not need event-loop
plumbing and just want a quiet `QApplication` in the background.

This fixture is session-scoped and `autouse=True`, so any test
that runs gets the application without explicit opt-in. Tests
that *do* need an event loop or signal-spy harness can request
`qtbot` on top of this — they'll find an application already
constructed.

References:
----------
* `decisions/ADR-003-workspace-ui-data-separation.md` — model is
  headless, but view/scene/item construction is not.
"""

from __future__ import annotations

import sys

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session", autouse=True)
def qapplication_session() -> QApplication:
    """Provide a session-scoped `QApplication` for Qt widget tests.

    Reuses `QApplication.instance()` if pytest-qt or some other
    plugin already created one; otherwise constructs a single
    instance for the whole session. Does not call `exec()` — tests
    that need event-loop processing should request `qtbot` and use
    its `wait*` helpers.

    The fixture does not yield-then-teardown because Qt holds
    global state that other plugins (pytest-qt) may still need
    during teardown; deleting the QApplication would leave dangling
    references.
    """
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app  # type: ignore[return-value]
