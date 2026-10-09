"""Oś czasu: play/pauza, czas, miniatura przebiegu z przewijaniem, głośność.

W trybie pliku miniatura pokazuje cały utwór (min/max w każdej kolumnie
pikseli), a kliknięcie lub przeciągnięcie przewija odtwarzanie.
W trybie na żywo pokazujemy tylko status: „NA ŻYWO” i czas nagrania.
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QFrame, QHBoxLayout, QPushButton, QSlider, QWidget

from osciviz.gui.icons import icon
from osciviz.gui.theme import theme
from osciviz.gui.widgets import label, tool_button


def format_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    m, s = divmod(seconds, 60)
    return f"{int(m):02d}:{s:05.2f}"


class WaveOverview(QWidget):
    """Miniatura całego pliku z głowicą odtwarzania."""

    seekRequested = Signal(float)  # sekundy

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(40)
        self.setCursor(Qt.PointingHandCursor)
        self.source = None
        self.position = 0.0
        self.live = False
        self.recording = False
        self.live_text = ""
        self._peaks = None
        self._peaks_width = 0
        self._hover_x = None
        self.setMouseTracking(True)

    def set_source(self, source) -> None:
        self.source = source
        self._peaks = None
        self.update()

    def set_position(self, seconds: float) -> None:
        self.position = seconds
        self.update()

    def _ensure_peaks(self) -> None:
        cols = max(1, self.width() // 2)
        if self.source is not None and (self._peaks is None or self._peaks_width != cols):
            self._peaks = self.source.peaks(cols)
            self._peaks_width = cols

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(QPen(theme.color("border"), 1))
        p.setBrush(theme.color("input"))
        p.drawRoundedRect(r, 8, 8)
        if self.live:
            self._paint_live(p, r)
            return
        if self.source is None:
            p.setPen(theme.color("faint"))
            p.drawText(r, Qt.AlignCenter, self.tr("Open an audio file or switch to Live input"))
            return
        self._ensure_peaks()
        peaks = self._peaks
        mid = r.center().y()
        half = r.height() / 2 - 6
        duration = max(self.source.duration, 1e-6)
        play_x = r.left() + r.width() * min(1.0, self.position / duration)
        # Przebieg jako wypełniony kształt min/max: przed głowicą w kolorze akcentu.
        n = len(peaks)
        xs = r.left() + (np.arange(n) + 0.5) * (r.width() / n)
        top = mid - np.clip(peaks[:, 1], 0, 1) * half
        bottom = mid - np.clip(peaks[:, 0], -1, 0) * half
        path = QPainterPath()
        path.moveTo(xs[0], top[0])
        for x, y in zip(xs, top, strict=True):
            path.lineTo(x, y)
        for x, y in zip(xs[::-1], bottom[::-1], strict=True):
            path.lineTo(x, y)
        path.closeSubpath()
        p.setPen(Qt.NoPen)
        p.setBrush(theme.color("faint"))
        p.save()
        p.setClipRect(QRectF(play_x, r.top(), r.right() - play_x, r.height()))
        p.drawPath(path)
        p.restore()
        grad = QLinearGradient(r.topLeft(), r.topRight())
        grad.setColorAt(0, theme.color("accent"))
        grad.setColorAt(1, QColor("#22D3EE") if theme.name != "high_contrast" else theme.color("accent"))
        p.save()
        p.setClipRect(QRectF(r.left(), r.top(), play_x - r.left(), r.height()))
        p.setBrush(grad)
        p.drawPath(path)
        p.restore()
        if self._hover_x is not None:
            p.setPen(QPen(theme.color("muted"), 1, Qt.DotLine))
            p.drawLine(QPointF(self._hover_x, r.top() + 3), QPointF(self._hover_x, r.bottom() - 3))
        p.setPen(QPen(theme.color("text"), 2))
        p.drawLine(QPointF(play_x, r.top() + 2), QPointF(play_x, r.bottom() - 2))
        p.setBrush(theme.color("text"))
        p.setPen(Qt.NoPen)
        p.drawEllipse(QPointF(play_x, r.top() + 3), 3.5, 3.5)

    def _paint_live(self, p: QPainter, r: QRectF) -> None:
        color = theme.color("danger") if self.recording else theme.color("success")
        p.setPen(Qt.NoPen)
        p.setBrush(color)
        p.drawEllipse(QPointF(r.left() + 18, r.center().y()), 5, 5)
        p.setPen(theme.color("text"))
        p.drawText(r.adjusted(32, 0, -10, 0), Qt.AlignVCenter | Qt.AlignLeft, self.live_text)

    def _seek_at(self, x: float) -> None:
        if self.source is None or self.live:
            return
        frac = min(1.0, max(0.0, (x - 1) / max(1.0, self.width() - 2)))
        self.seekRequested.emit(frac * self.source.duration)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton:
            self._seek_at(event.position().x())

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        self._hover_x = event.position().x()
        if event.buttons() & Qt.LeftButton:
            self._seek_at(self._hover_x)
        self.update()

    def leaveEvent(self, event) -> None:  # noqa: N802
        self._hover_x = None
        self.update()

    def resizeEvent(self, event) -> None:  # noqa: N802
        self._peaks = None
        super().resizeEvent(event)


class Timeline(QFrame):
    playToggled = Signal()
    rewind = Signal()
    seekRequested = Signal(float)
    volumeChanged = Signal(float)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Timeline")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 14, 10)
        layout.setSpacing(10)
        self.rewind_btn = tool_button("skip-back", "", size=16)
        self.rewind_btn.clicked.connect(self.rewind)
        self.play_btn = QPushButton()
        self.play_btn.setObjectName("PlayButton")
        self.play_btn.setCursor(Qt.PointingHandCursor)
        self.play_btn.setIconSize(QSize(16, 16))
        self.play_btn.clicked.connect(self.playToggled)
        self.time_label = label("00:00.00", "mono")
        self.time_label.setMinimumWidth(70)
        self.total_label = label("/ 00:00.00", "faint")
        self.overview = WaveOverview()
        self.overview.seekRequested.connect(self.seekRequested)
        self.vol_btn = tool_button("volume", "", size=16)
        self.volume = QSlider(Qt.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(80)
        self.volume.setFixedWidth(90)
        self.volume.valueChanged.connect(lambda v: self.volumeChanged.emit(v / 100.0))
        layout.addWidget(self.rewind_btn)
        layout.addWidget(self.play_btn)
        layout.addWidget(self.time_label)
        layout.addWidget(self.total_label)
        layout.addSpacing(4)
        layout.addWidget(self.overview, 1)
        layout.addSpacing(4)
        layout.addWidget(self.vol_btn)
        layout.addWidget(self.volume)
        self.set_playing(False)
        self.retranslate()

    def retranslate(self) -> None:
        self.rewind_btn.setToolTip(self.tr("Go to start"))
        self.play_btn.setToolTip(self.tr("Play / pause (Space)"))
        self.vol_btn.setToolTip(self.tr("Volume"))

    def refresh_theme(self) -> None:
        self.set_playing(self.playing)
        self.overview.update()

    def set_playing(self, playing: bool) -> None:
        self.playing = playing
        self.play_btn.setIcon(icon("pause" if playing else "play", theme.tokens["accent_text"]))

    def set_source(self, source) -> None:
        self.overview.set_source(source)
        self.total_label.setText("/ " + format_time(source.duration if source else 0.0))

    def set_time(self, seconds: float) -> None:
        self.time_label.setText(format_time(seconds))
        self.overview.set_position(seconds)

    def set_live(self, live: bool, text: str = "", recording: bool = False) -> None:
        self.overview.live = live
        self.overview.recording = recording
        self.overview.live_text = text
        for w in (self.rewind_btn, self.play_btn, self.total_label, self.vol_btn, self.volume):
            w.setVisible(not live)
        self.overview.update()
