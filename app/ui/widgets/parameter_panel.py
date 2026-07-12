from __future__ import annotations

from typing import Any

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QPushButton,
    QSpinBox,
    QWidget,
)

from app.common.models import ParameterSpec, ParameterType


class ParameterPanel(QWidget):
    parameters_changed = pyqtSignal(dict)

    def __init__(self) -> None:
        super().__init__()
        self.layout = QFormLayout(self)
        self.widgets: dict[str, QWidget] = {}
        self.specs: list[ParameterSpec] = []
        self.reset_button = QPushButton("恢复默认值")
        self.reset_button.clicked.connect(self.reset_defaults)

    def set_specs(self, specs: list[ParameterSpec], values: dict[str, Any] | None = None) -> None:
        while self.layout.count():
            item = self.layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.widgets, self.specs = {}, specs
        values = values or {}
        for spec in specs:
            widget = self._create_widget(spec, values.get(spec.name, spec.default))
            self.widgets[spec.name] = widget
            self.layout.addRow(spec.label, widget)
        self.reset_button = QPushButton("恢复默认值")
        self.reset_button.clicked.connect(self.reset_defaults)
        self.layout.addRow(self.reset_button)

    def _create_widget(self, spec: ParameterSpec, value: Any) -> QWidget:
        if spec.type == ParameterType.BOOL:
            widget = QCheckBox()
            widget.setChecked(bool(value))
            widget.toggled.connect(self._emit)
        elif spec.type == ParameterType.CHOICE:
            widget = QComboBox()
            widget.addItems(spec.choices)
            widget.setCurrentText(str(value))
            widget.currentTextChanged.connect(self._emit)
        elif spec.type == ParameterType.FLOAT:
            widget = QDoubleSpinBox()
            widget.setRange(spec.minimum or -1e9, spec.maximum or 1e9)
            widget.setSingleStep(spec.step or 0.01)
            widget.setDecimals(3)
            widget.setValue(float(value))
            widget.valueChanged.connect(self._emit)
        else:
            widget = QSpinBox()
            widget.setRange(int(spec.minimum or -1_000_000), int(spec.maximum or 1_000_000))
            widget.setSingleStep(int(spec.step or 1))
            widget.setValue(int(value))
            widget.valueChanged.connect(self._emit)
        return widget

    def values(self) -> dict[str, Any]:
        result = {}
        for name, widget in self.widgets.items():
            if isinstance(widget, QCheckBox):
                result[name] = widget.isChecked()
            elif isinstance(widget, QComboBox):
                result[name] = widget.currentText()
            else:
                result[name] = widget.value()
        return result

    def _emit(self, *_args) -> None:
        self.parameters_changed.emit(self.values())

    def reset_defaults(self) -> None:
        self.set_specs(self.specs)
        self.parameters_changed.emit(self.values())
