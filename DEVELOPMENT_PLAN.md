# RDK X5 电赛视觉调试平台开发计划

## 1. 项目目标

开发一套基于 Python Qt 的跨平台视觉调试平台，主要运行于 D-Robotics RDK X5 开发板，同时支持在 Windows 和普通 Linux 电脑上进行界面、算法和通信逻辑开发。

平台面向大学生电子设计竞赛等快速开发场景，首期提供以下能力：

- 摄像头、视频文件和图片输入。
- 实时画面显示、视觉结果叠加和性能统计。
- 可插拔的 OpenCV 传统视觉算法。
- 简单实用的串口调试工具。
- RDK X5 Bayes-e BPU 上的 YOLO 推理。
- 参数实时修改、配置保存、日志记录和结果采集。
- 在没有 RDK X5 的电脑上，通过模拟或 CPU 后端完成大部分开发。

## 2. 调研结论

### 2.1 RDK X5 平台

根据 D-Robotics 官方资料，RDK X5 的主要能力包括：

- 8 核 ARM Cortex-A55 CPU。
- Bayes-e BPU，约 10 TOPS INT8 推理算力。
- Ubuntu 22.04 系统环境。
- 支持 2 路 MIPI Camera 和 4 路 USB 3.0 接口。
- RDK X5 BPU 部署模型使用 `.bin` 格式。
- 当前官方 YOLO Python 示例主要使用 `hbm_runtime` 调用 BPU。
- 部分旧系统和旧示例使用 `hobot_dnn/pyeasy_dnn`，需要根据开发板实际系统决定是否提供兼容层。

参考资料：

- [RDK 官方文档](https://github.com/D-Robotics/rdk_doc/blob/main/docs/RDK.md)
- [RDK X5 Ultralytics YOLO 示例](https://github.com/D-Robotics/rdk_model_zoo/tree/rdk_x5/samples/vision/ultralytics_yolo)
- [RDK X5 YOLO Python Runtime](https://github.com/D-Robotics/rdk_model_zoo/tree/rdk_x5/samples/vision/ultralytics_yolo/runtime/python)
- [RDK X5 YOLO 模型转换说明](https://github.com/D-Robotics/rdk_model_zoo/tree/rdk_x5/samples/vision/ultralytics_yolo/conversion)

### 2.2 Qt Python 选型

首期建议使用 **PyQt5**：

- RDK 官方系统资料中明确出现 `python3-pyqt5` 软件包。
- Ubuntu 22.04 ARM64 上的安装可行性通常优于直接使用 PySide6 的 PyPI wheel。
- Windows、Ubuntu PC 和 RDK X5 均可使用。
- Qt5 在嵌入式 Linux 上较成熟，适合电赛期间优先保证稳定性。

注意事项：

- PyQt5 使用 GPL/商业双许可证。电赛和内部开发通常不构成问题，如果未来进行闭源商业发布，应重新评估许可证或迁移到 PySide6。
- UI 层需要隔离 Qt 相关代码，业务、视觉和推理模块不得直接依赖具体 Qt 绑定，以降低后续迁移成本。

### 2.3 串口选型

串口首期使用 `pyserial`，串口收发由独立 Worker 管理：

- Windows 和 Linux 行为较统一。
- 安装和部署简单。
- 支持串口枚举、超时、二进制数据和常用串口参数。
- 不依赖额外的 Qt SerialPort ARM64 软件包。

### 2.4 视频输入策略

视频源按统一接口设计，分阶段支持：

1. 本地图片和视频文件。
2. OpenCV `VideoCapture` USB 摄像头。
3. RDK X5 MIPI Camera。
4. 可选的 TROS/ROS 2 图像话题或网络视频流。

MIPI Camera 不与 OpenCV USB 输入强行绑定。后续根据实际相机和系统版本，使用 `hobot_vio/libsrcampy`、TROS 图像节点或 RDK 原生多媒体链路实现独立适配器。

## 3. 总体技术方案

### 3.1 推荐技术栈

| 模块 | 首选方案 | 说明 |
|---|---|---|
| GUI | PyQt5 | 优先保证 RDK X5 ARM64 可部署性 |
| 图像处理 | OpenCV、NumPy | 跨平台、生态成熟 |
| 串口 | pyserial | 简单、跨平台 |
| 配置 | YAML | 适合人工编辑和参数管理 |
| 日志 | Python `logging` | 同时输出文件和 GUI 控制台 |
| PC 推理 | Mock，可选 ONNX Runtime | 无开发板时调试业务流程 |
| RDK 推理 | `hbm_runtime` | 当前 RDK X5 官方示例使用的 BPU API |
| 旧版兼容 | `hobot_dnn/pyeasy_dnn` | 根据实际 BSP 决定是否实现 |
| 测试 | pytest | 测试协议、配置、后处理等非硬件模块 |

### 3.2 数据流

```text
摄像头 / 视频文件 / 图片 / MIPI
                 │
                 ▼
          VideoSource 采集线程
                 │
          最新帧缓冲（1～2 帧）
                 │
                 ▼
       Algorithm Pipeline 推理线程
          ├─ OpenCV 传统视觉插件
          ├─ PC Mock/ONNX 后端
          └─ RDK X5 BPU 后端
                 │
          图像 + 结构化检测结果
                 │
                 ▼
             Qt 主界面

串口设备 ── SerialWorker ── Qt Signal ── 串口调试面板
```

### 3.3 线程模型

- Qt 主线程只负责界面事件和画面显示。
- 视频采集运行在独立线程。
- 算法预处理、BPU 推理和后处理运行在推理线程。
- 串口收发运行在独立 Worker 中。
- 工作线程通过 Qt Signal 向主线程传递状态和结果。
- 禁止工作线程直接修改 Qt 控件。
- 视频队列采用有限长度，只保留最新帧，避免推理不足时延迟持续累积。
- 停止任务时必须支持安全退出、释放摄像头、模型和串口资源。

## 4. 功能规划

### 4.1 主界面

主窗口采用菜单栏、工具栏、中央视频区域、状态栏和可停靠面板组合。

计划包含以下区域：

- 视频显示区域。
- 视频源控制面板。
- 算法和模型参数面板。
- 串口调试面板。
- 日志控制台。
- 性能与设备状态面板。

### 4.2 视频视觉调试

- 打开摄像头、视频文件和图片。
- 选择摄像头设备、分辨率和帧率。
- 原图、结果图和左右对比显示。
- 开始、暂停、继续、停止和单帧处理。
- 等比例缩放和窗口自适应。
- 截图及结果保存。
- 可选视频录像。
- 鼠标查看像素坐标与 RGB/HSV 值。
- ROI 框选。
- 中心十字线、参考线和目标中心点显示。
- 显示采集 FPS、推理 FPS、显示 FPS和丢帧数。
- 显示预处理、BPU 推理、后处理及总延迟。

### 4.3 视觉算法插件

定义统一算法接口，示意如下：

```python
class VisionAlgorithm:
    def initialize(self, config): ...
    def process(self, frame, params): ...
    def shutdown(self): ...
```

算法返回值至少包含：

- 用于显示的图像或绘制指令。
- 结构化检测结果。
- 性能指标。
- 可选的下位机控制数据。

首期提供简单示例插件：

- 原图透传。
- 灰度化或边缘检测。
- HSV 阈值与目标轮廓提取。
- YOLO 目标检测。

后续可以添加圆检测、直线检测、二维码、数字识别、装甲板识别和目标跟踪等电赛算法。

### 4.4 动态参数调试

- 算法声明自己的参数定义。
- GUI 根据定义自动生成滑块、数值框、复选框和下拉框。
- 参数变化后即时通知算法。
- 支持恢复默认值。
- 支持保存和加载 YAML 配置。
- 区分全局参数、视频源参数和算法参数。

### 4.5 串口调试

- 自动扫描串口设备。
- 配置波特率、数据位、停止位、校验位和流控。
- 打开、关闭和刷新串口。
- ASCII 和 HEX 收发。
- 可选时间戳和自动换行。
- 定时发送。
- 接收暂停与清空。
- 收发字节统计。
- 串口日志保存。
- 支持预设发送命令。
- 预留比赛通信协议接口，包括帧头、长度、命令字、负载和 CRC。
- 支持将视觉目标坐标或类别结果发送给下位机。

### 4.6 RDK X5 BPU YOLO

首期完成目标检测，之后再扩展分类、分割和姿态估计。

功能包括：

- 自动检测 `hbm_runtime` 是否可用。
- 加载 RDK X5 `.bin` 模型。
- 加载类别文件和模型配置。
- 显示模型输入输出信息。
- 配置置信度和 NMS 阈值。
- 配置类别过滤。
- 配置 BPU Core 和任务优先级。
- BGR 图像缩放、Letterbox 和 NV12 预处理。
- BPU 前向推理。
- YOLO 输出解码和 NMS。
- 检测框、类别、置信度和中心点绘制。
- 输出采集、预处理、推理、后处理和总耗时。
- 模型加载失败时给出清晰错误，不使整个 GUI 崩溃。

### 4.7 PC 调试后端

普通电脑通常没有 RDK BPU，因此需要提供：

- Mock 推理后端，用固定或简单规则生成检测结果。
- 可选 ONNX Runtime 后端，用于验证算法流程和模型输出。
- 与 RDK BPU 后端一致的调用接口和结果数据结构。
- GUI 自动显示当前后端，不允许将 PC 推理性能误认为 BPU 性能。

## 5. 推荐目录结构

```text
rdkx5_vision_gui/
├─ main.py
├─ pyproject.toml
├─ requirements-desktop.txt
├─ requirements-rdkx5.txt
├─ README.md
├─ configs/
│  ├─ app.yaml
│  ├─ camera.yaml
│  ├─ serial.yaml
│  └─ models.yaml
├─ app/
│  ├─ ui/
│  │  ├─ main_window.py
│  │  ├─ widgets/
│  │  └─ qt_compat.py
│  ├─ workers/
│  │  ├─ video_worker.py
│  │  ├─ inference_worker.py
│  │  └─ serial_worker.py
│  ├─ video/
│  │  ├─ base.py
│  │  ├─ opencv_source.py
│  │  └─ rdk_mipi_source.py
│  ├─ algorithms/
│  │  ├─ base.py
│  │  ├─ registry.py
│  │  └─ plugins/
│  ├─ inference/
│  │  ├─ base.py
│  │  ├─ mock_backend.py
│  │  ├─ onnx_backend.py
│  │  ├─ rdk_hbm_backend.py
│  │  └─ rdk_legacy_backend.py
│  ├─ serial/
│  │  ├─ transport.py
│  │  └─ protocol.py
│  └─ common/
│     ├─ config.py
│     ├─ logging.py
│     ├─ metrics.py
│     └─ models.py
├─ models/
├─ logs/
├─ recordings/
├─ scripts/
└─ tests/
```

## 6. 分阶段开发计划

### 阶段 0：开发板环境验证

预计时间：0.5～1 天。

任务：

- 获取 RDK OS、BSP、Python 和内核版本。
- 验证 PyQt5 安装和最小窗口启动。
- 验证 HDMI/桌面显示环境。
- 检查 OpenCV、NumPy、pyserial 和 YAML 依赖。
- 检查 `hbm_runtime` 版本及官方示例能否运行。
- 检查 USB 摄像头设备和支持的分辨率、格式。
- 确认 MIPI Camera 型号及官方采集方式。
- 确认串口设备名和当前用户权限。

验收标准：

- RDK X5 上成功显示最小 Qt 窗口。
- 能读取一帧 USB 或 MIPI 摄像头图像。
- 官方 `.bin` 示例模型能够完成一次 BPU 推理。
- 能打开目标串口并完成收发测试。

### 阶段 1：工程骨架和主界面

预计时间：1 天。

任务：

- 创建项目目录和依赖文件。
- 创建 PyQt5 主窗口、停靠面板和状态栏。
- 实现 YAML 配置加载与保存。
- 实现文件日志和 GUI 日志输出。
- 建立 Worker 生命周期管理。
- 建立统一异常捕获和用户提示。

验收标准：

- Windows、Ubuntu PC 和 RDK X5 均能启动主界面。
- 关闭窗口时所有 Worker 正常退出。
- 配置和日志文件能够正常生成。

### 阶段 2：视频调试基础功能

预计时间：1～2 天。

任务：

- 实现统一 `VideoSource` 接口。
- 实现图片、视频文件和 USB 摄像头输入。
- 实现视频采集 Worker 和有限长度帧缓冲。
- 实现 Qt 图像显示和等比例缩放。
- 实现开始、暂停、停止和单帧处理。
- 实现截图、FPS、延迟和丢帧统计。

验收标准：

- 连续播放摄像头和视频时界面保持响应。
- 推理处理变慢时延迟不会无限累积。
- 连续切换和关闭视频源不会导致摄像头占用或程序崩溃。

### 阶段 3：串口调试模块

预计时间：1 天。

任务：

- 串口扫描、连接、断开和异常重连。
- 常用串口参数设置。
- ASCII/HEX 收发和时间戳。
- 定时发送和预设命令。
- 收发计数和日志保存。
- 建立可替换的比赛通信协议接口。

验收标准：

- Windows COM 口和 Linux `/dev/tty*` 均能使用。
- 串口持续接收时 GUI 不阻塞。
- 拔出串口后程序不崩溃，并能显示明确错误。

### 阶段 4：算法插件与参数系统

预计时间：1～2 天。

任务：

- 定义算法基类、注册表和结果数据结构。
- 实现动态参数控件。
- 实现参数 YAML 保存与恢复。
- 添加透传、边缘检测和 HSV 目标提取示例。
- 实现 ROI、十字线和结构化结果显示。
- 实现 Mock 推理后端。

验收标准：

- 新算法无需修改主窗口即可注册和显示。
- 参数修改能够实时生效。
- 单个算法异常不会终止整个程序。

### 阶段 5：RDK X5 BPU YOLO

预计时间：2 天。

任务：

- 封装统一推理后端接口。
- 实现 `hbm_runtime` 模型加载和调度参数设置。
- 实现 Letterbox、BGR 到 NV12 等预处理。
- 实现 YOLO Detect 输出解码与 NMS。
- 实现检测结果绘制和类别过滤。
- 输出分阶段性能数据。
- 增加模型、类别文件和阈值配置。
- 根据开发板环境评估旧版 `hobot_dnn` 兼容层。

验收标准：

- 能加载官方 YOLO `.bin` 模型。
- 图片、视频和 USB 摄像头均能完成 BPU 推理。
- 检测框坐标映射正确。
- 停止和切换模型时 BPU 资源能够正确释放。
- 性能数据与 `hrt_model_exec perf` 的纯模型性能差异能够得到解释。

### 阶段 6：MIPI Camera 与板端优化

预计时间：1～2 天。

任务：

- 根据相机型号实现 RDK MIPI 视频源适配器。
- 处理 NV12 图像和图像缓冲生命周期。
- 评估减少 BGR/NV12 重复转换的方案。
- 检查 GUI 显示、BPU 和相机链路并发稳定性。
- 优化画面刷新率、内存复制和后处理性能。

验收标准：

- MIPI Camera 可以稳定显示和推理。
- 连续运行 30 分钟以上无明显内存增长。
- 不出现旧帧覆盖、花屏或缓冲区失效问题。

### 阶段 7：稳定性、部署和文档

预计时间：1～2 天。

任务：

- 长时间运行和异常恢复测试。
- 摄像头、串口、模型反复打开关闭测试。
- 完善依赖安装与启动脚本。
- 完善 Windows 和 RDK X5 部署说明。
- 编写算法插件和串口协议扩展说明。
- 整理比赛现场快速排障清单。

验收标准：

- 连续运行至少 2 小时无崩溃和明显资源泄漏。
- 新系统按文档能够完成安装和启动。
- 缺少摄像头、串口或 BPU 环境时，程序仍能启动并清晰提示。

## 7. YOLO 模型部署流程

模型训练和转换不放在 RDK X5 GUI 进程中执行，推荐流程如下：

1. 在 PC 上使用 Ultralytics 完成模型训练。
2. 根据 RDK 官方示例要求导出 ONNX。
3. 准备与比赛场景接近的校准图片。
4. 在 x86 Ubuntu/OpenExplorer Docker 环境中运行模型转换。
5. 使用 `hb_mapper checker` 检查算子支持情况。
6. 使用 `hb_mapper makertbin` 生成 Bayes-e `.bin` 模型。
7. 使用 `hrt_model_exec model_info` 检查输入输出。
8. 使用 `hrt_model_exec perf` 测量纯模型性能。
9. 将 `.bin`、类别文件和模型配置部署到 RDK X5。
10. 使用 GUI 验证预处理、推理、后处理和真实摄像头端到端性能。

模型目录中应同时保存：

- `.bin` 模型文件。
- 类别名称文件。
- 输入宽高和输入格式。
- 模型类型和 YOLO 版本。
- 置信度与 NMS 默认参数。
- Letterbox 或直接缩放策略。
- 输出节点协议和后处理配置。
- 模型转换工具链版本。

## 8. 性能与稳定性策略

- 使用单生产者、单消费者的最新帧模型。
- 默认帧缓冲长度为 1，必要时允许配置为 2。
- UI 刷新频率与推理频率分离。
- 统计采集、排队、预处理、推理、后处理和显示耗时。
- 日志输出限速，避免每帧写日志。
- 录像和截图不得在 UI 主线程执行大量磁盘写入。
- 对 NumPy 后处理进行向量化，避免大型 Python 循环。
- 检测结果使用结构化对象传递，避免业务逻辑解析绘制后的图像。
- 对摄像头断开、串口拔出、模型损坏和配置错误进行恢复处理。

## 9. 主要风险及应对措施

### 9.1 Qt ARM64 安装风险

风险：PC 上可以运行，但 RDK X5 缺少匹配的 PyQt5/PySide6 包。

措施：将 Qt 最小程序验证列为阶段 0 的硬性门槛；优先使用 RDK/Ubuntu 软件源提供的 PyQt5。

### 9.2 MIPI Camera 接入差异

风险：MIPI Camera 不能直接通过普通 `cv2.VideoCapture` 使用。

措施：视频源接口独立设计；第一版先完成文件和 USB 摄像头，之后基于实际相机实现 RDK 专用适配器。

### 9.3 NV12 转换开销

风险：摄像头 BGR 输出、GUI RGB 显示和 BPU NV12 输入之间存在多次转换。

措施：首期先保证正确性并记录耗时；后期评估直接使用 RDK NV12 缓冲和减少内存复制。

### 9.4 Python 后处理瓶颈

风险：YOLO NMS、分割和姿态后处理占用大量 CPU。

措施：NumPy 向量化；必要时使用 OpenCV、Numba 或 C++ 扩展；将后处理耗时单独展示。

### 9.5 视频延迟累积

风险：推理速度低于采集速度时，普通队列会导致画面越来越延迟。

措施：仅保留最新帧，主动丢弃过期帧并统计丢帧数。

### 9.6 BPU API 版本差异

风险：不同 BSP 中可能使用 `hbm_runtime` 或 `hobot_dnn`。

措施：统一推理后端接口；以当前系统的 `hbm_runtime` 为主，根据实际板端环境增加旧版兼容后端。

### 9.7 远程界面性能

风险：SSH X11 转发不适合高帧率图像显示。

措施：首期以 RDK HDMI 本地 GUI 和 PC 本地开发为主；如确有需求，后续设计板端服务与 PC 客户端分离模式。

### 9.8 串口权限

风险：Linux 用户无权打开 `/dev/ttyUSB*` 或 `/dev/ttyACM*`。

措施：部署文档中加入 `dialout` 用户组、udev 规则和设备名检查说明。

## 10. 首期完成定义

满足以下条件时，视为首期平台完成：

- Windows 和 RDK X5 均能启动 GUI。
- 支持图片、视频文件和至少一种摄像头输入。
- 视频播放、算法运行和串口收发不会阻塞界面。
- 算法可以通过插件方式注册和切换。
- 参数可以实时修改并保存。
- 串口支持 ASCII/HEX 收发和定时发送。
- RDK X5 能加载 `.bin` YOLO 模型并使用 BPU 实时推理。
- GUI 能显示检测框和各阶段性能指标。
- 检测结果能够通过统一接口发送给串口协议模块。
- 摄像头、串口和模型异常不会导致程序直接崩溃。
- 连续运行 2 小时无明显内存泄漏和资源占用增长。

## 11. 工期估算

| 阶段 | 预计时间 |
|---|---:|
| 阶段 0：开发板环境验证 | 0.5～1 天 |
| 阶段 1：工程骨架和主界面 | 1 天 |
| 阶段 2：视频调试基础功能 | 1～2 天 |
| 阶段 3：串口调试模块 | 1 天 |
| 阶段 4：算法插件与参数系统 | 1～2 天 |
| 阶段 5：RDK X5 BPU YOLO | 2 天 |
| 阶段 6：MIPI Camera 与优化 | 1～2 天 |
| 阶段 7：稳定性、部署和文档 | 1～2 天 |

基础可用版本预计需要 **8～11 个开发日**。实际时间主要取决于 MIPI Camera 型号、开发板系统版本、自训练 YOLO 模型的算子兼容性和模型转换结果。

## 12. 下一步

下一步进入阶段 0 和阶段 1：

1. 在 RDK X5 上执行环境探针，记录系统、Python、Qt、OpenCV、BPU 和摄像头信息。
2. 在本仓库创建可同时运行于 Windows 和 RDK X5 的项目骨架。
3. 完成最小 PyQt5 主窗口、日志、配置和 Worker 生命周期管理。
4. 以视频文件和 USB 摄像头打通第一条完整数据链路。
