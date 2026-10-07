"""Ustawienia aplikacji: motyw i język interfejsu (zapamiętywane w QSettings)."""

from __future__ import annotations

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QAbstractButton, QButtonGroup, QDialog, QHBoxLayout, QPushButton, QVBoxLayout, QWidget

from osciviz.gui.theme import TOKENS
from osciviz.gui.widgets import Section, Segmented, label


class ThemeSwatch(QAbstractButton):
    """Kafelek z miniaturą motywu (rysowany ręcznie, bez arkusza stylów)."""

    def __init__(self, name: str, title: str) -> None:
        super().__init__()
        self.name = name
        self.title = title
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(QSize(124, 96))

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(124, 96)

    def paintEvent(self, event) -> None:  # noqa: N802
        t = TOKENS[self.name]
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(2, 2, self.width() - 4, self.height() - 28)
        p.setPen(QPen(QColor(t["accent"]) if self.isChecked() else QColor(t["border_strong"]),
                      2 if self.isChecked() else 1))
        p.setBrush(QColor(t["bg"]))
        p.drawRoundedRect(r, 9, 9)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(t["surface"]))
        side = QRectF(r.left() + 6, r.top() + 6, r.width() * 0.3, r.height() - 12)
        main = QRectF(side.right() + 5, r.top() + 6, r.right() - side.right() - 11, r.height() - 12)
        p.drawRoundedRect(side, 4, 4)
        p.drawRoundedRect(main, 4, 4)
        p.setBrush(QColor(t["muted"]))
        for i in range(3):
            p.drawRoundedRect(QRectF(side.left() + 5, side.top() + 6 + i * 9, side.width() - 10, 4), 2, 2)
        p.setBrush(QColor(t["accent"]))
        p.drawRoundedRect(QRectF(main.right() - 26, main.bottom() - 12, 20, 7), 3, 3)
        p.setPen(self.palette().windowText().color())
        p.drawText(QRectF(0, self.height() - 22, self.width(), 20), Qt.AlignCenter, self.title)


class SettingsDialog(QDialog):
    themeChanged = Signal(str)
    languageChanged = Signal(str)

    def __init__(self, current_theme: str, current_lang: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("Settings"))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(6)
        layout.addWidget(label(self.tr("Settings"), "brand"))
        sec = Section(self.tr("Appearance"))
        row = QWidget()
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(10)
        self.group = QButtonGroup(self)
        for name, title in (("dark", self.tr("Dark")), ("light", self.tr("Light")),
                            ("high_contrast", self.tr("High contrast"))):
            sw = ThemeSwatch(name, title)
            sw.setChecked(name == current_theme)
            sw.clicked.connect(lambda _=False, n=name: self.themeChanged.emit(n))
            self.group.addButton(sw)
            rl.addWidget(sw)
        sec.add_widget(row)
        layout.addWidget(sec)
        sec = Section(self.tr("Language"))
        self.lang = Segmented([("pl", "Polski"), ("en", "English")])
        self.lang.set_value(current_lang)
        self.lang.changed.connect(self.languageChanged)
        sec.add_row(self.tr("Interface"), self.lang)
        layout.addWidget(sec)
        layout.addSpacing(8)
        close = QPushButton(self.tr("Done"))
        close.setProperty("variant", "primary")
        close.clicked.connect(self.accept)
        bl = QHBoxLayout()
        bl.addStretch(1)
        bl.addWidget(close)
        layout.addLayout(bl)
