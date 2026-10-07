"""Ikony interfejsu jako małe pliki SVG zapisane w kodzie.

Każda ikona to fragment SVG w siatce 24×24 rysowany kreską (styl „outline”).
``icon(name, color)`` podmienia kolor kreski i renderuje SVG do ``QIcon``
w kilku rozmiarach (ostre na ekranach Retina). Dzięki temu ikony zawsze
pasują do aktywnego motywu i nie potrzebujemy plików graficznych.
"""

from __future__ import annotations

from functools import lru_cache

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QIcon, QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

PATHS: dict[str, str] = {
    "play": '<path d="M7 4.5v15l12.5-7.5z" fill="{c}" stroke-linejoin="round"/>',
    "pause": '<rect x="6" y="4.5" width="4" height="15" rx="1.2" fill="{c}" stroke="none"/>'
             '<rect x="14" y="4.5" width="4" height="15" rx="1.2" fill="{c}" stroke="none"/>',
    "skip-back": '<path d="M18 5v14L8 12z" fill="{c}"/><path d="M6 5v14"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "waveform": '<path d="M2 12h3l2.5-6 4 13 3.5-10 2.5 6 1.5-3H22"/>',
    "xy": '<path d="M12 12c-2.5-4-7-4-7 0s4.5 4 7 0 7-4 7 0-4.5 4-7 0z"/>'
          '<path d="M12 3v2M12 19v2M3 12h1M20 12h1" opacity=".5"/>',
    "spectrum": '<path d="M4 20V13M8 20V8M12 20V4M16 20v-9M20 20v-5"/>',
    "particles": '<circle cx="6" cy="7" r="1.3" fill="{c}"/><circle cx="12" cy="5" r="1.3" fill="{c}"/>'
                 '<circle cx="18" cy="8" r="1.3" fill="{c}"/><circle cx="8" cy="13" r="1.3" fill="{c}"/>'
                 '<circle cx="15" cy="13" r="1.3" fill="{c}"/><circle cx="5" cy="18" r="1.3" fill="{c}"/>'
                 '<circle cx="11" cy="19" r="1.3" fill="{c}"/><circle cx="19" cy="17" r="1.3" fill="{c}"/>',
    "eye": '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
    "eye-off": '<path d="M3 3l18 18"/><path d="M10.6 5.1A10 10 0 0 1 12 5c6.5 0 10 7 10 7a17 17 0 0 1-3 3.8'
               'M6.6 6.6C3.8 8.4 2 12 2 12s3.5 7 10 7a9.7 9.7 0 0 0 5.4-1.6"/>',
    "lock": '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
    "unlock": '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 7.8-1"/>',
    "trash": '<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"/>',
    "copy": '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V5a1 1 0 0 0-1-1H5a1 1 0 0 0-1 1v10'
            'a1 1 0 0 0 1 1h3"/>',
    "undo": '<path d="M9 14L4 9l5-5"/><path d="M4 9h11a5 5 0 0 1 0 10h-3"/>',
    "redo": '<path d="M15 14l5-5-5-5"/><path d="M20 9H9a5 5 0 0 0 0 10h3"/>',
    "grid": '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M3 15h18M9 3v18M15 3v18"/>',
    "magnet": '<path d="M6 3v8a6 6 0 0 0 12 0V3"/><path d="M6 7h4M14 7h4M10 3v8a2 2 0 0 0 4 0V3"/>',
    "camera": '<path d="M4 8h3l2-3h6l2 3h3a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1z"/>'
              '<circle cx="12" cy="13.5" r="3.5"/>',
    "export": '<path d="M12 15V3M7 8l5-5 5 5"/><path d="M4 14v5a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-5"/>',
    "folder": '<path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>',
    "save": '<path d="M5 3h11l4 4v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a1 1 0 0 1 1-1z"/>'
            '<path d="M8 3v5h7M8 21v-7h8v7"/>',
    "settings": '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M4.9 4.9l2.1 2.1M17 17l2.1 2.1'
                'M2 12h3M19 12h3M4.9 19.1L7 17M17 7l2.1-2.1"/>',
    "sliders": '<path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12M20 18h0"/><circle cx="16" cy="6" r="2"/>'
               '<circle cx="10" cy="12" r="2"/><circle cx="18" cy="18" r="2"/>',
    "music": '<path d="M9 18V5l11-2v13"/><circle cx="6.5" cy="18" r="2.5"/><circle cx="17.5" cy="16" r="2.5"/>',
    "mic": '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/>',
    "live": '<circle cx="12" cy="12" r="2.5" fill="{c}"/><path d="M7.8 7.8a6 6 0 0 0 0 8.4M16.2 7.8a6 6 0 0 1 0 8.4'
            'M5 5a10 10 0 0 0 0 14M19 5a10 10 0 0 1 0 14"/>',
    "record": '<circle cx="12" cy="12" r="6.5" fill="{c}" stroke="none"/>',
    "stop": '<rect x="6.5" y="6.5" width="11" height="11" rx="2" fill="{c}" stroke="none"/>',
    "image": '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="2"/>'
             '<path d="M21 16l-5-5-9 9"/>',
    "chevron-up": '<path d="M6 15l6-6 6 6"/>',
    "chevron-down": '<path d="M6 9l6 6 6-6"/>',
    "chevron-right": '<path d="M9 6l6 6-6 6"/>',
    "fit": '<path d="M4 9V5a1 1 0 0 1 1-1h4M15 4h4a1 1 0 0 1 1 1v4M20 15v4a1 1 0 0 1-1 1h-4M9 20H5a1 1 0 0 1-1-1v-4"/>',
    "volume": '<path d="M4 9h4l5-4v14l-5-4H4z"/><path d="M16.5 8.5a5 5 0 0 1 0 7M19 6a8.5 8.5 0 0 1 0 12"/>',
    "preset": '<path d="M12 3l2.6 5.6 6 .7-4.5 4.1 1.2 6L12 16.4 6.7 19.4l1.2-6L3.4 9.3l6-.7z"/>',
    "reset": '<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/>',
    "file-plus": '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/>'
                 '<path d="M14 3v6h6M12 12v6M9 15h6"/>',
    "logo": '<rect x="2" y="2" width="20" height="20" rx="6" fill="{c}" stroke="none"/>'
            '<path d="M5 12.5h2.5l1.7-4 2.6 8 2.4-6 1.6 3.5H19" stroke="#fff" stroke-width="1.9"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.5v.5"/>',
    "dots": '<circle cx="5" cy="12" r="1.4" fill="{c}"/><circle cx="12" cy="12" r="1.4" fill="{c}"/>'
            '<circle cx="19" cy="12" r="1.4" fill="{c}"/>',
}

LAYER_ICONS = {"waveform": "waveform", "xy": "xy", "spectrum": "spectrum", "particles": "particles"}


def svg_source(name: str, color: str, stroke_width: float = 1.8) -> str:
    body = PATHS[name].replace("{c}", color)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        f'stroke="{color}" stroke-width="{stroke_width}" stroke-linecap="round" '
        f'stroke-linejoin="round">{body}</svg>'
    )


def render_pixmap(name: str, color: str, size: int, stroke_width: float = 1.8) -> QPixmap:
    renderer = QSvgRenderer(QByteArray(svg_source(name, color, stroke_width).encode()))
    image = QImage(size, size, QImage.Format_ARGB32_Premultiplied)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()
    return QPixmap.fromImage(image)


@lru_cache(maxsize=512)
def icon(name: str, color: str = "#E7E9EE", active_color: str | None = None,
         stroke_width: float = 1.8) -> QIcon:
    """Ikona w danym kolorze; ``active_color`` — kolor stanu „włączony” (checked)."""
    result = QIcon()
    for size in (16, 20, 24, 32, 40, 48, 64):
        result.addPixmap(render_pixmap(name, color, size, stroke_width), QIcon.Normal, QIcon.Off)
        if active_color:
            result.addPixmap(render_pixmap(name, active_color, size, stroke_width), QIcon.Normal, QIcon.On)
    return result
