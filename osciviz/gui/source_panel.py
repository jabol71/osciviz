"""Panel źródła dźwięku: plik albo przechwytywanie na żywo (np. z FL Studio).

Tryb „Na żywo” pokazuje listę źródeł i sam wybiera najlepsze: na Windows
dźwięk z głównych głośników (WASAPI loopback), na macOS — BlackHole. Wirtualny
kabel (BlackHole, VB-Cable) jest podświetlony. Gdy nie ma żadnego sposobu
przechwycenia FL Studio, panel pokazuje odnośnik do instrukcji konfiguracji. Przycisk REC nagrywa sesję do WAV.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QPushButton, QStackedWidget, QVBoxLayout, QWidget

from osciviz.core.audio_source import list_live_devices
from osciviz.core.sd import import_error
from osciviz.gui.icons import icon
from osciviz.gui.keys import IS_WINDOWS, with_keys
from osciviz.gui.theme import theme
from osciviz.gui.widgets import Segmented, label, tool_button

GUIDE_URL = "https://github.com/jabol71/osciviz/blob/main/docs/user-guide/live-capture.md"


class SourcePanel(QFrame):
    modeChanged = Signal(str)  # "file" | "live"
    openFileRequested = Signal()
    startLiveRequested = Signal(object)  # indeks urządzenia
    stopLiveRequested = Signal()
    recordToggled = Signal(bool)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Panel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 12)
        layout.setSpacing(8)
        header = QHBoxLayout()
        self.title = label("", "title")
        header.addWidget(self.title)
        header.addStretch(1)
        self.live_pill = label("", "pill-live")
        self.live_pill.hide()
        header.addWidget(self.live_pill)
        layout.addLayout(header)
        self.mode = Segmented([("file", ""), ("live", "")])
        self.mode.set_value("file")
        self.mode.changed.connect(self._mode_changed)
        layout.addWidget(self.mode)

        self.stack = QStackedWidget()
        # --- plik ---
        file_page = QWidget()
        fl = QVBoxLayout(file_page)
        fl.setContentsMargins(0, 2, 0, 0)
        fl.setSpacing(6)
        self.file_card = QFrame()
        self.file_card.setObjectName("Card")
        cl = QHBoxLayout(self.file_card)
        cl.setContentsMargins(10, 8, 10, 8)
        cl.setSpacing(10)
        self.file_icon = label()
        self.file_icon.setPixmap(icon("music", theme.tokens["accent"]).pixmap(20, 20))
        cl.addWidget(self.file_icon)
        info = QVBoxLayout()
        info.setSpacing(0)
        self.file_name = label("", "title")
        self.file_meta = label("", "faint")
        info.addWidget(self.file_name)
        info.addWidget(self.file_meta)
        cl.addLayout(info, 1)
        self.open_btn = tool_button("folder", "", size=16)
        self.open_btn.clicked.connect(self.openFileRequested)
        cl.addWidget(self.open_btn)
        fl.addWidget(self.file_card)
        self.stack.addWidget(file_page)

        # --- na żywo ---
        live_page = QWidget()
        ll = QVBoxLayout(live_page)
        ll.setContentsMargins(0, 2, 0, 0)
        ll.setSpacing(6)
        dev_row = QHBoxLayout()
        self.devices = QComboBox()
        self.devices.setIconSize(QSize(14, 14))
        dev_row.addWidget(self.devices, 1)
        self.refresh_btn = tool_button("reset", "", size=15)
        self.refresh_btn.clicked.connect(self.refresh_devices)
        dev_row.addWidget(self.refresh_btn)
        ll.addLayout(dev_row)
        self.hint = label("", "faint")
        self.hint.setWordWrap(True)
        self.hint.setOpenExternalLinks(True)
        self.hint.setTextFormat(Qt.RichText)
        ll.addWidget(self.hint)
        btn_row = QHBoxLayout()
        self.listen_btn = QPushButton()
        self.listen_btn.setCheckable(True)
        self.listen_btn.setProperty("variant", "primary")
        self.listen_btn.setCursor(Qt.PointingHandCursor)
        self.listen_btn.toggled.connect(self._listen_toggled)
        self.rec_btn = QPushButton()
        self.rec_btn.setCheckable(True)
        self.rec_btn.setProperty("variant", "danger")
        self.rec_btn.setCursor(Qt.PointingHandCursor)
        self.rec_btn.setEnabled(False)
        self.rec_btn.toggled.connect(self.recordToggled)
        btn_row.addWidget(self.listen_btn, 1)
        btn_row.addWidget(self.rec_btn)
        ll.addLayout(btn_row)
        self.stack.addWidget(live_page)
        layout.addWidget(self.stack)

        self._file_info = None
        self.retranslate()

    def retranslate(self) -> None:
        self.title.setText(self.tr("Audio source"))
        self.live_pill.setText(self.tr("LIVE"))
        self.mode.set_text("file", self.tr("File"))
        self.mode.set_text("live", self.tr("Live input"))
        self.open_btn.setToolTip(with_keys(self.tr("Open audio file…"), "Ctrl+I"))
        self.refresh_btn.setToolTip(self.tr("Refresh device list"))
        self._update_listen_text()
        self.rec_btn.setText(self.tr("● REC"))
        self.rec_btn.setToolTip(self.tr("Record the live session to a WAV file"))
        self.set_file_info(self._file_info)
        if self.mode.value() == "live":
            self.refresh_devices()

    def _update_listen_text(self) -> None:
        self.listen_btn.setText(self.tr("Stop listening") if self.listen_btn.isChecked()
                                else self.tr("Start listening"))
        self.listen_btn.setIcon(icon("stop" if self.listen_btn.isChecked() else "live",
                                     theme.tokens["accent_text"]))

    def set_file_info(self, info: tuple[str, float, int] | None) -> None:
        self._file_info = info
        if info is None:
            self.file_name.setText(self.tr("No audio loaded"))
            self.file_meta.setText(self.tr("WAV, FLAC, MP3, OGG, AIFF"))
        else:
            name, duration, sr = info
            m, s = divmod(int(duration), 60)
            self.file_name.setText(name)
            self.file_meta.setText(f"{m}:{s:02d} · {sr / 1000:g} kHz · {self.tr('stereo')}")

    def _mode_changed(self, mode: str) -> None:
        self.stack.setCurrentIndex(0 if mode == "file" else 1)
        if mode == "live":
            self.refresh_devices()
        elif self.listen_btn.isChecked():
            self.listen_btn.setChecked(False)
        self.modeChanged.emit(mode)

    def set_mode(self, mode: str) -> None:
        self.mode.set_value(mode)
        self.stack.setCurrentIndex(0 if mode == "file" else 1)

    def refresh_devices(self) -> None:
        self.devices.clear()
        err = import_error()
        devices = list_live_devices()
        preferred = -1  # indeks pozycji wybieranej automatycznie
        has_loopback = has_virtual = False
        for d in devices:
            if d["kind"] == "loopback":
                has_loopback = True
                text = self.tr("System sound: %1").replace("%1", d["name"])
                item_icon = icon("volume", theme.tokens["accent"] if d["is_default"] else theme.tokens["muted"])
            else:
                has_virtual = has_virtual or d["is_virtual"]
                text = d["name"]
                item_icon = icon("live", theme.tokens["accent"]) if d["is_virtual"] else icon("mic", theme.tokens["muted"])
            self.devices.addItem(item_icon, text, (d["kind"], d["index"]))
            # Na Windows domyślnie dźwięk z głównego wyjścia; na macOS — BlackHole.
            wanted = d["is_default"] if has_loopback else d["is_virtual"]
            if wanted and preferred < 0:
                preferred = self.devices.count() - 1
        if preferred >= 0:
            self.devices.setCurrentIndex(preferred)
        self.hint.setText(self._hint_text(devices, err, has_loopback, has_virtual))
        self.listen_btn.setEnabled(bool(devices))

    def _hint_text(self, devices: list, err: str | None, has_loopback: bool, has_virtual: bool) -> str:
        if has_loopback:
            text = self.tr("“System sound” captures everything playing on the chosen speakers. "
                           "Play something in FL Studio and press Start.")
            if has_virtual:
                text += " " + self.tr("VB-Cable detected: choose “CABLE Output” if FL Studio plays into CABLE Input.")
            return text
        if has_virtual:
            if IS_WINDOWS:
                return self.tr("VB-Cable detected — set FL Studio's output to CABLE Input and press Start.")
            return self.tr("BlackHole detected — set FL Studio's output to your "
                           "Multi-Output Device and press Start.")
        if err and not devices:
            return self.tr("Audio input is unavailable on this system (PortAudio missing).")
        if not devices:
            return self.tr("No input devices found.")
        if IS_WINDOWS:
            return self.tr('To capture FL Studio, install VB-Cable — <a href="%1">setup guide</a>.').replace(
                "%1", GUIDE_URL)
        return self.tr('BlackHole not found. To capture FL Studio, install BlackHole 2ch — '
                       '<a href="%1">setup guide</a>.').replace("%1", GUIDE_URL)

    def _listen_toggled(self, on: bool) -> None:
        self._update_listen_text()
        self.rec_btn.setEnabled(on)
        if not on and self.rec_btn.isChecked():
            self.rec_btn.setChecked(False)
        if on:
            self.startLiveRequested.emit(self.devices.currentData())
        else:
            self.stopLiveRequested.emit()
        self.live_pill.setVisible(on)

    def set_listening(self, on: bool) -> None:
        self.listen_btn.blockSignals(True)
        self.listen_btn.setChecked(on)
        self.listen_btn.blockSignals(False)
        self._update_listen_text()
        self.rec_btn.setEnabled(on)
        self.live_pill.setVisible(on)
