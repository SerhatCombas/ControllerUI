from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QLabel, QSizePolicy, QWidget

from src.features.SystemModelingModule.panels.ModelLibraryPanel.model_library_panel import ModelLibraryTree
from src.shared.types.model_component import ModelComponent


class WorkspaceComponent(QLabel):
    def __init__(self, component: ModelComponent, parent: QWidget) -> None:
        super().__init__(parent)
        self.component = component
        self.is_selected = False
        self.setToolTip(component.name)
        self.setAlignment(Qt.AlignCenter)
        self.setPixmap(QPixmap(str(component.asset_path)).scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.setFixedSize(96, 82)
        self.apply_selection_style()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.parent().select_component(self)
        super().mousePressEvent(event)

    def set_selected(self, is_selected: bool) -> None:
        self.is_selected = is_selected
        self.apply_selection_style()

    def apply_selection_style(self) -> None:
        border = "2px solid #4a90e2" if self.is_selected else "1px solid #c7d2dd"
        self.setStyleSheet(
            f"""
            QLabel {{
                background: #ffffff;
                border: {border};
                border-radius: 6px;
            }}
            """
        )


class BlockDiagramWorkspace(QWidget):
    selection_changed = Signal(object)

    def __init__(self, components: list[ModelComponent]) -> None:
        super().__init__()
        self.components = {component.component_id: component for component in components}
        self.selected_node: WorkspaceComponent | None = None
        self.setAcceptDrops(True)
        self.setMinimumSize(520, 640)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setStyleSheet("background: #f8fbff;")

        self.hint = QLabel("Drag components from the library into the workspace.", self)
        self.hint.setAlignment(Qt.AlignCenter)
        self.hint.setStyleSheet("color: #75808a; background: transparent; border: none;")

    def mousePressEvent(self, event) -> None:
        child = self.childAt(event.position().toPoint())
        if event.button() == Qt.LeftButton and child is None:
            self.clear_selection()
        super().mousePressEvent(event)

    def resizeEvent(self, event) -> None:
        self.hint.setGeometry(self.rect())
        super().resizeEvent(event)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasFormat(ModelLibraryTree.mime_type):
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        component_id = bytes(event.mimeData().data(ModelLibraryTree.mime_type)).decode("utf-8")
        component = self.components.get(component_id)
        if component is None:
            return

        self.hint.hide()
        node = WorkspaceComponent(component, self)
        position = event.position().toPoint()
        node.move(max(8, position.x() - 48), max(8, position.y() - 41))
        node.show()
        self.select_component(node)
        event.acceptProposedAction()

    def select_component(self, node: WorkspaceComponent) -> None:
        if self.selected_node is not None and self.selected_node is not node:
            self.selected_node.set_selected(False)
        self.selected_node = node
        node.set_selected(True)
        self.selection_changed.emit(node.component)

    def clear_selection(self) -> None:
        if self.selected_node is not None:
            self.selected_node.set_selected(False)
        self.selected_node = None
        self.selection_changed.emit(None)

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setPen(QPen(Qt.GlobalColor.lightGray, 1))
        step = 24
        for x in range(0, self.width(), step):
            painter.drawLine(x, 0, x, self.height())
        for y in range(0, self.height(), step):
            painter.drawLine(0, y, self.width(), y)
