from pathlib import Path

from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QVBoxLayout, QWidget

from src.features.SystemModelingModule.panels.ModelLibraryPanel.model_library_panel import ModelLibraryPanel
from src.features.SystemModelingModule.workspace.BlockDiagramWorkspace.block_diagram_workspace import (
    BlockDiagramWorkspace,
)
from src.features.SystemModelingModule.workspace.BlockDiagramWorkspace.component_inspector_panel import (
    ComponentInspectorPanel,
)
from src.shared.components.collapsible_sidebar import CollapsibleSidebar


class SystemModelingView(QWidget):
    def __init__(self, project_root: Path) -> None:
        super().__init__()
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        library_panel = ModelLibraryPanel(project_root)
        library_panel.setObjectName("ModelLibraryPanel")
        workspace = BlockDiagramWorkspace(library_panel.components)
        workspace.setObjectName("BlockDiagramWorkspace")
        inspector_panel = ComponentInspectorPanel()
        inspector_panel.hide()
        workspace.selection_changed.connect(inspector_panel.show_component)

        library_sidebar = CollapsibleSidebar("Library", library_panel, side="left", expanded=True)

        work_area = QWidget()
        work_area_layout = QHBoxLayout(work_area)
        work_area_layout.setContentsMargins(0, 0, 0, 0)
        work_area_layout.setSpacing(10)
        work_area_layout.addWidget(library_sidebar)
        work_area_layout.addWidget(workspace, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(work_area, 1)
        layout.addWidget(inspector_panel)
