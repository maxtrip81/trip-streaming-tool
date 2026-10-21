"""Custom widgets: LCD display, stereo VU meter, application icon."""

from __future__ import annotations

import time

from PySide6.QtCore import QPointF, QRectF, Qt, QSize
from PySide6.QtGui import QColor, QFont, QFontDatabase, QIcon, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QSizePolicy, QWidget

VU_MIN_DB = -60.0


def mono_font(size: int) -> QFont:
    font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
    font.setPointSize(size)
    font.setStyleHint(QFont.StyleHint.Monospace)
    return font


class LcdDisplay(QWidget):
    """Four-line backlit display (status, stream stats, recording, song)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.lines = ["", "", "", ""]
        self.color = QColor("#38f2b0")
        self.setMinimumHeight(92)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._scroll = 0
        self._last_scroll = time.monotonic()

    def set_color(self, color: str) -> None:
        self.color = QColor(color)
        self.update()

    def set_lines(self, lines) -> None:
        lines = list(lines) + [""] * (4 - len(lines))
        if lines != self.lines:
            if lines[3] != self.lines[3]:
                self._scroll = 0
            self.lines = lines
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        bg = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        bg.setColorAt(0, QColor("#0b1513"))
        bg.setColorAt(1, QColor("#050a09"))
        p.setPen(QPen(QColor("#1f2d2a"), 1))
        p.setBrush(bg)
        p.drawRoundedRect(rect, 8, 8)

        dim = QColor(self.color)
        dim.setAlphaF(0.55)
        big = mono_font(15)
        big.setBold(True)
        small = mono_font(10)
        x = rect.left() + 12
        width = rect.width() - 24
        p.setFont(big)
        p.setPen(self.color)
        p.drawText(QRectF(x, rect.top() + 6, width, 26), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   self.lines[0])
        p.setFont(small)
        p.setPen(dim)
        p.drawText(QRectF(x, rect.top() + 32, width, 17), Qt.AlignmentFlag.AlignLeft, self.lines[1])
        p.drawText(QRectF(x, rect.top() + 49, width, 17), Qt.AlignmentFlag.AlignLeft, self.lines[2])
        # song line scrolls when too long
        p.setPen(self.color)
        text = self.lines[3]
        metrics = p.fontMetrics()
        text_w = metrics.horizontalAdvance(text)
        y = rect.top() + 66
        p.save()
        p.setClipRect(QRectF(x, y, width, 18))
        if text_w > width:
            now = time.monotonic()
            self._scroll = (self._scroll + (now - self._last_scroll) * 30) % (text_w + 40)
            self._last_scroll = now
            p.drawText(QPointF(x - self._scroll, y + 13), text)
            p.drawText(QPointF(x - self._scroll + text_w + 40, y + 13), text)
        else:
            self._last_scroll = time.monotonic()
            p.drawText(QPointF(x, y + 13), text)
        p.restore()


class VuMeter(QWidget):
    """Horizontal segmented stereo meter with peak hold, scale from -60 to 0 dBFS."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.levels = [VU_MIN_DB, VU_MIN_DB]
        self.peaks = [VU_MIN_DB, VU_MIN_DB]
        self._peak_time = [0.0, 0.0]
        self._display = [VU_MIN_DB, VU_MIN_DB]
        self.setMinimumHeight(46)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_levels(self, levels) -> None:
        if len(levels) == 1:
            levels = [levels[0], levels[0]]
        now = time.monotonic()
        for i in range(2):
            value = max(VU_MIN_DB, float(levels[i]))
            # fast attack, smooth fall-off
            self._display[i] = value if value > self._display[i] else max(value, self._display[i] - 1.5)
            if value >= self.peaks[i] or now - self._peak_time[i] > 1.5:
                self.peaks[i] = value
                self._peak_time[i] = now
        self.update()

    @staticmethod
    def _frac(db: float) -> float:
        return min(1.0, max(0.0, (db - VU_MIN_DB) / -VU_MIN_DB))

    def paintEvent(self, event):
        p = QPainter(self)
        rect = QRectF(self.rect())
        label_w = 14
        bar_h = 13
        segs = 48
        left = rect.left() + label_w
        width = rect.width() - label_w - 2
        seg_w = width / segs
        p.setFont(mono_font(8))
        for ch in range(2):
            y = rect.top() + 2 + ch * (bar_h + 4)
            p.setPen(QColor("#7b8b87"))
            p.drawText(QRectF(rect.left(), y, label_w, bar_h), Qt.AlignmentFlag.AlignVCenter, "LR"[ch])
            lit = self._frac(self._display[ch]) * segs
            peak_seg = int(self._frac(self.peaks[ch]) * segs) - 1
            for s in range(segs):
                db = VU_MIN_DB + (s + 1) / segs * -VU_MIN_DB
                if db > -3:
                    on, off = QColor("#ff4d5a"), QColor("#3a1418")
                elif db > -12:
                    on, off = QColor("#ffc94d"), QColor("#3a2e12")
                else:
                    on, off = QColor("#38f2b0"), QColor("#10302a")
                color = on if (s < lit or s == peak_seg) else off
                p.fillRect(QRectF(left + s * seg_w + 1, y, seg_w - 2, bar_h), color)
        # scale
        p.setPen(QColor("#5f6e6a"))
        y = rect.top() + 2 + 2 * (bar_h + 4) - 2
        for db in (-60, -48, -36, -24, -12, -6, -3, 0):
            x = left + self._frac(db) * width
            p.drawText(QRectF(x - 14, y, 28, 11), Qt.AlignmentFlag.AlignCenter, str(db))

    def sizeHint(self):
        return QSize(360, 46)


def app_icon() -> QIcon:
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256, 512):
        icon.addPixmap(icon_pixmap(size))
    return icon


def icon_pixmap(size: int) -> QPixmap:
    """TRIP logo: a dark rounded square with a mint broadcast wave and a red 'on air' dot."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    s = size / 64.0
    grad = QLinearGradient(0, 0, 0, size)
    grad.setColorAt(0, QColor("#1c2b33"))
    grad.setColorAt(1, QColor("#0a1014"))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(grad)
    p.drawRoundedRect(QRectF(2 * s, 2 * s, 60 * s, 60 * s), 14 * s, 14 * s)
    pen = QPen(QColor("#38f2b0"), 4.2 * s, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    path = QPainterPath()
    path.moveTo(10 * s, 34 * s)
    points = [(16, 34), (20, 22), (25, 46), (30, 14), (35, 50), (40, 26), (44, 38), (48, 34), (54, 34)]
    for x, y in points:
        path.lineTo(x * s, y * s)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(path)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#ff4d5a"))
    p.drawEllipse(QPointF(50 * s, 14 * s), 5 * s, 5 * s)
    p.end()
    return pix
