"""Efekty po renderze: poświata (glow) i powidok (persistence).

Glow: obraz warstwy zmniejszamy do połowy rozdzielczości (taniej, a i tak
będzie rozmyty), rozmywamy Gaussem w dwóch przebiegach (poziomo, pionowo)
i nakładamy addytywnie na wynik — jasne linie „świecą”.

Persistence: trzymamy dwie tekstury akumulacji i co klatkę zamieniamy je
miejscami (ping-pong): ``nowa = stara · decay + bieżąca_klatka``. Tak
działał luminofor w lampie oscyloskopu.
"""

from __future__ import annotations

import moderngl


def make_target(ctx: moderngl.Context, size: tuple[int, int]) -> tuple[moderngl.Texture, moderngl.Framebuffer]:
    """Tekstura RGBA16F + framebuffer. Półprecyzyjne floaty pozwalają na
    jasności > 1 (sumowanie poświaty) bez przycinania w pośrednich krokach."""
    tex = ctx.texture(size, 4, dtype="f2")
    tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
    tex.repeat_x = False
    tex.repeat_y = False
    return tex, ctx.framebuffer(color_attachments=[tex])


class GlowPass:
    def __init__(self, ctx: moderngl.Context, blur_prog: moderngl.Program, quad) -> None:
        self.ctx = ctx
        self.prog = blur_prog
        self.quad = quad
        self.size = (0, 0)
        self.a = self.b = None

    def ensure(self, full_size: tuple[int, int]) -> None:
        size = (max(1, full_size[0] // 2), max(1, full_size[1] // 2))
        if size != self.size:
            self.release()
            self.size = size
            self.a = make_target(self.ctx, size)
            self.b = make_target(self.ctx, size)

    def run(self, source: moderngl.Texture, sigma_px_full: float) -> moderngl.Texture:
        """Rozmywa ``source``; ``sigma_px_full`` w pikselach pełnej rozdzielczości."""
        sigma = max(0.5, sigma_px_full / 2.0)  # połowa rozdzielczości → połowa sigmy
        w, h = self.size
        self.ctx.disable(moderngl.BLEND)
        # Przebieg 1: poziomy, z pełnej rozdzielczości do połówki (a).
        self.a[1].use()
        self.ctx.viewport = (0, 0, w, h)
        self.a[1].clear(0, 0, 0, 0)
        source.use(0)
        self.prog["u_tex"].value = 0
        self.prog["u_dir"].value = (1.0 / w, 0.0)
        self.prog["u_sigma"].value = sigma
        self.quad.render(moderngl.TRIANGLE_STRIP)
        # Przebieg 2: pionowy (a → b).
        self.b[1].use()
        self.b[1].clear(0, 0, 0, 0)
        self.a[0].use(0)
        self.prog["u_dir"].value = (0.0, 1.0 / h)
        self.quad.render(moderngl.TRIANGLE_STRIP)
        return self.b[0]

    def release(self) -> None:
        for pair in (self.a, self.b):
            if pair:
                pair[1].release()
                pair[0].release()
        self.a = self.b = None


class PersistenceBuffer:
    """Para tekstur akumulacji (ping-pong) dla jednej warstwy."""

    def __init__(self, ctx: moderngl.Context, size: tuple[int, int]) -> None:
        self.size = size
        self.front = make_target(ctx, size)
        self.back = make_target(ctx, size)
        self.front[1].clear(0, 0, 0, 0)
        self.back[1].clear(0, 0, 0, 0)

    def swap(self) -> None:
        self.front, self.back = self.back, self.front

    def release(self) -> None:
        for tex, fbo in (self.front, self.back):
            fbo.release()
            tex.release()
