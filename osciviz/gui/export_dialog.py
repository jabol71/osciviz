"""Okno eksportu MP4: rozdzielczość, FPS, jakość, koder, zakres, ścieżka,
pasek postępu z szacowanym czasem i anulowaniem."""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QHBoxLayout,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from osciviz.gui.icons import icon
from osciviz.gui.theme import theme
from osciviz.gui.timeline import format_time
from osciviz.gui.widgets import Section, Segmented, SliderSpin, Toggle, label
from osciviz.io.exporter import RESOLUTION_PRESETS, ExportSettings, VideoExporter, resolution_for


class ExportDialog(QDialog):
    def __init__(self, scene, source, default_path: str, default_image: str | None, parent=None) -> None:
        super().__init__(parent)
        self.scene = scene
        self.source = source
        self.default_image = default_image
        self.exporter: VideoExporter | None = None
        self.setWindowTitle(self.tr("Export video"))
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(6)
        head = QHBoxLayout()
        badge = label()
        badge.setFixedSize(36, 36)
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet(f"background: {theme.tokens['accent_soft']}; border-radius: 10px;")
        badge.setPixmap(icon("export", theme.tokens["accent"]).pixmap(18, 18))
        head.addWidget(badge)
        titles = QVBoxLayout()
        titles.setSpacing(0)
        titles.addWidget(label(self.tr("Export MP4"), "brand"))
        titles.addWidget(label(self.tr("H.264 + AAC, plays in QuickTime and everywhere else"), "faint"))
        head.addLayout(titles, 1)
        layout.addLayout(head)
        layout.addSpacing(6)

        sec = Section(self.tr("Video"))
        self.resolution = QComboBox()
        for short, name in RESOLUTION_PRESETS.items():
            w, h = resolution_for(scene.aspect, short)
            self.resolution.addItem(f"{name}  ·  {w} × {h}", (w, h))
        self.resolution.setCurrentIndex(1)
        sec.add_row(self.tr("Resolution"), self.resolution)
        self.fps = Segmented([("30", "30 fps"), ("60", "60 fps")])
        self.fps.set_value("60")
        sec.add_row(self.tr("Frame rate"), self.fps)
        self.crf = SliderSpin(12, 32, 1, 0)
        self.crf.setValue(18)
        sec.add_row(self.tr("Quality (CRF)"), self.crf,
                    self.tr("Lower = better quality and bigger file. 18 is visually lossless."))
        self.codec = QComboBox()
        self.codec.addItem(self.tr("libx264 (software, best quality)"), "libx264")
        if sys.platform == "darwin":
            self.codec.addItem(self.tr("VideoToolbox (hardware, faster)"), "h264_videotoolbox")
        sec.add_row(self.tr("Encoder"), self.codec)
        layout.addWidget(sec)

        sec = Section(self.tr("Range & audio"))
        duration = source.duration
        rng = QWidget()
        rl = QHBoxLayout(rng)
        rl.setContentsMargins(0, 0, 0, 0)
        self.start = QDoubleSpinBox()
        self.end = QDoubleSpinBox()
        for spin in (self.start, self.end):
            spin.setRange(0.0, duration)
            spin.setDecimals(2)
            spin.setSuffix(" s")
            spin.setButtonSymbols(QDoubleSpinBox.NoButtons)
        self.end.setValue(duration)
        rl.addWidget(self.start, 1)
        rl.addWidget(label("→", "muted"))
        rl.addWidget(self.end, 1)
        sec.add_row(self.tr("From → to"), rng)
        self.audio = Toggle()
        self.audio.setChecked(source.path is not None)
        self.audio.setEnabled(source.path is not None)
        holder = QWidget()
        hl = QHBoxLayout(holder)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.addWidget(self.audio)
        hl.addStretch(1)
        sec.add_row(self.tr("Include audio"), holder)
        path_row = QWidget()
        pl = QHBoxLayout(path_row)
        pl.setContentsMargins(0, 0, 0, 0)
        self.path = QLineEdit(default_path)
        browse = QPushButton(icon("folder", theme.tokens["text"]), "")
        browse.setCursor(Qt.PointingHandCursor)
        browse.clicked.connect(self._browse)
        pl.addWidget(self.path, 1)
        pl.addWidget(browse)
        sec.add_row(self.tr("Save to"), path_row)
        layout.addWidget(sec)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.hide()
        self.status = label("", "faint")
        layout.addSpacing(6)
        layout.addWidget(self.progress)
        layout.addWidget(self.status)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.cancel_btn = QPushButton(self.tr("Cancel"))
        self.cancel_btn.clicked.connect(self._cancel)
        self.export_btn = QPushButton(icon("export", theme.tokens["accent_text"]), self.tr("Export"))
        self.export_btn.setProperty("variant", "primary")
        self.export_btn.setDefault(True)
        self.export_btn.clicked.connect(self._start)
        buttons.addWidget(self.cancel_btn)
        buttons.addWidget(self.export_btn)
        layout.addSpacing(8)
        layout.addLayout(buttons)

    def _browse(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, self.tr("Export video"), self.path.text(),
                                              self.tr("MP4 video (*.mp4)"))
        if path:
            if not path.lower().endswith(".mp4"):
                path += ".mp4"
            self.path.setText(path)

    def settings(self) -> ExportSettings:
        w, h = self.resolution.currentData()
        return ExportSettings(
            path=self.path.text(), width=w, height=h, fps=int(self.fps.value()),
            crf=int(self.crf.value()), codec=self.codec.currentData(),
            start=self.start.value(), end=max(self.end.value(), self.start.value() + 0.05),
            include_audio=self.audio.isChecked(),
        )

    def _start(self) -> None:
        s = self.settings()
        if not s.path:
            self._browse()
            s = self.settings()
            if not s.path:
                return
        self.exporter = VideoExporter(self.scene, self.source, s, self.default_image)
        self.exporter.progress.connect(self._on_progress)
        self.exporter.finished_ok.connect(self._on_done)
        self.exporter.failed.connect(self._on_failed)
        self.export_btn.setEnabled(False)
        self.progress.show()
        self.status.setText(self.tr("Preparing…"))
        self.exporter.start()

    def _on_progress(self, i: int, total: int, eta: float) -> None:
        self.progress.setValue(int(i * 100 / total))
        self.status.setText(self.tr("Frame %1 of %2 · about %3 left")
                            .replace("%1", str(i)).replace("%2", str(total))
                            .replace("%3", format_time(eta)[:-3]))

    def _on_done(self, path: str) -> None:
        self.status.setText(self.tr("Saved to %1").replace("%1", path))
        self.progress.setValue(100)
        self.cancel_btn.setText(self.tr("Close"))
        self.export_btn.setEnabled(True)
        self.exporter = None

    def _on_failed(self, message: str) -> None:
        self.export_btn.setEnabled(True)
        self.progress.hide()
        self.status.setText(self.tr("Export cancelled.") if not message
                            else self.tr("Export failed: %1").replace("%1", message))
        self.exporter = None

    def _cancel(self) -> None:
        if self.exporter is not None:
            self.exporter.cancel()
            self.status.setText(self.tr("Cancelling…"))
            return
        self.reject()

    def closeEvent(self, event) -> None:  # noqa: N802
        if self.exporter is not None:
            self.exporter.cancel()
            self.exporter.wait(5000)
        super().closeEvent(event)
