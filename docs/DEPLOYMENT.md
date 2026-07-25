# 部署与硬件验收

## Windows / Ubuntu PC

安装 `uv` 后在仓库根目录执行：

```text
uv sync --extra desktop --extra dev
uv run python main.py
```

需要 ONNX 时追加 `--extra onnx`。PC 默认使用 Mock 后端，不会把其性能标记为 BPU 性能。

## RDK X5

1. 确认 RDK OS/BSP 与模型转换工具链版本匹配。
2. 安装系统 PyQt5、OpenCV，并用 `uv sync --no-extra` 安装纯 Python 依赖。
3. 运行 `uv run rdkx5-probe`，保存 `environment-report.json`。
4. 运行 `uv run python main.py`，验证 Qt/HDMI 显示。
5. 用官方示例和 `hrt_model_exec model_info/perf` 验证 `.bin`。
6. 对于 Model Zoo 格式的 YOLO Detect `.bin`，配置 `rdk-hbm`、`classes_num`、`labels`、`reg: 16` 与 `strides: [8, 16, 32]` 即可；该后端已内置 NV12 输入、DFL 解码和 NMS。其他输出协议（分割、姿态或非 Model Zoo 导出的模型）需要单独适配。
7. MIPI 相机若使用 `libsrcampy`，确认相机 ID、分辨率、传感器配置与 BSP 一致。

`uv` 创建的隔离环境默认看不到 apt 安装的系统包时，可在板端创建允许 system-site-packages 的环境，或使用 RDK 软件源对应的 Python 解释器。不要用 PyPI wheel 覆盖 BSP 自带的 `hbm_runtime`。

## 串口权限

Linux 上将用户加入 `dialout` 组后重新登录，并确认 `/dev/ttyUSB*` 或 `/dev/ttyACM*` 权限。比赛前固定设备名时使用 udev 规则，避免拔插后编号变化。

## 验收矩阵

| 项目 | PC | RDK X5 |
|---|---:|---:|
| GUI、图片、视频、USB 摄像头 | 必测 | 必测 |
| Mock/ONNX | 必测/选测 | 选测 |
| `.bin` BPU 推理 | 不适用 | 必测 |
| MIPI Camera | 不适用 | 必测 |
| 串口收发与拔插恢复 | 必测 | 必测 |
| 30 分钟相机/BPU稳定性 | 不适用 | 必测 |
| 2 小时整机稳定性 | 必测 | 必测 |
