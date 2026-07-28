import cv2

from app.video.factory import build_camera_source
from app.video.opencv_source import CameraSource, _default_backend
from app.video.rdk_mipi_source import RdkMipiSource


def test_linux_camera_source_defaults_to_v4l2(monkeypatch):
    monkeypatch.setattr("app.video.opencv_source.platform.system", lambda: "Linux")

    assert _default_backend("/dev/video0") == cv2.CAP_V4L2
    assert _default_backend(0) == cv2.CAP_V4L2


def test_windows_camera_index_defaults_to_dshow(monkeypatch):
    monkeypatch.setattr("app.video.opencv_source.platform.system", lambda: "Windows")

    assert _default_backend(0) == cv2.CAP_DSHOW


def test_build_usb_camera_source_from_config():
    source = build_camera_source(
        {
            "type": "usb",
            "device": "/dev/video0",
            "width": 640,
            "height": 480,
            "fps": 15,
            "backend": "v4l2",
            "fourcc": "MJPG",
        }
    )

    assert isinstance(source, CameraSource)
    assert source.source == "/dev/video0"
    assert source.width == 640
    assert source.height == 480
    assert source.requested_fps == 15
    assert source.backend == cv2.CAP_V4L2
    assert source.fourcc == "MJPG"


def test_build_mipi_camera_source_from_config():
    source = build_camera_source(
        {
            "type": "mipi",
            "mipi": {"camera_id": 1, "width": 1920, "height": 1080},
        }
    )

    assert isinstance(source, RdkMipiSource)
    assert source.camera_id == 1
    assert source.width == 1920
    assert source.height == 1080
