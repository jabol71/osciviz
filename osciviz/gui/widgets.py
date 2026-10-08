"""Drobne widżety wielokrotnego użytku: suwak z polem liczbowym, wybór
koloru, przełącznik, kontrolka segmentowa, zwijana sekcja, przyciski z ikoną."""

from __future__ import annotations

from PySide6.QtCore import Property, QEasingCurve, QPropertyAnimation, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QAbstractButton,
    QButtonGroup,
    QColorDialog,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSlider,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from osciviz.gui.icons import icon
from osciviz.gui.theme import theme


def tool_button(icon_name: str, tooltip: str = "", checkable: bool = False, size: int = 18,
                parent: QWidget | None = None) -> QToolButton:
    btn = QToolButton(parent)
    btn.setIcon(icon(icon_name, theme.tokens["text"], theme.tokens["accent"]))
    btn.setIconSize(QSize(size, size))
    btn.setToolTip(tooltip)
    btn.setCheckable(checkable)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setProperty("icon_name", icon_name)
    return btn


def refresh_icons(root: QWidget) -> None:
    """Przerysowuje ikony przycisków po zmianie motywu (kolor kreski)."""
    for btn in root.findChildren(QAbstractButton):
        name = btn.property("icon_name")
        if name:
            color_key = btn.property("icon_color") or "text"
            btn.setIcon(icon(name, theme.tokens[color_key], theme.tokens["accent"]))


def divider(vertical: bool = False) -> QFrame:
    line = QFrame()
    line.setObjectName("VDivider" if vertical else "Divider")
    return line


def label(text: str = "", role: str | None = None) -> QLabel:
    lab = QLabel(text)
    if role:
        lab.setProperty("role", role)
    return lab


class SliderSpin(QWidget):
    """Suwak + pole liczbowe zsynchronizowane ze sobą.

    Sygnały: ``valueChanged(float)`` przy każdej zmianie oraz
    ``gestureFinished()`` po puszczeniu suwaka / zatwierdzeniu pola —
    inspektor używa go, by zakończyć łączenie kroków undo.
    """

    valueChanged = Signal(float)
    gestureFinished = Signal()

    STEPS = 1000

    def __init__(self, minimum: float, maximum: float, step: float = 0.01, decimals: int | None = None,
                 suffix: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.minimum, self.maximum = float(minimum), float(maximum)
        if decimals is None:
            decimals = 0 if step >= 1 else (1 if step >= 0.1 else 2)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setMinimumWidth(40)
        self.slider.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.slider.setRange(0, self.STEPS)
        self.slider.setFocusPolicy(Qt.NoFocus)
        self.spin = QDoubleSpinBox()
        self.spin.setRange(self.minimum, self.maximum)
        self.spin.setSingleStep(step)
        self.spin.setDecimals(decimals)
        self.spin.setSuffix(suffix)
        self.spin.setButtonSymbols(QDoubleSpinBox.NoButtons)
        self.spin.setFixedWidth(74)
        self.spin.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.spin.setKeyboardTracking(False)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self.slider, 1)
        layout.addWidget(self.spin)
        self._block = False
        self.slider.valueChanged.connect(self._from_slider)
        self.slider.sliderReleased.connect(self.gestureFinished)
        self.spin.valueChanged.connect(self._from_spin)
        self.spin.editingFinished.connect(self.gestureFinished)

    def _to_slider(self, value: float) -> int:
        span = self.maximum - self.minimum
        return int(round((value - self.minimum) / span * self.STEPS)) if span > 0 else 0

    def _from_slider(self, pos: int) -> None:
        if self._block:
            return
        value = self.minimum + (self.maximum - self.minimum) * pos / self.STEPS
        self._block = True
        self.spin.setValue(value)
        self._block = False
        self.valueChanged.emit(self.spin.value())

    def _from_spin(self, value: float) -> None:
        if self._block:
            return
        self._block = True
        self.slider.setValue(self._to_slider(value))
        self._block = False
        self.valueChanged.emit(value)

    def value(self) -> float:
        return self.spin.value()

    def setValue(self, value: float) -> None:  # noqa: N802 (konwencja Qt)
        self._block = True
        self.spin.setValue(value)
        self.slider.setValue(self._to_slider(value))
        self._block = False


class ColorButton(QPushButton):
    """Przycisk pokazujący kolor; kliknięcie otwiera systemowy wybór koloru."""

    colorChanged = Signal(str)

    def __init__(self, color: str = "#FFFFFF", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._color = color
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(28)
        self.clicked.connect(self._pick)
        self._update()

    def color(self) -> str:
        return self._color

    def setColor(self, color: str) -> None:  # noqa: N802
        self._color = color
        self._update()

    def _update(self) -> None:
        self.setText(self._color.upper())
        fg = "#000000" if QColor(self._color).lightnessF() > 0.6 else "#FFFFFF"
        self.setStyleSheet(
            f"QPushButton {{ background: {self._color}; color: {fg}; border-radius: 7px;"
            f" border: 1px solid rgba(255,255,255,0.18); font-family: 'SF Mono','Menlo','Cascadia Mono','Consolas',monospace;"
            f" font-size: 12px; }}"
        )

    def _pick(self) -> None:
        color = QColorDialog.getColor(QColor(self._color), self.window(), self.tr("Choose color"))
        if color.isValid():
            self.setColor(color.name())
            self.colorChanged.emit(self._color)


class Toggle(QAbstractButton):
    """Przełącznik w stylu iOS/macOS z animowaną gałką."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(34, 20)
        self._offset = 0.0
        self._anim = QPropertyAnimation(self, b"offset", self)
        self._anim.setDuration(140)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self.toggled.connect(self._animate)

    def _get_offset(self) -> float:
        return self._offset

    def _set_offset(self, value: float) -> None:
        self._offset = value
        self.update()

    offset = Property(float, _get_offset, _set_offset)

    def _animate(self, checked: bool) -> None:
        self._anim.stop()
        self._anim.setEndValue(1.0 if checked else 0.0)
        self._anim.start()

    def setChecked(self, checked: bool) -> None:  # noqa: N802
        super().setChecked(checked)
        self._anim.stop()
        self._offset = 1.0 if checked else 0.0
        self.update()

    def sizeHint(self) -> QSize:  # noqa: N802
        return QSize(34, 20)

    def paintEvent(self, event) -> None:  # noqa: N802
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        track_off = theme.color("surface3")
        track_on = theme.color("accent")
        t = self._offset
        color = QColor(
            int(track_off.red() + (track_on.red() - track_off.red()) * t),
            int(track_off.green() + (track_on.green() - track_off.green()) * t),
            int(track_off.blue() + (track_on.blue() - track_off.blue()) * t),
        )
        p.setPen(theme.color("border_strong") if t < 0.5 else Qt.NoPen)
        p.setBrush(color)
        p.drawRoundedRect(QRectF(0.5, 0.5, self.width() - 1, self.height() - 1), 10, 10)
        knob = self.height() - 6
        x = 3 + (self.width() - knob - 6) * t
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#FFFFFF") if theme.name != "high_contrast" or t < 0.5 else QColor("#000000"))
        p.drawEllipse(QRectF(x, 3, knob, knob))


class Segmented(QFrame):
    """Kontrolka segmentowa (wybór jednej z kilku opcji)."""

    changed = Signal(str)

    def __init__(self, options: list[tuple[str, str]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Segmented")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.buttons: dict[str, QPushButton] = {}
        for key, text in options:
            btn = QPushButton(text)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
            btn.setMinimumWidth(36)
            self.group.addButton(btn)
            self.buttons[key] = btn
            layout.addWidget(btn)
            btn.clicked.connect(lambda _=False, k=key: self.changed.emit(k))

    def set_value(self, key: str) -> None:
        if key in self.buttons:
            self.buttons[key].setChecked(True)

    def value(self) -> str:
        for key, btn in self.buttons.items():
            if btn.isChecked():
                return key
        return ""

    def set_text(self, key: str, text: str) -> None:
        self.buttons[key].setText(text)


class Section(QWidget):
    """Zwijana sekcja inspektora: nagłówek z chevronem + zawartość."""

    def __init__(self, title: str, parent: QWidget | None = None, expanded: bool = True) -> None:
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        self.header = QToolButton()
        self.header.setText(title.upper().replace("&", "&&"))
        self.header.setCheckable(True)
        self.header.setChecked(expanded)
        self.header.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.header.setCursor(Qt.PointingHandCursor)
        self.header.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.header.setStyleSheet(
            "QToolButton { border: none; background: transparent; padding: 10px 2px 6px 2px;"
            f" color: {theme.tokens['muted']}; font-size: 11px; font-weight: 600; letter-spacing: 0.6px;"
            " text-align: left; } QToolButton:checked { background: transparent; }"
            f" QToolButton:hover {{ color: {theme.tokens['text']}; background: transparent; }}"
        )
        self.header.setIconSize(QSize(12, 12))
        self.body = QWidget()
        self.form = QVBoxLayout(self.body)
        self.form.setContentsMargins(0, 2, 0, 8)
        self.form.setSpacing(8)
        outer.addWidget(self.header)
        outer.addWidget(self.body)
        self.header.toggled.connect(self._toggle)
        self._toggle(expanded)

    def _toggle(self, expanded: bool) -> None:
        self.body.setVisible(expanded)
        self.header.setIcon(icon("chevron-down" if expanded else "chevron-right", theme.tokens["muted"]))

    def add_row(self, title: str, widget: QWidget, tooltip: str = "") -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        lab = QLabel(title)
        lab.setProperty("role", "muted")
        lab.setFixedWidth(90)
        lab.setWordWrap(True)
        if tooltip:
            lab.setToolTip(tooltip)
        layout.addWidget(lab)
        layout.addWidget(widget, 1)
        self.form.addWidget(row)
        return row

    def add_widget(self, widget: QWidget) -> None:
        self.form.addWidget(widget)
