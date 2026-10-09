"""Motywy: ciemny, jasny i wysoki kontrast.

Kolory każdego motywu to słownik „tokenów” (tło, powierzchnia, ramka, tekst,
akcent…). Arkusz stylów motywu powstaje przy jego włączeniu z jednego
szablonu ``themes/base.qss.template`` przez podstawienie tokenów — dzięki temu
trzy motywy zawsze mają ten sam układ, a różnią się tylko kolorami.

Tokeny są też używane w kodzie rysującym (płótno, oś czasu), bo QSS nie
sięga do tego, co malujemy ręcznie przez ``QPainter``.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

THEMES_DIR = Path(__file__).with_name("themes")
THEME_NAMES = ("dark", "light", "high_contrast")

TOKENS: dict[str, dict[str, str]] = {
    "dark": {
        "bg": "#0B0C10", "surface": "#121318", "surface2": "#191B22", "surface3": "#22252E",
        "border": "#23262F", "border_strong": "#323642", "text": "#E8EAF0", "muted": "#8B90A0",
        "faint": "#5A5F6E", "accent": "#7C5CFF", "accent_hover": "#9079FF", "accent_press": "#6A48F5",
        "accent_text": "#FFFFFF", "accent_soft": "rgba(124, 92, 255, 0.16)", "danger": "#FF4D6D",
        "success": "#2EE59D", "canvas": "#08090C", "canvas_dim": "rgba(8, 9, 12, 0.62)",
        "grid": "rgba(255, 255, 255, 0.07)", "grid_axis": "rgba(255, 255, 255, 0.16)",
        "selection": "#7C5CFF", "ruler": "#0F1015", "ruler_text": "#6B7080", "focus": "#9079FF",
        "input": "#0F1015", "scroll": "#2A2D37", "tooltip": "#22252E",
    },
    "light": {
        "bg": "#F3F4F7", "surface": "#FFFFFF", "surface2": "#F5F6F8", "surface3": "#ECEDF1",
        "border": "#E3E5EA", "border_strong": "#CDD0D8", "text": "#14161C", "muted": "#626877",
        "faint": "#9AA0AE", "accent": "#6446F0", "accent_hover": "#7558FF", "accent_press": "#5235E0",
        "accent_text": "#FFFFFF", "accent_soft": "rgba(100, 70, 240, 0.12)", "danger": "#E5304F",
        "success": "#0FA968", "canvas": "#E6E8ED", "canvas_dim": "rgba(230, 232, 237, 0.72)",
        "grid": "rgba(255, 255, 255, 0.09)", "grid_axis": "rgba(255, 255, 255, 0.2)",
        "selection": "#6446F0", "ruler": "#FFFFFF", "ruler_text": "#8A8F9C", "focus": "#6446F0",
        "input": "#FFFFFF", "scroll": "#CFD2DA", "tooltip": "#14161C",
    },
    "high_contrast": {
        "bg": "#000000", "surface": "#000000", "surface2": "#000000", "surface3": "#1A1A1A",
        "border": "#FFFFFF", "border_strong": "#FFFFFF", "text": "#FFFFFF", "muted": "#FFFFFF",
        "faint": "#D0D0D0", "accent": "#FFD400", "accent_hover": "#FFE24D", "accent_press": "#E6BF00",
        "accent_text": "#000000", "accent_soft": "rgba(255, 212, 0, 0.25)", "danger": "#FF5C5C",
        "success": "#00FF88", "canvas": "#000000", "canvas_dim": "rgba(0, 0, 0, 0.7)",
        "grid": "rgba(255, 255, 255, 0.18)", "grid_axis": "rgba(255, 255, 255, 0.45)",
        "selection": "#FFD400", "ruler": "#000000", "ruler_text": "#FFFFFF", "focus": "#00E5FF",
        "input": "#000000", "scroll": "#FFFFFF", "tooltip": "#000000",
    },
}


def build_stylesheet(name: str) -> str:
    template = (THEMES_DIR / "base.qss.template").read_text(encoding="utf-8")
    for key, value in TOKENS[name].items():
        template = template.replace("{{" + key + "}}", value)
    return template


class ThemeManager:
    """Trzyma aktywny motyw i nakłada go na aplikację."""

    def __init__(self) -> None:
        self.name = "dark"

    @property
    def tokens(self) -> dict[str, str]:
        return TOKENS[self.name]

    def color(self, key: str) -> QColor:
        value = self.tokens[key]
        if value.startswith("rgba"):
            r, g, b, a = (float(v) for v in value[5:-1].split(","))
            return QColor(int(r), int(g), int(b), int(a * 255))
        return QColor(value)

    def apply(self, app: QApplication, name: str) -> None:
        self.name = name if name in TOKENS else "dark"
        qss = build_stylesheet(self.name).replace("@CHEVRON@", self._chevron_file())
        # Paleta dla elementów rysowanych natywnie (np. okna dialogowe systemu).
        t = self.tokens
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(t["bg"]))
        palette.setColor(QPalette.WindowText, QColor(t["text"]))
        palette.setColor(QPalette.Base, QColor(t["input"]))
        palette.setColor(QPalette.AlternateBase, QColor(t["surface2"]))
        palette.setColor(QPalette.Text, QColor(t["text"]))
        palette.setColor(QPalette.Button, QColor(t["surface2"]))
        palette.setColor(QPalette.ButtonText, QColor(t["text"]))
        palette.setColor(QPalette.Highlight, QColor(t["accent"]))
        palette.setColor(QPalette.HighlightedText, QColor(t["accent_text"]))
        palette.setColor(QPalette.PlaceholderText, QColor(t["faint"]))
        palette.setColor(QPalette.ToolTipBase, QColor(t["tooltip"]))
        palette.setColor(QPalette.ToolTipText, QColor("#FFFFFF" if self.name != "high_contrast" else t["text"]))
        app.setPalette(palette)
        app.setStyleSheet(qss)
        # Pasek tytułu okna rysuje system. Od Qt 6.8 można mu podpowiedzieć jasny
        # lub ciemny schemat — dzięki temu na Windows 11 (i macOS) pasek pasuje do motywu.
        hints = app.styleHints()
        if hasattr(hints, "setColorScheme"):
            dark = QColor(t["bg"]).lightness() < 128
            hints.setColorScheme(Qt.ColorScheme.Dark if dark else Qt.ColorScheme.Light)

    def _chevron_file(self) -> str:
        """Strzałka list rozwijanych jako plik SVG w kolorze motywu (QSS wymaga ścieżki)."""
        from osciviz.gui.icons import svg_source  # noqa: PLC0415

        folder = Path(tempfile.gettempdir()) / "osciviz-theme"
        folder.mkdir(exist_ok=True)
        path = folder / f"chevron-{self.name}.svg"
        path.write_text(svg_source("chevron-down", self.tokens["muted"], 2.2), encoding="utf-8")
        return path.as_posix()


theme = ThemeManager()  # jedna instancja na aplikację
