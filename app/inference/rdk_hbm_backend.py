from __future__ import annotations

import importlib
import logging
import time
from typing import Any

import cv2
import numpy as np

from app.common.models import Detection, PerformanceMetrics
from app.common.runtime_paths import resolve_data_file
from app.inference.base import InferenceBackend
from app.inference.utils import bgr_to_nv12, letterbox, nms


logger = logging.getLogger(__name__)


class RdkHbmBackend(InferenceBackend):
    """YOLO Detect backend for an RDK X5 NV12 ``.bin`` model.

    This follows the RDK Model Zoo ``ultralytics_yolo`` runtime protocol:
    ``HB_HBMRuntime.run({model_name: {input_name: packed_nv12}})`` and six
    outputs ordered as classification/DFL-box pairs for strides 8, 16 and 32.
    """

    name = "rdk-hbm"

    def __init__(self) -> None:
        self.runtime: Any | None = None
        self.model_name = ""
        self.input_name = ""
        self.output_names: list[str] = []
        self.input_size = (640, 640)
        self.classes_num = 80
        self.confidence = 0.25
        self.nms_threshold = 0.70
        self.reg = 16
        self.strides = [8, 16, 32]
        self.resize_type = 1
        self.labels: list[str] = []

    @property
    def available(self) -> bool:
        try:
            return importlib.util.find_spec("hbm_runtime") is not None
        except (ImportError, AttributeError):
            return False

    def load(self, config: dict[str, Any]) -> None:
        model_path = resolve_data_file(config.get("model", ""))
        if not model_path.is_file():
            raise RuntimeError(f"RDK .bin model does not exist: {model_path}")
        logger.info("Loading RDK HBM .bin model: %s", model_path.resolve())
        try:
            hbm_runtime = importlib.import_module("hbm_runtime")
        except ImportError as exc:
            raise RuntimeError(
                "hbm_runtime is unavailable. Run this backend with the matching RDK X5 BSP Python."
            ) from exc

        self.classes_num = self._positive_int(config.get("classes_num", 80), "classes_num")
        self.reg = self._positive_int(config.get("reg", 16), "reg")
        self.strides = [self._positive_int(value, "strides item") for value in config.get("strides", [8, 16, 32])]
        if not self.strides:
            raise RuntimeError("strides must not be empty")
        self.confidence = self._threshold(config.get("confidence", 0.25), "confidence")
        self.nms_threshold = self._threshold(config.get("nms", 0.70), "nms")
        self.resize_type = int(config.get("resize_type", 1))
        if self.resize_type not in (0, 1):
            raise RuntimeError("resize_type must be 0 (resize) or 1 (letterbox)")
        self.labels = [str(label) for label in config.get("labels", [])]

        runtime_class = getattr(hbm_runtime, "HB_HBMRuntime", None)
        if runtime_class is None:
            raise RuntimeError("hbm_runtime does not provide HB_HBMRuntime")
        self.runtime = runtime_class(str(model_path))
        model_names = list(getattr(self.runtime, "model_names", []))
        requested_name = config.get("model_name")
        if requested_name and requested_name not in model_names:
            raise RuntimeError(f"model_name {requested_name!r} is not in {model_names}")
        if not model_names and not requested_name:
            raise RuntimeError("the .bin runtime did not expose a model name")
        self.model_name = requested_name or model_names[0]
        try:
            self.input_name = list(self.runtime.input_names[self.model_name])[0]
            self.output_names = list(self.runtime.output_names[self.model_name])
            input_shape = self.runtime.input_shapes[self.model_name][self.input_name]
        except (AttributeError, IndexError, KeyError, TypeError) as exc:
            raise RuntimeError("unable to read the .bin input/output metadata") from exc
        if len(self.output_names) != len(self.strides) * 2:
            raise RuntimeError(
                "this backend supports YOLO Detect classification/DFL outputs only: "
                f"expected {len(self.strides) * 2} outputs, got {len(self.output_names)}"
            )
        self.input_size = self._input_size(input_shape, config.get("input_size"))

        scheduling: dict[str, dict[str, Any]] = {}
        if "priority" in config:
            scheduling["priority"] = {self.model_name: int(config["priority"])}
        if "bpu_cores" in config:
            scheduling["bpu_cores"] = {self.model_name: list(config["bpu_cores"])}
        if scheduling and hasattr(self.runtime, "set_scheduling_params"):
            self.runtime.set_scheduling_params(**scheduling)
        logger.info(
            "RDK HBM model ready: model=%s input=%s size=%sx%s outputs=%s classes=%s",
            self.model_name,
            self.input_name,
            self.input_size[0],
            self.input_size[1],
            self.output_names,
            self.classes_num,
        )

    def infer(self, frame: np.ndarray) -> tuple[list[Detection], PerformanceMetrics]:
        if self.runtime is None:
            raise RuntimeError("RDK BPU model has not been loaded")
        total_started = time.perf_counter()
        started = total_started
        if self.resize_type == 1:
            image, ratio, padding = letterbox(frame, self.input_size)
        else:
            image = cv2.resize(frame, self.input_size, interpolation=cv2.INTER_NEAREST)
            ratio, padding = 1.0, (0, 0)
        packed_nv12 = bgr_to_nv12(image).reshape(-1).astype(np.uint8, copy=False)
        preprocess_ms = (time.perf_counter() - started) * 1000

        started = time.perf_counter()
        outputs = self.runtime.run({self.model_name: {self.input_name: packed_nv12}})
        inference_ms = (time.perf_counter() - started) * 1000

        started = time.perf_counter()
        raw_outputs = outputs[self.model_name]
        detections = self._decode(raw_outputs, ratio, padding, frame.shape)
        postprocess_ms = (time.perf_counter() - started) * 1000
        return detections, PerformanceMetrics(
            preprocess_ms=preprocess_ms,
            inference_ms=inference_ms,
            postprocess_ms=postprocess_ms,
            total_ms=(time.perf_counter() - total_started) * 1000,
        )

    def _decode(
        self,
        outputs: dict[str, np.ndarray],
        ratio: float,
        padding: tuple[int, int],
        original_shape: tuple[int, ...],
    ) -> list[Detection]:
        """Decode Model Zoo YOLOv5u/8/9/10/11/12/13 Detect output tensors."""
        raw_threshold = -np.log(1.0 / self.confidence - 1.0)
        weights = np.arange(self.reg, dtype=np.float32)
        candidates: list[tuple[np.ndarray, np.ndarray, np.ndarray]] = []
        for level, stride in enumerate(self.strides):
            try:
                cls = np.asarray(outputs[self.output_names[level * 2]]).reshape(-1, self.classes_num)
                box = np.asarray(outputs[self.output_names[level * 2 + 1]]).reshape(-1, 4 * self.reg)
            except (KeyError, ValueError) as exc:
                raise RuntimeError(
                    "unexpected YOLO .bin output shape; check classes_num, reg and output node order"
                ) from exc
            if len(cls) != len(box):
                raise RuntimeError("classification and box output sizes do not match")
            class_ids = cls.argmax(axis=1)
            logits = cls[np.arange(len(cls)), class_ids]
            valid = np.flatnonzero(logits >= raw_threshold)
            if not valid.size:
                continue
            distances = self._dfl(box[valid], weights)
            grid_h = self.input_size[1] // stride
            grid_w = self.input_size[0] // stride
            if grid_h * grid_w != len(cls):
                raise RuntimeError(
                    f"stride-{stride} output has {len(cls)} cells, expected {grid_h * grid_w} from model input"
                )
            anchors = self._anchors(grid_h, grid_w)[valid]
            boxes = np.concatenate((anchors - distances[:, :2], anchors + distances[:, 2:]), axis=1)
            candidates.append((boxes * stride, self._sigmoid(logits[valid]), class_ids[valid]))
        if not candidates:
            return []

        boxes = np.concatenate([item[0] for item in candidates])
        scores = np.concatenate([item[1] for item in candidates])
        class_ids = np.concatenate([item[2] for item in candidates]).astype(int)
        selected: list[int] = []
        for class_id in np.unique(class_ids):
            indices = np.flatnonzero(class_ids == class_id)
            selected.extend(indices[nms(boxes[indices], scores[indices], self.nms_threshold)].tolist())

        original_h, original_w = original_shape[:2]
        left, top = padding
        result: list[Detection] = []
        for index in selected:
            box = boxes[index].astype(np.float32, copy=True)
            if self.resize_type == 1:
                box[[0, 2]] = (box[[0, 2]] - left) / ratio
                box[[1, 3]] = (box[[1, 3]] - top) / ratio
            else:
                box[[0, 2]] *= original_w / self.input_size[0]
                box[[1, 3]] *= original_h / self.input_size[1]
            box[[0, 2]] = np.clip(box[[0, 2]], 0, original_w)
            box[[1, 3]] = np.clip(box[[1, 3]], 0, original_h)
            class_id = int(class_ids[index])
            label = self.labels[class_id] if class_id < len(self.labels) else str(class_id)
            result.append(Detection(*box.tolist(), float(scores[index]), class_id, label))
        return result

    @staticmethod
    def _dfl(boxes: np.ndarray, weights: np.ndarray) -> np.ndarray:
        logits = boxes.reshape(-1, 4, len(weights)).astype(np.float32, copy=False)
        logits -= logits.max(axis=2, keepdims=True)
        probabilities = np.exp(logits)
        probabilities /= probabilities.sum(axis=2, keepdims=True)
        return (probabilities * weights).sum(axis=2)

    @staticmethod
    def _anchors(height: int, width: int) -> np.ndarray:
        x, y = np.meshgrid(np.arange(width, dtype=np.float32) + 0.5, np.arange(height, dtype=np.float32) + 0.5)
        return np.column_stack((x.ravel(), y.ravel()))

    @staticmethod
    def _sigmoid(values: np.ndarray) -> np.ndarray:
        return 1.0 / (1.0 + np.exp(-values))

    @staticmethod
    def _positive_int(value: Any, name: str) -> int:
        value = int(value)
        if value <= 0:
            raise RuntimeError(f"{name} must be a positive integer")
        return value

    @staticmethod
    def _threshold(value: Any, name: str) -> float:
        value = float(value)
        if not 0.0 < value < 1.0:
            raise RuntimeError(f"{name} must be between 0 and 1 (exclusive)")
        return value

    @staticmethod
    def _input_size(shape: Any, configured: Any) -> tuple[int, int]:
        if configured is not None:
            if len(configured) != 2:
                raise RuntimeError("input_size must be [width, height]")
            return tuple(RdkHbmBackend._positive_int(item, "input_size item") for item in configured)
        if len(shape) < 3:
            raise RuntimeError(f"unsupported RDK model input shape: {shape}")
        height, width = (shape[2], shape[3]) if len(shape) >= 4 and shape[1] == 3 else (shape[1], shape[2])
        return RdkHbmBackend._positive_int(width, "model input width"), RdkHbmBackend._positive_int(height, "model input height")

    def close(self) -> None:
        self.runtime = None
        self.model_name = self.input_name = ""
        self.output_names = []
