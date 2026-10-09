"""Renderer: rysuje scenę do dowolnego framebuffera.

Ten sam kod obsługuje podgląd w oknie, zrzut PNG i eksport MP4. Renderer
nie zna widżetów — dostaje:

- ``scene``  — dane projektu,
- ``frame``  — kontekst klatki (próbki, analiza),
- ``sim``    — stan zależny od historii (widmo, cząsteczki),
- ``target`` — docelowy framebuffer i jego rozmiar w pikselach,
- ``view``   — macierz 3×3: scena → współrzędne ekranu (NDC, zakres [-1, 1]),
- ``px_per_unit`` — ile pikseli framebuffera przypada na jednostkę sceny
  (potrzebne do rozmiaru punktów i promienia poświaty).

Potok jednej klatki:

1. tło kadru → tekstura sceny,
2. dla każdej widocznej warstwy (od spodu):
   a. geometria → bufor MSAA warstwy (wygładzanie krawędzi) → rozwiązanie
      do zwykłej tekstury,
   b. (XY) akumulacja powidoku,
   c. (opcjonalnie) poświata — rozmycie Gaussa,
   d. nałożenie na teksturę sceny z kryciem i trybem mieszania
      (normal: ONE, 1−SRC_ALPHA; additive: ONE, ONE),
3. tekstura sceny → docelowy framebuffer (z lekkim mapowaniem tonów).
"""

from __future__ import annotations

from importlib import resources

import moderngl
import numpy as np

from osciviz.core.frame import FrameContext
from osciviz.render import geometry
from osciviz.render.postfx import GlowPass, PersistenceBuffer, make_target
from osciviz.scene.layers import Layer, ParticleLayer, SpectrumLayer, WaveformLayer, XYLayer
from osciviz.scene.scene import Scene
from osciviz.scene.simulation import Simulation

BLEND_NORMAL = (moderngl.ONE, moderngl.ONE_MINUS_SRC_ALPHA)
BLEND_ADD = (moderngl.ONE, moderngl.ONE)


def load_shader(name: str) -> str:
    return resources.files("osciviz.render").joinpath("shaders", name).read_text(encoding="utf-8")


def hex_to_rgba(color: str, alpha: float = 1.0) -> tuple[float, float, float, float]:
    color = color.lstrip("#")
    if len(color) == 3:
        color = "".join(c * 2 for c in color)
    r, g, b = (int(color[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    return (r, g, b, alpha)


def gradient(params: dict) -> tuple[tuple, tuple]:
    """Kolory początku i końca gradientu (bez gradientu oba są takie same)."""
    end = params["color2"] if params["use_gradient"] else params["color"]
    return hex_to_rgba(params["color"]), hex_to_rgba(end)


def ortho_view(center: tuple[float, float], half_size: tuple[float, float]) -> np.ndarray:
    """Macierz widoku: prostokąt sceny ``center ± half_size`` → NDC ``[-1, 1]²``."""
    cx, cy = center
    hx, hy = half_size
    return np.array([[1 / hx, 0, -cx / hx], [0, 1 / hy, -cy / hy], [0, 0, 1]], dtype=np.float64)


def mat3_bytes(m: np.ndarray) -> bytes:
    # GLSL oczekuje macierzy kolumnami (column-major), numpy trzyma wierszami.
    return np.ascontiguousarray(m.T, dtype=np.float32).tobytes()


class Renderer:
    def __init__(self, ctx: moderngl.Context) -> None:
        self.ctx = ctx
        quad_vs = load_shader("quad.vert")
        self.mesh_prog = ctx.program(vertex_shader=load_shader("mesh.vert"),
                                     fragment_shader=load_shader("mesh.frag"))
        self.points_prog = ctx.program(vertex_shader=load_shader("points.vert"),
                                       fragment_shader=load_shader("points.frag"))
        self.blur_prog = ctx.program(vertex_shader=quad_vs, fragment_shader=load_shader("blur.frag"))
        self.comp_prog = ctx.program(vertex_shader=quad_vs, fragment_shader=load_shader("composite.frag"))
        self.fade_prog = ctx.program(vertex_shader=quad_vs, fragment_shader=load_shader("fade.frag"))
        self.final_prog = ctx.program(vertex_shader=quad_vs, fragment_shader=load_shader("final.frag"))

        # Prostokąt pełnoekranowy (4 wierzchołki, TRIANGLE_STRIP).
        quad = np.array([-1, -1, 1, -1, -1, 1, 1, 1], dtype=np.float32)
        self.quad_vbo = ctx.buffer(quad.tobytes())
        self.quads = {
            prog: ctx.vertex_array(prog, [(self.quad_vbo, "2f", "in_pos")])
            for prog in (self.blur_prog, self.comp_prog, self.fade_prog, self.final_prog)
        }
        # Dynamiczne bufory na geometrię (powiększane w razie potrzeby).
        self.mesh_vbo = ctx.buffer(reserve=1 << 20, dynamic=True)
        self.mesh_vao = ctx.vertex_array(
            self.mesh_prog, [(self.mesh_vbo, "2f 2f 1f", "in_pos", "in_uv", "in_alpha")])
        self.pts_vbo = ctx.buffer(reserve=1 << 20, dynamic=True)
        self.pts_vao = ctx.vertex_array(
            self.points_prog, [(self.pts_vbo, "2f 4f", "in_pos", "in_color")])

        self.samples = min(4, ctx.max_samples) if ctx.max_samples else 0
        self.size = (0, 0)
        self.scene_target = None
        self.layer_target = None
        self.msaa_fbo = None
        self.msaa_rb = None
        self.glow = GlowPass(ctx, self.blur_prog, self.quads[self.blur_prog])
        self.persistence: dict[str, PersistenceBuffer] = {}
        self.black = ctx.texture((1, 1), 4, np.zeros(4, np.uint8).tobytes())

    # --- zasoby ----------------------------------------------------------------
    def _ensure_size(self, size: tuple[int, int]) -> None:
        if size == self.size:
            return
        self._release_targets()
        self.size = size
        self.scene_target = make_target(self.ctx, size)
        self.layer_target = make_target(self.ctx, size)
        if self.samples > 1:
            self.msaa_rb = self.ctx.renderbuffer(size, 4, samples=self.samples, dtype="f2")
            self.msaa_fbo = self.ctx.framebuffer(color_attachments=[self.msaa_rb])
        self.glow.ensure(size)

    def _release_targets(self) -> None:
        for pair in (self.scene_target, self.layer_target):
            if pair:
                pair[1].release()
                pair[0].release()
        if self.msaa_fbo:
            self.msaa_fbo.release()
            self.msaa_rb.release()
            self.msaa_fbo = self.msaa_rb = None
        self.reset_history()

    def reset_history(self) -> None:
        """Czyści powidoki (np. po zmianie kamery lub przewinięciu)."""
        for buf in self.persistence.values():
            buf.release()
        self.persistence.clear()

    def release(self) -> None:
        self._release_targets()
        self.glow.release()

    # --- rysowanie ---------------------------------------------------------------
    def render(self, scene: Scene, frame: FrameContext, sim: Simulation,
               target: moderngl.Framebuffer, size: tuple[int, int], view: np.ndarray,
               px_per_unit: float, clear_target: tuple | None = None) -> None:
        ctx = self.ctx
        self._ensure_size(size)
        view_bytes = mat3_bytes(view)
        self.mesh_prog["u_view"].write(view_bytes)
        self.points_prog["u_view"].write(view_bytes)

        # 1. Tło kadru.
        scene_tex, scene_fbo = self.scene_target
        self._use(scene_fbo, clear=(0, 0, 0, 0))
        ctx.disable(moderngl.BLEND)
        hx, hy = scene.extent
        self._draw_mesh(geometry.rect_mesh(hx, hy), hex_to_rgba(scene.background),
                        hex_to_rgba(scene.background), feather=0.0)

        # 2. Warstwy od spodu.
        alive = set()
        for layer in scene.layers:
            alive.add(layer.id)
            if not layer.visible or layer.opacity <= 0.0:
                continue
            image = self._render_layer(layer, frame, sim, view, px_per_unit)
            if image is None:
                continue
            glow_tex, glow_strength = None, 0.0
            glow = float(layer.params.get("glow", 0.0))
            if glow > 0.0:
                radius_px = layer.params.get("glow_radius", 10.0) * geometry.PX * px_per_unit
                glow_tex = self.glow.run(image, radius_px)
                glow_strength = glow
            self._use(scene_fbo)
            ctx.blend_func = BLEND_ADD if layer.blend_mode == "additive" else BLEND_NORMAL
            self._composite(image, float(layer.opacity), glow_tex, glow_strength)

        for key in list(self.persistence):
            if key not in alive:
                self.persistence.pop(key).release()

        # 3. Scena → cel.
        self._use(target, clear=clear_target)
        ctx.blend_func = BLEND_NORMAL
        scene_tex.use(0)
        self.final_prog["u_image"].value = 0
        self.quads[self.final_prog].render(moderngl.TRIANGLE_STRIP)
        ctx.disable(moderngl.BLEND)

    def _use(self, fbo: moderngl.Framebuffer, clear: tuple | None = None) -> None:
        """Ustawia framebuffer jako cel rysowania (opcjonalnie czyści) i włącza mieszanie."""
        fbo.use()
        self.ctx.viewport = (0, 0, *self.size)
        if clear is not None:
            fbo.clear(*clear)
        self.ctx.enable(moderngl.BLEND)

    def _composite(self, image: moderngl.Texture, opacity: float,
                   glow_tex: moderngl.Texture | None = None, glow_strength: float = 0.0) -> None:
        """Nakłada teksturę (i ewentualnie jej poświatę) na bieżący framebuffer."""
        image.use(0)
        (glow_tex or self.black).use(1)
        self.comp_prog["u_image"].value = 0
        self.comp_prog["u_glow"].value = 1
        self.comp_prog["u_opacity"].value = opacity
        self.comp_prog["u_glow_strength"].value = glow_strength
        self.quads[self.comp_prog].render(moderngl.TRIANGLE_STRIP)

    def _upload(self, vbo: moderngl.Buffer, data: bytes) -> None:
        """Wgrywa dane do bufora, powiększając go w razie potrzeby."""
        if len(data) > vbo.size:
            vbo.orphan(len(data) * 2)
        vbo.write(data)

    def _begin_layer(self) -> None:
        self._use(self.msaa_fbo or self.layer_target[1], clear=(0, 0, 0, 0))

    def _end_layer(self) -> moderngl.Texture:
        if self.msaa_fbo:
            # Rozwiązanie MSAA: uśrednienie próbek do zwykłej tekstury.
            self.ctx.copy_framebuffer(self.layer_target[1], self.msaa_fbo)
        return self.layer_target[0]

    def _render_layer(self, layer: Layer, frame: FrameContext, sim: Simulation,
                      view: np.ndarray, px_per_unit: float) -> moderngl.Texture | None:
        p = layer.params
        self._begin_layer()
        self.ctx.blend_func = BLEND_NORMAL
        if isinstance(layer, WaveformLayer):
            self._draw_mesh(geometry.waveform_mesh(layer, frame), *gradient(p),
                            feather=self._feather(p["thickness"], px_per_unit))
        elif isinstance(layer, XYLayer):
            self.ctx.blend_func = BLEND_ADD  # nakładające się przebiegi rozjaśniają się
            color = hex_to_rgba(p["color"])
            self._draw_mesh(geometry.xy_mesh(layer, frame), color, color,
                            feather=self._feather(p["thickness"], px_per_unit))
        elif isinstance(layer, SpectrumLayer):
            values = sim.spectrum.get(layer.id)
            if values is None:
                values = np.zeros(int(p["bands"]), np.float32)
            self._draw_mesh(geometry.spectrum_mesh(layer, values), *gradient(p), feather=0.0)
        elif isinstance(layer, ParticleLayer):
            if not self._draw_particles(layer, sim, px_per_unit):
                return None
        image = self._end_layer()
        if isinstance(layer, XYLayer) and p["persistence"] > 0.0:
            image = self._accumulate(layer.id, image, p["persistence"], frame.dt)
        return image

    @staticmethod
    def _feather(thickness_px: float, px_per_unit: float) -> float:
        # Szerokość wygładzenia ≈ 1.2 px ekranu, wyrażona jako ułamek połowy grubości.
        half_px = thickness_px * geometry.PX * px_per_unit / 2
        return float(min(0.9, 1.2 / max(half_px, 1e-3)))

    def _draw_mesh(self, vertices: np.ndarray, color1, color2, feather: float) -> None:
        if len(vertices) == 0:
            return
        self._upload(self.mesh_vbo, np.ascontiguousarray(vertices, dtype=np.float32).tobytes())
        self.mesh_prog["u_color1"].value = color1
        self.mesh_prog["u_color2"].value = color2
        self.mesh_prog["u_feather"].value = feather
        self.mesh_vao.render(moderngl.TRIANGLES, vertices=len(vertices))

    def _draw_particles(self, layer: ParticleLayer, sim: Simulation, px_per_unit: float) -> bool:
        state = sim.particles.get(layer.id)
        if state is None:
            return False
        p = layer.params
        system = state.system
        data = np.empty((system.count, 6), dtype=np.float32)
        data[:, 0:2] = system.pos
        data[:, 2:6] = system.colors
        self._upload(self.pts_vbo, data.tobytes())
        size = p["size"] * geometry.PX * px_per_unit
        if p["high_size"]:
            size *= 1.0 + 1.5 * state.high_value
        brightness = p["brightness"]
        if p["mid_brightness"]:
            brightness *= 0.6 + 0.8 * state.mid_value
        prog = self.points_prog
        prog["u_model"].write(mat3_bytes(layer.transform.matrix()))
        prog["u_point_size"].value = float(max(1.0, size))
        prog["u_brightness"].value = float(brightness)
        prog["u_opacity"].value = 1.0
        self.ctx.enable(moderngl.PROGRAM_POINT_SIZE)
        self.ctx.blend_func = BLEND_ADD  # nakładające się punkty świecą mocniej
        self.pts_vao.render(moderngl.POINTS, vertices=system.count)
        return True

    def _accumulate(self, layer_id: str, image: moderngl.Texture, persistence: float,
                    dt: float) -> moderngl.Texture:
        buf = self.persistence.get(layer_id)
        if buf is None or buf.size != self.size:
            if buf:
                buf.release()
            buf = PersistenceBuffer(self.ctx, self.size)
            self.persistence[layer_id] = buf
        # Zanikanie niezależne od liczby klatek na sekundę: decay = p^(dt·60).
        decay = float(persistence ** max(dt * 60.0, 0.0))
        self._use(buf.back[1])
        self.ctx.disable(moderngl.BLEND)
        buf.front[0].use(0)
        self.fade_prog["u_tex"].value = 0
        self.fade_prog["u_decay"].value = decay
        self.quads[self.fade_prog].render(moderngl.TRIANGLE_STRIP)
        # Bieżąca klatka dodana na wierzch wygaszonej historii.
        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = BLEND_NORMAL
        self._composite(image, 1.0)
        buf.swap()
        return buf.front[0]
