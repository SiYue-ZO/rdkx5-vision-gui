from __future__ import annotations

import platform
from pathlib import Path

import cv2
import numpy as np

from app.video.base import VideoSource


class OpenCVSource(VideoSource):
    def __init__(
        self,
        source: int | str,
        width: int = 0,
        height: int = 0,
        fps: float = 0,
        backend: int | None = None,
        fourcc: str = "",
    ) -> None:
        self.source = source
        self.width = width
        self.height = height
        self.requested_fps = fps
        self.backend = backend
        self.fourcc = fourcc
        self.capture: cv2.VideoCapture | None = None

    def open(self) -> None:
        self.close()
        backend = self.backend if self.backend is not None else _default_backend(self.source)
        self.capture = cv2.VideoCapture(self.source, backend)
        if self.fourcc and len(self.fourcc) == 4:
            self.capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*self.fourcc))
        if self.width:
            self.capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        if self.height:
            self.capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        if self.requested_fps:
            self.capture.set(cv2.CAP_PROP_FPS, self.requested_fps)
        if not self.capture.isOpened():
            self.close()
            raise RuntimeError(
                f"Cannot open video source {self.source!r} with OpenCV backend {backend}. "
                "On Linux/RDK, check /dev/video* permissions, whether another process is "
                "using the camera, and the camera width/height/fps in configs/camera.yaml."
            )

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
            "backend": self.capture.get(cv2.CAP_PROP_BACKEND),
            "width": self.capture.get(cv2.CAP_PROP_FRAME_WIDTH),
            "height": self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT),
            "fps": self.fps,
        }


class CameraSource(OpenCVSource):
    def __init__(
        self,
        device: int | str = 0,
        width: int = 0,
        height: int = 0,
        fps: float = 0,
        backend: int | None = None,
        fourcc: str = "",
    ) -> None:
        super().__init__(device, width, height, fps, backend, fourcc)


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
            raise RuntimeError(f"Cannot read image: {self.path}")

    def read(self) -> tuple[bool, np.ndarray | None]:
        return (self.frame is not None, None if self.frame is None else self.frame.copy())

    def close(self) -> None:
        self.frame = None

    @property
    def is_open(self) -> bool:
        return self.frame is not None


def _default_backend(source: int | str) -> int:
    system = platform.system()
    if system == "Windows" and isinstance(source, int) and hasattr(cv2, "CAP_DSHOW"):
        return cv2.CAP_DSHOW
    if system == "Linux" and _looks_like_camera(source) and hasattr(cv2, "CAP_V4L2"):
        return cv2.CAP_V4L2
    return cv2.CAP_ANY


def _looks_like_camera(source: int | str) -> bool:
    return isinstance(source, int) or str(source).startswith("/dev/video")
