from __future__ import annotations

import time

from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot

from app.common.metrics import RateMeter
from app.common.models import FramePacket
from app.video.base import VideoSource
from app.workers.frame_buffer import LatestFrameBuffer


class VideoWorker(QObject):
    status = pyqtSignal(str)
    error = pyqtSignal(str)
    frame_captured = pyqtSignal(object, float, int)
    finished = pyqtSignal()

    def __init__(self, source: VideoSource, buffer: LatestFrameBuffer) -> None:
        super().__init__()
        self.source, self.buffer = source, buffer
        self.running = False
        self.paused = False
        self.step_requested = False

    @pyqtSlot()
    def run(self) -> None:
        self.running = True
        meter = RateMeter()
        sequence = 0
        try:
            self.source.open()
            self.status.emit(f"视频源已打开: {self.source.info}")
            frame_interval = 1 / self.source.fps if self.source.fps > 1 else 0.03
            while self.running:
                if self.paused and not self.step_requested:
                    time.sleep(0.02)
                    continue
                self.step_requested = False
                started = time.perf_counter()
                ok, frame = self.source.read()
                if not ok or frame is None:
                    self.status.emit("视频源已结束")
                    break
                capture_ms = (time.perf_counter() - started) * 1000
                packet = FramePacket(frame, sequence, time.time(), capture_ms)
                self.buffer.put(packet)
                fps = meter.tick()
                self.frame_captured.emit(frame, fps, self.buffer.dropped)
                sequence += 1
                remaining = frame_interval - (time.perf_counter() - started)
                if remaining > 0:
                    time.sleep(min(remaining, 0.05))
        except Exception as exc:
            self.error.emit(str(exc))
        finally:
            self.source.close()
            self.buffer.close()
            self.running = False
            self.finished.emit()

    @pyqtSlot(bool)
    def set_paused(self, paused: bool) -> None:
        self.paused = paused

    def step(self) -> None:
        self.paused = True
        self.step_requested = True

    @pyqtSlot()
    def stop(self) -> None:
        self.running = False
        self.buffer.close()
