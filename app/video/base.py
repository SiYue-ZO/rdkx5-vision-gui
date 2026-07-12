from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

import numpy as np


class VideoSource(ABC):
    @abstractmethod
    def open(self) -> None: ...

    @abstractmethod
    def read(self) -> tuple[bool, np.ndarray | None]: ...

    @abstractmethod
    def close(self) -> None: ...

    @property
    @abstractmethod
    def is_open(self) -> bool: ...

    @property
    def fps(self) -> float:
        return 0.0

    @property
    def info(self) -> dict[str, Any]:
        return {}

    def __enter__(self) -> "VideoSource":
        self.open()
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()
