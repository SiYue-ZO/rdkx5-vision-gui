from __future__ import annotations

import importlib
import time
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from app.common.models import Detection, PerformanceMetrics
from app.inference.base import InferenceBackend
from app.inference.utils import bgr_to_nv12, letterbox


class RdkRunnerCallback(Protocol):
    """适配特定 BSP 的 BPU 前向调用。

    输入是已经完成 Letterbox 和 BGR→NV12 的连续数组；返回值必须按模型输出节点
    顺序转换为 NumPy 数组。实现中可以设置 BPU Core、优先级和量化参数。
    """

    def __call__(self, tensor: np.ndarray) -> list[np.ndarray]: ...


class YoloDecoderCallback(Protocol):
    """把模型专属输出转换为平台统一检测结果。

    ``ratio`` 和 ``padding`` 来自 Letterbox；``original_shape`` 是原始 BGR 图像形状。
    回调必须完成置信度过滤、NMS 和坐标回映，返回原图坐标系的 Detection。
    """

    def __call__(
        self,
        outputs: list[np.ndarray],
        ratio: float,
        padding: tuple[int, int],
        original_shape: tuple[int, ...],
    ) -> list[Detection]: ...


class RdkHbmBackend(InferenceBackend):
    """RDK X5 hbm_runtime adapter.

    BSP releases expose slightly different Python objects. A runtime callable may be injected
    through config['runner']; otherwise this adapter probes the common HB_HBMRuntime API.
    Model-specific output decoding is injected through config['decoder'].
    """

    name = "rdk-hbm"

    def __init__(self) -> None:
        self.runtime = self.model = None
        # runner 解决不同 BSP 的 hbm_runtime 调用差异。
        self.runner: RdkRunnerCallback | None = None
        # decoder 解决 YOLO 版本、量化方式和输出节点协议差异。
        self.decoder: YoloDecoderCallback | None = None

    @property
    def available(self) -> bool:
        try:
            return importlib.util.find_spec("hbm_runtime") is not None
        except (ImportError, AttributeError):
            return False

    def load(self, config: dict[str, Any]) -> None:
        """加载 `.bin`，也允许通过 config 注入 runner/decoder 回调。

        示例：``{"runner": my_runner, "decoder": my_decoder, "input_size": [640, 640]}``。
        注入 runner 后不会自动创建 ``HB_HBMRuntime``，适合适配官方示例的具体 API。
        """
        self.input_size = tuple(config.get("input_size", [640, 640]))
        self.decoder = config.get("decoder")
        self.runner = config.get("runner")
        if self.runner:
            return
        model_path = Path(config.get("model", ""))
        if not model_path.is_file():
            raise RuntimeError(f"RDK .bin 模型不存在: {model_path}")
        try:
            hbm = importlib.import_module("hbm_runtime")
        except ImportError as exc:
            raise RuntimeError("当前环境没有 hbm_runtime；请在匹配 BSP 的 RDK X5 上运行") from exc
        runtime_class = getattr(hbm, "HB_HBMRuntime", None)
        if runtime_class is None:
            raise RuntimeError("hbm_runtime 中没有 HB_HBMRuntime，请按当前 BSP 注入 runner 适配器")
        self.runtime = runtime_class(str(model_path))
        model_name = config.get("model_name")
        names = getattr(self.runtime, "model_names", [])
        chosen = model_name or (names[0] if names else None)
        self.model = self.runtime.get_model(chosen) if chosen else self.runtime

        def default_runner(tensor: np.ndarray) -> list[np.ndarray]:
            if hasattr(self.model, "forward"):
                return [np.asarray(item) for item in self.model.forward(tensor)]
            if hasattr(self.model, "run"):
                return [np.asarray(item) for item in self.model.run(tensor)]
            raise RuntimeError("无法识别当前 hbm_runtime 推理方法，请注入 runner")

        self.runner = default_runner

    def infer(self, frame: np.ndarray) -> tuple[list[Detection], PerformanceMetrics]:
        """执行 Letterbox、NV12 转换、BPU 前向与模型专属解码。"""
        if self.runner is None:
            raise RuntimeError("BPU 模型尚未加载")
        total_started = time.perf_counter()
        started = total_started
        image, ratio, padding = letterbox(frame, self.input_size)
        tensor = bgr_to_nv12(image)
        preprocess_ms = (time.perf_counter() - started) * 1000
        started = time.perf_counter()
        outputs = self.runner(tensor)
        inference_ms = (time.perf_counter() - started) * 1000
        started = time.perf_counter()
        detections = self.decoder(outputs, ratio, padding, frame.shape) if self.decoder else []
        postprocess_ms = (time.perf_counter() - started) * 1000
        return detections, PerformanceMetrics(
            preprocess_ms=preprocess_ms,
            inference_ms=inference_ms,
            postprocess_ms=postprocess_ms,
            total_ms=(time.perf_counter() - total_started) * 1000,
        )

    def close(self) -> None:
        self.runner = self.model = self.runtime = None
