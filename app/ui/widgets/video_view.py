from __future__ import annotations

import cv2
import numpy as np
from PyQt5.QtCore import QPoint, QRect, Qt, pyqtSignal
from PyQt5.QtGui import QImage, QMouseEvent, QPainter, QPen, QPixmap
from PyQt5.QtWidgets import QLabel, QSizePolicy


class VideoView(QLabel):
    pixel_hovered = pyqtSignal(int, int, object)
    roi_selected = pyqtSignal(object)

    def __init__(self) -> None:
        super().__init__("请打开图片、视频或摄像头")
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(640, 360)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setStyleSheet("background:#181818;color:#aaa;border:1px solid #333")
        self._image: np.ndarray | None = None
        self._pixmap = QPixmap()
        self._draw_crosshair = True
        self._drag_start: QPoint | None = None
        self._drag_end: QPoint | None = None
        self.setMouseTracking(True)

    def set_frame(self, frame: np.ndarray) -> None:
        self._image = np.ascontiguousarray(frame)
        rgb = cv2.cvtColor(self._image, cv2.COLOR_BGR2RGB)
        height, width, channels = rgb.shape
        image = QImage(rgb.data, width, height, channels * width, QImage.Format_RGB888).copy()
        self._pixmap = QPixmap.fromImage(image)
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if self._pixmap.isNull():
            return
        painter = QPainter(self)
        target = self._target_rect()
        painter.drawPixmap(target, self._pixmap)
        if self._draw_crosshair:
            painter.setPen(QPen(Qt.green, 1, Qt.DashLine))
            painter.drawLine(
                target.center().x(), target.top(), target.center().x(), target.bottom()
            )
            painter.drawLine(
                target.left(), target.center().y(), target.right(), target.center().y()
            )
        if self._drag_start and self._drag_end:
            painter.setPen(QPen(Qt.yellow, 2))
            painter.drawRect(QRect(self._drag_start, self._drag_end).normalized())

    def _target_rect(self) -> QRect:
        scaled = self._pixmap.size().scaled(self.size(), Qt.KeepAspectRatio)
        return QRect(
            (self.width() - scaled.width()) // 2,
            (self.height() - scaled.height()) // 2,
            scaled.width(),
            scaled.height(),
        )

    def _image_point(self, point: QPoint) -> tuple[int, int] | None:
        if self._image is None:
            return None
        rect = self._target_rect()
        if not rect.contains(point):
            return None
        h, w = self._image.shape[:2]
        return (
            min(w - 1, int((point.x() - rect.left()) * w / rect.width())),
            min(h - 1, int((point.y() - rect.top()) * h / rect.height())),
        )

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        point = self._image_point(event.pos())
        if point and self._image is not None:
            x, y = point
            bgr = self._image[y, x]
            hsv = cv2.cvtColor(np.uint8([[bgr]]), cv2.COLOR_BGR2HSV)[0, 0]
            self.pixel_hovered.emit(
                x, y, {"rgb": tuple(map(int, bgr[::-1])), "hsv": tuple(map(int, hsv))}
            )
        if self._drag_start:
            self._drag_end = event.pos()
            self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton and self._image_point(event.pos()):
            self._drag_start = self._drag_end = event.pos()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._drag_start and self._drag_end:
            first, second = self._image_point(self._drag_start), self._image_point(self._drag_end)
            if first and second:
                x1, x2 = sorted((first[0], second[0]))
                y1, y2 = sorted((first[1], second[1]))
                self.roi_selected.emit((x1, y1, x2, y2))
        self._drag_start = self._drag_end = None
        self.update()
