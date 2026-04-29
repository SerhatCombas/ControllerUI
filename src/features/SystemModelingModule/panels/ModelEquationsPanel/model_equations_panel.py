from PySide6.QtWidgets import QPlainTextEdit, QSizePolicy, QVBoxLayout, QWidget


class ModelEquationsPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        self.editor = QPlainTextEdit()
        self.editor.setReadOnly(True)
        self.editor.setPlaceholderText("Model equations will appear here.")
        self.editor.setPlainText(
            "System equations\n\n"
            "M x'' + C x' + K x = F(t)\n\n"
            "Controller equations\n\n"
            "u(t) = Kp e(t) + Ki integral(e(t)) dt + Kd de(t)/dt\n"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.addWidget(self.editor)

