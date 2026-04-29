from PySide6.QtWidgets import QHBoxLayout, QSizePolicy, QWidget

from src.features.ControllerDesignModule.panels.ControllerTuningPanel.controller_tuning_panel import (
    ControllerTuningPanel,
)
from src.features.ControllerDesignModule.panels.ModelEquationsPanel.model_equations_panel import (
    ModelEquationsPanel,
)
from src.features.ControllerDesignModule.panels.SimulationResultsPanel.simulation_results_panel import (
    SimulationResultsPanel,
)
from src.shared.components.collapsible_sidebar import CollapsibleSidebar


class SystemControllingView(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        configuration_panel = ControllerTuningPanel()
        configuration_panel.setObjectName("ControllerTuningPanel")

        results_panel = SimulationResultsPanel()
        results_panel.setObjectName("SimulationResultsPanel")

        equations_panel = ModelEquationsPanel()
        equations_panel.setObjectName("ModelEquationsPanel")

        configuration_sidebar = CollapsibleSidebar(
            "Configuration",
            configuration_panel,
            side="left",
            expanded=True,
        )
        equations_sidebar = CollapsibleSidebar(
            "Model Equations",
            equations_panel,
            side="right",
            expanded=False,
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(configuration_sidebar)
        layout.addWidget(results_panel, 1)
        layout.addWidget(equations_sidebar)
