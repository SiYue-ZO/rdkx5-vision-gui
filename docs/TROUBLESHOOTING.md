# 比赛现场快速排障

- GUI 无法启动：确认 `uv run python -c "from PyQt5 import QtWidgets"`；板端确认 HDMI/桌面会话和 `DISPLAY`。
- 摄像头打不开：检查设备是否被其他程序占用；Linux 用 `v4l2-ctl --list-devices`；降低分辨率/FPS。
- MIPI 花屏：核对 sensor 配置、NV12 宽高、缓冲生命周期；读取后立即复制用于跨线程传递。
- BPU 模型失败：用 `hrt_model_exec model_info` 核对模型、输入格式、节点名；确认 BSP/runtime 和转换工具链匹配。
- 框位置偏移：检查 Letterbox 比例、上下左右 padding、输出是 `xywh` 还是 `xyxy`。
- 延迟不断增加：确认使用 `LatestFrameBuffer`，不要把每帧通过无界队列排队。
- 串口 Permission denied：检查 `dialout` 组和 udev；确认设备名没有因拔插变化。
- 串口乱码：双方波特率、数据位、停止位、校验位必须一致；HEX 模式不要混入非十六进制字符。
- 内存增长：关闭录像/逐帧日志，确认相机 buffer 被复制或及时释放，反复开关源检查线程退出。
