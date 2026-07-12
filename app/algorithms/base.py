from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import numpy as np

from app.common.models import AlgorithmResult, ParameterSpec


class VisionAlgorithm(ABC):
    """所有视觉算法插件必须继承的接口。

    生命周期由推理 Worker 管理，依次为 ``initialize -> process(多次) -> shutdown``。
    这些方法运行在推理线程中，禁止在其中读写 Qt 控件。跨线程输出应全部放进
    :class:`AlgorithmResult`，由主线程的 ``on_algorithm_result`` 回调消费。
    """

    # 注册表使用 name 作为稳定 ID；保存到 YAML 后不应随意修改。
    name = "base"
    # display_name 仅用于 GUI 展示，可以使用中文。
    display_name = "Base"
    # GUI 根据参数声明自动创建控件，并将当前值作为 process 的 params 传入。
    parameters: list[ParameterSpec] = []

    def initialize(self, config: dict[str, Any] | None = None) -> None:
        """初始化算法资源，每次启动视频管线调用一次。

        可在这里加载模型、标定文件或查找硬件。失败时抛出带有明确原因的异常，
        Worker 会将错误显示到日志和状态栏。
        """
        self.config = config or {}

    @abstractmethod
    def process(self, frame: np.ndarray, params: dict[str, Any]) -> AlgorithmResult:
        """处理一帧 BGR uint8 图像并返回结构化结果。

        ``frame`` 由采集线程提供。若要在图像上绘制，请先 ``frame.copy()``，避免修改
        原始画面。``params`` 是 GUI 当前参数的快照，因此本方法无需加锁。

        ``AlgorithmResult.control_data`` 非空时，主窗口会自动把它交给串口发送接口。
        """
        ...

    def shutdown(self) -> None:
        """释放模型、文件、设备等资源；即使处理中途异常也会被调用。"""
        pass
