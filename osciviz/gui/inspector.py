"""Inspektor właściwości: dynamiczny formularz parametrów zaznaczonej warstwy.

Formularz powstaje automatycznie ze schematu ``Layer.PARAMS``: rodzaj
parametru (``float``, ``color``, ``enum``…) wyznacza widżet. Każda zmiana
to komenda undo; kolejne ruchy jednego suwaka mają ten sam identyfikator
gestu, więc łączą się w jeden krok historii.

Bez zaznaczenia inspektor pokazuje ustawienia płótna (proporcje, tło, siatka).
"""

from __future__ import annotations

import itertools
from pathlib import Path

from PySide6.QtCore import QCoreApplication, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from osciviz.gui.icons import LAYER_ICONS, icon
from osciviz.gui.theme import theme
from osciviz.gui.widgets import ColorButton, Section, Segmented, SliderSpin, Toggle, label, tool_button
from osciviz.scene import commands as cmd
from osciviz.scene.scene import ASPECT_RATIOS


def tp(text: str) -> str:
    """Tłumaczenie etykiet parametrów (kontekst „Params”)."""
    return QCoreApplication.translate("Params", text)


class Inspector(QFrame):
    requestApplyPreset = Signal(str)
    requestSavePreset = Signal()

    def __init__(self, scene, undo_stack, presets, canvas, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Panel")
        self.scene = scene
        self.undo = undo_stack
        self.presets = presets
        self.canvas = canvas
        self._gestures = itertools.count(1)
        self._gesture = next(self._gestures)
        self._setters: list = []  # funkcje odświeżające wartości widżetów
        self._built_for = None
        self._updating = False

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        outer.addWidget(self.scroll)

        scene.selection_changed.connect(self.rebuild)
        scene.layers_changed.connect(self._on_structure)
        scene.changed.connect(self.refresh)
        scene.settings_changed.connect(self.refresh)
        canvas.optionsChanged.connect(self.refresh)
        self.rebuild()

    # --- pomocnicze -------------------------------------------------------------
    def _end_gesture(self) -> None:
        self._gesture = next(self._gestures)

    def _on_structure(self) -> None:
        # Zmiana typu/trybu/nazwy może zmienić formularz — przebuduj, ale tylko
        # jeśli zmienił się „kształt” zaznaczenia.
        key = self._form_key()
        if key != self._built_for:
            self.rebuild()
        else:
            self.refresh()

    def _form_key(self):
        sel = self.scene.selected_layers()
        return tuple((lay.id, lay.TYPE) for lay in sel)

    def refresh(self) -> None:
        if self._updating:
            return
        self._updating = True
        for setter in self._setters:
            setter()
        self._updating = False

    def retranslate(self) -> None:
        self._built_for = None
        self.rebuild()

    def rebuild(self) -> None:
        self._setters = []
        self._built_for = self._form_key()
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setSpacing(4)
        sel = self.scene.selected_layers()
        if not sel:
            self._build_canvas(layout)
        elif len(sel) == 1:
            self._build_layer(layout, sel[0])
        else:
            self._build_multi(layout, sel)
        layout.addStretch(1)
        old = self.scroll.takeWidget()
        self.scroll.setWidget(body)
        if old is not None:
            old.deleteLater()
        self.refresh()

    def _header(self, layout, icon_name: str, title: QWidget, subtitle: str) -> None:
        row = QHBoxLayout()
        row.setSpacing(10)
        badge = QLabel()
        badge.setFixedSize(34, 34)
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet(f"background: {theme.tokens['accent_soft']}; border-radius: 9px;")
        badge.setPixmap(icon(icon_name, theme.tokens["accent"]).pixmap(18, 18))
        row.addWidget(badge)
        col = QVBoxLayout()
        col.setSpacing(0)
        col.addWidget(title)
        col.addWidget(label(subtitle, "faint"))
        row.addLayout(col, 1)
        layout.addLayout(row)
        layout.addSpacing(6)

    # --- płótno -----------------------------------------------------------------
    def _build_canvas(self, layout) -> None:
        self._header(layout, "sliders", label(self.tr("Canvas"), "brand"),
                     self.tr("Nothing selected — project settings"))
        sec = Section(self.tr("Frame"))
        grid = QGridLayout()
        grid.setSpacing(6)
        aspect_buttons = {}
        for i, ratio in enumerate(ASPECT_RATIOS):
            b = QPushButton(ratio)
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setProperty("variant", "ghost")
            b.setStyleSheet(f"QPushButton {{ border: 1px solid {theme.tokens['border']}; padding: 6px; }}")
            b.clicked.connect(lambda _=False, r=ratio: self._set_scene("aspect", r))
            grid.addWidget(b, i // 3, i % 3)
            aspect_buttons[ratio] = b
        holder = QWidget()
        holder.setLayout(grid)
        sec.add_row(self.tr("Aspect ratio"), holder)

        def set_aspect():
            for r, b in aspect_buttons.items():
                b.setChecked(r == self.scene.aspect)
        self._setters.append(set_aspect)

        bg = ColorButton(self.scene.background)
        bg.colorChanged.connect(lambda c: self._set_scene("background", c))
        self._setters.append(lambda: bg.setColor(self.scene.background))
        sec.add_row(self.tr("Background"), bg)
        layout.addWidget(sec)

        sec = Section(self.tr("Grid & guides"))
        for option, title in (("show_grid", self.tr("Show grid (G)")), ("snap", self.tr("Snap to grid")),
                              ("show_rulers", self.tr("Rulers"))):
            toggle = Toggle()
            toggle.toggled.connect(lambda on, o=option: self.canvas.set_option(o, on))
            self._setters.append(lambda t=toggle, o=option: t.setChecked(getattr(self.canvas, o)))
            sec.add_row(title, _left(toggle))
        step = SliderSpin(0.05, 1.0, 0.05, 2)
        step.valueChanged.connect(lambda v: self.canvas.set_option("grid_step", max(0.01, v)))
        self._setters.append(lambda: step.setValue(self.canvas.grid_step))
        sec.add_row(self.tr("Grid step"), step)
        layout.addWidget(sec)

        sec = Section(self.tr("Export"))
        seed = QSpinBox()
        seed.setRange(0, 2_000_000_000)
        seed.setButtonSymbols(QSpinBox.NoButtons)
        seed.valueChanged.connect(lambda v: self._set_scene("seed", int(v)) if not self._updating else None)
        self._setters.append(lambda: seed.setValue(self.scene.seed))
        sec.add_row(self.tr("Random seed"), seed,
                    self.tr("Particles use this seed, so exports are reproducible"))
        layout.addWidget(sec)

        tip = label(self.tr("Tip: click a layer on the canvas to edit it. Drag on empty space to "
                            "select several, scroll to zoom, hold Space or the middle button to pan."),
                    "faint")
        tip.setWordWrap(True)
        layout.addSpacing(8)
        layout.addWidget(tip)

    def _set_scene(self, attr: str, value) -> None:
        if self._updating or getattr(self.scene, attr) == value:
            self.refresh()
            return
        self.undo.push(cmd.SetSceneSettingCommand(self.scene, attr, value))

    # --- wiele warstw -------------------------------------------------------
    def _build_multi(self, layout, layers) -> None:
        self._header(layout, "copy", label(self.tr("%1 layers").replace("%1", str(len(layers))), "brand"),
                     self.tr("Common properties"))
        sec = Section(self.tr("Layer"))
        self._add_common(sec, layers)
        layout.addWidget(sec)

    def _add_common(self, sec: Section, layers) -> None:
        ids = [lay.id for lay in layers]
        opacity = SliderSpin(0, 100, 1, 0, " %")
        opacity.valueChanged.connect(
            lambda v: None if self._updating else self.undo.push(
                cmd.SetLayerPropCommand(self.scene, ids, "opacity", v / 100.0, self._gesture)))
        opacity.gestureFinished.connect(self._end_gesture)
        self._setters.append(lambda: opacity.setValue(layers[0].opacity * 100))
        sec.add_row(self.tr("Opacity"), opacity)
        blend = Segmented([("normal", self.tr("Normal")), ("additive", self.tr("Additive"))])
        blend.changed.connect(lambda v: self.undo.push(cmd.SetLayerPropCommand(self.scene, ids, "blend_mode", v)))
        self._setters.append(lambda: blend.set_value(layers[0].blend_mode))
        sec.add_row(self.tr("Blending"), blend)

    # --- jedna warstwa -------------------------------------------------------
    def _build_layer(self, layout, layer) -> None:
        name = QLineEdit(layer.name)
        name.setObjectName("NameEdit")
        name.editingFinished.connect(lambda: self._rename(layer, name.text().strip()))
        self._setters.append(lambda: name.setText(layer.name) if not name.hasFocus() else None)
        self._header(layout, LAYER_ICONS[layer.TYPE], name,
                     QCoreApplication.translate("LayerTypes", layer.DISPLAY_NAME))

        # Presety.
        preset_row = QHBoxLayout()
        preset_row.setSpacing(6)
        combo = compact_combo()
        combo.addItem(self.tr("Presets…"), "")
        for key, title in self.presets.list_for(layer.TYPE):
            combo.addItem(icon("preset", theme.tokens["muted"]), title, key)
        combo.activated.connect(lambda i: self._apply_preset(combo, i))
        preset_row.addWidget(combo, 1)
        save = tool_button("save", self.tr("Save as preset…"), size=16)
        save.clicked.connect(self.requestSavePreset)
        preset_row.addWidget(save)
        layout.addLayout(preset_row)
        layout.addSpacing(4)

        sec = Section(self.tr("Layer"))
        self._add_common(sec, [layer])
        layout.addWidget(sec)
        layout.addWidget(self._transform_section(layer))

        groups: dict[str, Section] = {}
        for spec in layer.PARAMS:
            group = groups.get(spec.group)
            if group is None:
                group = Section(tp(spec.group))
                groups[spec.group] = group
                layout.addWidget(group)
            widget = self._param_widget(layer, spec)
            group.add_row(tp(spec.label), widget)

    def _rename(self, layer, text: str) -> None:
        if text and text != layer.name:
            self.undo.push(cmd.SetLayerPropCommand(self.scene, [layer.id], "name", text))

    def _apply_preset(self, combo: QComboBox, index: int) -> None:
        key = combo.itemData(index)
        combo.setCurrentIndex(0)
        if key:
            self.requestApplyPreset.emit(key)

    def _transform_section(self, layer) -> Section:
        sec = Section(self.tr("Transform"))
        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)
        fields = [("x", "X", -20, 20, 0.01), ("y", "Y", -20, 20, 0.01),
                  ("sx", self.tr("W"), -50, 50, 0.01), ("sy", self.tr("H"), -50, 50, 0.01),
                  ("rotation", self.tr("Angle"), -360, 360, 1.0)]
        for i, (attr, caption, lo, hi, step) in enumerate(fields):
            spin = QDoubleSpinBox()
            spin.setRange(lo, hi)
            spin.setSingleStep(step)
            spin.setDecimals(1 if attr == "rotation" else 3)
            spin.setButtonSymbols(QDoubleSpinBox.NoButtons)
            spin.setKeyboardTracking(False)
            spin.setPrefix(f"{caption}  ")
            spin.setMinimumWidth(60)
            spin.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
            if attr == "rotation":
                spin.setSuffix("°")
            spin.valueChanged.connect(lambda v, a=attr: self._set_transform(layer, a, v))
            self._setters.append(lambda s=spin, a=attr: s.setValue(getattr(layer.transform, a)))
            grid.addWidget(spin, i // 2, i % 2)
        reset = QPushButton(icon("reset", theme.tokens["text"]), self.tr("Reset"))
        reset.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        reset.setMinimumWidth(60)
        reset.setCursor(Qt.PointingHandCursor)
        reset.clicked.connect(lambda: self.canvas.reset_transform())
        grid.addWidget(reset, 2, 1)
        holder = QWidget()
        holder.setLayout(grid)
        sec.add_widget(holder)
        return sec

    def _set_transform(self, layer, attr: str, value: float) -> None:
        if self._updating or layer.locked:
            self.refresh()
            return
        t = layer.transform.copy()
        if abs(getattr(t, attr) - value) < 1e-9:
            return
        setattr(t, attr, value)
        self.undo.push(cmd.SetTransformsCommand(self.scene, {layer.id: t}))

    def _param_widget(self, layer, spec) -> QWidget:
        key = spec.key

        def push(value, gesture=None):
            if self._updating:
                return
            self.undo.push(cmd.SetParamCommand(self.scene, layer.id, key, value, gesture))

        if spec.kind in ("float", "int"):
            w = SliderSpin(spec.minimum, spec.maximum, spec.step,
                           0 if spec.kind == "int" else None, spec.suffix)
            w.valueChanged.connect(lambda v: push(v, self._gesture))
            w.gestureFinished.connect(self._end_gesture)
            self._setters.append(lambda: w.setValue(layer.params[key]))
            return w
        if spec.kind == "bool":
            w = Toggle()
            w.toggled.connect(lambda v: push(v))
            self._setters.append(lambda: w.setChecked(bool(layer.params[key])))
            return _left(w)
        if spec.kind == "color":
            w = ColorButton(layer.params[key])
            w.colorChanged.connect(lambda c: push(c))
            self._setters.append(lambda: w.setColor(layer.params[key]))
            return w
        if spec.kind == "enum":
            labels = [tp(t) for _, t in spec.options]
            if len(spec.options) <= 3 and sum(len(t) for t in labels) <= 20:
                w = Segmented([(v, tp(t)) for v, t in spec.options])
                w.changed.connect(lambda v: push(v))
                self._setters.append(lambda: w.set_value(layer.params[key]))
                return w
            w = compact_combo()
            for v, t in spec.options:
                w.addItem(tp(t), v)
            w.activated.connect(lambda i: push(w.itemData(i)))
            self._setters.append(lambda: w.setCurrentIndex(max(0, w.findData(layer.params[key]))))
            return w
        if spec.kind == "image":
            holder = QWidget()
            row = QHBoxLayout(holder)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(6)
            btn = QPushButton(icon("image", theme.tokens["text"]), "")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet("text-align: left;")
            btn.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
            btn.setMinimumWidth(60)
            clear = tool_button("reset", self.tr("Use default image"), size=15)

            def choose():
                path, _ = QFileDialog.getOpenFileName(
                    self, self.tr("Choose image"), "",
                    self.tr("Images (*.png *.jpg *.jpeg *.bmp *.webp *.tif *.tiff)"))
                if path:
                    push(path)
            btn.clicked.connect(choose)
            clear.clicked.connect(lambda: push(""))

            def show():
                value = layer.params[key]
                btn.setText(Path(value).name if value else self.tr("Default (OSCIVIZ)"))
                btn.setToolTip(value)
            self._setters.append(show)
            row.addWidget(btn, 1)
            row.addWidget(clear)
            return holder
        return QLabel(str(layer.params.get(key)))


def compact_combo() -> QComboBox:
    """Lista rozwijana, która nie rozpycha panelu długimi pozycjami."""
    combo = QComboBox()
    combo.setSizeAdjustPolicy(QComboBox.AdjustToMinimumContentsLengthWithIcon)
    combo.setMinimumContentsLength(6)
    combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    return combo


def _left(widget: QWidget) -> QWidget:
    holder = QWidget()
    row = QHBoxLayout(holder)
    row.setContentsMargins(0, 0, 0, 0)
    row.addWidget(widget)
    row.addStretch(1)
    return holder
