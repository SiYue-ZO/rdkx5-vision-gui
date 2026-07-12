# 串口协议扩展

完整发送/接收回调和自定义协议示例请参阅 [二次开发指南](EXTENDING.md)。

内置示例帧格式（小端）：

```text
AA 55 | payload_length:u16 | command:u8 | payload:N | crc16:u16
```

CRC 覆盖 `length + command + payload`，算法为 CRC16-Modbus。业务协议可继承或替换 `BinaryFrameProtocol`。建议为视觉目标定义版本化负载，例如命令 `0x10`：时间戳、目标有效位、类别、中心 X/Y、置信度；多字节字段必须明确大小端和缩放系数。

串口 `received` Signal 给出的是任意长度原始字节块。内置协议应交给 `BinaryFrameStreamParser.feed()`，再通过 `MainWindow.on_protocol_frame()` 处理完整帧。发送可调用 `send_serial_data()` 或 `send_protocol_frame()`。
