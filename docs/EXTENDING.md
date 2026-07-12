# 二次开发指南：算法、YOLO 与串口回调

本文是后续开发的主入口。平台把扩展分成三层：

1. 普通视觉功能写成 `VisionAlgorithm` 插件。
2. YOLO 模型运行方式写成 `InferenceBackend`，RDK 的 BSP 差异由 `runner` 适配，模型输出差异由 `decoder` 适配。
3. 串口业务通过主窗口公开回调处理；数据包格式实现 `PacketProtocol`。

## 1. 开发环境与验证命令

项目使用 `uv` 和 Python 3.11：

```powershell
uv sync --extra desktop --extra dev
uv run python main.py
uv run pytest
uv run ruff check .
```

不要在 `.venv` 中手工执行 `pip install`；新增依赖应写入 `pyproject.toml`，然后执行 `uv sync`。

## 2. 编写普通视觉算法

新建 `app/algorithms/plugins/my_algorithm.py`：

```python
from typing import Any

import cv2
import numpy as np

from app.algorithms.base import VisionAlgorithm
from app.common.models import (
    AlgorithmResult,
    Detection,
    ParameterSpec,
    ParameterType,
)


class MyAlgorithm(VisionAlgorithm):
    # name 会写入 YAML，发布后应保持稳定。
    name = "my_algorithm"
    display_name = "我的目标算法"
    parameters = [
        ParameterSpec("threshold", "阈值", ParameterType.INT, 100, 0, 255, 1),
        ParameterSpec("enabled", "启用输出", ParameterType.BOOL, True),
    ]

    def initialize(self, config: dict[str, Any] | None = None) -> None:
        super().initialize(config)
        # 在这里加载标定文件、模板或模型；不要创建/修改 Qt 控件。

    def process(self, frame: np.ndarray, params: dict[str, Any]) -> AlgorithmResult:
        # frame 是 BGR uint8。绘图前复制，避免污染左侧原图。
        output = frame.copy()
        threshold = int(params["threshold"])
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        _, mask = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY)

        detections: list[Detection] = []
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            x, y, width, height = cv2.boundingRect(contour)
            if width * height < 100:
                continue
            detections.append(Detection(x, y, x + width, y + height, 1.0, 0, "target"))
            cv2.rectangle(output, (x, y), (x + width, y + height), (0, 255, 0), 2)

        # control_data 必须是已经编码好的 bytes；非空时主窗口自动发串口。
        control_data = None
        if params["enabled"] and detections:
            center_x, center_y = detections[0].center
            control_data = f"{center_x:.0f},{center_y:.0f}\n".encode("ascii")

        return AlgorithmResult(
            image=output,
            detections=detections,
            control_data=control_data,
            metadata={"mask": mask, "threshold": threshold},
        )

    def shutdown(self) -> None:
        # 关闭文件、设备或模型。方法必须允许资源只初始化了一部分的情况。
        pass
```

然后在 `app/algorithms/registry.py` 的 `create_default_registry()` 中导入并注册：

```python
from app.algorithms.plugins.my_algorithm import MyAlgorithm

for item in (..., MyAlgorithm):
    registry.register(item)
```

参数变化会自动保存到 `configs/app.yaml`。`process()` 运行在推理线程中，应避免无限循环；单帧异常会进入 GUI 日志。

### AlgorithmResult 字段

| 字段 | 用途 |
|---|---|
| `image` | 必填，供 GUI 显示的 BGR 图像 |
| `detections` | 机器可读的目标框、类别、置信度和中心点 |
| `metrics` | 预处理、推理、后处理等性能信息 |
| `control_data` | 可选的已编码串口数据，主窗口自动发送 |
| `metadata` | mask、姿态、调试数值等自定义信息，不建议放不可释放的硬件缓冲 |

## 3. 使用算法结果回调

如果业务逻辑不适合写进算法，可以继承 `MainWindow`：

```python
from app.common.models import AlgorithmResult
from app.ui.main_window import MainWindow


class ContestWindow(MainWindow):
    def on_algorithm_result(self, result: AlgorithmResult) -> None:
        # 本方法在 Qt 主线程调用，只做快速分发。
        if result.detections:
            target = max(result.detections, key=lambda item: item.score)
            x, y = map(round, target.center)
            payload = x.to_bytes(2, "little") + y.to_bytes(2, "little")
            self.send_protocol_frame(command=0x10, payload=payload)
```

若这里需要写数据库、访问网络或执行大量计算，应再创建 Worker，不要阻塞 Qt 主线程。

可以新建 `contest_main.py` 启动自定义窗口，而不修改平台入口：

```python
import sys

from PyQt5.QtWidgets import QApplication

from app.common.logging import configure_logging
from my_contest_window import ContestWindow


configure_logging()
app = QApplication(sys.argv)
window = ContestWindow()
window.show()
raise SystemExit(app.exec_())
```

运行 `uv run python contest_main.py`。比赛业务文件建议放在独立包中，升级平台核心代码时更容易合并。

## 4. YOLO 接口

### 4.1 普通 PC 的 ONNX 模型

安装后端：

```powershell
uv sync --extra desktop --extra onnx
```

修改 `configs/app.yaml`：

```yaml
inference:
  backend: onnxruntime
  model: models/my_model.onnx
  labels: [red, blue]
  confidence: 0.25
  nms: 0.45
```

当前 ONNX 后端支持常见 `Nx6` 或 `Nx(4+classes)` Detect 输出。模型输出不同（例如分割、姿态、多输出头）时，应继承 `InferenceBackend`，实现 `load/infer/close`，并在 `app/inference/__init__.py:create_backend()` 注册后端名称。

### 4.2 自定义推理后端

```python
class MyBackend(InferenceBackend):
    name = "my-backend"

    def load(self, config):
        self.model = load_model(config["model"])

    def infer(self, frame):
        # 返回框必须映射回 frame 的原始像素坐标。
        detections = [Detection(10, 20, 100, 120, 0.9, 0, "target")]
        return detections, PerformanceMetrics(inference_ms=5.0)

    def close(self):
        self.model = None
```

`YoloAlgorithm` 会负责 GUI 阈值过滤和绘制，不需要在后端中接触 Qt。

### 4.3 RDK X5 的 runner 和 decoder

RDK BSP 与 YOLO 转换产物可能不同，因此分为两个回调：

```python
def my_runner(nv12_tensor: np.ndarray) -> list[np.ndarray]:
    # nv12_tensor 已是 H*3/2 x W 的 uint8 NV12。
    # 按当前 BSP 的 hbm_runtime 官方示例设置输入、BPU Core、优先级并执行。
    outputs = board_model.forward(nv12_tensor)
    return [np.asarray(output) for output in outputs]


def my_decoder(outputs, ratio, padding, original_shape):
    # 1. 按量化参数反量化输出。
    # 2. 解码对应 YOLO 版本的类别分数和 xywh/xyxy。
    # 3. 置信度过滤与分类别 NMS。
    # 4. 去掉 padding 并除以 ratio，映射回原图坐标。
    # 5. 按原图宽高裁剪坐标。
    return [Detection(x1, y1, x2, y2, score, class_id, label)]
```

创建后端时注入：

```python
backend = RdkHbmBackend()
backend.load({
    "input_size": [640, 640],
    "runner": my_runner,
    "decoder": my_decoder,
})
```

如果不注入 `runner`，后端会尝试常见的 `HB_HBMRuntime` API。正式比赛模型必须用 `hrt_model_exec model_info` 确认输入格式、输出节点、量化参数，并为该模型编写 decoder；不能把其他 YOLO 版本的解码器直接套用。

## 5. 串口发送接口

主窗口提供两个方法：

```python
self.send_serial_data(b"raw bytes")
self.send_protocol_frame(command=0x10, payload=b"payload")
```

- `send_serial_data` 发送原始 bytes，不做任何编码。
- `send_protocol_frame` 默认使用 `BinaryFrameProtocol`，也可传入自定义协议实例。
- 实际 pyserial 写入发生在串口 Worker 线程。
- `AlgorithmResult.control_data` 非空时等价于自动调用 `send_serial_data`。
- 串口未打开时发送不会阻塞界面，但会触发 `on_serial_error`。

## 6. 串口接收回调

可以覆盖以下方法：

```python
class ContestWindow(MainWindow):
    def on_serial_received(self, data: bytes) -> None:
        # 原始字节块回调。需要默认数据显示和 AA55 拆包时调用 super。
        super().on_serial_received(data)

    def on_protocol_frame(self, frame: ProtocolFrame) -> None:
        # 这里只会收到已经通过长度和 CRC 校验的完整帧。
        if frame.command == 0x01:
            self.send_protocol_frame(0x81, b"pong")

    def on_serial_status(self, text: str) -> None:
        super().on_serial_status(text)

    def on_serial_error(self, text: str) -> None:
        super().on_serial_error(text)
```

串口读取边界与协议帧边界无关。一次回调可能只有半帧，也可能包含多帧。内置 `BinaryFrameStreamParser.feed(data)` 已处理半包、粘包、帧头前噪声和 CRC 错误恢复。

## 7. 自定义数据包协议

协议至少实现 `encode` 和 `decode`：

```python
import struct

from app.serial.protocol import ProtocolFrame


class MyProtocol:
    HEADER = b"\x5A\xA5"

    def encode(self, command: int, payload: bytes = b"") -> bytes:
        body = bytes([command, len(payload)]) + payload
        checksum = sum(body) & 0xFF
        return self.HEADER + body + bytes([checksum])

    def decode(self, data: bytes) -> ProtocolFrame:
        if not data.startswith(self.HEADER):
            raise ValueError("bad header")
        command, length = data[2], data[3]
        if len(data) != 5 + length or sum(data[2:-1]) & 0xFF != data[-1]:
            raise ValueError("bad packet")
        return ProtocolFrame(command, data[4:-1])
```

自定义协议通常还要编写对应的增量 StreamParser。Parser 应维护私有 `bytearray`，寻找帧头、读取长度、等待完整帧、校验失败后重新同步。不要在 `on_serial_received` 中直接对每个 data 调用完整包 `decode`。

发送自定义协议：

```python
self.send_protocol_frame(0x20, payload, protocol=MyProtocol())
```

## 8. 推荐的后续开发顺序

1. 先用图片和 Mock 后端完成算法与 GUI 参数调试。
2. 为算法添加纯函数单元测试，测试固定输入产生的 Detection/协议 payload。
3. 用虚拟串口或回环测试自定义协议的半包、粘包、坏 CRC 和断线行为。
4. 在 PC 使用 ONNX 对照训练框架输出，确认 Letterbox 和坐标回映。
5. 在 RDK X5 运行环境探针和官方 `.bin` 示例，再实现 runner。
6. 根据该 `.bin` 的输出节点编写 decoder，并用同一张图片比较 PC/RDK 检测结果。
7. 最后接真实相机和下位机，进行反复开关及长时间稳定性测试。
