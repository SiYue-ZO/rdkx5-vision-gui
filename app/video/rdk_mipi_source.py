from __future__ import annotations

import importlib
from typing import Any

import cv2
import numpy as np

from app.video.base import VideoSource


class RdkMipiSource(VideoSource):
    """Adapter for libsrcampy; imported lazily so desktop startup stays functional."""

    def __init__(self, camera_id: int = 0, width: int = 1920, height: int = 1080) -> None:
        self.camera_id, self.width, self.height = camera_id, width, height
        self.camera: Any = None

    def open(self) -> None:
        try:
            module = importlib.import_module("libsrcampy")
        except ImportError as exc:
            raise RuntimeError("当前环境没有 libsrcampy，无法使用 RDK MIPI 相机") from exc
        self.camera = module.Camera()
        result = self.camera.open_cam(self.camera_id, 0, self.width, self.height)
        if result not in (0, None):
            self.close()
            raise RuntimeError(f"MIPI 相机打开失败，错误码: {result}")

    def read(self) -> tuple[bool, np.ndarray | None]:
        if self.camera is None:
            return False, None
        raw = self.camera.get_img(2, self.width, self.height)
        if raw is None:
            return False, None
        nv12 = np.frombuffer(raw, dtype=np.uint8).reshape(self.height * 3 // 2, self.width)
        return True, cv2.cvtColor(nv12, cv2.COLOR_YUV2BGR_NV12)

    def close(self) -> None:
        if self.camera is not None:
            try:
                self.camera.close_cam()
            finally:
                self.camera = None

    @property
    def is_open(self) -> bool:
        return self.camera is not None
