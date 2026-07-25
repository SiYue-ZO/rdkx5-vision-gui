import numpy as np

from app.inference.rdk_hbm_backend import RdkHbmBackend


def test_decodes_model_zoo_dfl_outputs_and_maps_to_original_image():
    backend = RdkHbmBackend()
    backend.input_size = (16, 16)
    backend.classes_num = 2
    backend.reg = 2
    backend.strides = [8]
    backend.confidence = 0.25
    backend.nms_threshold = 0.70
    backend.resize_type = 1
    backend.labels = ["target", "other"]
    backend.output_names = ["cls", "box"]

    # Four stride-8 cells. Cell zero has class-0 confidence; all DFL distances use bin zero.
    cls = np.full((1, 2, 2, 2), -10.0, dtype=np.float32)
    cls.reshape(-1, 2)[0, 0] = 10.0
    box = np.tile(np.array([10.0, -10.0] * 4, dtype=np.float32), (1, 2, 2, 1))

    detections = backend._decode({"cls": cls, "box": box}, 1.0, (0, 0), (16, 16, 3))

    assert len(detections) == 1
    detection = detections[0]
    assert detection.class_id == 0
    assert detection.label == "target"
    assert detection.score > 0.99
    assert np.allclose((detection.x1, detection.y1, detection.x2, detection.y2), (4, 4, 4, 4), atol=0.01)
