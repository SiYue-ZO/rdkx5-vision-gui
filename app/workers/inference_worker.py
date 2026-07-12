from __future__ import annotations

import time

from PyQt5.QtCore import QObject, QMutex, pyqtSignal, pyqtSlot

from app.algorithms.base import VisionAlgorithm
from app.common.metrics import RateMeter
from app.workers.frame_buffer import LatestFrameBuffer


class InferenceWorker(QObject):
    result_ready = pyqtSignal(object)
    error = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, algorithm: VisionAlgorithm, buffer: LatestFrameBuffer, params: dict) -> None:
        super().__init__()
        self.algorithm, self.buffer = algorithm, buffer
        self.params = dict(params)
        self.running = False
        self._mutex = QMutex()

    @pyqtSlot()
    def run(self) -> None:
        self.running = True
        meter = RateMeter()
        try:
            while self.running:
                packet = self.buffer.get(0.1)
                if packet is None:
                    if self.buffer.closed:
                        break
                    continue
                started = time.perf_counter()
                self._mutex.lock()
                params = dict(self.params)
                self._mutex.unlock()
                try:
                    result = self.algorithm.process(packet.frame, params)
                except Exception as exc:
                    self.error.emit(f"算法处理失败: {exc}")
                    continue
                result.metrics.capture_ms = packet.capture_ms
                result.metrics.total_ms = (time.perf_counter() - started) * 1000
                result.metrics.inference_fps = meter.tick()
                result.metrics.dropped_frames = self.buffer.dropped
                self.result_ready.emit(result)
        finally:
            try:
                self.algorithm.shutdown()
            finally:
                self.running = False
                self.finished.emit()

    @pyqtSlot(dict)
    def update_params(self, params: dict) -> None:
        self._mutex.lock()
        self.params = dict(params)
        self._mutex.unlock()

    @pyqtSlot()
    def stop(self) -> None:
        self.running = False
        self.buffer.close()
