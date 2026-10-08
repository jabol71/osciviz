# -*- mode: python ; coding: utf-8 -*-
# Specyfikacja PyInstallera: buduje OsciViz.app na macOS albo folder z OsciViz.exe na Windows.
#   pyinstaller packaging/osciviz.spec --noconfirm
import sys
from pathlib import Path

IS_MAC = sys.platform == "darwin"
IS_WINDOWS = sys.platform == "win32"

ROOT = Path(SPECPATH).parent
PKG = ROOT / "osciviz"

datas = [
    (str(PKG / "render" / "shaders"), "osciviz/render/shaders"),
    (str(PKG / "gui" / "themes"), "osciviz/gui/themes"),
    (str(PKG / "resources" / "presets"), "osciviz/resources/presets"),
]
datas += [(str(p), "osciviz/i18n") for p in (PKG / "i18n").glob("*.qm")]

HIDDEN = ["glcontext", "moderngl", "sounddevice", "_sounddevice_data", "soundfile"]

a = Analysis(
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[str(ROOT)],
    datas=datas,
    hiddenimports=HIDDEN,
    excludes=["tkinter", "PySide6.QtWebEngineCore", "PySide6.QtQml", "PySide6.QtQuick", "PySide6.Qt3DCore"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="OsciViz",
    console=False,
    argv_emulation=False,
    # Windows: ikona pliku .exe (na macOS ikonę dostaje paczka .app niżej).
    icon=str(ROOT / "packaging" / "OsciViz.ico") if IS_WINDOWS else None,
)
coll = COLLECT(exe, a.binaries, a.datas, name="OsciViz")
if IS_MAC:
    app = BUNDLE(
        coll,
        name="OsciViz.app",
        icon=str(ROOT / "packaging" / "OsciViz.icns"),
        bundle_identifier="io.github.jabol71.osciviz",
        version="1.0.0",
        info_plist={
            "CFBundleName": "OsciViz",
            "CFBundleDisplayName": "OsciViz",
            "CFBundleShortVersionString": "1.0.0",
            "LSMinimumSystemVersion": "13.0",
            "NSHighResolutionCapable": True,
            "NSRequiresAquaSystemAppearance": False,
            # Bez tego macOS nie pozwoli czytać wejścia audio (BlackHole jest „mikrofonem”).
            "NSMicrophoneUsageDescription":
                "OsciViz potrzebuje dostępu do wejścia audio, aby wizualizować dźwięk na żywo "
                "(np. z FL Studio przez BlackHole).",
            "CFBundleDocumentTypes": [{
                "CFBundleTypeName": "OsciViz Project",
                "CFBundleTypeExtensions": ["osv"],
                "CFBundleTypeRole": "Editor",
            }],
        },
    )
