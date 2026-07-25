from __future__ import annotations

from datetime import datetime

from PyQt5.QtCore import QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QPlainTextEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.serial.transport import SerialConfig, SerialTransport


class SerialPanel(QWidget):
    open_requested = pyqtSignal(object)
    close_requested = pyqtSignal()
    send_requested = pyqtSignal(bytes)

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        controls = QGridLayout()
        self.port = QComboBox()
        self.port.setEditable(True)
        self.baud = QComboBox()
        self.baud.addItems(["9600", "115200", "230400", "460800", "921600"])
        self.baud.setCurrentText("115200")
        self.refresh_button = QPushButton("刷新")
        self.open_button = QPushButton("打开")
        controls.addWidget(QLabel("端口"), 0, 0)
        controls.addWidget(self.port, 0, 1)
        controls.addWidget(self.refresh_button, 0, 2)
        controls.addWidget(QLabel("波特率"), 1, 0)
        controls.addWidget(self.baud, 1, 1)
        controls.addWidget(self.open_button, 1, 2)
        layout.addLayout(controls)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output)
        send_row = QHBoxLayout()
        self.input = QLineEdit()
        self.hex_mode = QCheckBox("HEX")
        self.send_button = QPushButton("发送")
        send_row.addWidget(self.input)
        send_row.addWidget(self.hex_mode)
        send_row.addWidget(self.send_button)
        layout.addLayout(send_row)
        timer_row = QHBoxLayout()
        self.timed = QCheckBox("定时发送")
        self.interval = QSpinBox()
        self.interval.setRange(20, 60000)
        self.interval.setValue(1000)
        self.interval.setSuffix(" ms")
        self.stats_label = QLabel("RX 0 / TX 0")
        timer_row.addWidget(self.timed)
        timer_row.addWidget(self.interval)
        timer_row.addStretch()
        timer_row.addWidget(self.stats_label)
        layout.addLayout(timer_row)
        self.send_timer = QTimer(self)
        self.send_timer.timeout.connect(self._send)
        self.refresh_button.clicked.connect(self.refresh_ports)
        self.open_button.clicked.connect(self._toggle)
        self.send_button.clicked.connect(self._send)
        self.timed.toggled.connect(self._toggle_timer)
        self.refresh_ports()

    def refresh_ports(self) -> None:
        current = self.port.currentData() or self.port.currentText().strip()
        self.port.clear()
        for device, description in SerialTransport.ports():
            self.port.addItem(f"{device} — {description}", device)
        index = self.port.findData(current)
        if index >= 0:
            self.port.setCurrentIndex(index)
        elif current:
            self.port.setEditText(current)

    def _toggle(self) -> None:
        if self.open_button.text() == "打开":
            device = self.port.currentData() or self.port.currentText().strip()
            if device:
                self.open_requested.emit(SerialConfig(device, int(self.baud.currentText())))
        else:
            self.close_requested.emit()

    def set_open(self, opened: bool) -> None:
        self.open_button.setText("关闭" if opened else "打开")

    def _payload(self) -> bytes:
        text = self.input.text()
        return bytes.fromhex(text) if self.hex_mode.isChecked() else text.encode("utf-8")

    def _send(self) -> None:
        try:
            payload = self._payload()
        except ValueError:
            self.append("HEX 格式错误")
            return
        if payload:
            self.send_requested.emit(payload)

    def _toggle_timer(self, enabled: bool) -> None:
        if enabled:
            self.send_timer.start(self.interval.value())
        else:
            self.send_timer.stop()

    def append(self, text: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.output.appendPlainText(f"[{timestamp}] {text}")

    def append_received(self, data: bytes) -> None:
        text = (
            data.hex(" ").upper()
            if self.hex_mode.isChecked()
            else data.decode("utf-8", errors="replace")
        )
        self.append(f"RX: {text}")

    def set_stats(self, rx: int, tx: int) -> None:
        self.stats_label.setText(f"RX {rx} / TX {tx}")
