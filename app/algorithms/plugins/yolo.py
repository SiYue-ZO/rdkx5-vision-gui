from __future__ import annotations

import cv2
import numpy as np

from app.algorithms.base import VisionAlgorithm
from app.common.models import AlgorithmResult, ParameterSpec, ParameterType
from app.inference.base import InferenceBackend
from app.inference.mock_backend import MockBackend


class YoloAlgorithm(VisionAlgorithm):
    """把任意 ``InferenceBackend`` 包装成标准视觉算法插件。

    自定义 YOLO 通常只需实现后端，不必修改本类。后端通过 ``config['backend']``
    注入，必须返回已经映射到原始图像坐标的 :class:`Detection` 列表。
    """

    name, display_name = "yolo", "YOLO 目标检测"
    parameters = [
        ParameterSpec("confidence", "置信度", ParameterType.FLOAT, 0.25, 0.0, 1.0, 0.01),
        ParameterSpec("show_center", "显示中心", ParameterType.BOOL, True),
    ]

    def initialize(self, config: dict | None = None) -> None:
        """接收已创建的后端并加载其模型配置。"""
        super().initialize(config)
        self.backend: InferenceBackend = (config or {}).get("backend") or MockBackend()
        self.backend.load(config or {})

    def process(self, frame: np.ndarray, params: dict) -> AlgorithmResult:
        """调用后端、应用 GUI 置信度阈值，并绘制检测框和中心点。"""
        detections, metrics = self.backend.infer(frame)
        confidence = float(params.get("confidence", 0.25))
        detections = [item for item in detections if item.score >= confidence]
        output = frame.copy()
        for item in detections:
            p1, p2 = (round(item.x1), round(item.y1)), (round(item.x2), round(item.y2))
            cv2.rectangle(output, p1, p2, (0, 220, 255), 2)
            cv2.putText(
                output,
                f"{item.label} {item.score:.2f}",
                (p1[0], max(18, p1[1] - 5)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (0, 220, 255),
                2,
            )
            if params.get("show_center", True):
                cv2.circle(output, tuple(map(round, item.center)), 4, (0, 0, 255), -1)
        return AlgorithmResult(image=output, detections=detections, metrics=metrics)

    def shutdown(self) -> None:
        """算法停止时关闭推理后端。"""
        self.backend.close()
