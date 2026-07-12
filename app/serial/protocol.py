from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Protocol


class PacketProtocol(Protocol):
    """自定义串口数据包协议应满足的最小接口。"""

    def encode(self, command: int, payload: bytes = b"") -> bytes:
        """把命令字和业务负载编码为可直接发送的完整数据包。"""
        ...

    def decode(self, data: bytes) -> "ProtocolFrame":
        """校验一个完整数据包并返回命令字和业务负载。"""
        ...


def crc16_modbus(data: bytes) -> int:
    """计算 CRC16-Modbus；返回主机整数，编码时由协议明确大小端。"""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc & 0xFFFF


@dataclass(slots=True)
class ProtocolFrame:
    """解包后的业务帧；payload 不含帧头、长度、命令字和 CRC。"""

    command: int
    payload: bytes


class BinaryFrameProtocol:
    """内置示例协议：AA55 + payload长度(u16 LE) + command(u8) + payload + CRC16。

    ``decode`` 只接收一个完整包。串口每次收到的是任意长度字节块时，请先交给
    :class:`BinaryFrameStreamParser`，不要假设一次 received Signal 就是一帧。
    """

    HEADER = b"\xaa\x55"

    def encode(self, command: int, payload: bytes = b"") -> bytes:
        """编码完整数据包，结果可传给 ``MainWindow.send_serial_data``。"""
        if not 0 <= command <= 255 or len(payload) > 65535:
            raise ValueError("命令字或负载长度无效")
        body = struct.pack("<HB", len(payload), command) + payload
        return self.HEADER + body + struct.pack("<H", crc16_modbus(body))

    def decode(self, data: bytes) -> ProtocolFrame:
        """校验完整数据包的帧头、长度和 CRC，并返回业务帧。"""
        if len(data) < 7 or not data.startswith(self.HEADER):
            raise ValueError("帧头或长度无效")
        length, command = struct.unpack_from("<HB", data, 2)
        expected = 2 + 3 + length + 2
        if len(data) != expected:
            raise ValueError("帧长度不匹配")
        body = data[2:-2]
        received_crc = struct.unpack_from("<H", data, len(data) - 2)[0]
        if crc16_modbus(body) != received_crc:
            raise ValueError("CRC 校验失败")
        return ProtocolFrame(command, data[5:-2])


class BinaryFrameStreamParser:
    """内置二进制协议的增量拆包器，处理半包、粘包和帧头前噪声。

    每次串口接收回调调用 ``feed(data)``；返回值可能为空、单帧或多帧。CRC 错误的
    候选帧会被丢弃，后续字节仍会继续同步。每个串口连接应使用独立 parser 实例。
    """

    def __init__(
        self, protocol: BinaryFrameProtocol | None = None, max_payload: int = 65535
    ) -> None:
        self.protocol = protocol or BinaryFrameProtocol()
        self.max_payload = max_payload
        self.buffer = bytearray()

    def feed(self, data: bytes) -> list[ProtocolFrame]:
        """追加一块串口数据，返回本次成功解析出的所有完整帧。"""
        self.buffer.extend(data)
        frames: list[ProtocolFrame] = []
        header = self.protocol.HEADER
        while True:
            start = self.buffer.find(header)
            if start < 0:
                # 保留可能成为下一次帧头开头的最后一个字节。
                self.buffer[:] = self.buffer[-1:] if self.buffer.endswith(header[:1]) else b""
                break
            if start:
                del self.buffer[:start]
            if len(self.buffer) < 5:
                break
            payload_length = struct.unpack_from("<H", self.buffer, 2)[0]
            if payload_length > self.max_payload:
                del self.buffer[0]
                continue
            packet_length = 7 + payload_length
            if len(self.buffer) < packet_length:
                break
            packet = bytes(self.buffer[:packet_length])
            del self.buffer[:packet_length]
            try:
                frames.append(self.protocol.decode(packet))
            except ValueError:
                # 包长度已知但校验失败，丢弃候选包并继续寻找下一帧。
                continue
        return frames

    def reset(self) -> None:
        """断开或切换串口时清空尚未组成完整帧的残留数据。"""
        self.buffer.clear()
