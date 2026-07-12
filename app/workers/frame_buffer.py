from __future__ import annotations

import threading

from app.common.models import FramePacket


class LatestFrameBuffer:
    def __init__(self) -> None:
        self._condition = threading.Condition()
        self._packet: FramePacket | None = None
        self._last_read = -1
        self.dropped = 0
        self.closed = False

    def put(self, packet: FramePacket) -> None:
        with self._condition:
            if self._packet is not None and self._packet.sequence > self._last_read:
                self.dropped += 1
            self._packet = packet
            self._condition.notify()

    def get(self, timeout: float = 0.1) -> FramePacket | None:
        with self._condition:
            self._condition.wait_for(
                lambda: (
                    self.closed
                    or (self._packet is not None and self._packet.sequence > self._last_read)
                ),
                timeout,
            )
            if self.closed or self._packet is None or self._packet.sequence <= self._last_read:
                return None
            self._last_read = self._packet.sequence
            return self._packet

    def reset(self) -> None:
        with self._condition:
            self._packet = None
            self._last_read = -1
            self.dropped = 0
            self.closed = False

    def close(self) -> None:
        with self._condition:
            self.closed = True
            self._condition.notify_all()
