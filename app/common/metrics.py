from __future__ import annotations

import time
from collections import deque


class RateMeter:
    def __init__(self, window: int = 30) -> None:
        self._times: deque[float] = deque(maxlen=max(2, window))

    def tick(self, timestamp: float | None = None) -> float:
        self._times.append(timestamp or time.perf_counter())
        return self.rate

    @property
    def rate(self) -> float:
        if len(self._times) < 2:
            return 0.0
        elapsed = self._times[-1] - self._times[0]
        return (len(self._times) - 1) / elapsed if elapsed > 0 else 0.0


class Stopwatch:
    def __enter__(self) -> "Stopwatch":
        self.started = time.perf_counter()
        self.elapsed_ms = 0.0
        return self

    def __exit__(self, *_args: object) -> None:
        self.elapsed_ms = (time.perf_counter() - self.started) * 1000
