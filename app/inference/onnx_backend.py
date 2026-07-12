from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from app.common.models import Detection, PerformanceMetrics
from app.inference.base import InferenceBackend
from app.inference.utils import letterbox, nms


class OnnxBackend(InferenceBackend):
    name = "onnxruntime"

    def __init__(self) -> None:
        self.session = None

    @property
    def available(self) -> bool:
        try:
            import onnxruntime  # noqa: F401

            return True
        except ImportError:
            return False

    def load(self, config: dict[str, Any]) -> None:
        try:
            import onnxruntime as ort
        except ImportError as exc:
            raise RuntimeError(
                "ONNX Runtime 未安装或无法加载，请执行 `uv sync --all-extras`；"
                f"原始错误: {exc}"
            ) from exc
        path = Path(config.get("model", ""))
        if not path.is_file():
            raise RuntimeError(f"ONNX 模型不存在: {path}")
        self.confidence = float(config.get("confidence", 0.25))
        self.nms_threshold = float(config.get("nms", 0.45))
        self.labels = list(config.get("labels", []))
        providers = config.get("providers") or ort.get_available_providers()
        self.session = ort.InferenceSession(str(path), providers=providers)
        input_meta = self.session.get_inputs()[0]
        self.input_name = input_meta.name
        shape = input_meta.shape
        configured_size = config.get("input_size")
        if configured_size is not None:
            if len(configured_size) != 2 or any(int(item) <= 0 for item in configured_size):
                raise RuntimeError("ONNX input_size 必须是两个正整数，例如 [640, 640]")
            self.input_size = tuple(map(int, configured_size))
        else:
            # 动态 ONNX 的维度可能是 "height"/"width" 等符号名称，不能直接转成整数。
            width = shape[3] if isinstance(shape[3], int) and shape[3] > 0 else 640
            height = shape[2] if isinstance(shape[2], int) and shape[2] > 0 else 640
            self.input_size = (width, height)

    def infer(self, frame: np.ndarray) -> tuple[list[Detection], PerformanceMetrics]:
        if self.session is None:
            raise RuntimeError("ONNX 模型尚未加载")
        total_started = time.perf_counter()
        started = time.perf_counter()
        image, ratio, padding = letterbox(frame, self.input_size)
        tensor = (
            cv2.cvtColor(image, cv2.COLOR_BGR2RGB).transpose(2, 0, 1)[None].astype(np.float32)
            / 255.0
        )
        preprocess_ms = (time.perf_counter() - started) * 1000
        started = time.perf_counter()
        outputs = self.session.run(None, {self.input_name: tensor})
        inference_ms = (time.perf_counter() - started) * 1000
        started = time.perf_counter()
        detections = self._decode(np.asarray(outputs[0]), ratio, padding)
        postprocess_ms = (time.perf_counter() - started) * 1000
        return detections, PerformanceMetrics(
            preprocess_ms=preprocess_ms,
            inference_ms=inference_ms,
            postprocess_ms=postprocess_ms,
            total_ms=(time.perf_counter() - total_started) * 1000,
        )

    def _decode(
        self, output: np.ndarray, ratio: float, padding: tuple[int, int]
    ) -> list[Detection]:
        predictions = np.squeeze(output)
        if predictions.ndim != 2:
            raise RuntimeError(f"不支持的 YOLO 输出形状: {output.shape}")
        if predictions.shape[0] < predictions.shape[1] and predictions.shape[0] <= 256:
            predictions = predictions.T
        if predictions.shape[1] == 6:
            boxes, scores, classes = (
                predictions[:, :4],
                predictions[:, 4],
                predictions[:, 5].astype(int),
            )
            xyxy = boxes.copy()
        elif predictions.shape[1] >= 5:
            class_scores = predictions[:, 4:]
            classes = class_scores.argmax(axis=1)
            scores = class_scores[np.arange(len(class_scores)), classes]
            boxes = predictions[:, :4]
            xyxy = np.column_stack(
                (
                    boxes[:, 0] - boxes[:, 2] / 2,
                    boxes[:, 1] - boxes[:, 3] / 2,
                    boxes[:, 0] + boxes[:, 2] / 2,
                    boxes[:, 1] + boxes[:, 3] / 2,
                )
            )
        else:
            raise RuntimeError(f"不支持的 YOLO 输出形状: {output.shape}")
        valid = scores >= self.confidence
        xyxy, scores, classes = xyxy[valid], scores[valid], classes[valid]
        selected: list[int] = []
        for class_id in np.unique(classes):
            indices = np.where(classes == class_id)[0]
            selected.extend(
                indices[nms(xyxy[indices], scores[indices], self.nms_threshold)].tolist()
            )
        left, top = padding
        result = []
        for index in selected:
            box = xyxy[index].astype(float)
            box[[0, 2]] = (box[[0, 2]] - left) / ratio
            box[[1, 3]] = (box[[1, 3]] - top) / ratio
            class_id = int(classes[index])
            label = self.labels[class_id] if class_id < len(self.labels) else str(class_id)
            result.append(Detection(*box.tolist(), float(scores[index]), class_id, label))
        return result

    def close(self) -> None:
        self.session = None
