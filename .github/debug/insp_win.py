import os, sys
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication
from osciviz.app import configure_opengl
from PySide6.QtCore import Qt
configure_opengl()
QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
app = QApplication(sys.argv)
app.setStyle("Fusion")
from PySide6.QtGui import QFont, QPalette
f = QFont("Segoe UI Variable Text", 10); f.setFamilies(["Segoe UI Variable Text", "Segoe UI"]); app.setFont(f)
from osciviz.gui.theme import theme
if os.environ.get("NOSCHEME"):
    type(app.styleHints()).setColorScheme = lambda *a: None
theme.apply(app, "dark")
def note(msg):
    print("::notice::" + msg.replace("\n", " | "), flush=True)
import PySide6
note(f"qt={PySide6.__version__} style={app.style().name()} platform={app.platformName()} scheme={app.styleHints().colorScheme()}")
from osciviz.gui.main_window import MainWindow
w = MainWindow(app); w.resize(1400, 900); w.show(); w.load_demo()
def shot():
    w.scene.set_selection([w.scene.layers[int(os.environ.get("SEL", "1"))].id])
    app.processEvents()
    img = w.inspector.grab()
    img.save(os.environ.get("OUT", "/tmp/claude-0/s/w/insp.png"))
    sp = w.inspector.findChildren(__import__("PySide6.QtWidgets", fromlist=["QDoubleSpinBox"]).QDoubleSpinBox)
    for s in sp[:3]:
        le = s.lineEdit()
        pal = le.palette()
        note(f"spin {s.width()}x{s.height()} edit={le.geometry().getRect()} vis={le.isVisible()} text={le.text()!r} "
             f"textColor={pal.color(QPalette.Text).name()} base={pal.color(QPalette.Base).name()} "
             f"spinText={s.palette().color(QPalette.Text).name()} dpr={s.devicePixelRatioF()} font={le.font().family()}/{le.font().pointSizeF()}")
        img = s.grab().toImage()
        # rozkład jasności pikseli pola — czy cokolwiek jest narysowane
        vals = sorted({img.pixelColor(x, y).lightness() for x in range(0, img.width(), 2) for y in range(0, img.height(), 2)})
        note(f"pixels lightness distinct={len(vals)} min={vals[0]} max={vals[-1]}")
    app.quit()
QTimer.singleShot(800, shot)
app.exec()
