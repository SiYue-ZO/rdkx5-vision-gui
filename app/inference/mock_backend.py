from __future__ import annotations

import time
from typing import Any

import numpy as np

from app.common.models import Detection, PerformanceMetrics
from app.inference.base import InferenceBackend


class MockBackend(InferenceBackend):
    name = "mock"

    def load(self, config: dict[str, Any]) -> None:
        self.label = str(config.get("label", "mock-target"))

    def infer(self, frame: np.ndarray) -> tuple[list[Detection], PerformanceMetrics]:
        started = time.perf_counter()
        height, width = frame.shape[:2]
        box_w, box_h = max(20, width // 4), max(20, height // 4)
        x1, y1 = (width - box_w) // 2, (height - box_h) // 2
        detections = [Detection(x1, y1, x1 + box_w, y1 + box_h, 0.9, 0, self.label)]
        total = (time.perf_counter() - started) * 1000
        return detections, PerformanceMetrics(inference_ms=total, total_ms=total)

    def close(self) -> None:
        pass
