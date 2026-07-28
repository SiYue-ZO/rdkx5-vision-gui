from __future__ import annotations

import logging
from pathlib import Path

import cv2
from PyQt5.QtCore import QMetaObject, QObject, QThread, Qt, pyqtSignal
from PyQt5.QtGui import QCloseEvent
from PyQt5.QtWidgets import (
    QAction,
    QComboBox,
    QDockWidget,
    QFileDialog,
    QLabel,
    QMainWindow,
    QPlainTextEdit,
    QSplitter,
    QToolBar,
)

from app.algorithms import create_default_registry
from app.common.config import ConfigManager
from app.common.metrics import RateMeter
from app.common.models import AlgorithmResult
from app.inference import create_backend
from app.serial.protocol import (
    BinaryFrameProtocol,
    BinaryFrameStreamParser,
    PacketProtocol,
    ProtocolFrame,
)
from app.ui.widgets.parameter_panel import ParameterPanel
from app.ui.widgets.serial_panel import SerialPanel
from app.ui.widgets.video_view import VideoView
from app.video import ImageSource, VideoFileSource, build_camera_source
from app.workers.frame_buffer import LatestFrameBuffer
from app.workers.inference_worker import InferenceWorker
from app.workers.recording_worker import RecordingWorker
from app.workers.serial_worker import SerialWorker
from app.workers.video_worker import VideoWorker


class QtLogHandler(QObject, logging.Handler):
    message = pyqtSignal(str)

    def __init__(self) -> None:
        QObject.__init__(self)
        logging.Handler.__init__(self)

    def emit(self, record: logging.LogRecord) -> None:
        self.message.emit(self.format(record))


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("RDK X5 视觉调试平台")
        self.resize(1360, 850)
        self.config_manager = ConfigManager()
        self.config = self.config_manager.load(
            "app.yaml", {"algorithm": "passthrough", "algorithm_params": {}}
        )
        self.registry = create_default_registry()
        self.video_thread = self.inference_thread = None
        self.video_worker = self.inference_worker = None
        self.frame_buffer = LatestFrameBuffer()
        self.last_result: AlgorithmResult | None = None
        self.capture_fps = 0.0
        self.display_meter = RateMeter()
        self.recording_thread = self.recording_worker = None
        # 默认解析内置 AA55 协议。自定义协议可在子类中替换或忽略该 parser。
        self.serial_parser = BinaryFrameStreamParser()
        self._build_ui()
        self._setup_serial()
        self._setup_logging()
        self._select_algorithm(self.config.get("algorithm", "passthrough"))

    def _build_ui(self) -> None:
        self.original_view, self.result_view = VideoView(), VideoView()
        self.original_view.setToolTip("原始图像")
        self.result_view.setToolTip("算法结果")
        self.view_splitter = QSplitter(Qt.Horizontal)
        self.view_splitter.addWidget(self.original_view)
        self.view_splitter.addWidget(self.result_view)
        # 固定主画面的布局，避免拖动分隔条时意外改变两个预览区的尺寸。
        self.view_splitter.handle(1).setEnabled(False)
        self.setCentralWidget(self.view_splitter)
        toolbar = QToolBar("主工具栏")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        for text, callback in (
            ("打开图片", self.open_image),
            ("打开视频", self.open_video),
            ("打开摄像头", self.open_camera),
            ("暂停/继续", self.toggle_pause),
            ("单帧", self.step_once),
            ("停止", self.stop_pipeline),
            ("截图", self.save_screenshot),
            ("开始/停止录像", self.toggle_recording),
        ):
            action = QAction(text, self)
            action.triggered.connect(callback)
            toolbar.addAction(action)
        toolbar.addSeparator()
        toolbar.addWidget(QLabel(" 算法: "))
        self.algorithm_combo = QComboBox()
        for name, display in self.registry.available():
            self.algorithm_combo.addItem(display, name)
        self.algorithm_combo.currentIndexChanged.connect(
            lambda: self._select_algorithm(self.algorithm_combo.currentData())
        )
        toolbar.addWidget(self.algorithm_combo)
        self.parameter_panel = ParameterPanel()
        self.parameter_panel.parameters_changed.connect(self._params_changed)
        dock = QDockWidget("算法参数", self)
        dock.setFeatures(QDockWidget.DockWidgetClosable)
        dock.setWidget(self.parameter_panel)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)
        self.serial_panel = SerialPanel()
        serial_dock = QDockWidget("串口调试", self)
        serial_dock.setFeatures(QDockWidget.DockWidgetClosable)
        serial_dock.setWidget(self.serial_panel)
        self.addDockWidget(Qt.RightDockWidgetArea, serial_dock)
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        log_dock = QDockWidget("日志", self)
        log_dock.setFeatures(QDockWidget.DockWidgetClosable)
        log_dock.setWidget(self.log_view)
        self.addDockWidget(Qt.BottomDockWidgetArea, log_dock)
        self.metrics_label = QLabel("就绪")
        self.pixel_label = QLabel()
        self.statusBar().addPermanentWidget(self.metrics_label)
        self.statusBar().addPermanentWidget(self.pixel_label)
        self.original_view.pixel_hovered.connect(self._show_pixel)
        self.result_view.pixel_hovered.connect(self._show_pixel)
        self.original_view.roi_selected.connect(
            lambda roi: self.statusBar().showMessage(f"ROI: {roi}")
        )
        file_menu = self.menuBar().addMenu("文件")
        for action in toolbar.actions()[:3]:
            file_menu.addAction(action)
        file_menu.addSeparator()
        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

    def _setup_serial(self) -> None:
        self.serial_thread = QThread(self)
        self.serial_worker = SerialWorker()
        self.serial_worker.moveToThread(self.serial_thread)
        self.serial_thread.start()
        self.serial_panel.open_requested.connect(self.serial_worker.open)
        self.serial_panel.close_requested.connect(self.serial_worker.close)
        self.serial_panel.send_requested.connect(self.serial_worker.send)
        self.serial_worker.received.connect(self.on_serial_received)
        self.serial_worker.stats.connect(self.on_serial_stats)
        self.serial_worker.status.connect(self.on_serial_status)
        self.serial_worker.error.connect(self.on_serial_error)

    def _setup_logging(self) -> None:
        handler = QtLogHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
        handler.message.connect(self.log_view.appendPlainText)
        logging.getLogger().addHandler(handler)
        self.qt_log_handler = handler

    def _select_algorithm(self, name: str | None) -> None:
        if not name:
            return
        if self.video_worker:
            self.stop_pipeline()
            self.statusBar().showMessage("算法已切换，请重新打开视频源", 4000)
        index = self.algorithm_combo.findData(name)
        if index >= 0 and index != self.algorithm_combo.currentIndex():
            self.algorithm_combo.blockSignals(True)
            self.algorithm_combo.setCurrentIndex(index)
            self.algorithm_combo.blockSignals(False)
        algorithm = self.registry.create(name)
        values = self.config.get("algorithm_params", {}).get(name, {})
        self.parameter_panel.set_specs(algorithm.parameters, values)
        self.config["algorithm"] = name

    def _params_changed(self, params: dict) -> None:
        name = self.algorithm_combo.currentData()
        self.config.setdefault("algorithm_params", {})[name] = params
        if self.inference_worker:
            self.inference_worker.update_params(params)

    def open_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "打开图片", "", "图片 (*.png *.jpg *.jpeg *.bmp)"
        )
        if path:
            self.start_pipeline(ImageSource(path))

    def open_video(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "打开视频", "", "视频 (*.mp4 *.avi *.mkv *.mov)"
        )
        if path:
            self.start_pipeline(VideoFileSource(path))

    def open_camera(self) -> None:
        camera_config = self.config_manager.load("camera.yaml")
        self.start_pipeline(build_camera_source(camera_config))

    def start_pipeline(self, source) -> None:
        self.stop_pipeline()
        self.frame_buffer = LatestFrameBuffer()
        name = self.algorithm_combo.currentData()
        algorithm = self.registry.create(name)
        algorithm_config = {}
        if name == "yolo":
            inference_config = dict(self.config.get("inference", {"backend": "mock"}))
            try:
                inference_config["backend_name"] = inference_config.get("backend", "mock")
                logging.getLogger(__name__).info(
                    "Initializing YOLO backend=%s model=%s",
                    inference_config["backend_name"],
                    inference_config.get("model", "<none>"),
                )
                backend = create_backend(inference_config)
                algorithm_config = {**inference_config, "backend": backend}
            except Exception as exc:
                self._show_error(str(exc))
                return
        try:
            algorithm.initialize(algorithm_config)
        except Exception as exc:
            self._show_error(str(exc))
            return
        params = self.parameter_panel.values()
        self.video_thread, self.inference_thread = QThread(self), QThread(self)
        self.video_worker = VideoWorker(source, self.frame_buffer)
        self.inference_worker = InferenceWorker(algorithm, self.frame_buffer, params)
        self.video_worker.moveToThread(self.video_thread)
        self.inference_worker.moveToThread(self.inference_thread)
        self.video_thread.started.connect(self.video_worker.run)
        self.inference_thread.started.connect(self.inference_worker.run)
        self.video_worker.finished.connect(self.video_thread.quit)
        self.inference_worker.finished.connect(self.inference_thread.quit)
        self.video_worker.frame_captured.connect(self._show_original)
        self.video_worker.status.connect(self.statusBar().showMessage)
        self.video_worker.error.connect(self._show_error)
        self.inference_worker.result_ready.connect(self._show_result)
        self.inference_worker.error.connect(self._show_error)
        self.video_thread.start()
        self.inference_thread.start()

    def stop_pipeline(self) -> None:
        if self.video_worker:
            self.video_worker.stop()
        if self.inference_worker:
            self.inference_worker.stop()
        for thread in (self.video_thread, self.inference_thread):
            if thread and thread.isRunning():
                thread.quit()
                thread.wait(1500)
        self.video_worker = self.inference_worker = None
        self.video_thread = self.inference_thread = None

    def toggle_pause(self) -> None:
        if self.video_worker:
            self.video_worker.set_paused(not self.video_worker.paused)

    def step_once(self) -> None:
        if self.video_worker:
            self.video_worker.step()

    def _show_original(self, frame, fps: float, dropped: int) -> None:
        self.capture_fps = fps
        self.original_view.set_frame(frame)

    def _show_result(self, result: AlgorithmResult) -> None:
        self.last_result = result
        self.result_view.set_frame(result.image)
        result.metrics.display_fps = self.display_meter.tick()
        result.metrics.capture_fps = self.capture_fps
        if self.recording_worker:
            self.recording_worker.enqueue(result.image)
        if result.control_data and self.serial_worker.transport.is_open:
            self.send_serial_data(result.control_data)
        m = result.metrics
        self.metrics_label.setText(
            f"采集/推理/显示 {m.capture_fps:.1f}/{m.inference_fps:.1f}/{m.display_fps:.1f} FPS | "
            f"总延迟 {m.total_ms:.1f} ms | 丢帧 {m.dropped_frames} | "
            f"目标 {len(result.detections)}"
        )
        self.on_algorithm_result(result)

    def on_algorithm_result(self, result: AlgorithmResult) -> None:
        """算法结果公开回调，在 Qt 主线程中每个处理帧调用一次。

        后续业务可以在子类中覆盖此方法，例如保存结构化结果、更新自定义控件，
        或根据 ``result.detections`` 生成控制包。耗时工作应转交其他 Worker，避免
        阻塞界面。若覆盖后仍需要默认行为，无需调用 super：默认实现为空。
        """

    def toggle_recording(self) -> None:
        if self.recording_worker:
            self.stop_recording()
            self.statusBar().showMessage("录像已停止", 3000)
            return
        directory = Path("recordings")
        directory.mkdir(exist_ok=True)
        path, _ = QFileDialog.getSaveFileName(
            self, "保存录像", str(directory / "result.mp4"), "MP4 (*.mp4)"
        )
        if not path:
            return
        self.recording_thread = QThread(self)
        self.recording_worker = RecordingWorker(path, max(1.0, self.capture_fps or 25.0))
        self.recording_worker.moveToThread(self.recording_thread)
        self.recording_thread.started.connect(self.recording_worker.run)
        self.recording_worker.finished.connect(self.recording_thread.quit)
        self.recording_worker.error.connect(self._show_error)
        self.recording_thread.start()
        self.statusBar().showMessage(f"正在录像: {path}", 3000)

    def stop_recording(self) -> None:
        if self.recording_worker:
            self.recording_worker.stop()
        if self.recording_thread and self.recording_thread.isRunning():
            self.recording_thread.wait(2000)
        self.recording_worker = self.recording_thread = None

    def _show_pixel(self, x: int, y: int, value: dict) -> None:
        self.pixel_label.setText(f"({x},{y}) RGB{value['rgb']} HSV{value['hsv']}")

    def save_screenshot(self) -> None:
        if not self.last_result:
            return
        directory = Path("screenshots")
        directory.mkdir(exist_ok=True)
        path, _ = QFileDialog.getSaveFileName(
            self, "保存截图", str(directory / "result.png"), "PNG (*.png);;JPEG (*.jpg)"
        )
        if path:
            suffix = Path(path).suffix or ".png"
            ok, encoded = cv2.imencode(suffix, self.last_result.image)
            if ok:
                encoded.tofile(path)
                self.statusBar().showMessage(f"已保存: {path}", 3000)

    def send_serial_data(self, data: bytes) -> None:
        """线程安全地发送原始字节；调用者负责完成协议编码。"""
        if not isinstance(data, bytes):
            raise TypeError("串口发送数据必须是 bytes")
        self.serial_panel.send_requested.emit(data)

    def send_protocol_frame(
        self,
        command: int,
        payload: bytes = b"",
        protocol: PacketProtocol | None = None,
    ) -> None:
        """使用指定协议编码并发送一帧；默认采用内置 AA55/CRC16 协议。"""
        codec = protocol or BinaryFrameProtocol()
        self.send_serial_data(codec.encode(command, payload))

    def on_serial_received(self, data: bytes) -> None:
        """串口原始接收回调，在 Qt 主线程中调用。

        ``data`` 可能是半包、粘包或任意字节块。默认实现先显示原始数据，再使用
        ``serial_parser`` 增量拆包，并为每个完整包调用 ``on_protocol_frame``。
        自定义纯文本协议时可覆盖本方法；如仍需默认显示，请调用 ``super()``。
        """
        self.serial_panel.append_received(data)
        for frame in self.serial_parser.feed(data):
            self.on_protocol_frame(frame)

    def on_protocol_frame(self, frame: ProtocolFrame) -> None:
        """内置协议完整帧回调；根据 ``frame.command`` 分发具体业务命令。"""

    def on_serial_stats(self, received_bytes: int, sent_bytes: int) -> None:
        """串口累计字节统计回调。"""
        self.serial_panel.set_stats(received_bytes, sent_bytes)

    def on_serial_status(self, text: str) -> None:
        """串口连接状态回调，可覆盖以更新其他设备状态控件。"""
        self.serial_panel.append(text)
        self.serial_panel.set_open("已打开" in text)

    def on_serial_error(self, text: str) -> None:
        """串口异常回调；默认写日志并在状态栏提示。"""
        self._show_error(text)

    def _show_error(self, text: str) -> None:
        logging.getLogger(__name__).error(text)
        self.statusBar().showMessage(text, 5000)

    def closeEvent(self, event: QCloseEvent) -> None:
        self.stop_pipeline()
        self.stop_recording()
        QMetaObject.invokeMethod(self.serial_worker, "close", Qt.BlockingQueuedConnection)
        self.serial_thread.quit()
        self.serial_thread.wait(1000)
        self.config_manager.save("app.yaml", self.config)
        event.accept()
