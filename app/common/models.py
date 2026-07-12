from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np


class ParameterType(str, Enum):
    INT = "int"
    FLOAT = "float"
    BOOL = "bool"
    CHOICE = "choice"
    TEXT = "text"


@dataclass(slots=True)
class ParameterSpec:
    name: str
    label: str
    type: ParameterType
    default: Any
    minimum: float | None = None
    maximum: float | None = None
    step: float | None = None
    choices: list[str] = field(default_factory=list)


@dataclass(slots=True)
class Detection:
    """统一目标检测结果，坐标使用原始图像像素的 xyxy 格式。"""

    x1: float
    y1: float
    x2: float
    y2: float
    score: float
    class_id: int
    label: str = ""

    @property
    def center(self) -> tuple[float, float]:
        return ((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)


@dataclass(slots=True)
class PerformanceMetrics:
    """一帧的分阶段耗时/FPS；自定义后端应尽量填写其负责的阶段。"""

    capture_ms: float = 0.0
    preprocess_ms: float = 0.0
    inference_ms: float = 0.0
    postprocess_ms: float = 0.0
    total_ms: float = 0.0
    capture_fps: float = 0.0
    inference_fps: float = 0.0
    display_fps: float = 0.0
    dropped_frames: int = 0


@dataclass(slots=True)
class AlgorithmResult:
    """算法与 GUI/串口业务之间唯一的数据交换对象。

    ``image`` 是 BGR 显示图；``detections`` 保留机器可读目标；``control_data`` 是可选
    的已编码串口字节，非空时主窗口自动发送；自定义附加信息放入 ``metadata``。
    """

    image: np.ndarray
    detections: list[Detection] = field(default_factory=list)
    metrics: PerformanceMetrics = field(default_factory=PerformanceMetrics)
    control_data: bytes | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class FramePacket:
    frame: np.ndarray
    sequence: int
    captured_at: float
    capture_ms: float = 0.0
