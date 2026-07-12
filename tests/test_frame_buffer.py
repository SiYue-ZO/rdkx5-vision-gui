import numpy as np

from app.common.models import FramePacket
from app.workers.frame_buffer import LatestFrameBuffer


def test_buffer_returns_latest_and_counts_drops():
    buffer = LatestFrameBuffer()
    frame = np.zeros((1, 1, 3), dtype=np.uint8)
    buffer.put(FramePacket(frame, 1, 0))
    buffer.put(FramePacket(frame, 2, 0))
    assert buffer.get().sequence == 2
    assert buffer.dropped == 1
