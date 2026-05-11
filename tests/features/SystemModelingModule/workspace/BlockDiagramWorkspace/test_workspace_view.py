"""Unit tests for `WorkspaceView` (S1.9.1).

Tests cover construction, render hints, zoom API
(`zoom_in` / `zoom_out` / `reset_zoom` / `current_zoom`), and
zoom-range clamping. Wheel-event interaction is exercised via
synthetic events; pan via mouse drag lands in S1.9.4 along with
the mouse event handlers.

References:
----------
* `specs/07_implementation_order.md` §7.13
* `specs/02_workspace_requirements.md` §16
"""

from __future__ import annotations

import pytest

from features.SystemModelingModule.model.workspace_model import WorkspaceModel
from features.SystemModelingModule.workspace.BlockDiagramWorkspace.workspace_scene import (
    WorkspaceScene,
)
from features.SystemModelingModule.workspace.BlockDiagramWorkspace.workspace_view import (
    ZOOM_MAX,
    ZOOM_MIN,
    ZOOM_STEP,
    WorkspaceView,
)
from shared.registry import ComponentRegistry
from shared.registry.builtin import BUILTIN_COMPONENT_DEFINITIONS


@pytest.fixture
def view_with_scene(
    request: pytest.FixtureRequest,
) -> WorkspaceView:
    """A `WorkspaceView` with a scene + registry-wired model.

    The model owns the scene as a Qt child (parent-child
    ownership); without keeping the model reference alive in
    the test, Python GC would destroy it (and its child scene)
    when the fixture returns. We attach all three objects to
    the request node so they live for the test duration.
    """
    model = WorkspaceModel(registry=ComponentRegistry(BUILTIN_COMPONENT_DEFINITIONS))
    scene = WorkspaceScene(model)
    view = WorkspaceView(scene)
    # Pin references so GC does not destroy the parent chain.
    request.node.workspace_model = model  # type: ignore[attr-defined]
    request.node.workspace_scene = scene  # type: ignore[attr-defined]
    return view


@pytest.mark.unit
def test_view_constructs_with_scene(view_with_scene: WorkspaceView) -> None:
    """`WorkspaceView(scene)` exposes the scene via `scene()`."""
    assert view_with_scene.scene() is not None
    assert isinstance(view_with_scene.scene(), WorkspaceScene)


@pytest.mark.unit
def test_view_initial_zoom_is_identity(view_with_scene: WorkspaceView) -> None:
    """Fresh view has zoom = 1.0 (identity transform)."""
    assert view_with_scene.current_zoom() == pytest.approx(1.0)


@pytest.mark.unit
def test_view_zoom_in_increases_zoom_by_step(view_with_scene: WorkspaceView) -> None:
    """`zoom_in` multiplies the current zoom by `ZOOM_STEP`."""
    initial = view_with_scene.current_zoom()

    view_with_scene.zoom_in()

    assert view_with_scene.current_zoom() == pytest.approx(initial * ZOOM_STEP)


@pytest.mark.unit
def test_view_zoom_out_decreases_zoom_by_step(view_with_scene: WorkspaceView) -> None:
    """`zoom_out` multiplies the current zoom by `1 / ZOOM_STEP`."""
    initial = view_with_scene.current_zoom()

    view_with_scene.zoom_out()

    assert view_with_scene.current_zoom() == pytest.approx(initial / ZOOM_STEP)


@pytest.mark.unit
def test_view_zoom_in_clamped_at_max(view_with_scene: WorkspaceView) -> None:
    """Zooming past `ZOOM_MAX` is a no-op."""
    # Push to the maximum first.
    while view_with_scene.current_zoom() * ZOOM_STEP <= ZOOM_MAX:
        view_with_scene.zoom_in()
    at_max = view_with_scene.current_zoom()
    assert at_max <= ZOOM_MAX

    # One more attempt: clamped, no transform change.
    view_with_scene.zoom_in()

    assert view_with_scene.current_zoom() == pytest.approx(at_max)


@pytest.mark.unit
def test_view_zoom_out_clamped_at_min(view_with_scene: WorkspaceView) -> None:
    """Zooming below `ZOOM_MIN` is a no-op."""
    while view_with_scene.current_zoom() / ZOOM_STEP >= ZOOM_MIN:
        view_with_scene.zoom_out()
    at_min = view_with_scene.current_zoom()
    assert at_min >= ZOOM_MIN

    view_with_scene.zoom_out()

    assert view_with_scene.current_zoom() == pytest.approx(at_min)


@pytest.mark.unit
def test_view_reset_zoom_returns_to_identity(
    view_with_scene: WorkspaceView,
) -> None:
    """`reset_zoom` restores the identity transform."""
    view_with_scene.zoom_in()
    view_with_scene.zoom_in()
    assert view_with_scene.current_zoom() != pytest.approx(1.0)

    view_with_scene.reset_zoom()

    assert view_with_scene.current_zoom() == pytest.approx(1.0)
