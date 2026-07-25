# RDK X5 SSH 发布

本项目的业务代码是 Python；但 PyQt5、OpenCV、hbm_runtime、hobot_dnn 和
libsrcampy 都包含与 RDK X5 BSP 紧耦合的原生库。因此发布包不尝试在 Windows
上把整个程序冻结为一个 ARM 二进制文件。这样可以避免把 x86 wheel 或与 BSP 不匹配
的 BPU/MIPI 运行时带到板端。

发布包包含 app、configs、models、启动/校验脚本和 main.py。其中模型默认包含在内，
构建时必须已经放入 models；日志、录像、截图和本机虚拟环境不会打包。

## 板端一次性准备

在对应 RDK X5 BSP 的板端安装系统提供的 GUI/视觉运行时，并确认下列导入可以成功：

    python3 -c "import numpy, cv2, serial, yaml; from PyQt5 import QtWidgets"

通常 PyQt5、OpenCV、numpy 以及 RDK 的 BPU/MIPI 库应使用 BSP/apt 提供的版本；
不要用 PC 侧的 wheel 覆盖它们。缺少纯 Python 依赖时，安装板端系统包
python3-serial 和 python3-yaml。需要 BPU 或 MIPI 时，还应在板端确认
hbm_runtime/hobot_dnn、libsrcampy 与当前 BSP 一致。

板端需要已启用 SSH，并建议配置公钥登录。GUI 在 HDMI 本地桌面运行时，SSH 会话应
拥有正确的 DISPLAY/X11 权限；仅 SSH X11 转发不适合高帧率调试。

## Windows 一条命令发布

PowerShell 中执行：

    .\scripts\deploy-rdkx5.ps1 -Target sunrise@192.168.1.10

该命令会生成 dist/rdkx5-vision.tar.gz 和 SHA-256 文件，使用 scp 上传，在板端创建
按时间戳命名的 release，解压并运行环境校验。仅在校验成功后更新
~/rdkx5-vision/current 软链接并后台启动。启动输出写入
current/logs/launcher.log。

常用选项：

    # 发布、校验但不启动
    .\scripts\deploy-rdkx5.ps1 -Target sunrise@192.168.1.10 -NoStart

    # 使用绝对板端目录；不将 models 放入包
    .\scripts\deploy-rdkx5.ps1 -Target sunrise@192.168.1.10 -RemoteRoot /opt/rdkx5-vision -NoModels

也可以只生成包后手工上传：

    python .\scripts\package_rdkx5.py
    scp .\dist\rdkx5-vision.tar.gz sunrise@192.168.1.10:/tmp/

在板端解压的 release 目录内，使用下面的命令前台运行，便于排障：

    bash scripts/verify-rdkx5.sh
    bash scripts/run-rdkx5.sh

## 构建为板端二进制

先在 RDK X5 上为系统 Python 安装一次 PyInstaller：

    python3 -m pip install --user "pyinstaller>=6,<7"

然后从 Windows 发布并在板端构建、启动二进制：

    .\scripts\deploy-rdkx5.ps1 -Target sunrise@192.168.1.10 -Binary

该命令仍先上传源码包，但只在 RDK 的 aarch64 环境中执行 PyInstaller。最终 current
指向 binary-dist/rdkx5-vision，启动的是 ELF 文件 rdkx5-vision，不依赖项目源码
目录或板端 Python 来启动。Qt、OpenCV 及检测到的 BPU/MIPI Python 扩展会被收集进
二进制目录；未被收集的 BSP 动态库仍由板端系统加载。

推荐使用默认 onedir 形式，而非 onefile：启动更快、日志和模型路径稳定，也更适合
Qt 与 RDK 的原生动态库。

二进制模式会自动让 PyQt5 使用自身的 Qt 平台插件，避免 OpenCV 自带的 Qt xcb 插件
抢占路径。若日志仍提示无法连接显示器，则是桌面会话权限问题：在板端 HDMI 桌面环境
中启动，或显式设置 DISPLAY=:0 和该用户可读的 XAUTHORITY。

## 为什么这比交叉编译成单文件更适合 RDK

纯 Python 代码不需要交叉编译。真正需要 ARM 架构且需要匹配 BSP 的，是 Qt、OpenCV
和 RDK 硬件库；将这些库留在目标系统，同时把代码、配置和模型做成可校验、可回滚的
release，能兼顾离线部署和 BPU/MIPI 兼容性。若必须得到单个 ARM 可执行文件，需要在
同版本 RDK rootfs 或板端 Docker 环境内使用 PyInstaller 构建，并把每个 Qt/OpenCV/BPU
动态库一起做兼容性验证；这不应在 Windows x86 环境中直接产出。
