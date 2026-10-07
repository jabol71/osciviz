"""Okno główne: układ paneli, menu, skróty, zegar klatek, pliki i eksport.

Przepływ jednej klatki (``_tick``, ok. 60 razy na sekundę):

1. odczyt zegara: pozycja odtwarzacza (plik) albo „teraz” (na żywo),
2. pobranie okna próbek ze źródła,
3. analiza (FFT, pasma) → ``FrameContext``,
4. krok symulacji (widmo, cząsteczki),
5. ``canvas.update()`` — rysowanie przez renderer.
"""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

import numpy as np
from PySide6.QtCore import (
    QCoreApplication,
    QEasingCurve,
    QPropertyAnimation,
    QSettings,
    QSize,
    QStandardPaths,
    Qt,
    QTimer,
    QTranslator,
    QUrl,
)
from PySide6.QtGui import QAction, QActionGroup, QDesktopServices, QKeySequence, QUndoStack
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from osciviz import APP_NAME, __version__
from osciviz.core.analysis import Analyzer
from osciviz.core.audio_player import AudioPlayer
from osciviz.core.audio_source import FileSource, LiveSource
from osciviz.core.demo import write_demo_wav
from osciviz.core.frame import build_frame, window_length
from osciviz.core.image_to_points import make_default_image
from osciviz.core.recorder import Recorder
from osciviz.gui.canvas_widget import CanvasWidget
from osciviz.gui.export_dialog import ExportDialog
from osciviz.gui.icons import LAYER_ICONS, icon
from osciviz.gui.inspector import Inspector
from osciviz.gui.layer_panel import LayerPanel
from osciviz.gui.settings_dialog import SettingsDialog
from osciviz.gui.source_panel import SourcePanel
from osciviz.gui.theme import THEME_NAMES, theme
from osciviz.gui.timeline import Timeline, format_time
from osciviz.gui.widgets import divider, label, refresh_icons, tool_button
from osciviz.io.exporter import OffscreenRenderer, resolution_for, save_png
from osciviz.io.presets import PresetError, PresetManager, write_preset
from osciviz.io.project_io import ProjectError, load_project, save_project
from osciviz.scene import commands as cmd
from osciviz.scene.layers import LAYER_TYPES, Layer, create_layer
from osciviz.scene.scene import Scene
from osciviz.scene.simulation import Simulation

I18N_DIR = Path(__file__).resolve().parent.parent / "i18n"
DOCS_URL = "https://github.com/jabol71/osciviz/tree/main/docs/user-guide"
PREVIEW_MAX_PARTICLES = 40000
AUDIO_FILTER = "Audio (*.wav *.flac *.mp3 *.ogg *.aif *.aiff)"


class Toast(QLabel):
    """Krótkie powiadomienie wyświetlane nad płótnem, znikające samo."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setStyleSheet(
            f"background: {theme.tokens['surface3']}; color: {theme.tokens['text']};"
            f" border: 1px solid {theme.tokens['border_strong']}; border-radius: 10px;"
            " padding: 8px 14px; font-weight: 500;")
        self.effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.effect)
        self.anim = QPropertyAnimation(self.effect, b"opacity", self)
        self.anim.setEasingCurve(QEasingCurve.OutCubic)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._fade_out)
        self.hide()

    def show_message(self, text: str, ms: int = 2200) -> None:
        self.setText(text)
        self.adjustSize()
        parent = self.parentWidget()
        self.move((parent.width() - self.width()) // 2, parent.height() - self.height() - 18)
        self.raise_()
        self.show()
        self.anim.stop()
        self.anim.setDuration(160)
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.start()
        self.timer.start(ms)

    def _fade_out(self) -> None:
        self.anim.stop()
        self.anim.setDuration(400)
        self.anim.setStartValue(1.0)
        self.anim.setEndValue(0.0)
        self.anim.finished.connect(self.hide)
        self.anim.start()


class MainWindow(QMainWindow):
    def __init__(self, app: QApplication) -> None:
        super().__init__()
        self.app = app
        self.settings = QSettings()
        self.scene = Scene()
        self.undo = QUndoStack(self)
        self.sim = Simulation(max_particles=PREVIEW_MAX_PARTICLES)
        self.analyzer = Analyzer()
        self.player = AudioPlayer()
        self.player.volume = 0.8
        self.source: FileSource | None = None
        self.live: LiveSource | None = None
        self.live_t0 = 0.0
        self.recorder: Recorder | None = None
        self.project_path: str | None = None
        self.translator: QTranslator | None = None
        self.language = "pl"
        self._extra_dirty = False
        self._last_tick = time.perf_counter()
        self._fps_frames = 0
        self._fps_t0 = time.perf_counter()

        data_dir = Path(QStandardPaths.writableLocation(QStandardPaths.AppDataLocation))
        data_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir = data_dir
        self.presets = PresetManager(data_dir / "presets")
        default_image = data_dir / "default-particles.png"
        self.default_image = str(default_image) if default_image.exists() else None
        if self.default_image is None:
            try:
                self.default_image = make_default_image(str(default_image))
            except Exception:
                self.default_image = None

        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(1100, 700)
        self.setUnifiedTitleAndToolBarOnMac(True)
        self._build_ui()
        self._build_actions()
        self._build_menus()
        self.retranslate()
        self._restore_settings()

        self.undo.cleanChanged.connect(self._update_title)
        self.undo.indexChanged.connect(self._on_undo_index)
        self.scene.selection_changed.connect(self._update_actions)
        self.scene.layers_changed.connect(self._update_actions)

        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.timeout.connect(self._tick)
        self.timer.start(16)
        self._update_actions()
        self._update_title()

    # ======================================================================
    # Budowa interfejsu
    # ======================================================================
    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("AppRoot")
        outer = QVBoxLayout(root)
        outer.setContentsMargins(8, 8, 8, 8)
        outer.setSpacing(8)
        outer.addWidget(self._build_top_bar())

        middle = QHBoxLayout()
        middle.setSpacing(8)
        left = QVBoxLayout()
        left.setSpacing(8)
        self.source_panel = SourcePanel()
        self.layer_panel = LayerPanel(self.scene, self.undo)
        left.addWidget(self.source_panel)
        left.addWidget(self.layer_panel, 1)
        left_holder = QWidget()
        left_holder.setLayout(left)
        left_holder.setFixedWidth(270)
        left.setContentsMargins(0, 0, 0, 0)
        middle.addWidget(left_holder)

        self.canvas = CanvasWidget(self.scene, self.undo, self.sim)
        self.canvas.default_image = self.default_image
        canvas_frame = QFrame()
        canvas_frame.setObjectName("Panel")
        cl = QVBoxLayout(canvas_frame)
        cl.setContentsMargins(1, 1, 1, 1)
        cl.addWidget(self.canvas)
        self.canvas_frame = canvas_frame
        middle.addWidget(canvas_frame, 1)

        self.inspector = Inspector(self.scene, self.undo, self.presets, self.canvas)
        self.inspector.setFixedWidth(312)
        middle.addWidget(self.inspector)
        outer.addLayout(middle, 1)

        self.timeline = Timeline()
        outer.addWidget(self.timeline)
        self.setCentralWidget(root)
        self.toast = Toast(canvas_frame)

        # Pasek stanu.
        self.status_coords = label("", "faint")
        self.status_zoom = label("", "faint")
        self.status_fps = label("", "faint")
        for w in (self.status_coords, self.status_zoom, self.status_fps):
            w.setMinimumWidth(90)
            self.statusBar().addPermanentWidget(w)
        self.statusBar().setSizeGripEnabled(False)

        # Połączenia.
        self.layer_panel.addLayerRequested.connect(self.add_layer)
        self.layer_panel.dup_btn.clicked.connect(self.duplicate_selection)
        self.layer_panel.del_btn.clicked.connect(self.delete_selection)
        self.canvas.requestPlayToggle.connect(self.toggle_play)
        self.canvas.requestDuplicate.connect(self.duplicate_selection)
        self.canvas.requestDelete.connect(self.delete_selection)
        self.canvas.requestSavePreset.connect(self.save_preset)
        self.canvas.requestApplyPreset.connect(self.apply_preset)
        self.canvas.cursorMoved.connect(lambda x, y: self.status_coords.setText(f"x {x:+.3f}   y {y:+.3f}"))
        self.canvas.zoomChanged.connect(lambda z: self.status_zoom.setText(f"{z / 540 * 100:.0f} %"))
        self.canvas.glError.connect(self._on_gl_error)
        self.inspector.requestApplyPreset.connect(self.apply_preset)
        self.inspector.requestSavePreset.connect(self.save_preset)
        self.inspector.canvasOptionsChanged.connect(self._sync_view_actions)
        self.timeline.playToggled.connect(self.toggle_play)
        self.timeline.rewind.connect(self.rewind)
        self.timeline.seekRequested.connect(self.seek)
        self.timeline.volumeChanged.connect(lambda v: setattr(self.player, "volume", v))
        self.source_panel.openFileRequested.connect(self.open_audio_dialog)
        self.source_panel.modeChanged.connect(self._on_source_mode)
        self.source_panel.startLiveRequested.connect(self.start_live)
        self.source_panel.stopLiveRequested.connect(self.stop_live)
        self.source_panel.recordToggled.connect(self.toggle_record)
        self.canvas.preset_names = self.presets.all()

    def _build_top_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("TopBar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(6)
        logo = QLabel()
        logo.setPixmap(icon("logo", theme.tokens["accent"]).pixmap(26, 26))
        self.logo = logo
        layout.addWidget(logo)
        brand = label(APP_NAME, "brand")
        layout.addWidget(brand)
        layout.addSpacing(6)
        self.project_label = label("", "faint")
        layout.addWidget(self.project_label)
        layout.addStretch(1)

        self.add_buttons: dict[str, QToolButton] = {}
        for type_name in LAYER_TYPES:
            btn = QToolButton()
            btn.setProperty("variant", "chip")
            btn.setProperty("icon_name", LAYER_ICONS[type_name])
            btn.setIcon(icon(LAYER_ICONS[type_name], theme.tokens["text"]))
            btn.setIconSize(QSize(16, 16))
            btn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _=False, t=type_name: self.add_layer(t))
            self.add_buttons[type_name] = btn
            layout.addWidget(btn)
        layout.addStretch(1)

        self.undo_btn = tool_button("undo")
        self.redo_btn = tool_button("redo")
        self.undo_btn.clicked.connect(self.undo.undo)
        self.redo_btn.clicked.connect(self.undo.redo)
        self.undo.canUndoChanged.connect(self.undo_btn.setEnabled)
        self.undo.canRedoChanged.connect(self.redo_btn.setEnabled)
        self.undo_btn.setEnabled(False)
        self.redo_btn.setEnabled(False)
        self.grid_btn = tool_button("grid", checkable=True)
        self.snap_btn = tool_button("magnet", checkable=True)
        self.fit_btn = tool_button("fit")
        self.fit_btn.clicked.connect(lambda: self.canvas.fit_view())
        self.png_btn = tool_button("camera")
        self.png_btn.clicked.connect(self.export_png)
        self.settings_btn = tool_button("settings")
        self.settings_btn.clicked.connect(self.open_settings)
        for w in (self.undo_btn, self.redo_btn):
            layout.addWidget(w)
        layout.addWidget(divider(True))
        for w in (self.grid_btn, self.snap_btn, self.fit_btn):
            layout.addWidget(w)
        layout.addWidget(divider(True))
        layout.addWidget(self.png_btn)
        self.export_btn = QPushButton()
        self.export_btn.setProperty("variant", "primary")
        self.export_btn.setProperty("icon_name", "export")
        self.export_btn.setProperty("icon_color", "accent_text")
        self.export_btn.setIcon(icon("export", theme.tokens["accent_text"]))
        self.export_btn.setCursor(Qt.PointingHandCursor)
        self.export_btn.clicked.connect(self.export_video)
        layout.addWidget(self.export_btn)
        layout.addWidget(self.settings_btn)
        return bar

    def _action(self, name: str, slot, shortcut=None, icon_name: str | None = None,
                checkable: bool = False) -> QAction:
        act = QAction(self)
        if icon_name:
            act.setIcon(icon(icon_name, theme.tokens["text"]))
        if shortcut is not None:
            if isinstance(shortcut, (list, tuple)):
                act.setShortcuts([QKeySequence(s) for s in shortcut])
            else:
                act.setShortcut(QKeySequence(shortcut))
        act.setCheckable(checkable)
        act.triggered.connect(slot)
        self.addAction(act)
        self.actions_by_name[name] = act
        return act

    def _build_actions(self) -> None:
        self.actions_by_name: dict[str, QAction] = {}
        a = self._action
        a("new", self.new_project, QKeySequence.New, "file-plus")
        a("open", self.open_project_dialog, QKeySequence.Open, "folder")
        a("save", self.save_project, QKeySequence.Save, "save")
        a("save_as", self.save_project_as, "Ctrl+Alt+S")
        a("import_audio", self.open_audio_dialog, "Ctrl+I", "music")
        a("import_preset", self.import_preset)
        a("export_preset", self.export_preset)
        a("export_mp4", self.export_video, "Ctrl+E", "export")
        a("export_png", self.export_png, "Ctrl+Shift+S", "camera")
        a("demo", self.load_demo)
        a("quit", self.close, QKeySequence.Quit)
        undo = self.undo.createUndoAction(self)
        undo.setShortcut(QKeySequence.Undo)
        undo.setIcon(icon("undo", theme.tokens["text"]))
        redo = self.undo.createRedoAction(self)
        redo.setShortcuts([QKeySequence("Ctrl+Shift+Z"), QKeySequence.Redo])
        redo.setIcon(icon("redo", theme.tokens["text"]))
        self.actions_by_name["undo"] = undo
        self.actions_by_name["redo"] = redo
        a("duplicate", self.duplicate_selection, "Ctrl+D", "copy")
        a("delete", self.delete_selection, [QKeySequence.Delete, QKeySequence(Qt.Key_Backspace)], "trash")
        a("select_all", lambda: self.scene.set_selection([lay.id for lay in self.scene.layers]),
          QKeySequence.SelectAll)
        a("deselect", lambda: self.scene.set_selection([]), "Esc")
        for type_name in LAYER_TYPES:
            a(f"add_{type_name}", lambda _=False, t=type_name: self.add_layer(t), None, LAYER_ICONS[type_name])
        a("raise", lambda: self.canvas._restack(1), "Ctrl+]", "chevron-up")
        a("lower", lambda: self.canvas._restack(-1), "Ctrl+[", "chevron-down")
        a("save_preset", self.save_preset, None, "preset")
        a("grid", self._toggle_grid, None, "grid", checkable=True)
        a("snap", self._toggle_snap, None, "magnet", checkable=True)
        a("rulers", self._toggle_rulers, None, None, checkable=True)
        a("fit", lambda: self.canvas.fit_view(), "Ctrl+0", "fit")
        a("zoom_in", lambda: self.canvas.zoom_by(1.25), "Ctrl++")
        a("zoom_out", lambda: self.canvas.zoom_by(0.8), "Ctrl+-")
        a("play", self.toggle_play, "Space", "play")
        a("rewind", self.rewind, "Home", "skip-back")
        a("settings", self.open_settings, QKeySequence.Preferences, "settings")
        a("guide", lambda: QDesktopServices.openUrl(QUrl(DOCS_URL)), QKeySequence.HelpContents, "info")
        a("shortcuts", self.show_shortcuts)
        a("about", self.show_about)
        self.actions_by_name["play"].setShortcutContext(Qt.ApplicationShortcut)
        self.actions_by_name["settings"].setMenuRole(QAction.PreferencesRole)
        self.actions_by_name["about"].setMenuRole(QAction.AboutRole)
        self.actions_by_name["quit"].setMenuRole(QAction.QuitRole)
        self.grid_btn.setDefaultAction(self.actions_by_name["grid"])
        self.snap_btn.setDefaultAction(self.actions_by_name["snap"])
        self.theme_group = QActionGroup(self)
        for name in THEME_NAMES:
            act = QAction(self, checkable=True)
            act.setData(name)
            act.triggered.connect(lambda _=False, n=name: self.set_theme(n))
            self.theme_group.addAction(act)
        self.lang_group = QActionGroup(self)
        for code, title in (("pl", "Polski"), ("en", "English")):
            act = QAction(title, self, checkable=True)
            act.setData(code)
            act.triggered.connect(lambda _=False, c=code: self.set_language(c))
            self.lang_group.addAction(act)

    def _build_menus(self) -> None:
        mb = self.menuBar()
        n = self.actions_by_name
        self.menu_file = mb.addMenu("")
        for key in ("new", "open"):
            self.menu_file.addAction(n[key])
        self.menu_recent = self.menu_file.addMenu("")
        self.menu_file.addSeparator()
        for key in ("save", "save_as"):
            self.menu_file.addAction(n[key])
        self.menu_file.addSeparator()
        for key in ("import_audio", "import_preset", "demo"):
            self.menu_file.addAction(n[key])
        self.menu_file.addSeparator()
        for key in ("export_mp4", "export_png", "export_preset"):
            self.menu_file.addAction(n[key])
        self.menu_file.addSeparator()
        self.menu_file.addAction(n["settings"])
        self.menu_file.addAction(n["quit"])

        self.menu_edit = mb.addMenu("")
        for key in ("undo", "redo"):
            self.menu_edit.addAction(n[key])
        self.menu_edit.addSeparator()
        for key in ("duplicate", "delete"):
            self.menu_edit.addAction(n[key])
        self.menu_edit.addSeparator()
        for key in ("select_all", "deselect"):
            self.menu_edit.addAction(n[key])

        self.menu_layer = mb.addMenu("")
        for type_name in LAYER_TYPES:
            self.menu_layer.addAction(n[f"add_{type_name}"])
        self.menu_layer.addSeparator()
        for key in ("raise", "lower", "save_preset"):
            self.menu_layer.addAction(n[key])

        self.menu_view = mb.addMenu("")
        for key in ("grid", "snap", "rulers"):
            self.menu_view.addAction(n[key])
        self.menu_view.addSeparator()
        for key in ("fit", "zoom_in", "zoom_out"):
            self.menu_view.addAction(n[key])
        self.menu_view.addSeparator()
        self.menu_theme = self.menu_view.addMenu("")
        self.menu_theme.addActions(self.theme_group.actions())
        self.menu_lang = self.menu_view.addMenu("")
        self.menu_lang.addActions(self.lang_group.actions())

        self.menu_play = mb.addMenu("")
        for key in ("play", "rewind"):
            self.menu_play.addAction(n[key])

        self.menu_help = mb.addMenu("")
        for key in ("guide", "shortcuts", "about"):
            self.menu_help.addAction(n[key])

    def retranslate(self) -> None:
        texts = {
            "new": self.tr("New project"), "open": self.tr("Open project…"), "save": self.tr("Save"),
            "save_as": self.tr("Save as…"), "import_audio": self.tr("Import audio…"),
            "import_preset": self.tr("Import layer preset…"), "export_preset": self.tr("Export layer preset…"),
            "export_mp4": self.tr("Export video (MP4)…"), "export_png": self.tr("Export snapshot (PNG)…"),
            "demo": self.tr("Load demo project"), "quit": self.tr("Quit"),
            "duplicate": self.tr("Duplicate"), "delete": self.tr("Delete"), "select_all": self.tr("Select all"),
            "deselect": self.tr("Deselect"), "raise": self.tr("Bring forward"), "lower": self.tr("Send backward"),
            "save_preset": self.tr("Save layer as preset…"), "grid": self.tr("Show grid"), "snap": self.tr("Snap to grid"),
            "rulers": self.tr("Show rulers"), "fit": self.tr("Fit canvas"), "zoom_in": self.tr("Zoom in"),
            "zoom_out": self.tr("Zoom out"), "play": self.tr("Play / pause"), "rewind": self.tr("Go to start"),
            "settings": self.tr("Settings…"), "guide": self.tr("User guide"), "shortcuts": self.tr("Keyboard shortcuts"),
            "about": self.tr("About OsciViz"),
        }
        for key, text in texts.items():
            self.actions_by_name[key].setText(text)
        self.actions_by_name["undo"].setText(self.tr("Undo"))
        self.actions_by_name["redo"].setText(self.tr("Redo"))
        for type_name, cls in LAYER_TYPES.items():
            name = QCoreApplication.translate("LayerTypes", cls.DISPLAY_NAME)
            self.actions_by_name[f"add_{type_name}"].setText(self.tr("Add %1").replace("%1", name))
            self.add_buttons[type_name].setText(name)
            self.add_buttons[type_name].setToolTip(self.tr("Add %1 layer").replace("%1", name.lower()))
        theme_titles = {"dark": self.tr("Dark"), "light": self.tr("Light"), "high_contrast": self.tr("High contrast")}
        for act in self.theme_group.actions():
            act.setText(theme_titles[act.data()])
        self.menu_file.setTitle(self.tr("File"))
        self.menu_recent.setTitle(self.tr("Open recent"))
        self.menu_edit.setTitle(self.tr("Edit"))
        self.menu_layer.setTitle(self.tr("Layer"))
        self.menu_view.setTitle(self.tr("View"))
        self.menu_theme.setTitle(self.tr("Theme"))
        self.menu_lang.setTitle(self.tr("Language"))
        self.menu_play.setTitle(self.tr("Playback"))
        self.menu_help.setTitle(self.tr("Help"))
        self.undo_btn.setToolTip(self.tr("Undo (⌘Z)"))
        self.redo_btn.setToolTip(self.tr("Redo (⇧⌘Z)"))
        self.grid_btn.setToolTip(self.tr("Grid (G)"))
        self.snap_btn.setToolTip(self.tr("Snap to grid"))
        self.fit_btn.setToolTip(self.tr("Fit canvas (⌘0)"))
        self.png_btn.setToolTip(self.tr("Snapshot PNG (⇧⌘S)"))
        self.settings_btn.setToolTip(self.tr("Settings"))
        self.export_btn.setText(self.tr("Export"))
        self.export_btn.setToolTip(self.tr("Export video (⌘E)"))
        self.statusBar().showMessage(self.tr("Ready"), 1500)
        self.source_panel.retranslate()
        self.layer_panel.retranslate()
        self.timeline.retranslate()
        self.inspector.retranslate()
        self._rebuild_recent()
        self._update_title()

    # ======================================================================
    # Ustawienia, motyw, język
    # ======================================================================
    def _restore_settings(self) -> None:
        s = self.settings
        geometry = s.value("window/geometry")
        if geometry is not None:
            self.restoreGeometry(geometry)
        else:
            self.resize(1480, 900)
        self.canvas.show_grid = s.value("view/grid", True, type=bool)
        self.canvas.snap = s.value("view/snap", False, type=bool)
        self.canvas.show_rulers = s.value("view/rulers", True, type=bool)
        self._sync_view_actions()
        for act in self.theme_group.actions():
            act.setChecked(act.data() == theme.name)
        for act in self.lang_group.actions():
            act.setChecked(act.data() == self.language)

    def _sync_view_actions(self) -> None:
        n = self.actions_by_name
        n["grid"].setChecked(self.canvas.show_grid)
        n["snap"].setChecked(self.canvas.snap)
        n["rulers"].setChecked(self.canvas.show_rulers)
        self.settings.setValue("view/grid", self.canvas.show_grid)
        self.settings.setValue("view/snap", self.canvas.snap)
        self.settings.setValue("view/rulers", self.canvas.show_rulers)

    def _toggle_grid(self) -> None:
        self.canvas.show_grid = self.actions_by_name["grid"].isChecked()
        self.canvas.update()
        self._sync_view_actions()
        self.inspector.refresh()

    def _toggle_snap(self) -> None:
        self.canvas.snap = self.actions_by_name["snap"].isChecked()
        self._sync_view_actions()
        self.inspector.refresh()

    def _toggle_rulers(self) -> None:
        self.canvas.show_rulers = self.actions_by_name["rulers"].isChecked()
        self.canvas.update()
        self._sync_view_actions()
        self.inspector.refresh()

    def set_theme(self, name: str) -> None:
        theme.apply(self.app, name)
        self.settings.setValue("ui/theme", theme.name)
        for act in self.theme_group.actions():
            act.setChecked(act.data() == theme.name)
        refresh_icons(self)
        self.logo.setPixmap(icon("logo", theme.tokens["accent"]).pixmap(26, 26))
        self.timeline.refresh_theme()
        self.layer_panel.rebuild()
        self.inspector.retranslate()
        self.source_panel.retranslate()
        self.toast.deleteLater()
        self.toast = Toast(self.canvas_frame)
        self.canvas.update()

    def set_language(self, code: str) -> None:
        self.language = code
        self.settings.setValue("ui/language", code)
        install_translator(self.app, code, self)
        for act in self.lang_group.actions():
            act.setChecked(act.data() == code)
        self.retranslate()

    def open_settings(self) -> None:
        dlg = SettingsDialog(theme.name, self.language, self)
        dlg.themeChanged.connect(self.set_theme)
        dlg.languageChanged.connect(self.set_language)
        dlg.exec()

    # ======================================================================
    # Zegar klatek
    # ======================================================================
    def _tick(self) -> None:
        now = time.perf_counter()
        dt = min(max(now - self._last_tick, 1 / 240), 0.1)
        self._last_tick = now
        sr = 48000
        playing = False
        if self.live is not None:
            sr = self.live.sample_rate
            n = window_length(sr, self.analyzer.fft_size)
            samples = self.live.get_window(n)
            t = now - self.live_t0
            playing = True
            if self.recorder is not None:
                text = self.tr("Recording  %1").replace("%1", format_time(self.recorder.elapsed))
                self.timeline.set_live(True, text, recording=True)
        elif self.source is not None:
            sr = self.source.sample_rate
            n = window_length(sr, self.analyzer.fft_size)
            pos = self.player.position
            samples = self.source.window_at(pos, n)
            t = pos / sr
            playing = self.player.is_playing
            self.timeline.set_time(t)
            if not playing and self.timeline._playing:
                self.timeline.set_playing(False)
        else:
            n = window_length(sr, self.analyzer.fft_size)
            samples = np.zeros((n, 2), np.float32)
            t = 0.0
        frame = build_frame(samples, sr, self.analyzer, t, dt, playing)
        self.sim.update(self.scene, frame, self.default_image)
        self.canvas.set_frame(frame)
        self._fps_frames += 1
        if now - self._fps_t0 >= 0.5:
            fps = self._fps_frames / (now - self._fps_t0)
            self.status_fps.setText(f"{fps:.0f} fps")
            self._fps_frames = 0
            self._fps_t0 = now

    # ======================================================================
    # Odtwarzanie i źródła
    # ======================================================================
    def toggle_play(self) -> None:
        if self.live is not None or self.source is None:
            if self.source is None and self.live is None:
                self.toast.show_message(self.tr("Open an audio file first (⌘I)"))
            return
        self.player.toggle()
        self.timeline.set_playing(self.player.is_playing)

    def rewind(self) -> None:
        self.seek(0.0)

    def seek(self, seconds: float) -> None:
        self.player.seek(seconds)
        self.sim.reset()
        self.analyzer.reset()

    def open_audio_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, self.tr("Import audio"), self._last_dir(),
                                              self.tr(AUDIO_FILTER))
        if path:
            self._remember_dir(path)
            if self.load_audio(path):
                self.scene.audio_path = path
                self._extra_dirty = True
                self._update_title()

    def load_audio(self, path: str) -> bool:
        try:
            source = FileSource(path)
        except Exception as exc:
            QMessageBox.warning(self, self.tr("Cannot open audio"),
                                self.tr("The file could not be read:\n%1").replace("%1", str(exc)))
            return False
        self.stop_live()
        self.source = source
        self.player.set_source(source)
        self.timeline.set_source(source)
        self.timeline.set_live(False)
        self.timeline.set_playing(False)
        self.source_panel.set_mode("file")
        self.source_panel.set_file_info((Path(path).name, source.duration, source.sample_rate))
        self.sim.reset()
        return True

    def _on_source_mode(self, mode: str) -> None:
        if mode == "file":
            self.stop_live()
            self.timeline.set_live(False)
        else:
            self.player.pause()
            self.timeline.set_playing(False)
            self.timeline.set_live(True, self.tr("Live input — choose a device and press Start"))

    def start_live(self, device) -> None:
        self.player.pause()
        self.timeline.set_playing(False)
        try:
            self.live = LiveSource(device)
        except Exception as exc:
            self.live = None
            self.source_panel.set_listening(False)
            QMessageBox.warning(
                self, self.tr("Cannot start live input"),
                self.tr("Opening the input device failed:\n%1\n\nOn macOS, allow microphone access for "
                        "OsciViz in System Settings → Privacy & Security → Microphone.")
                .replace("%1", str(exc)))
            return
        self.live_t0 = time.perf_counter()
        self.sim.reset()
        self.timeline.set_live(True, self.tr("Listening  ·  %1 Hz").replace("%1", str(self.live.sample_rate)))

    def stop_live(self) -> None:
        if self.recorder is not None:
            self.toggle_record(False)
        if self.live is not None:
            self.live.close()
            self.live = None
        self.source_panel.set_listening(False)
        if self.source_panel.mode.value() == "live":
            self.timeline.set_live(True, self.tr("Live input — choose a device and press Start"))

    def toggle_record(self, on: bool) -> None:
        if on and self.live is not None and self.recorder is None:
            folder = Path(QStandardPaths.writableLocation(QStandardPaths.MusicLocation)) / "OsciViz"
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / f"session-{datetime.now():%Y%m%d-%H%M%S}.wav"
            self.recorder = Recorder(path, self.live.sample_rate)
            self.recorder.start()
            self.live.recorder = self.recorder
            return
        if not on and self.recorder is not None:
            if self.live is not None:
                self.live.recorder = None
            path = self.recorder.stop()
            seconds = self.recorder.elapsed
            self.recorder = None
            self.source_panel.rec_btn.blockSignals(True)
            self.source_panel.rec_btn.setChecked(False)
            self.source_panel.rec_btn.blockSignals(False)
            if self.live is not None:
                self.timeline.set_live(True, self.tr("Listening  ·  %1 Hz").replace("%1", str(self.live.sample_rate)))
            answer = QMessageBox.question(
                self, self.tr("Recording saved"),
                self.tr("Saved %1 of audio to:\n%2\n\nUse this recording as the project audio "
                        "(for MP4 export)?").replace("%1", format_time(seconds)).replace("%2", path))
            if answer == QMessageBox.Yes:
                self.stop_live()
                if self.load_audio(path):
                    self.scene.audio_path = path
                    self._extra_dirty = True
                    self._update_title()

    # ======================================================================
    # Warstwy
    # ======================================================================
    def _unique_name(self, base: str) -> str:
        names = {lay.name for lay in self.scene.layers}
        if base not in names:
            return base
        i = 2
        while f"{base} {i}" in names:
            i += 1
        return f"{base} {i}"

    def add_layer(self, type_name: str) -> Layer:
        layer = create_layer(type_name)
        layer.name = self._unique_name(QCoreApplication.translate("LayerTypes", layer.DISPLAY_NAME))
        cx, cy = self.canvas.center
        hx, hy = self.scene.extent
        layer.transform.x = float(np.clip(cx, -hx, hx))
        layer.transform.y = float(np.clip(cy, -hy, hy))
        self.undo.push(cmd.AddLayersCommand(self.scene, [layer]))
        self.canvas.setFocus()
        return layer

    def duplicate_selection(self) -> None:
        sel = self.scene.selected_layers()
        if not sel:
            return
        clones = []
        for layer in sel:
            clone = layer.clone()
            clone.name = self._unique_name(layer.name)
            clone.transform.x += 0.05
            clone.transform.y -= 0.05
            clones.append(clone)
        index = max(self.scene.index_of(lay.id) for lay in sel) + 1
        self.undo.push(cmd.AddLayersCommand(self.scene, clones, index, self.tr("Duplicate")))

    def delete_selection(self) -> None:
        if self.scene.selection:
            self.undo.push(cmd.RemoveLayersCommand(self.scene, list(self.scene.selection)))

    def _update_actions(self) -> None:
        n = self.actions_by_name
        has = bool(self.scene.selection)
        single = len(self.scene.selection) == 1
        for key in ("duplicate", "delete", "raise", "lower"):
            n[key].setEnabled(has)
        n["save_preset"].setEnabled(single)
        n["export_preset"].setEnabled(single)

    # ======================================================================
    # Presety
    # ======================================================================
    def apply_preset(self, key: str) -> None:
        data = self.presets.get(key)
        sel = self.scene.selected_layers()
        if not data or len(sel) != 1 or sel[0].TYPE != data["type"]:
            return
        self.undo.push(cmd.ApplyPresetCommand(self.scene, sel[0].id, data.get("params", {})))
        self.toast.show_message(self.tr("Preset “%1” applied").replace("%1", data["name"]))

    def save_preset(self) -> None:
        sel = self.scene.selected_layers()
        if len(sel) != 1:
            return
        name, ok = QInputDialog.getText(self, self.tr("Save preset"), self.tr("Preset name:"),
                                        text=sel[0].name)
        if ok and name.strip():
            try:
                self.presets.save_user(sel[0], name.strip())
            except (PresetError, OSError) as exc:
                QMessageBox.warning(self, self.tr("Save preset"), str(exc))
                return
            self._presets_changed()
            self.toast.show_message(self.tr("Preset saved"))

    def import_preset(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, self.tr("Import layer preset"), self._last_dir(),
                                              self.tr("Layer preset (*.json)"))
        if not path:
            return
        try:
            key = self.presets.import_file(path)
        except (PresetError, OSError) as exc:
            QMessageBox.warning(self, self.tr("Import preset"), str(exc))
            return
        self._presets_changed()
        sel = self.scene.selected_layers()
        if len(sel) == 1 and key.startswith(sel[0].TYPE + ":"):
            self.apply_preset(key)
        else:
            self.toast.show_message(self.tr("Preset imported"))

    def export_preset(self) -> None:
        sel = self.scene.selected_layers()
        if len(sel) != 1:
            return
        default = str(Path(self._last_dir()) / f"{sel[0].name}.json")
        path, _ = QFileDialog.getSaveFileName(self, self.tr("Export layer preset"), default,
                                              self.tr("Layer preset (*.json)"))
        if path:
            write_preset(sel[0], path)
            self.toast.show_message(self.tr("Preset exported"))

    def _presets_changed(self) -> None:
        self.canvas.preset_names = self.presets.all()
        self.inspector.retranslate()

    # ======================================================================
    # Projekt
    # ======================================================================
    def is_dirty(self) -> bool:
        return not self.undo.isClean() or self._extra_dirty

    def _on_undo_index(self, _index: int) -> None:
        self._update_title()

    def _update_title(self) -> None:
        name = Path(self.project_path).stem if self.project_path else self.tr("Untitled")
        dirty = self.is_dirty()
        self.setWindowTitle(f"{name}[*] — {APP_NAME}")
        self.setWindowModified(dirty)
        self.project_label.setText(f"/  {name}{'  •' if dirty else ''}")

    def _confirm_discard(self) -> bool:
        if not self.is_dirty() or not self.scene.layers:
            return True
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Question)
        box.setWindowTitle(APP_NAME)
        box.setText(self.tr("Save changes to this project?"))
        box.setInformativeText(self.tr("Your changes will be lost if you don't save them."))
        box.setStandardButtons(QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        box.setDefaultButton(QMessageBox.Save)
        answer = box.exec()
        if answer == QMessageBox.Save:
            return self.save_project()
        return answer == QMessageBox.Discard

    def _reset_project(self) -> None:
        self.stop_live()
        self.player.set_source(None)
        self.source = None
        self.timeline.set_source(None)
        self.timeline.set_playing(False)
        self.source_panel.set_file_info(None)
        self.scene.clear()
        self.undo.clear()
        self.sim.reset()
        self.project_path = None
        self._extra_dirty = False

    def new_project(self) -> None:
        if not self._confirm_discard():
            return
        self._reset_project()
        self.canvas.fit_view()
        self._update_title()

    def open_project_dialog(self) -> None:
        if not self._confirm_discard():
            return
        path, _ = QFileDialog.getOpenFileName(self, self.tr("Open project"), self._last_dir(),
                                              self.tr("OsciViz project (*.osv)"))
        if path:
            self.open_project(path)

    def open_project(self, path: str) -> bool:
        self._reset_project()
        extract = self.data_dir / "open" / Path(path).stem
        try:
            load_project(path, self.scene, extract)
        except ProjectError as exc:
            QMessageBox.critical(self, self.tr("Cannot open project"), str(exc))
            self._update_title()
            return False
        if self.scene.audio_path:
            self.load_audio(self.scene.audio_path)
        self.project_path = path
        self._remember_dir(path)
        self._add_recent(path)
        self.undo.clear()
        self.canvas.fit_view()
        self._update_title()
        self.toast.show_message(self.tr("Opened %1").replace("%1", Path(path).name))
        return True

    def save_project(self) -> bool:
        if not self.project_path:
            return self.save_project_as()
        try:
            save_project(self.scene, self.project_path)
        except ProjectError as exc:
            QMessageBox.critical(self, self.tr("Cannot save project"), str(exc))
            return False
        self.undo.setClean()
        self._extra_dirty = False
        self._add_recent(self.project_path)
        self._update_title()
        self.toast.show_message(self.tr("Saved"))
        return True

    def save_project_as(self) -> bool:
        default = self.project_path or str(Path(self._last_dir()) / "project.osv")
        path, _ = QFileDialog.getSaveFileName(self, self.tr("Save project"), default,
                                              self.tr("OsciViz project (*.osv)"))
        if not path:
            return False
        if not path.lower().endswith(".osv"):
            path += ".osv"
        self.project_path = path
        self._remember_dir(path)
        return self.save_project()

    def load_demo(self) -> None:
        """Projekt demonstracyjny: syntetyczny utwór i po jednej warstwie każdego typu."""
        if not self._confirm_discard():
            return
        self._reset_project()
        demo_wav = self.data_dir / "demo-track.wav"
        if not demo_wav.exists():
            write_demo_wav(str(demo_wav))
        build_demo_scene(self.scene, self.presets)
        self.scene.audio_path = str(demo_wav)
        self.load_audio(str(demo_wav))
        self.undo.clear()
        self.canvas.fit_view()
        self._update_title()

    def _add_recent(self, path: str) -> None:
        recent = [p for p in (self.settings.value("files/recent", [], type=list) or []) if p != path]
        recent.insert(0, path)
        self.settings.setValue("files/recent", recent[:8])
        self._rebuild_recent()

    def _rebuild_recent(self) -> None:
        self.menu_recent.clear()
        recent = self.settings.value("files/recent", [], type=list) or []
        for path in recent:
            self.menu_recent.addAction(Path(path).name, lambda p=path: self._open_recent(p))
        if not recent:
            act = self.menu_recent.addAction(self.tr("No recent projects"))
            act.setEnabled(False)

    def _open_recent(self, path: str) -> None:
        if self._confirm_discard():
            self.open_project(path)

    def _last_dir(self) -> str:
        return self.settings.value("files/last_dir",
                                   QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation))

    def _remember_dir(self, path: str) -> None:
        self.settings.setValue("files/last_dir", str(Path(path).parent))

    # ======================================================================
    # Eksport
    # ======================================================================
    def export_png(self) -> None:
        if self.canvas.ctx is None:
            return
        name = Path(self.project_path).stem if self.project_path else "osciviz"
        default = str(Path(self._last_dir()) / f"{name}-{datetime.now():%H%M%S}.png")
        path, _ = QFileDialog.getSaveFileName(self, self.tr("Export snapshot"), default,
                                              self.tr("PNG image (*.png)"))
        if not path:
            return
        size = resolution_for(self.scene.aspect, 2160)
        self.canvas.makeCurrent()
        try:
            offscreen = OffscreenRenderer(size, ctx=self.canvas.ctx)
            image = offscreen.render(self.scene, self.canvas.frame, self.sim)
            offscreen.release()
        finally:
            self.canvas.doneCurrent()
        save_png(image, path)
        self._remember_dir(path)
        self.toast.show_message(self.tr("Snapshot saved · %1 × %2").replace("%1", str(size[0]))
                                .replace("%2", str(size[1])))

    def export_video(self) -> None:
        if self.recorder is not None:
            QMessageBox.information(self, self.tr("Export video"),
                                    self.tr("Stop the recording first, then export it as a file."))
            return
        source = self.source
        if source is None:
            seconds, ok = QInputDialog.getDouble(
                self, self.tr("Export video"),
                self.tr("No audio is loaded. Export a silent video of length (seconds):"), 10.0, 1.0, 600.0, 1)
            if not ok:
                return
            source = FileSource(data=np.zeros((int(seconds * 48000), 2), np.float32), sample_rate=48000)
        self.player.pause()
        self.timeline.set_playing(False)
        name = Path(self.project_path).stem if self.project_path else "osciviz"
        default = str(Path(self._last_dir()) / f"{name}.mp4")
        dlg = ExportDialog(self.scene, source, default, self.default_image, self)
        dlg.exec()

    # ======================================================================
    # Pomoc
    # ======================================================================
    def show_shortcuts(self) -> None:
        rows = [
            ("Space", self.tr("Play / pause")), ("⌘Z / ⇧⌘Z", self.tr("Undo / redo")),
            ("⌘S · ⌘O · ⌘N", self.tr("Save · open · new")), ("⌘E", self.tr("Export MP4")),
            ("⇧⌘S", self.tr("Snapshot PNG")), ("⌘D", self.tr("Duplicate")), ("⌫", self.tr("Delete")),
            ("← ↑ → ↓", self.tr("Move (Shift: large step)")), ("R / ⇧R", self.tr("Rotate +5° / −5°")),
            ("+ / −", self.tr("Scale")), ("G", self.tr("Toggle grid")), ("Tab", self.tr("Next layer")),
            (self.tr("Scroll / pinch"), self.tr("Zoom view")),
            (self.tr("Space + drag / middle button"), self.tr("Pan view")),
            (self.tr("Shift + handle"), self.tr("Keep proportions")),
            (self.tr("Alt + handle"), self.tr("Scale from center")),
            (self.tr("⌘ + rotate handle"), self.tr("Snap to 15°")),
        ]
        html = "<table cellspacing='6'>" + "".join(
            f"<tr><td><b>{k}</b></td><td style='padding-left:18px'>{v}</td></tr>" for k, v in rows) + "</table>"
        QMessageBox.information(self, self.tr("Keyboard shortcuts"), html)

    def show_about(self) -> None:
        QMessageBox.about(
            self, self.tr("About OsciViz"),
            f"<h3>{APP_NAME} {__version__}</h3><p>"
            + self.tr("A software oscilloscope and audio visualizer. Build layered visuals "
                      "from waveforms, XY scopes, spectra and particle images, then export them to MP4.")
            + "</p><p>" + self.tr("Course project — Computer Graphics and GUI.") + "</p>")

    def _on_gl_error(self, message: str) -> None:
        QMessageBox.critical(self, self.tr("OpenGL error"),
                             self.tr("Could not initialise OpenGL 4.1:\n%1").replace("%1", message))

    def closeEvent(self, event) -> None:  # noqa: N802
        if not self._confirm_discard():
            event.ignore()
            return
        self.timer.stop()
        self.stop_live()
        self.player.close()
        self.settings.setValue("window/geometry", self.saveGeometry())
        event.accept()


def build_demo_scene(scene: Scene, presets: PresetManager) -> None:
    """Układ demonstracyjny: cząsteczki w tle, pierścień widma, fala i XY."""
    from osciviz.scene.layers import ParticleLayer, SpectrumLayer, WaveformLayer, XYLayer

    def preset(layer, key):
        data = presets.get(key)
        if data:
            layer.apply_params(data["params"])

    particles = ParticleLayer("Logo")
    preset(particles, "particles:Puls basu")
    particles.params["count"] = 26000
    particles.transform.y = 0.12
    particles.transform.sx = particles.transform.sy = 1.15
    ring = SpectrumLayer("Pierścień")
    preset(ring, "spectrum:Pierścień")
    ring.transform.sx = ring.transform.sy = 0.42
    ring.transform.x = -1.25
    ring.transform.y = 0.42
    ring.opacity = 0.9
    wave = WaveformLayer("Neon")
    preset(wave, "waveform:Neon")
    wave.transform.y = -0.62
    wave.transform.sx = 1.25
    wave.transform.sy = 0.8
    xy = XYLayer("Retro XY")
    preset(xy, "xy:Retro XY")
    xy.transform.x = 1.3
    xy.transform.y = 0.42
    xy.transform.sx = xy.transform.sy = 0.55
    for layer in (particles, ring, wave, xy):
        scene.layers.append(layer)
    scene.layers_changed.emit()
    scene.changed.emit()


def install_translator(app: QApplication, code: str, owner) -> None:
    old = getattr(owner, "translator", None)
    if old is not None:
        app.removeTranslator(old)
    translator = QTranslator(app)
    if translator.load(str(I18N_DIR / f"osciviz_{code}.qm")):
        app.installTranslator(translator)
        owner.translator = translator
    else:
        owner.translator = None
