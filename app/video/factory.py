from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import cv2

from app.video.base import VideoSource
from app.video.opencv_source import CameraSource
from app.video.rdk_mipi_source import RdkMipiSource


DEFAULT_CAMERA_CONFIG: dict[str, Any] = {
    "type": "usb",
    "device": 0,
    "width": 1280,
    "height": 720,
    "fps": 30,
}


def build_camera_source(config: Mapping[str, Any] | None = None) -> VideoSource:
    values = {**DEFAULT_CAMERA_CONFIG, **dict(config or {})}
    camera_type = str(values.get("type", "usb")).lower()
    if camera_type == "mipi":
        mipi = dict(values.get("mipi") or {})
        return RdkMipiSource(
            camera_id=int(mipi.get("camera_id", 0)),
            width=int(mipi.get("width", values.get("width", 1920))),
            height=int(mipi.get("height", values.get("height", 1080))),
        )
    if camera_type != "usb":
        raise ValueError(f"Unsupported camera type: {camera_type!r}")
    return CameraSource(
        device=_normalize_device(values.get("device", 0)),
        width=int(values.get("width", 0) or 0),
        height=int(values.get("height", 0) or 0),
        fps=float(values.get("fps", 0) or 0),
        backend=_backend_id(values.get("backend")),
        fourcc=str(values.get("fourcc", "") or ""),
    )


def _normalize_device(device: Any) -> int | str:
    if isinstance(device, int):
        return device
    text = str(device)
    return int(text) if text.isdecimal() else text


def _backend_id(value: Any) -> int | None:
    if value is None or str(value).lower() in {"", "auto"}:
        return None
    if isinstance(value, int):
        return value
    name = str(value).strip().lower()
    backends = {
        "any": cv2.CAP_ANY,
        "v4l2": getattr(cv2, "CAP_V4L2", cv2.CAP_ANY),
        "dshow": getattr(cv2, "CAP_DSHOW", cv2.CAP_ANY),
        "gstreamer": getattr(cv2, "CAP_GSTREAMER", cv2.CAP_ANY),
    }
    if name not in backends:
        raise ValueError(f"Unsupported OpenCV camera backend: {value!r}")
    return backends[name]
