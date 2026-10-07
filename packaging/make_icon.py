"""Generuje ikonę aplikacji (packaging/OsciViz.icns i icon.png) z logo SVG.

Uruchom: ``python packaging/make_icon.py``. Ikona to zaokrąglony kwadrat z gradientem
i białą linią przebiegu — ten sam znak co w pasku górnym aplikacji.
"""

from pathlib import Path

from PIL import Image
from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024">
<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
<stop offset="0" stop-color="#8B6BFF"/><stop offset="1" stop-color="#22D3EE"/></linearGradient>
<radialGradient id="glow" cx="0.5" cy="0.5" r="0.5"><stop offset="0" stop-color="#ffffff" stop-opacity="0.35"/>
<stop offset="1" stop-color="#ffffff" stop-opacity="0"/></radialGradient></defs>
<rect x="100" y="100" width="824" height="824" rx="190" fill="#0B0C10"/>
<rect x="112" y="112" width="800" height="800" rx="180" fill="url(#g)" opacity="0.95"/>
<circle cx="512" cy="512" r="330" fill="url(#glow)"/>
<path d="M210 540 H330 L400 360 L510 700 L610 420 L680 590 L730 500 H814" fill="none"
 stroke="#ffffff" stroke-width="54" stroke-linecap="round" stroke-linejoin="round"/>
</svg>"""


def main() -> None:
    app = QGuiApplication.instance() or QGuiApplication([])  # noqa: F841 (wymagane przez QtSvg)
    out = Path(__file__).parent
    renderer = QSvgRenderer(QByteArray(SVG.encode()))
    image = QImage(1024, 1024, QImage.Format_RGBA8888)
    image.fill(Qt.transparent)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    renderer.render(painter, QRectF(0, 0, 1024, 1024))
    painter.end()
    png = out / "icon.png"
    image.save(str(png))
    Image.open(png).save(out / "OsciViz.icns")
    print("Zapisano", png, "i", out / "OsciViz.icns")


if __name__ == "__main__":
    main()
