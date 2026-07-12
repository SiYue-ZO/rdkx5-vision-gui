from __future__ import annotations

import queue
from pathlib import Path

import cv2
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot


class RecordingWorker(QObject):
    error = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, path: str | Path, fps: float = 25.0) -> None:
        super().__init__()
        self.path = str(path)
        self.fps = fps
        self.frames: queue.Queue = queue.Queue(maxsize=2)
        self.running = False

    def enqueue(self, frame) -> None:
        try:
            self.frames.put_nowait(frame.copy())
        except queue.Full:
            try:
                self.frames.get_nowait()
            except queue.Empty:
                pass
            try:
                self.frames.put_nowait(frame.copy())
            except queue.Full:
                pass

    @pyqtSlot()
    def run(self) -> None:
        self.running = True
        writer = None
        try:
            while self.running or not self.frames.empty():
                try:
                    frame = self.frames.get(timeout=0.1)
                except queue.Empty:
                    continue
                if writer is None:
                    height, width = frame.shape[:2]
                    writer = cv2.VideoWriter(
                        self.path,
                        cv2.VideoWriter_fourcc(*"mp4v"),
                        self.fps,
                        (width, height),
                    )
                    if not writer.isOpened():
                        raise RuntimeError(f"无法创建录像文件: {self.path}")
                writer.write(frame)
        except Exception as exc:
            self.error.emit(str(exc))
        finally:
            if writer:
                writer.release()
            self.finished.emit()

    def stop(self) -> None:
        self.running = False
