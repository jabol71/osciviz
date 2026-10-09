"""Płótno podglądu: OpenGL (moderngl) + nakładka edytora rysowana QPainterem.

Odpowiada za:

- **kamerę podglądu** (przesuwanie, zoom względem kursora) — niezależną od
  kadru eksportu, który jest pokazany jako ramka z przyciemnionym otoczeniem,
- **przeliczanie współrzędnych** ekran ↔ scena (z uwzględnieniem Retiny:
  framebuffer ma rozmiar widżetu × ``devicePixelRatio()``),
- **interakcję**: zaznaczanie (klik, Shift+klik, prostokąt), przesuwanie,
  uchwyty skalowania i obrotu, skróty klawiszowe, menu kontekstowe,
- **nakładkę**: siatkę, osie, linijki, ramki zaznaczenia i uchwyty —
  tylko w podglądzie, nigdy w eksporcie.

Każda zmiana sceny idzie przez komendę undo (``scene/commands.py``).
"""

from __future__ import annotations

import itertools
import math

import moderngl
import numpy as np
from PySide6.QtCore import QEvent, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QFont, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from PySide6.QtWidgets import QMenu

from osciviz.core.frame import FrameContext, silent_frame
from osciviz.gui.icons import icon
from osciviz.gui.theme import theme
from osciviz.render.renderer import Renderer, ortho_view
from osciviz.scene import commands as cmd
from osciviz.scene.transform import Transform, apply_point, corners, hit_test

HANDLE_PX = 8  # bok uchwytu w pikselach ekranu
HANDLE_HIT_PX = 9  # promień trafienia uchwytu
ROTATE_OFFSET_PX = 26  # odległość uchwytu obrotu od górnej krawędzi
RULER_PX = 20
MIN_SCALE = 0.02

# Uchwyty skalowania: (znak X, znak Y) w lokalnym układzie warstwy.
HANDLE_SIGNS = [(-1, -1), (0, -1), (1, -1), (1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0)]


class CanvasWidget(QOpenGLWidget):
    cursorMoved = Signal(float, float)  # pozycja kursora w układzie sceny
    zoomChanged = Signal(float)
    requestPlayToggle = Signal()
    requestDuplicate = Signal()
    requestDelete = Signal()
    requestSavePreset = Signal()
    requestApplyPreset = Signal(str)  # nazwa presetu
    glError = Signal(str)
    optionsChanged = Signal()  # siatka / przyciąganie / linijki / krok siatki

    def __init__(self, scene, undo_stack, simulation, parent=None) -> None:
        super().__init__(parent)
        self.scene = scene
        self.undo = undo_stack
        self.sim = simulation
        self.frame: FrameContext = silent_frame()
        self.ctx: moderngl.Context | None = None
        self.renderer: Renderer | None = None
        self.default_image: str | None = None
        self.preset_names: list[tuple[str, str]] = []  # (klucz, nazwa) dla menu kontekstowego

        # Kamera: środek widoku w scenie i zoom = piksele (logiczne) na jednostkę sceny.
        self.center = [0.0, 0.0]
        self.zoom = 200.0
        self._auto_fit = True  # dopasuj kadr przy zmianie rozmiaru, dopóki użytkownik nie ruszy kamery

        self.show_grid = True
        self.snap = False
        self.grid_step = 0.25
        self.show_rulers = True

        # Stan interakcji.
        self._drag = None  # słownik opisujący trwający gest
        self._space = False
        self._space_used = False
        self._hover_handle = None
        self._gesture_ids = itertools.count(1)

        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)
        self.setMinimumSize(320, 220)
        self.grabGesture(Qt.PinchGesture)

        scene.changed.connect(self.update)
        scene.selection_changed.connect(self.update)
        scene.settings_changed.connect(self._on_settings_changed)

    # ======================================================================
    # Współrzędne
    # ======================================================================
    def scene_to_screen(self, x: float, y: float) -> QPointF:
        return QPointF(self.width() / 2 + (x - self.center[0]) * self.zoom,
                       self.height() / 2 - (y - self.center[1]) * self.zoom)

    def screen_to_scene(self, pos: QPointF) -> tuple[float, float]:
        return (self.center[0] + (pos.x() - self.width() / 2) / self.zoom,
                self.center[1] - (pos.y() - self.height() / 2) / self.zoom)

    def view_matrix(self) -> np.ndarray:
        """Scena → NDC. Połowa widoku w jednostkach sceny = (połowa piksela) / zoom."""
        return ortho_view(self.center, (self.width() / 2 / self.zoom, self.height() / 2 / self.zoom))

    def set_option(self, name: str, value) -> None:
        """Zmienia opcję widoku (``show_grid``, ``snap``, ``show_rulers``, ``grid_step``)
        i powiadamia menu oraz inspektor, żeby wszystkie przełączniki były zgodne."""
        if getattr(self, name) == value:
            return
        setattr(self, name, value)
        self.update()
        self.optionsChanged.emit()

    def fit_view(self) -> None:
        hx, hy = self.scene.extent
        margin = 56 + (RULER_PX if self.show_rulers else 0)
        w = max(50, self.width() - 2 * margin)
        h = max(50, self.height() - 2 * margin)
        self.zoom = min(w / (2 * hx), h / (2 * hy))
        self.center = [0.0, 0.0]
        self._auto_fit = True
        self._camera_changed()

    def zoom_by(self, factor: float, anchor: QPointF | None = None) -> None:
        """Zoom względem punktu ``anchor`` (punkt pod kursorem zostaje w miejscu)."""
        if anchor is None:
            anchor = QPointF(self.width() / 2, self.height() / 2)
        before = self.screen_to_scene(anchor)
        self.zoom = float(np.clip(self.zoom * factor, 10.0, 20000.0))
        after = self.screen_to_scene(anchor)
        self.center[0] += before[0] - after[0]
        self.center[1] += before[1] - after[1]
        self._auto_fit = False
        self._camera_changed()

    def _camera_changed(self) -> None:
        if self.renderer:
            self.renderer.reset_history()  # powidok XY jest w pikselach ekranu
        self.zoomChanged.emit(self.zoom)
        self.update()

    def _on_settings_changed(self) -> None:
        if self._auto_fit:
            self.fit_view()
        self.update()

    def set_frame(self, frame: FrameContext) -> None:
        self.frame = frame
        self.update()

    # ======================================================================
    # OpenGL
    # ======================================================================
    def initializeGL(self) -> None:  # noqa: N802
        try:
            self.ctx = moderngl.create_context()
            self.renderer = Renderer(self.ctx)
        except Exception as exc:  # brak obsługi OpenGL 4.1
            self.ctx = None
            self.renderer = None
            self.glError.emit(str(exc))

    def resizeGL(self, w: int, h: int) -> None:  # noqa: N802
        if self._auto_fit:
            self.fit_view()

    def paintGL(self) -> None:  # noqa: N802
        dpr = self.devicePixelRatioF()
        size = (max(1, round(self.width() * dpr)), max(1, round(self.height() * dpr)))
        bg = theme.color("canvas")
        painter = QPainter(self)
        if self.ctx is not None:
            # begin/endNativePainting: QPainter zapisuje i potem przywraca swój stan
            # OpenGL, więc rysowanie moderngl nie psuje nakładki (np. cache glifów).
            painter.beginNativePainting()
            fbo = self.ctx.detect_framebuffer(self.defaultFramebufferObject())
            self.renderer.render(
                self.scene, self.frame, self.sim, fbo, size, self.view_matrix(),
                px_per_unit=self.zoom * dpr,
                clear_target=(bg.redF(), bg.greenF(), bg.blueF(), 1.0),
            )
            self.ctx.disable(moderngl.BLEND | moderngl.PROGRAM_POINT_SIZE)
            painter.endNativePainting()
        else:
            painter.fillRect(self.rect(), bg)
        painter.setRenderHint(QPainter.Antialiasing)
        self._paint_overlay(painter)
        painter.end()

    # ======================================================================
    # Nakładka edytora
    # ======================================================================
    def _frame_rect(self) -> QRectF:
        hx, hy = self.scene.extent
        tl = self.scene_to_screen(-hx, hy)
        br = self.scene_to_screen(hx, -hy)
        return QRectF(tl, br)

    def _paint_overlay(self, p: QPainter) -> None:
        frame = self._frame_rect()
        # Przyciemnienie poza kadrem eksportu.
        outside = QPainterPath()
        outside.addRect(QRectF(self.rect()))
        inner = QPainterPath()
        inner.addRoundedRect(frame, 2, 2)
        p.fillPath(outside.subtracted(inner), theme.color("canvas_dim"))
        if self.show_grid:
            self._paint_grid(p, frame)
        # Ramka kadru.
        p.setPen(QPen(theme.color("border_strong"), 1))
        p.setBrush(Qt.NoBrush)
        p.drawRect(frame)
        self._paint_selection(p)
        if self._drag and self._drag["kind"] == "rubber":
            r = QRectF(self._drag["start"], self._drag["current"]).normalized()
            accent = theme.color("accent")
            fill = QColor(accent)
            fill.setAlpha(36)
            p.setPen(QPen(accent, 1, Qt.DashLine))
            p.setBrush(fill)
            p.drawRect(r)
        if self.show_rulers:
            self._paint_rulers(p)
        if self.ctx is None:
            p.setPen(theme.color("muted"))
            p.drawText(self.rect(), Qt.AlignCenter,
                       self.tr("OpenGL 4.1 is not available — preview disabled"))

    def _grid_lines(self, lo: float, hi: float, step: float) -> np.ndarray:
        start = math.ceil(lo / step) * step
        return np.arange(start, hi + step * 0.5, step)

    def _paint_grid(self, p: QPainter, frame: QRectF) -> None:
        hx, hy = self.scene.extent
        step = self.grid_step
        while step * self.zoom < 12:  # za gęsta siatka przy małym zoomie
            step *= 2
        p.save()
        p.setClipRect(frame)
        p.setPen(QPen(theme.color("grid"), 1))
        for x in self._grid_lines(-hx, hx, step):
            sx = self.scene_to_screen(x, 0).x()
            p.drawLine(QPointF(sx, frame.top()), QPointF(sx, frame.bottom()))
        for y in self._grid_lines(-hy, hy, step):
            sy = self.scene_to_screen(0, y).y()
            p.drawLine(QPointF(frame.left(), sy), QPointF(frame.right(), sy))
        # Osie przez środek układu.
        p.setPen(QPen(theme.color("grid_axis"), 1))
        origin = self.scene_to_screen(0, 0)
        p.drawLine(QPointF(origin.x(), frame.top()), QPointF(origin.x(), frame.bottom()))
        p.drawLine(QPointF(frame.left(), origin.y()), QPointF(frame.right(), origin.y()))
        p.restore()

    def _paint_rulers(self, p: QPainter) -> None:
        w, h = self.width(), self.height()
        p.save()
        p.setPen(Qt.NoPen)
        p.setBrush(theme.color("ruler"))
        p.drawRect(QRectF(0, 0, w, RULER_PX))
        p.drawRect(QRectF(0, 0, RULER_PX, h))
        font = QFont(self.font())
        font.setPointSizeF(max(7.5, font.pointSizeF() * 0.72))
        p.setFont(font)
        # Krok podziałki: „ładna” liczba (1, 2, 5 × 10^k) dająca ~80 px odstępu.
        raw = 80 / self.zoom
        mag = 10 ** math.floor(math.log10(raw))
        step = next(m * mag for m in (1, 2, 5, 10) if m * mag >= raw)
        decimals = max(0, -math.floor(math.log10(step) + 1e-9))
        x0, y1 = self.screen_to_scene(QPointF(RULER_PX, RULER_PX))
        x1, y0 = self.screen_to_scene(QPointF(w, h))
        text_color = theme.color("ruler_text")
        tick = QPen(theme.color("border_strong"), 1)
        for k in range(math.ceil(x0 / step * 5), math.floor(x1 / step * 5) + 1):
            x = k * step / 5
            sx = self.scene_to_screen(x, 0).x()
            major = k % 5 == 0
            p.setPen(tick)
            p.drawLine(QPointF(sx, RULER_PX - (8 if major else 4)), QPointF(sx, RULER_PX))
            if major:
                _path_text(p, QPointF(sx + 3, 11), f"{k * step / 5:.{decimals}f}", font, text_color)
        for k in range(math.ceil(y0 / step * 5), math.floor(y1 / step * 5) + 1):
            y = k * step / 5
            sy = self.scene_to_screen(0, y).y()
            major = k % 5 == 0
            p.setPen(tick)
            p.drawLine(QPointF(RULER_PX - (8 if major else 4), sy), QPointF(RULER_PX, sy))
            if major:
                p.save()
                p.translate(11, sy - 3)
                p.rotate(-90)
                _path_text(p, QPointF(0, 0), f"{y:.{decimals}f}", font, text_color)
                p.restore()
        p.setPen(QPen(theme.color("border"), 1))
        p.drawLine(QPointF(0, RULER_PX), QPointF(w, RULER_PX))
        p.drawLine(QPointF(RULER_PX, 0), QPointF(RULER_PX, h))
        p.setBrush(theme.color("ruler"))
        p.setPen(Qt.NoPen)
        p.drawRect(QRectF(0, 0, RULER_PX, RULER_PX))
        p.restore()

    def _layer_polygon(self, layer) -> QPolygonF:
        pts = corners(layer.transform, layer.half_extent())
        return QPolygonF([self.scene_to_screen(float(x), float(y)) for x, y in pts])

    def _paint_selection(self, p: QPainter) -> None:
        accent = theme.color("selection")
        selected = self.scene.selected_layers()
        for layer in selected:
            p.setPen(QPen(accent, 1.5))
            p.setBrush(Qt.NoBrush)
            p.drawPolygon(self._layer_polygon(layer))
        if len(selected) != 1 or selected[0].locked:
            for layer in selected:
                if layer.locked:
                    c = self._layer_polygon(layer).boundingRect().topRight()
                    p.drawPixmap(int(c.x()) + 4, int(c.y()) - 18,
                                 icon("lock", theme.tokens["selection"]).pixmap(14, 14))
            return
        layer = selected[0]
        handles = self._handle_positions(layer)
        # Linia do uchwytu obrotu.
        top = handles["edges"][5]
        rot = handles["rotate"]
        p.setPen(QPen(accent, 1.2))
        p.drawLine(top, rot)
        p.setBrush(QColor("#FFFFFF"))
        p.setPen(QPen(accent, 1.5))
        p.drawEllipse(rot, 5.5, 5.5)
        half = HANDLE_PX / 2
        for i, pt in enumerate(handles["edges"]):
            hovered = self._hover_handle == ("scale", i)
            p.setBrush(accent if hovered else QColor("#FFFFFF"))
            p.drawRoundedRect(QRectF(pt.x() - half, pt.y() - half, HANDLE_PX, HANDLE_PX), 2, 2)

    def _handle_positions(self, layer) -> dict:
        hx, hy = layer.half_extent()
        m = layer.transform.matrix()
        edges = []
        for sx, sy in HANDLE_SIGNS:
            x, y = apply_point(m, sx * hx, sy * hy)
            edges.append(self.scene_to_screen(x, y))
        # Uchwyt obrotu: nad środkiem „górnej” krawędzi (lokalne +Y), w kierunku od środka.
        cx, cy = apply_point(m, 0, 0)
        tx, ty = apply_point(m, 0, hy)
        c = self.scene_to_screen(cx, cy)
        t = self.scene_to_screen(tx, ty)
        d = t - c
        length = math.hypot(d.x(), d.y()) or 1.0
        rot = t + d * (ROTATE_OFFSET_PX / length)
        return {"edges": edges, "rotate": rot, "center": c}

    def _hit_handle(self, pos: QPointF):
        selected = self.scene.selected_layers()
        if len(selected) != 1 or selected[0].locked or not selected[0].visible:
            return None
        handles = self._handle_positions(selected[0])
        if _dist(pos, handles["rotate"]) <= HANDLE_HIT_PX:
            return ("rotate", -1)
        for i, pt in enumerate(handles["edges"]):
            if _dist(pos, pt) <= HANDLE_HIT_PX:
                return ("scale", i)
        return None

    def _hit_layer(self, pos: QPointF):
        x, y = self.screen_to_scene(pos)
        margin = 6 / self.zoom
        for layer in reversed(self.scene.layers):  # od najwyższej warstwy
            if not layer.visible:
                continue
            t = layer.transform
            local_margin = margin / max(min(abs(t.sx), abs(t.sy)), 1e-3)
            if hit_test(t, layer.half_extent(), x, y, local_margin):
                return layer
        return None

    # ======================================================================
    # Mysz
    # ======================================================================
    def mousePressEvent(self, event) -> None:  # noqa: N802
        self.setFocus()
        pos = event.position()
        if event.button() == Qt.MiddleButton or (event.button() == Qt.LeftButton and self._space):
            self._space_used = True
            self._drag = {"kind": "pan", "last": pos}
            self.setCursor(Qt.ClosedHandCursor)
            return
        if event.button() == Qt.RightButton:
            return  # menu kontekstowe w contextMenuEvent
        if event.button() != Qt.LeftButton:
            return
        handle = self._hit_handle(pos)
        if handle:
            layer = self.scene.selected_layers()[0]
            self._drag = {"kind": handle[0], "index": handle[1], "layer": layer.id,
                          "start_t": layer.transform.copy(), "press": self.screen_to_scene(pos),
                          "gesture": next(self._gesture_ids)}
            return
        shift = bool(event.modifiers() & Qt.ShiftModifier)
        layer = self._hit_layer(pos)
        if layer is None:
            self._drag = {"kind": "rubber", "start": pos, "current": pos, "additive": shift,
                          "base": list(self.scene.selection) if shift else []}
            if not shift:
                self.scene.set_selection([])
            return
        selection = list(self.scene.selection)
        if shift:
            if layer.id in selection:
                selection.remove(layer.id)
            else:
                selection.append(layer.id)
            self.scene.set_selection(selection)
            return
        if layer.id not in selection:
            self.scene.set_selection([layer.id])
        movable = [lay for lay in self.scene.selected_layers() if not lay.locked]
        if movable:
            self._drag = {"kind": "move", "press": self.screen_to_scene(pos),
                          "start": {lay.id: lay.transform.copy() for lay in movable},
                          "primary": layer.id, "gesture": next(self._gesture_ids), "moved": False}

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        pos = event.position()
        sx, sy = self.screen_to_scene(pos)
        self.cursorMoved.emit(sx, sy)
        drag = self._drag
        if drag is None:
            handle = self._hit_handle(pos)
            if handle != self._hover_handle:
                self._hover_handle = handle
                self.update()
            self._update_cursor(pos, handle)
            return
        kind = drag["kind"]
        if kind == "pan":
            delta = pos - drag["last"]
            drag["last"] = pos
            self.center[0] -= delta.x() / self.zoom
            self.center[1] += delta.y() / self.zoom
            self._auto_fit = False
            self._camera_changed()
        elif kind == "rubber":
            drag["current"] = pos
            self._update_rubber_selection()
            self.update()
        elif kind == "move":
            self._drag_move(sx, sy, event.modifiers())
        elif kind == "scale":
            self._drag_scale(sx, sy, event.modifiers())
        elif kind == "rotate":
            self._drag_rotate(sx, sy, event.modifiers())

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if self._drag and self._drag["kind"] == "pan":
            self.unsetCursor()
        self._drag = None
        self.update()

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton and self._hit_layer(event.position()) is None:
            self.fit_view()

    def _update_cursor(self, pos: QPointF, handle) -> None:
        if self._space:
            self.setCursor(Qt.OpenHandCursor)
        elif handle and handle[0] == "rotate":
            self.setCursor(Qt.CrossCursor)
        elif handle:
            # Kursor zgodny z kierunkiem uchwytu na ekranie (z uwzględnieniem obrotu).
            layer = self.scene.selected_layers()[0]
            hs = self._handle_positions(layer)
            d = hs["edges"][handle[1]] - hs["center"]
            angle = math.degrees(math.atan2(-d.y(), d.x())) % 180
            cursors = [Qt.SizeHorCursor, Qt.SizeBDiagCursor, Qt.SizeVerCursor, Qt.SizeFDiagCursor]
            self.setCursor(cursors[int(((angle + 22.5) % 180) // 45)])
        elif self._hit_layer(pos) is not None:
            self.setCursor(Qt.SizeAllCursor)
        else:
            self.unsetCursor()

    def _update_rubber_selection(self) -> None:
        r = QRectF(self._drag["start"], self._drag["current"]).normalized()
        ids = list(self._drag["base"])
        for layer in self.scene.layers:
            if not layer.visible:
                continue
            poly = self._layer_polygon(layer)
            if r.intersects(poly.boundingRect()) and layer.id not in ids:
                ids.append(layer.id)
        self.scene.set_selection(ids)

    def _snap_value(self, v: float) -> float:
        return round(v / self.grid_step) * self.grid_step

    def _drag_move(self, x: float, y: float, modifiers) -> None:
        drag = self._drag
        dx = x - drag["press"][0]
        dy = y - drag["press"][1]
        if modifiers & Qt.ShiftModifier:  # Shift: ruch tylko w jednej osi
            if abs(dx) > abs(dy):
                dy = 0.0
            else:
                dx = 0.0
        primary = drag["start"].get(drag["primary"]) or next(iter(drag["start"].values()))
        if self.snap:
            dx = self._snap_value(primary.x + dx) - primary.x
            dy = self._snap_value(primary.y + dy) - primary.y
        new = {}
        for layer_id, t in drag["start"].items():
            nt = t.copy()
            nt.x += dx
            nt.y += dy
            new[layer_id] = nt
        self.undo.push(cmd.SetTransformsCommand(self.scene, new, drag["gesture"], self.tr("Move")))

    def _drag_scale(self, x: float, y: float, modifiers) -> None:
        """Skalowanie uchwytem w lokalnym (obróconym) układzie warstwy.

        1. Kursor przenosimy do układu warstwy bez skali: ``R(−θ)·(p − pozycja)``.
        2. Domyślnie przeciwległy bok/narożnik („kotwica”) stoi w miejscu:
           nowy rozmiar = odległość kursora od kotwicy, nowy środek = środek
           odcinka kotwica–kursor (przeliczony z powrotem do sceny).
        3. Alt: skalowanie względem środka (rozmiar = 2 · |kursor|).
        4. Shift: zachowanie proporcji (ten sam współczynnik w obu osiach).
        """
        drag = self._drag
        layer = self.scene.layer(drag["layer"])
        if layer is None:
            return
        t0: Transform = drag["start_t"]
        hx, hy = layer.half_extent()
        sign_x, sign_y = HANDLE_SIGNS[drag["index"]]
        a = math.radians(t0.rotation)
        c, s = math.cos(a), math.sin(a)
        px, py = x - t0.x, y - t0.y
        lx, ly = c * px + s * py, -s * px + c * py  # R(−θ)·p
        w0, h0 = hx * t0.sx, hy * t0.sy  # połowy wymiarów przed gestem
        from_center = bool(modifiers & Qt.AltModifier)
        if from_center:
            anchor_x, anchor_y = 0.0, 0.0
            new_wx = abs(lx) if sign_x else w0
            new_hy = abs(ly) if sign_y else h0
        else:
            anchor_x, anchor_y = -sign_x * w0, -sign_y * h0
            new_wx = abs(lx - anchor_x) / 2 if sign_x else w0
            new_hy = abs(ly - anchor_y) / 2 if sign_y else h0
        rx = new_wx / max(w0, 1e-9)
        ry = new_hy / max(h0, 1e-9)
        if modifiers & Qt.ShiftModifier:
            r = max(rx, ry) if (sign_x and sign_y) else (rx if sign_x else ry)
            rx = ry = r
            new_wx, new_hy = w0 * r, h0 * r
        nt = t0.copy()
        nt.sx = math.copysign(max(abs(t0.sx * rx), MIN_SCALE), t0.sx)
        nt.sy = math.copysign(max(abs(t0.sy * ry), MIN_SCALE), t0.sy)
        if not from_center:
            # Nowy środek w lokalnym układzie: kotwica + połowa nowego rozmiaru w stronę uchwytu.
            cx_local = anchor_x + sign_x * new_wx if sign_x else 0.0
            cy_local = anchor_y + sign_y * new_hy if sign_y else 0.0
            nt.x = t0.x + c * cx_local - s * cy_local  # R(θ)·środek
            nt.y = t0.y + s * cx_local + c * cy_local
        self.undo.push(cmd.SetTransformsCommand(self.scene, {layer.id: nt}, drag["gesture"],
                                                self.tr("Scale")))

    def _drag_rotate(self, x: float, y: float, modifiers) -> None:
        drag = self._drag
        t0: Transform = drag["start_t"]
        a0 = math.atan2(drag["press"][1] - t0.y, drag["press"][0] - t0.x)
        a1 = math.atan2(y - t0.y, x - t0.x)
        angle = t0.rotation + math.degrees(a1 - a0)
        if modifiers & (Qt.ControlModifier | Qt.MetaModifier):
            angle = round(angle / 15.0) * 15.0
        angle = (angle + 180.0) % 360.0 - 180.0
        nt = t0.copy()
        nt.rotation = angle
        self.undo.push(cmd.SetTransformsCommand(self.scene, {drag["layer"]: nt}, drag["gesture"],
                                                self.tr("Rotate")))

    def wheelEvent(self, event) -> None:  # noqa: N802
        pixel = event.pixelDelta()
        mods = event.modifiers()
        zoom_mod = mods & (Qt.ControlModifier | Qt.MetaModifier)
        if not pixel.isNull() and not zoom_mod:
            # Gładzik (dwa palce): przesuwanie widoku, jak w aplikacjach macOS.
            self.center[0] -= pixel.x() / self.zoom
            self.center[1] += pixel.y() / self.zoom
            self._auto_fit = False
            self._camera_changed()
            return
        delta = event.angleDelta().y() or pixel.y()
        if delta:
            self.zoom_by(1.0015 ** delta, event.position())

    def event(self, event) -> bool:
        if event.type() == QEvent.Gesture:
            pinch = event.gesture(Qt.PinchGesture)
            if pinch is not None:
                self.zoom_by(pinch.scaleFactor(), self.mapFromGlobal(QCursor.pos()))
                return True
        if event.type() == QEvent.NativeGesture and event.gestureType() == Qt.ZoomNativeGesture:
            self.zoom_by(1.0 + event.value(), event.position())
            return True
        if event.type() == QEvent.ShortcutOverride:
            # Te klawisze płótno obsługuje samo, gdy ma fokus.
            if event.key() in (Qt.Key_Space, Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down,
                               Qt.Key_R, Qt.Key_G, Qt.Key_Plus, Qt.Key_Minus, Qt.Key_Equal,
                               Qt.Key_Tab) and not (event.modifiers() & Qt.ControlModifier):
                event.accept()
                return True
        if event.type() == QEvent.KeyPress and event.key() in (Qt.Key_Tab, Qt.Key_Backtab):
            self._select_next(-1 if event.key() == Qt.Key_Backtab else 1)
            return True
        return super().event(event)

    def contextMenuEvent(self, event) -> None:  # noqa: N802
        layer = self._hit_layer(QPointF(event.pos()))
        if layer is not None and layer.id not in self.scene.selection:
            self.scene.set_selection([layer.id])
        menu = QMenu(self)
        tok = theme.tokens["text"]
        has_sel = bool(self.scene.selection)
        sel = self.scene.selected_layers()
        entries = [("copy", self.tr("Duplicate"), self.requestDuplicate.emit),
                   ("trash", self.tr("Delete"), self.requestDelete.emit), None,
                   ("chevron-up", self.tr("Bring forward"), lambda: self.restack(1)),
                   ("chevron-down", self.tr("Send backward"), lambda: self.restack(-1)),
                   ("reset", self.tr("Reset transform"), self.reset_transform), None]
        for entry in entries:
            if entry is None:
                menu.addSeparator()
            else:
                menu.addAction(icon(entry[0], tok), entry[1], entry[2]).setEnabled(has_sel)
        presets = menu.addMenu(icon("preset", tok), self.tr("Apply preset"))
        presets.setEnabled(len(sel) == 1)
        if len(sel) == 1:
            for key, name in self.preset_names:
                if key.startswith(sel[0].TYPE + ":"):
                    presets.addAction(name, lambda k=key: self.requestApplyPreset.emit(k))
        a = menu.addAction(icon("save", tok), self.tr("Save as preset…"), self.requestSavePreset.emit)
        a.setEnabled(len(sel) == 1)
        menu.addSeparator()
        menu.addAction(icon("fit", tok), self.tr("Fit canvas to view"), self.fit_view)
        menu.exec(event.globalPos())

    # ======================================================================
    # Klawiatura
    # ======================================================================
    def keyPressEvent(self, event) -> None:  # noqa: N802
        key = event.key()
        mods = event.modifiers()
        shift = bool(mods & Qt.ShiftModifier)
        if key == Qt.Key_Space:
            if not event.isAutoRepeat():
                self._space = True
                self._space_used = False
                self.setCursor(Qt.OpenHandCursor)
            return
        if key in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down):
            step = 0.1 if shift else 0.01
            dx = {Qt.Key_Left: -step, Qt.Key_Right: step}.get(key, 0.0)
            dy = {Qt.Key_Down: -step, Qt.Key_Up: step}.get(key, 0.0)
            self.nudge(self.tr("Move"), dx=dx, dy=dy)
            return
        if key == Qt.Key_R:
            self.nudge(self.tr("Rotate"), rotation=-5.0 if shift else 5.0)
            return
        if key in (Qt.Key_Plus, Qt.Key_Equal, Qt.Key_Minus):
            self.nudge(self.tr("Scale"), factor=1 / 1.05 if key == Qt.Key_Minus else 1.05)
            return
        if key == Qt.Key_G and not mods:
            self.set_option("show_grid", not self.show_grid)
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key_Space and not event.isAutoRepeat():
            self._space = False
            self.unsetCursor()
            if not self._space_used:
                self.requestPlayToggle.emit()  # Spacja bez przeciągania = play/pauza
            return
        super().keyReleaseEvent(event)

    def nudge(self, text: str, dx: float = 0.0, dy: float = 0.0, rotation: float = 0.0,
              factor: float = 1.0) -> None:
        """Krok z klawiatury dla wszystkich odblokowanych zaznaczonych warstw."""
        new = {}
        for layer in self.scene.selected_layers():
            if not layer.locked:
                t = layer.transform
                new[layer.id] = Transform(t.x + dx, t.y + dy, t.sx * factor, t.sy * factor, t.rotation + rotation)
        if new:
            self.undo.push(cmd.SetTransformsCommand(self.scene, new, None, text))

    def reset_transform(self) -> None:
        new = {lay.id: Transform() for lay in self.scene.selected_layers() if not lay.locked}
        if new:
            self.undo.push(cmd.SetTransformsCommand(self.scene, new, None, self.tr("Reset transform")))

    def restack(self, direction: int) -> None:
        command = cmd.restack_command(self.scene, direction)
        if command is not None:
            self.undo.push(command)

    def _select_next(self, direction: int) -> None:
        layers = list(reversed(self.scene.layers))  # kolejność jak w panelu (od góry)
        if not layers:
            return
        current = self.scene.selection[-1] if self.scene.selection else None
        ids = [lay.id for lay in layers]
        i = ids.index(current) if current in ids else -1
        self.scene.set_selection([ids[(i + direction) % len(ids)]])


def _path_text(p: QPainter, pos: QPointF, text: str, font: QFont, color: QColor) -> None:
    """Tekst jako ścieżka wektorowa — niezawodny w QOpenGLWidget przy małych
    rozmiarach czcionki (omija pamięć podręczną glifów silnika OpenGL)."""
    path = QPainterPath()
    path.addText(pos, font, text)
    p.save()
    p.setPen(Qt.NoPen)
    p.setBrush(color)
    p.drawPath(path)
    p.restore()


def _dist(a: QPointF, b: QPointF) -> float:
    d = a - b
    return math.hypot(d.x(), d.y())
