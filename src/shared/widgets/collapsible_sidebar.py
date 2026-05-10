from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class CollapsedSidebarRail(QWidget):
    def __init__(self, title: str, side: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.title = title
        self.side = side
        self.setObjectName("CollapsedSidebarRail")
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(f"Open {title}")

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.parent().expand()
        super().mousePressEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect().adjusted(5, 5, -5, -5)
        painter.setBrush(QColor("#252729"))
        painter.setPen(QPen(QColor("#464b50"), 1))
        painter.drawRoundedRect(rect, 7, 7)

        accent_x = rect.left() + 5 if self.side == "left" else rect.right() - 5
        painter.setPen(QPen(QColor("#4a90e2"), 2))
        painter.drawLine(accent_x, rect.top() + 14, accent_x, rect.bottom() - 14)

        painter.setPen(QPen(QColor("#d8dde2")))
        painter.translate(self.width() / 2, self.height() / 2)
        painter.rotate(-90)
        text_rect = QRect(-self.height() // 2, -self.width() // 2, self.height(), self.width())
        painter.drawText(text_rect, Qt.AlignCenter, self.title)


class CollapsibleSidebar(QFrame):
    expanded_width = 300
    collapsed_width = 44

    def __init__(
        self, title: str, content: QWidget, side: str = "left", expanded: bool = True
    ) -> None:
        super().__init__()
        self.title = title
        self.side = side
        self.content = content
        self.is_expanded = expanded
        self.setObjectName("CollapsibleSidebar")
        self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)

        self.toggle_button = QPushButton("‹" if side == "right" else "›")
        self.toggle_button.setObjectName("SidebarToggleButton")
        self.toggle_button.setFixedSize(24, 24)
        self.toggle_button.setToolTip(f"Toggle {title}")
        self.toggle_button.clicked.connect(self.toggle)

        self.title_label = QLabel(title)
        self.title_label.setObjectName("SidebarTitle")

        header = QWidget()
        header.setObjectName("SidebarHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(10, 8, 10, 8)
        header_layout.setSpacing(8)

        if side == "right":
            header_layout.addWidget(self.toggle_button)
            header_layout.addWidget(self.title_label, 1)
        else:
            header_layout.addWidget(self.title_label, 1)
            header_layout.addWidget(self.toggle_button)

        self.expanded_page = QWidget()
        expanded_layout = QVBoxLayout(self.expanded_page)
        expanded_layout.setContentsMargins(0, 0, 0, 0)
        expanded_layout.setSpacing(0)
        expanded_layout.addWidget(header)
        expanded_layout.addWidget(content, 1)

        self.collapsed_page = CollapsedSidebarRail(title, side, self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.expanded_page)
        layout.addWidget(self.collapsed_page)

        self.apply_state()

    def toggle(self) -> None:
        self.is_expanded = not self.is_expanded
        self.apply_state()

    def expand(self) -> None:
        self.is_expanded = True
        self.apply_state()

    def collapse(self) -> None:
        self.is_expanded = False
        self.apply_state()

    def apply_state(self) -> None:
        self.expanded_page.setVisible(self.is_expanded)
        self.collapsed_page.setVisible(not self.is_expanded)
        self.setFixedWidth(self.expanded_width if self.is_expanded else self.collapsed_width)
        self.toggle_button.setText("‹" if self.side == "left" else "›")
