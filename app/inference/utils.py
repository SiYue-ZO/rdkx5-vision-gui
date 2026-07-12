from __future__ import annotations

import cv2
import numpy as np


def letterbox(image: np.ndarray, size: tuple[int, int], color: int = 114):
    target_w, target_h = size
    height, width = image.shape[:2]
    ratio = min(target_w / width, target_h / height)
    new_w, new_h = round(width * ratio), round(height * ratio)
    resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    left, top = (target_w - new_w) // 2, (target_h - new_h) // 2
    output = np.full((target_h, target_w, 3), color, dtype=np.uint8)
    output[top : top + new_h, left : left + new_w] = resized
    return output, ratio, (left, top)


def bgr_to_nv12(image: np.ndarray) -> np.ndarray:
    height, width = image.shape[:2]
    if height % 2 or width % 2:
        raise ValueError("NV12 图像宽高必须为偶数")
    i420 = cv2.cvtColor(image, cv2.COLOR_BGR2YUV_I420).reshape(-1)
    y_size = width * height
    y = i420[:y_size]
    u = i420[y_size : y_size + y_size // 4]
    v = i420[y_size + y_size // 4 :]
    uv = np.empty(y_size // 2, dtype=np.uint8)
    uv[0::2], uv[1::2] = u, v
    return np.concatenate((y, uv)).reshape(height * 3 // 2, width)


def nms(boxes: np.ndarray, scores: np.ndarray, threshold: float) -> list[int]:
    if len(boxes) == 0:
        return []
    x1, y1, x2, y2 = boxes.T
    areas = np.maximum(0, x2 - x1) * np.maximum(0, y2 - y1)
    order = scores.argsort()[::-1]
    keep: list[int] = []
    while order.size:
        i = int(order[0])
        keep.append(i)
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        inter = np.maximum(0, xx2 - xx1) * np.maximum(0, yy2 - yy1)
        union = areas[i] + areas[order[1:]] - inter
        iou = np.divide(inter, union, out=np.zeros_like(inter), where=union > 0)
        order = order[np.where(iou <= threshold)[0] + 1]
    return keep
