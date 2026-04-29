from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QSizePolicy,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)


class ControllerTuningPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)

        tabs = QTabWidget()
        tabs.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        tabs.addTab(self._build_controller_tab(), "Controller")
        tabs.addTab(self._build_io_selection_tab(), "I/O Selection")
        tabs.addTab(self._build_simulation_settings_tab(), "Simulation Settings")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        layout.addWidget(tabs, 1)

    def _build_controller_tab(self) -> QWidget:
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        controller_type = QComboBox()
        controller_type.addItems(["PID", "LQR", "Zustandsregler", "MPR"])

        parameter_stack = QStackedWidget()
        parameter_stack.addWidget(self._build_pid_parameters())
        parameter_stack.addWidget(self._build_lqr_parameters())
        parameter_stack.addWidget(self._build_state_controller_parameters())
        parameter_stack.addWidget(self._build_mpr_parameters())

        controller_type.currentIndexChanged.connect(parameter_stack.setCurrentIndex)

        selector_form = QFormLayout()
        selector_form.addRow("Controller type", controller_type)

        layout.addLayout(selector_form)
        layout.addWidget(parameter_stack, 1)
        return tab

    def _build_io_selection_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)

        input_source = QComboBox()
        input_source.addItems(["Road displacement", "Reference signal", "External force", "Workspace input"])

        input_profile = QComboBox()
        input_profile.addItems(["Step", "Sine", "Ramp", "Impulse", "Custom"])

        output_position = QCheckBox()
        output_position.setChecked(True)
        output_velocity = QCheckBox()
        output_acceleration = QCheckBox()
        control_effort = QCheckBox()
        error_signal = QCheckBox()

        form.addRow("Input source", input_source)
        form.addRow("Input profile", input_profile)
        form.addRow("Body position", output_position)
        form.addRow("Body velocity", output_velocity)
        form.addRow("Body acceleration", output_acceleration)
        form.addRow("Control effort", control_effort)
        form.addRow("Error signal", error_signal)
        return tab

    def _build_simulation_settings_tab(self) -> QWidget:
        tab = QWidget()
        form = QFormLayout(tab)

        solver = QComboBox()
        solver.addItems(["RK45", "RK23", "DOP853", "BDF", "Radau"])

        backend = QComboBox()
        backend.addItems(["Numeric", "State space", "Transfer function"])

        form.addRow("Duration [s]", spinbox(12.0, 0.1, 1000.0, 0.5))
        form.addRow("Sample time [s]", spinbox(0.01, 0.0001, 10.0, 0.001))
        form.addRow("Solver", solver)
        form.addRow("Backend", backend)
        form.addRow("Relative tolerance", spinbox(0.001, 0.000001, 1.0, 0.001))
        form.addRow("Absolute tolerance", spinbox(0.000001, 0.000000001, 1.0, 0.000001))
        return tab

    def _build_pid_parameters(self) -> QWidget:
        panel = QWidget()
        form = QFormLayout(panel)
        enable_pid = QCheckBox()
        enable_pid.setChecked(True)
        form.addRow("Enable PID", enable_pid)
        form.addRow("Kp", spinbox(850.0, -100000.0, 100000.0, 1.0))
        form.addRow("Ki", spinbox(45.0, -100000.0, 100000.0, 1.0))
        form.addRow("Kd", spinbox(180.0, -100000.0, 100000.0, 1.0))
        form.addRow("Output limit", spinbox(1000.0, 0.0, 100000.0, 10.0))
        return panel

    def _build_lqr_parameters(self) -> QWidget:
        panel = QWidget()
        form = QFormLayout(panel)
        form.addRow("State weight q1", spinbox(1.0, 0.0, 100000.0, 0.1))
        form.addRow("State weight q2", spinbox(1.0, 0.0, 100000.0, 0.1))
        form.addRow("Control weight r", spinbox(0.1, 0.0001, 100000.0, 0.1))
        form.addRow("Integral action", QCheckBox())
        return panel

    def _build_state_controller_parameters(self) -> QWidget:
        panel = QWidget()
        form = QFormLayout(panel)
        form.addRow("K1", spinbox(10.0, -100000.0, 100000.0, 0.1))
        form.addRow("K2", spinbox(5.0, -100000.0, 100000.0, 0.1))
        form.addRow("K3", spinbox(1.0, -100000.0, 100000.0, 0.1))
        form.addRow("Observer gain L1", spinbox(20.0, -100000.0, 100000.0, 0.1))
        form.addRow("Observer gain L2", spinbox(20.0, -100000.0, 100000.0, 0.1))
        return panel

    def _build_mpr_parameters(self) -> QWidget:
        panel = QWidget()
        form = QFormLayout(panel)
        form.addRow("Prediction horizon", spinbox(20.0, 1.0, 500.0, 1.0))
        form.addRow("Control horizon", spinbox(5.0, 1.0, 500.0, 1.0))
        form.addRow("Tracking weight", spinbox(1.0, 0.0, 100000.0, 0.1))
        form.addRow("Control effort weight", spinbox(0.1, 0.0, 100000.0, 0.1))
        form.addRow("Input constraint", spinbox(100.0, 0.0, 100000.0, 1.0))
        return panel


def spinbox(value: float, minimum: float, maximum: float, step: float) -> QDoubleSpinBox:
    field = QDoubleSpinBox()
    field.setRange(minimum, maximum)
    field.setSingleStep(step)
    field.setValue(value)
    field.setDecimals(3)
    return field
