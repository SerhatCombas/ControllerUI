from pathlib import Path

from PySide6.QtCore import QByteArray, QMimeData, Qt
from PySide6.QtGui import QDrag, QIcon, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QLineEdit,
    QSizePolicy,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.shared.types.model_component import ModelComponent


class ModelLibraryTree(QTreeWidget):
    mime_type = "application/x-system-model-component"

    def __init__(self, components: list[ModelComponent]) -> None:
        super().__init__()
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.components = {component.component_id: component for component in components}
        self.setHeaderHidden(True)
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragOnly)
        self.setIndentation(16)
        self.populate(components)

    def populate(self, components: list[ModelComponent], filter_text: str = "") -> None:
        self.clear()
        normalized_filter = filter_text.strip().lower()
        grouped: dict[str, dict[str, dict[str, list[ModelComponent]]]] = {}

        for component in components:
            target = f"{component.name} {component.domain} {component.family} {component.category}".lower()
            if normalized_filter and normalized_filter not in target:
                continue

            grouped.setdefault(component.domain, {}).setdefault(component.family, {}).setdefault(
                component.category, []
            ).append(component)

        for domain, families in grouped.items():
            domain_item = QTreeWidgetItem([domain])
            self.addTopLevelItem(domain_item)

            for family, categories in families.items():
                family_item = QTreeWidgetItem([family])
                domain_item.addChild(family_item)

                for category, category_components in categories.items():
                    category_item = QTreeWidgetItem([category])
                    family_item.addChild(category_item)

                    for component in sorted(category_components, key=lambda item: item.name):
                        component_item = QTreeWidgetItem([component.name])
                        component_item.setData(0, Qt.UserRole, component.component_id)
                        component_item.setIcon(0, QIcon(str(component.asset_path)))
                        category_item.addChild(component_item)

        self.expandAll()

    def startDrag(self, supported_actions: Qt.DropActions) -> None:
        item = self.currentItem()
        if item is None:
            return

        component_id = item.data(0, Qt.UserRole)
        if not component_id:
            return

        component = self.components[component_id]
        mime_data = QMimeData()
        mime_data.setData(self.mime_type, QByteArray(component.component_id.encode("utf-8")))

        drag = QDrag(self)
        drag.setMimeData(mime_data)
        drag.setPixmap(QPixmap(str(component.asset_path)).scaled(42, 42, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        drag.exec(Qt.CopyAction)


class ModelLibraryPanel(QWidget):
    def __init__(self, project_root: Path) -> None:
        super().__init__()
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.project_root = project_root
        self.components = discover_model_components(project_root)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search components")

        self.tree = ModelLibraryTree(self.components)
        self.search_input.textChanged.connect(lambda text: self.tree.populate(self.components, text))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        layout.addWidget(self.search_input)
        layout.addWidget(self.tree, 1)


def discover_model_components(project_root: Path) -> list[ModelComponent]:
    models_root = (
        project_root
        / "src"
        / "features"
        / "SystemModelingModule"
        / "panels"
        / "ModelLibraryPanel"
        / "Models"
    )
    components: list[ModelComponent] = []

    for asset_path in sorted(models_root.rglob("*.svg")):
        relative = asset_path.relative_to(models_root)
        if len(relative.parts) < 4:
            continue

        domain, family, category = relative.parts[:3]
        name = asset_path.stem.replace("_", " ")
        component_id = "/".join(relative.with_suffix("").parts)
        components.append(
            ModelComponent(
                component_id=component_id,
                name=to_title(name),
                domain=domain,
                family=family,
                category=category,
                asset_path=asset_path,
            )
        )

    return components


def to_title(value: str) -> str:
    words = []
    for chunk in value.replace("-", " ").split():
        spaced = "".join(f" {char}" if char.isupper() else char for char in chunk).strip()
        words.extend(spaced.split())
    return " ".join(word.capitalize() for word in words)
