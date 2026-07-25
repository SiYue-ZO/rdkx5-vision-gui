from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import sys

import serial
from serial.tools import list_ports


@dataclass(slots=True)
class SerialConfig:
    port: str
    baudrate: int = 115200
    bytesize: int = 8
    parity: str = "N"
    stopbits: float = 1
    timeout: float = 0.05
    xonxoff: bool = False
    rtscts: bool = False


class SerialTransport:
    def __init__(self) -> None:
        self.connection: serial.Serial | None = None
        self.rx_bytes = 0
        self.tx_bytes = 0

    @staticmethod
    def ports() -> list[tuple[str, str]]:
        """Return serial ports, including board UARTs missed by pyserial discovery.

        PyInstaller can omit pyserial's platform-specific discovery module. More
        importantly, some embedded Linux BSPs expose UARTs as ``/dev/ttyS*`` (or
        vendor-specific names) without the sysfs metadata that pyserial expects.
        Scan stable device-node names as a fallback so that a visible UART is
        still selectable in the packaged application.
        """
        ports: dict[str, str] = {}
        try:
            ports.update(
                (port.device, port.description or "Serial port")
                for port in list_ports.comports()
            )
        except Exception:
            # Opening a port will still report its concrete error to the user.
            # Do not let enumeration failure hide board UART device nodes.
            pass

        if sys.platform.startswith("linux"):
            for pattern in ("ttyS*", "ttyUSB*", "ttyACM*", "ttyAMA*", "ttyTHS*", "ttyHS*"):
                for device in Path("/dev").glob(pattern):
                    ports.setdefault(str(device), f"Linux UART ({device.name})")

        return sorted(ports.items())

    def open(self, config: SerialConfig) -> None:
        self.close()
        self.connection = serial.Serial(**asdict(config))

    def read(self, size: int = 4096) -> bytes:
        if not self.connection or not self.connection.is_open:
            return b""
        waiting = self.connection.in_waiting
        data = self.connection.read(min(size, waiting or 1))
        self.rx_bytes += len(data)
        return data

    def write(self, data: bytes) -> int:
        if not self.connection or not self.connection.is_open:
            raise RuntimeError("串口尚未打开")
        count = self.connection.write(data)
        self.tx_bytes += count
        return count

    def close(self) -> None:
        if self.connection is not None:
            try:
                self.connection.close()
            finally:
                self.connection = None

    @property
    def is_open(self) -> bool:
        return bool(self.connection and self.connection.is_open)
