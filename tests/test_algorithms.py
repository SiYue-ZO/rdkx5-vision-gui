import numpy as np

from app.algorithms import create_default_registry


def test_registry_and_passthrough():
    registry = create_default_registry()
    assert {name for name, _ in registry.available()} >= {
        "passthrough",
        "edge",
        "hsv_target",
        "yolo",
    }
    frame = np.zeros((64, 64, 3), dtype=np.uint8)
    algorithm = registry.create("passthrough")
    algorithm.initialize({})
    assert algorithm.process(frame, {}).image.shape == frame.shape


def test_hsv_detects_colored_target():
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    frame[20:80, 30:70] = (0, 0, 255)
    algorithm = create_default_registry().create("hsv_target")
    algorithm.initialize({})
    result = algorithm.process(
        frame,
        {
            "h_min": 0,
            "h_max": 10,
            "s_min": 200,
            "s_max": 255,
            "v_min": 200,
            "v_max": 255,
            "min_area": 100,
        },
    )
    assert len(result.detections) == 1
