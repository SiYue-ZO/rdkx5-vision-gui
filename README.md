# RDK X5 视觉调试平台

一个面向大学生电子设计竞赛、机器人视觉和嵌入式 AI 调试的跨平台桌面工具。项目使用 Python、PyQt5、OpenCV 和 `uv`，可在 Windows/Linux PC 上完成绝大多数界面、算法、YOLO 与串口协议开发，并为 D-Robotics RDK X5 提供 MIPI Camera 和 Bayes-e BPU 适配接口。

> 当前状态：PC 端核心功能和自动化测试已完成。RDK X5 的 `.bin` 模型、MIPI Camera、真实串口及长时间稳定性仍需使用目标开发板和实际外设验收。

## 功能

- 图片、循环视频、USB 摄像头输入，以及 `libsrcampy` MIPI Camera 适配器。
- 独立采集、推理和串口线程，只保留最新帧，避免慢推理造成延迟累积。
- 原图/结果双画面、等比例显示、中心十字线、ROI、像素 RGB/HSV、截图和后台录像。
- 可插拔视觉算法和自动参数面板，内置透传、Canny、HSV 目标提取和 YOLO 插件。
- Mock、ONNX Runtime、RDK `hbm_runtime` 和旧 BSP 推理后端接口。
- Letterbox、BGR→NV12、常见 YOLO Detect 解码、分类别 NMS 和坐标回映。
- 串口枚举、ASCII/HEX 收发、定时发送、字节统计及异常提示。
- 可替换数据包协议、CRC16-Modbus、半包/粘包/噪声处理和完整帧回调。
- YAML 配置、轮转日志、环境探针、统一异常处理和安全资源释放。

## 环境要求

- Python 3.10～3.12，推荐并默认使用 Python 3.11。
- [`uv`](https://docs.astral.sh/uv/)。
- Windows 10/11、普通 Linux，或运行 Ubuntu 22.04 系列系统的 RDK X5。

所有 Python 环境与依赖均由 `uv` 管理。不要在 `.venv` 中手工运行 `pip install`。

## 快速开始

### Windows / Linux PC

```shell
uv sync --extra desktop --extra dev
uv run python main.py
```

也可以使用安装后的命令入口：

```shell
uv run rdkx5-vision
```

首次运行时 `uv` 会根据 `.python-version` 获取 Python 3.11，并按照 `uv.lock` 创建可复现的本地虚拟环境。

### ONNX Runtime

```shell
uv sync --extra desktop --extra onnx
```

然后修改 `configs/app.yaml`：

```yaml
inference:
  backend: onnxruntime
  model: models/model.onnx
  labels: [class0, class1]
  confidence: 0.25
  nms: 0.45
```

### RDK X5

RDK 的 PyQt5、OpenCV、`hbm_runtime` 和相机库应优先使用与 BSP 匹配的系统软件包，不要用 PyPI 包覆盖板端运行库。

```shell
bash scripts/install-rdkx5.sh
uv run rdkx5-probe
uv run python main.py
```

环境探针会生成被 Git 忽略的 `environment-report.json`，用于检查 Qt、OpenCV、BPU Runtime、MIPI Camera 库、视频设备和串口设备。

## 使用流程

1. 从工具栏打开图片、视频或 USB 摄像头。
2. 选择透传、Canny、HSV 或 YOLO 算法。
3. 在右侧算法面板实时修改参数。
4. 使用串口面板选择端口并进行 ASCII/HEX 收发。
5. 需要比赛控制协议时，通过算法的 `control_data` 或主窗口回调发送结构化数据。

没有 BPU 或模型时，YOLO 默认使用 Mock 后端，便于先打通 GUI、算法结果和串口业务链路。

## 二次开发

项目提供稳定的扩展接口：

- `VisionAlgorithm`：编写传统视觉、识别、跟踪等算法。
- `InferenceBackend`：添加新的 ONNX、BPU 或其他模型运行时。
- `RdkRunnerCallback`：适配特定 RDK BSP 的 BPU 前向调用。
- `YoloDecoderCallback`：适配不同 YOLO 版本和 `.bin` 输出节点。
- `on_algorithm_result()`：接收每帧结构化算法结果。
- `send_serial_data()` / `send_protocol_frame()`：发送原始字节或协议帧。
- `on_serial_received()` / `on_protocol_frame()`：处理原始串口块或完整校验帧。
- `PacketProtocol`：实现自定义帧头、长度、命令字和校验协议。

完整代码示例、线程约束和推荐开发顺序见 [二次开发指南](docs/EXTENDING.md)。

## 项目结构

```text
.
├─ app/
│  ├─ algorithms/      # 算法接口、注册表和内置插件
│  ├─ common/          # 配置、日志、指标和数据模型
│  ├─ inference/       # Mock、ONNX 和 RDK 推理后端
│  ├─ serial/          # 串口传输、协议与流式拆包
│  ├─ tools/           # RDK/PC 环境探针
│  ├─ ui/              # PyQt5 主窗口和控件
│  ├─ video/           # 图片、视频、USB/MIPI 视频源
│  └─ workers/         # 采集、推理、串口和录像 Worker
├─ configs/            # 应用、相机、模型和串口 YAML 配置
├─ docs/               # 扩展、部署、协议与排障文档
├─ models/             # 本地模型目录，模型文件默认不提交
├─ scripts/            # Windows/Linux/RDK 启动与安装脚本
├─ tests/              # 非硬件自动化测试
├─ main.py             # 源码运行入口
├─ pyproject.toml      # 项目元数据和依赖声明
└─ uv.lock             # uv 锁文件
```

## 配置

- `configs/app.yaml`：当前算法、算法参数和推理后端。
- `configs/camera.yaml`：USB/MIPI 相机参数。
- `configs/serial.yaml`：串口默认值和预设命令。
- `configs/models.yaml`：Mock、ONNX 与 RDK 模型示例。

模型文件、录像、截图、运行日志和环境报告默认不会提交到 Git。

## 测试

```shell
uv sync --extra desktop --extra dev
uv run pytest
uv run ruff check .
uv run python -m compileall -q app tests
```

当前自动化测试覆盖配置读写、算法注册与处理、最新帧缓冲、Letterbox/NV12/NMS、CRC 和串口流式拆包。

硬件验收必须在目标 RDK X5 上完成：

- Qt/HDMI 最小窗口与完整 GUI。
- USB 或 MIPI Camera 连续取帧。
- 官方或比赛 `.bin` 模型 BPU 推理。
- 下位机串口收发、拔插和异常恢复。
- MIPI/BPU 30 分钟稳定性和整机 2 小时稳定性。

## 文档

- [二次开发指南](docs/EXTENDING.md)
- [算法插件说明](docs/ALGORITHM_PLUGIN.md)
- [串口协议说明](docs/PROTOCOL.md)
- [部署与硬件验收](docs/DEPLOYMENT.md)
- [现场排障清单](docs/TROUBLESHOOTING.md)
- [原始开发计划](DEVELOPMENT_PLAN.md)

## 注意事项

- PyQt5 使用 GPL/商业双许可证；闭源商业发布前请重新评估许可证。
- 不同 RDK BSP 的 BPU Python API 可能不同，部署时必须以当前系统官方示例为准。
- 不同 YOLO 版本、量化方式和输出节点需要对应的 decoder，不能直接混用。
- SSH X11 转发不适合高帧率调试，RDK 端建议使用 HDMI 本地桌面。
