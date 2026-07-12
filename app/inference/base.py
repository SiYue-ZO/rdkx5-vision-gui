from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import numpy as np

from app.common.models import Detection, PerformanceMetrics


class InferenceBackend(ABC):
    """YOLO/其他模型推理后端的统一接口。

    后端只负责模型预处理、执行与后处理，不负责绘制 GUI。这样 Mock、ONNX 和
    RDK BPU 后端能够被同一个 :class:`YoloAlgorithm` 使用。
    """

    name = "base"

    @abstractmethod
    def load(self, config: dict[str, Any]) -> None:
        """加载模型和类别配置；每次后端启用时调用一次。"""
        ...

    @abstractmethod
    def infer(self, frame: np.ndarray) -> tuple[list[Detection], PerformanceMetrics]:
        """输入 BGR 图像，返回原图坐标系中的检测结果和分阶段性能数据。"""
        ...

    @abstractmethod
    def close(self) -> None:
        """释放 Session/BPU 模型等后端资源，必须允许重复调用。"""
        ...

    @property
    def available(self) -> bool:
        """当前机器是否具备此后端所需的运行库。"""
        return True
