from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from app.video.base import VideoSource


class OpenCVSource(VideoSource):
    def __init__(self, source: int | str, width: int = 0, height: int = 0, fps: float = 0) -> None:
        self.source = source
        self.width = width
        self.height = height
        self.requested_fps = fps
        self.capture: cv2.VideoCapture | None = None

    def open(self) -> None:
        self.close()
        backend = cv2.CAP_DSHOW if isinstance(self.source, int) and hasattr(cv2, "CAP_DSHOW") else 0
        self.capture = cv2.VideoCapture(self.source, backend)
        if self.width:
            self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        if self.height:
            self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        if self.requested_fps:
            self.capture.set(cv2.CAP_PROP_FPS, self.requested_fps)
        if not self.capture.isOpened():
            self.close()
            raise RuntimeError(f"无法打开视频源: {self.source}")

    def read(self) -> tuple[bool, np.ndarray | None]:
        if not self.capture:
            return False, None
        return self.capture.read()

    def close(self) -> None:
        if self.capture is not None:
            self.capture.release()
            self.capture = None

    @property
    def is_open(self) -> bool:
        return bool(self.capture and self.capture.isOpened())

    @property
    def fps(self) -> float:
        return float(self.capture.get(cv2.CAP_PROP_FPS)) if self.capture else 0.0

    @property
    def info(self) -> dict[str, float | str]:
        if not self.capture:
            return {"source": str(self.source)}
        return {
            "source": str(self.source),
            "width": self.capture.get(cv2.CAP_PROP_FRAME_WIDTH),
            "height": self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT),
            "fps": self.fps,
        }


class CameraSource(OpenCVSource):
    def __init__(self, device: int = 0, width: int = 0, height: int = 0, fps: float = 0) -> None:
        super().__init__(device, width, height, fps)


class VideoFileSource(OpenCVSource):
    def __init__(self, path: str | Path, loop: bool = True) -> None:
        super().__init__(str(path))
        self.loop = loop

    def read(self) -> tuple[bool, np.ndarray | None]:
        ok, frame = super().read()
        if not ok and self.loop and self.capture:
            self.capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ok, frame = self.capture.read()
        return ok, frame


class ImageSource(VideoSource):
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.frame: np.ndarray | None = None

    def open(self) -> None:
        data = np.fromfile(str(self.path), dtype=np.uint8)
        self.frame = cv2.imdecode(data, cv2.IMREAD_COLOR)
        if self.frame is None:
            raise RuntimeError(f"无法读取图片: {self.path}")

    def read(self) -> tuple[bool, np.ndarray | None]:
        return (self.frame is not None, None if self.frame is None else self.frame.copy())

    def close(self) -> None:
        self.frame = None

    @property
    def is_open(self) -> bool:
        return self.frame is not None
