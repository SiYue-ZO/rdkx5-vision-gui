from __future__ import annotations

import cv2
import numpy as np

from app.algorithms.base import VisionAlgorithm
from app.common.models import AlgorithmResult, Detection, ParameterSpec, ParameterType


class PassthroughAlgorithm(VisionAlgorithm):
    name, display_name = "passthrough", "原图透传"

    def process(self, frame: np.ndarray, params: dict) -> AlgorithmResult:
        return AlgorithmResult(image=frame.copy())


class EdgeAlgorithm(VisionAlgorithm):
    name, display_name = "edge", "Canny 边缘"
    parameters = [
        ParameterSpec("low", "低阈值", ParameterType.INT, 60, 0, 255, 1),
        ParameterSpec("high", "高阈值", ParameterType.INT, 150, 0, 255, 1),
        ParameterSpec("blur", "模糊核", ParameterType.INT, 3, 1, 15, 2),
    ]

    def process(self, frame: np.ndarray, params: dict) -> AlgorithmResult:
        kernel = max(1, int(params.get("blur", 3))) | 1
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (kernel, kernel), 0)
        edge = cv2.Canny(gray, int(params.get("low", 60)), int(params.get("high", 150)))
        return AlgorithmResult(image=cv2.cvtColor(edge, cv2.COLOR_GRAY2BGR))


class HsvTargetAlgorithm(VisionAlgorithm):
    name, display_name = "hsv_target", "HSV 目标提取"
    parameters = [
        ParameterSpec("h_min", "H 最小", ParameterType.INT, 0, 0, 179),
        ParameterSpec("h_max", "H 最大", ParameterType.INT, 179, 0, 179),
        ParameterSpec("s_min", "S 最小", ParameterType.INT, 80, 0, 255),
        ParameterSpec("s_max", "S 最大", ParameterType.INT, 255, 0, 255),
        ParameterSpec("v_min", "V 最小", ParameterType.INT, 80, 0, 255),
        ParameterSpec("v_max", "V 最大", ParameterType.INT, 255, 0, 255),
        ParameterSpec("min_area", "最小面积", ParameterType.INT, 300, 0, 100000),
    ]

    def process(self, frame: np.ndarray, params: dict) -> AlgorithmResult:
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        lower = np.array([params.get("h_min", 0), params.get("s_min", 80), params.get("v_min", 80)])
        upper = np.array(
            [params.get("h_max", 179), params.get("s_max", 255), params.get("v_max", 255)]
        )
        mask = cv2.inRange(hsv, lower, upper)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        output = frame.copy()
        detections: list[Detection] = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < int(params.get("min_area", 300)):
                continue
            x, y, w, h = cv2.boundingRect(contour)
            detections.append(Detection(x, y, x + w, y + h, 1.0, 0, "target"))
            cv2.rectangle(output, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.circle(output, (x + w // 2, y + h // 2), 4, (0, 0, 255), -1)
        return AlgorithmResult(image=output, detections=detections, metadata={"mask": mask})
