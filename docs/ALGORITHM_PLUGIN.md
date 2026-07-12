# 算法插件开发

完整接口、YOLO 后端和回调示例请参阅 [二次开发指南](EXTENDING.md)。

算法仅依赖 NumPy/OpenCV 和公共数据模型，不应访问 Qt 控件。最小插件：

```python
class MyAlgorithm(VisionAlgorithm):
    name = "my_algorithm"
    display_name = "我的算法"
    parameters = [ParameterSpec("threshold", "阈值", ParameterType.INT, 100, 0, 255)]

    def process(self, frame, params):
        return AlgorithmResult(image=frame.copy(), metadata={"threshold": params["threshold"]})
```

在 `app/algorithms/registry.py` 注册后，GUI 会自动生成参数控件。初始化硬件或模型放在 `initialize()`，资源释放放在 `shutdown()`；每帧异常会被 Worker 捕获并显示，不应主动操作 GUI。

算法执行顺序为 `initialize()` 一次、`process()` 多次、`shutdown()` 一次。`process()` 运行在推理线程；结果统一通过 `AlgorithmResult` 返回。需要发送下位机数据时，将已经编码好的 `bytes` 放入 `control_data`。
