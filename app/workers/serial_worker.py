from __future__ import annotations

from PyQt5.QtCore import QObject, QTimer, pyqtSignal, pyqtSlot

from app.serial.transport import SerialConfig, SerialTransport


class SerialWorker(QObject):
    """运行在独立 QThread 中的串口 I/O Worker。

    应通过 Signal 调用本对象的槽，不要从 GUI 线程直接访问 pyserial connection。
    ``received`` 发出的是本次读取到的原始字节块，不保证对应一个完整协议帧。
    """

    # 原始接收字节回调；协议拆包应在接收者中使用增量 parser 完成。
    received = pyqtSignal(bytes)
    # 连接/断开等可展示状态。
    status = pyqtSignal(str)
    # 打开、读取或发送异常；异常不会直接终止 GUI。
    error = pyqtSignal(str)
    # 累计接收字节数、累计发送字节数。
    stats = pyqtSignal(int, int)

    def __init__(self) -> None:
        super().__init__()
        self.transport = SerialTransport()
        self.timer: QTimer | None = None

    @pyqtSlot(object)
    def open(self, config: SerialConfig) -> None:
        """按 SerialConfig 打开端口，并启动 10 ms 非阻塞轮询。"""
        try:
            self.transport.open(config)
            self.timer = QTimer(self)
            self.timer.timeout.connect(self.poll)
            self.timer.start(10)
            self.status.emit(f"串口已打开: {config.port}")
        except Exception as exc:
            self.error.emit(f"串口打开失败: {exc}")

    @pyqtSlot()
    def poll(self) -> None:
        """读取当前可用字节并触发 received；仅在串口线程调用。"""
        try:
            data = self.transport.read()
            if data:
                self.received.emit(data)
                self.stats.emit(self.transport.rx_bytes, self.transport.tx_bytes)
        except Exception as exc:
            self.error.emit(f"串口读取失败: {exc}")
            self.close()

    @pyqtSlot(bytes)
    def send(self, data: bytes) -> None:
        """发送已经编码好的原始字节；协议编码应在调用本槽之前完成。"""
        try:
            self.transport.write(data)
            self.stats.emit(self.transport.rx_bytes, self.transport.tx_bytes)
        except Exception as exc:
            self.error.emit(f"串口发送失败: {exc}")

    @pyqtSlot()
    def close(self) -> None:
        """停止轮询并释放串口，允许重复调用。"""
        if self.timer:
            self.timer.stop()
        self.transport.close()
        self.status.emit("串口已关闭")
