from PySide6.QtWidgets import QGridLayout, QLabel, QPushButton, QSizePolicy, QVBoxLayout, QWidget


class SimulationResultsPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        layout.addWidget(QLabel("Results and Analysis"))

        grid = QGridLayout()
        grid.setSpacing(8)
        grid.addWidget(plot_placeholder("Time Response"), 0, 0)
        grid.addWidget(plot_placeholder("Step Response"), 0, 1)
        grid.addWidget(plot_placeholder("Bode"), 1, 0)
        grid.addWidget(plot_placeholder("Pole-Zero"), 1, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setRowStretch(0, 1)
        grid.setRowStretch(1, 1)
        layout.addLayout(grid, 1)

        self.run_button = QPushButton("Run Simulation")
        self.run_button.setObjectName("RunSimulationButton")
        layout.addWidget(self.run_button)


def plot_placeholder(title: str) -> QWidget:
    panel = QLabel(f"{title}\n\nRun simulation to inspect response.")
    panel.setMinimumSize(220, 180)
    panel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
    panel.setStyleSheet(
        """
        QLabel {
            background: #ffffff;
            color: #66717b;
            border: 1px solid #c7d2dd;
            qproperty-alignment: AlignCenter;
        }
        """
    )
    return panel
