import numpy as np

from app.inference.utils import bgr_to_nv12, letterbox, nms


def test_letterbox_shape_and_mapping():
    image = np.zeros((100, 200, 3), dtype=np.uint8)
    output, ratio, padding = letterbox(image, (640, 640))
    assert output.shape == (640, 640, 3)
    assert ratio == 3.2
    assert padding == (0, 160)


def test_nv12_shape():
    assert bgr_to_nv12(np.zeros((480, 640, 3), dtype=np.uint8)).shape == (720, 640)


def test_nms_suppresses_overlap():
    boxes = np.array([[0, 0, 10, 10], [1, 1, 11, 11], [30, 30, 40, 40]], dtype=float)
    assert nms(boxes, np.array([0.9, 0.8, 0.7]), 0.5) == [0, 2]
