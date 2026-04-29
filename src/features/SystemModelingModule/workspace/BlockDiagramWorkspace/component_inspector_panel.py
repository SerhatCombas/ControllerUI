from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDoubleSpinBox, QFrame, QGridLayout, QLabel, QSizePolicy

from src.shared.types.model_component import ModelComponent


class ComponentInspectorPanel(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("ComponentInspectorPanel")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setFixedHeight(168)

        self.value_labels: dict[str, QLabel] = {}
        self.layout = QGridLayout(self)
        self.layout.setContentsMargins(14, 10, 14, 10)
        self.layout.setHorizontalSpacing(18)
        self.layout.setVerticalSpacing(8)
        self.parameter_widgets = []

        fields = [
            ("Selected", "No selection"),
            ("Component ID", "-"),
            ("Domain", "-"),
            ("Category", "-"),
            ("Boundary", "-"),
            ("Motion", "-"),
            ("Directional", "-"),
            ("Source", "-"),
            ("Source Type", "-"),
            ("Rotation", "0"),
            ("Ports", "-"),
            ("Status", "Click a component to select it."),
        ]

        for index, (label, value) in enumerate(fields):
            row = index // 4
            col = (index % 4) * 2
            name_label = QLabel(label)
            name_label.setObjectName("InspectorFieldName")
            value_label = QLabel(value)
            value_label.setObjectName("InspectorFieldValue")
            value_label.setMinimumWidth(0)
            value_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            self.value_labels[label] = value_label
            self.layout.addWidget(name_label, row, col)
            self.layout.addWidget(value_label, row, col + 1)

    def show_component(self, component: ModelComponent | None) -> None:
        if component is None:
            self.hide()
            return

        self.value_labels["Selected"].setText(component.name)
        self.value_labels["Component ID"].setText(short_component_id(component.component_id))
        self.value_labels["Component ID"].setToolTip(component.component_id)
        self.value_labels["Domain"].setText(component.domain)
        self.value_labels["Category"].setText(component.category)
        self.value_labels["Boundary"].setText(boundary_for(component))
        self.value_labels["Motion"].setText(motion_for(component))
        self.value_labels["Directional"].setText(directional_for(component))
        self.value_labels["Source"].setText(source_for(component))
        self.value_labels["Source Type"].setText(source_type_for(component))
        self.value_labels["Rotation"].setText("0")
        self.value_labels["Ports"].setText(ports_for(component))
        self.value_labels["Status"].setText("Selected component is ready for configuration.")
        self.show_parameters(component)
        self.show()

    def show_parameters(self, component: ModelComponent) -> None:
        self.clear_parameters()
        parameter_row = 3

        for index, parameter in enumerate(parameters_for(component)):
            label, value, minimum, maximum, step = parameter
            col = index * 2
            name_label = QLabel(label)
            name_label.setObjectName("InspectorFieldName")
            field = parameter_spinbox(value, minimum, maximum, step)
            self.layout.addWidget(name_label, parameter_row, col)
            self.layout.addWidget(field, parameter_row, col + 1)
            self.parameter_widgets.extend([name_label, field])

    def clear_parameters(self) -> None:
        while self.parameter_widgets:
            widget = self.parameter_widgets.pop()
            self.layout.removeWidget(widget)
            widget.deleteLater()


def boundary_for(component: ModelComponent) -> str:
    component_id = component.component_id.lower()
    if "ground" in component_id or "fixed" in component_id:
        return "Reference"
    return "Free"


def motion_for(component: ModelComponent) -> str:
    if component.family in {"Translational", "Rotational"}:
        return component.family
    return "-"


def short_component_id(component_id: str) -> str:
    if len(component_id) <= 42:
        return component_id
    return f".../{component_id.split('/')[-1]}"


def directional_for(component: ModelComponent) -> str:
    return "Yes" if component.category in {"Sources", "Sensors"} else "No"


def source_for(component: ModelComponent) -> str:
    return "Yes" if component.category == "Sources" else "No"


def source_type_for(component: ModelComponent) -> str:
    return component.name if component.category == "Sources" else "-"


def ports_for(component: ModelComponent) -> str:
    component_id = component.component_id.lower()
    if any(token in component_id for token in ["ground", "fixed"]):
        return "1"
    if any(token in component_id for token in ["sensor", "spring", "damper", "resistor", "capacitor", "inductor"]):
        return "2"
    return "-"


def parameters_for(component: ModelComponent) -> list[tuple[str, float, float, float, float]]:
    component_id = component.component_id.lower()

    if "mass" in component_id:
        return [("Mass [kg]", 300.0, 0.0, 100000.0, 1.0)]
    if "springdamper" in component_id or "spring_damper" in component_id:
        return [
            ("Stiffness [N/m]", 15000.0, 0.0, 1000000.0, 100.0),
            ("Damping [Ns/m]", 1200.0, 0.0, 100000.0, 10.0),
        ]
    if "spring" in component_id:
        return [("Stiffness [N/m]", 15000.0, 0.0, 1000000.0, 100.0)]
    if "damper" in component_id:
        return [("Damping [Ns/m]", 1200.0, 0.0, 100000.0, 10.0)]
    if "resistor" in component_id:
        return [("Resistance [Ohm]", 100.0, 0.0, 1000000000.0, 1.0)]
    if "capacitor" in component_id:
        return [("Capacitance [F]", 0.001, 0.0, 1000000.0, 0.001)]
    if "inductor" in component_id:
        return [("Inductance [H]", 0.01, 0.0, 1000000.0, 0.001)]
    if "constantvoltage" in component_id:
        return [("Voltage [V]", 12.0, -1000000.0, 1000000.0, 1.0)]
    if "stepvoltage" in component_id:
        return [
            ("Initial [V]", 0.0, -1000000.0, 1000000.0, 1.0),
            ("Final [V]", 12.0, -1000000.0, 1000000.0, 1.0),
            ("Step time [s]", 1.0, 0.0, 1000000.0, 0.1),
        ]
    if "sinevoltage" in component_id:
        return [
            ("Amplitude [V]", 1.0, 0.0, 1000000.0, 0.1),
            ("Frequency [Hz]", 1.0, 0.0, 1000000.0, 0.1),
            ("Phase [deg]", 0.0, -360.0, 360.0, 1.0),
        ]
    if "rampvoltage" in component_id:
        return [
            ("Slope [V/s]", 1.0, -1000000.0, 1000000.0, 0.1),
            ("Start time [s]", 0.0, 0.0, 1000000.0, 0.1),
        ]
    if "signalvoltage" in component_id:
        return [
            ("Amplitude [V]", 1.0, 0.0, 1000000.0, 0.1),
            ("Offset [V]", 0.0, -1000000.0, 1000000.0, 0.1),
        ]
    if "sensor" in component_id:
        return [("Gain", 1.0, -1000000.0, 1000000.0, 0.1)]
    return []


def parameter_spinbox(value: float, minimum: float, maximum: float, step: float) -> QDoubleSpinBox:
    field = QDoubleSpinBox()
    field.setRange(minimum, maximum)
    field.setSingleStep(step)
    field.setValue(value)
    field.setDecimals(3)
    field.setFixedWidth(96)
    return field
