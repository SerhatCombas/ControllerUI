"""ComponentLibraryTree: drag-source widget for placed component definitions.

Per spec/01 §11 and spec/07 §7.13. The library tree presents the
contents of a `ComponentRegistry` grouped by `library_path` (e.g.,
`("Electrical", "Analog", "Components")`) and produces drag
payloads that the workspace scene accepts via the
`COMPONENT_MIME_TYPE` MIME type wired in S1.9.3.

S1.10 scope: minimal viable widget for the application-shell
manual smoke. Cosmetic polish (SVG icons in items, tree styling,
search filter) lands in S1.11; this widget exists so the
end-to-end drag-drop pipeline (library → drop → `AddComponentCommand`
→ `componentAdded` → scene item) can be exercised in the real
application.

Design notes:

* The widget is intentionally separate from the legacy
  `model_library_panel.py` — that file uses the pre-S1.B
  `ModelComponent` dataclass and a different MIME schema.
  Refitting it inside the same module would mix two patterns
  during the integration cycle; a clean rewrite avoids that
  risk and lets S1.11 retire the legacy file when ready.
* Grouping by `library_path` is hierarchical: each tuple
  element becomes a tree-node level. Definitions whose paths
  share a prefix get the same parent node.

References:
----------
* `specs/01_library_requirements.md` §11 (Library Panel)
* `specs/07_implementation_order.md` §7.13
* `decisions/ADR-021-builtin-component-definitions.md`
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import QByteArray, QMimeData, Qt
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem

from features.SystemModelingModule.workspace.BlockDiagramWorkspace.workspace_scene import (
    COMPONENT_MIME_TYPE,
)

if TYPE_CHECKING:
    from collections.abc import Iterable

    from PySide6.QtWidgets import QWidget

    from shared.registry import ComponentDefinition


# Role under which we stash the dotted-namespace definition id on
# each leaf item. `Qt.UserRole` is the canonical Qt slot for
# per-item user data; using a named alias keeps the lookup
# self-documenting at the call sites.
_DEFINITION_ID_ROLE = Qt.ItemDataRole.UserRole


class ComponentLibraryTree(QTreeWidget):
    """Tree widget that presents component definitions as drag sources.

    Args:
        definitions: Iterable of `ComponentDefinition` records.
            Typically `BUILTIN_COMPONENT_DEFINITIONS` from the
            wired registry. The tree builds its hierarchy by
            walking each definition's `library_path` and
            grouping under shared prefixes.
        parent: Optional Qt parent widget.

    Notes:
        * The widget enables drag (but not drop) — drops belong
          to the workspace scene.
        * Drag payload format matches `COMPONENT_MIME_TYPE`
          from S1.9.3: a single MIME entry with the dotted
          definition id (e.g.,
          `"electrical.analog.components.resistor"`) as
          UTF-8-encoded bytes.
    """

    def __init__(
        self,
        definitions: Iterable[ComponentDefinition],
        parent: QWidget | None = None,
    ) -> None:
        """Construct, populate the tree, and configure drag mode."""
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setDragEnabled(True)
        self.setDragDropMode(QTreeWidget.DragDropMode.DragOnly)
        # Build the hierarchy.
        self._definitions: dict[str, ComponentDefinition] = {}
        self._populate(definitions)
        self.expandAll()

    @property
    def definitions(self) -> dict[str, ComponentDefinition]:
        """Read-only mapping of `definition_id` → `ComponentDefinition`."""
        return dict(self._definitions)

    def _populate(self, definitions: Iterable[ComponentDefinition]) -> None:
        """Build the tree nodes from a definition iterable.

        Walks each definition's `library_path` tuple element by
        element; nodes are created lazily as new prefixes appear.
        Leaf items carry the `definition_id` on the
        `_DEFINITION_ID_ROLE` data slot for retrieval at drag
        start.
        """
        # Map: tuple-prefix → parent QTreeWidgetItem so subsequent
        # children of the same path share the same parent.
        prefix_nodes: dict[tuple[str, ...], QTreeWidgetItem | None] = {(): None}
        for definition in definitions:
            self._definitions[definition.id] = definition
            # Walk path prefixes left-to-right, creating intermediate
            # tree nodes as needed.
            parent_item: QTreeWidgetItem | None = None
            for depth in range(1, len(definition.library_path) + 1):
                prefix = definition.library_path[:depth]
                node = prefix_nodes.get(prefix)
                if node is None:
                    node = QTreeWidgetItem([prefix[-1]])
                    if parent_item is None:
                        self.addTopLevelItem(node)
                    else:
                        parent_item.addChild(node)
                    prefix_nodes[prefix] = node
                parent_item = node
            # Add the leaf item for the definition itself.
            leaf = QTreeWidgetItem([definition.display_name])
            leaf.setData(0, _DEFINITION_ID_ROLE, definition.id)
            if parent_item is None:
                self.addTopLevelItem(leaf)
            else:
                parent_item.addChild(leaf)

    def selected_definition_id(self) -> str | None:
        """Return the `definition_id` of the currently selected leaf, or `None`.

        Returns `None` when no item is selected or the selected
        item is an internal (non-leaf) node. Test convenience
        and a hook for keyboard-based "place selected" actions
        in later stages.
        """
        item = self.currentItem()
        if item is None:
            return None  # type: ignore[unreachable]
        data = item.data(0, _DEFINITION_ID_ROLE)
        if not isinstance(data, str):
            return None
        return data

    def startDrag(  # noqa: N802 — Qt API override
        self,
        supported_actions: Qt.DropAction,
    ) -> None:
        """Override the drag start to produce a `COMPONENT_MIME_TYPE` payload.

        Only leaf items (those with a `definition_id` on the
        user-data role) initiate a drag; clicks on parent
        category nodes do nothing.
        """
        definition_id = self.selected_definition_id()
        if definition_id is None:
            return
        mime = QMimeData()
        mime.setData(
            COMPONENT_MIME_TYPE,
            QByteArray(definition_id.encode("utf-8")),
        )
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(supported_actions)


__all__ = ["ComponentLibraryTree"]
