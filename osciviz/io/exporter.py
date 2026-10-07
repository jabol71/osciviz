"""Eksport PNG i MP4.

Oba eksporty używają tego samego ``Renderer`` co podgląd, ale z **własnym**
kontekstem OpenGL (``moderngl.create_standalone_context``) i własnym stanem
symulacji. Dzięki temu:

- eksport MP4 działa w wątku ``QThread`` i nie blokuje GUI,
- nie koliduje z kontekstem okna podglądu,
- stan zależny od historii (cząsteczki, obwiednie, powidok XY) jest liczony
  od początku zakresu ze stałym krokiem ``dt = 1/fps`` — wynik jest powtarzalny.

MP4: każda klatka (surowe RGB) trafia do potoku ffmpeg przez
``imageio_ffmpeg.write_frames``; ffmpeg od razu dołącza przycięty fragment
audio (AAC), ustawia ``yuv420p`` (zgodność z QuickTime) i ``+faststart``.
"""

from __future__ import annotations

import copy
import os
import tempfile
import time
from dataclasses import dataclass

import numpy as np
from PySide6.QtCore import QThread, Signal

from osciviz.core.analysis import Analyzer
from osciviz.core.audio_source import FileSource
from osciviz.core.frame import build_frame, window_length
from osciviz.render.renderer import Renderer, ortho_view
from osciviz.scene.layers import layer_from_dict
from osciviz.scene.scene import Scene, parse_aspect
from osciviz.scene.simulation import Simulation

RESOLUTION_PRESETS = {  # krótszy bok → etykieta
    720: "720p", 1080: "1080p", 1440: "1440p", 2160: "4K",
}


def resolution_for(aspect: str, short_side: int) -> tuple[int, int]:
    """Rozmiar w pikselach dla proporcji i krótszego boku (zaokrąglony do parzystych)."""
    w, h = parse_aspect(aspect)
    if w >= h:
        height = short_side
        width = int(round(short_side * w / h))
    else:
        width = short_side
        height = int(round(short_side * h / w))
    return width - width % 2, height - height % 2


def snapshot_scene(scene: Scene) -> Scene:
    """Głęboka kopia danych sceny (eksport w wątku nie może widzieć edycji z GUI)."""
    copy_scene = Scene()
    copy_scene.aspect = scene.aspect
    copy_scene.background = scene.background
    copy_scene.seed = scene.seed
    copy_scene.audio_path = scene.audio_path
    for layer in scene.layers:
        clone = layer_from_dict(copy.deepcopy(layer.to_dict()))
        if hasattr(layer, "_extent"):
            clone._extent = layer._extent
        copy_scene.layers.append(clone)
    return copy_scene


class OffscreenRenderer:
    """Renderowanie sceny do obrazu RGB w zadanej rozdzielczości."""

    def __init__(self, size: tuple[int, int], ctx=None) -> None:
        import moderngl  # noqa: PLC0415

        self.own_ctx = ctx is None
        self.ctx = ctx or moderngl.create_standalone_context(require=410)
        self.size = size
        self.renderer = Renderer(self.ctx)
        self.tex = self.ctx.texture(size, 4)
        self.fbo = self.ctx.framebuffer(color_attachments=[self.tex])

    def render(self, scene: Scene, frame, sim: Simulation) -> np.ndarray:
        w, h = self.size
        ex, ey = scene.extent
        view = ortho_view((0.0, 0.0), (ex, ey))
        px_per_unit = h / (2 * ey)
        self.renderer.render(scene, frame, sim, self.fbo, self.size, view, px_per_unit,
                             clear_target=(0.0, 0.0, 0.0, 1.0))
        data = self.fbo.read(components=3, alignment=1)
        # OpenGL ma początek układu w lewym dolnym rogu — odwracamy wiersze.
        return np.frombuffer(data, dtype=np.uint8).reshape(h, w, 3)[::-1].copy()

    def release(self) -> None:
        self.renderer.release()
        self.fbo.release()
        self.tex.release()
        if self.own_ctx:
            self.ctx.release()


def save_png(image: np.ndarray, path: str) -> None:
    from PIL import Image  # noqa: PLC0415

    Image.fromarray(image).save(path)


@dataclass
class ExportSettings:
    path: str
    width: int
    height: int
    fps: int = 60
    crf: int = 18
    codec: str = "libx264"  # albo "h264_videotoolbox" (sprzętowy na macOS)
    start: float = 0.0
    end: float = 10.0
    include_audio: bool = True


def build_ffmpeg_params(settings: ExportSettings) -> list[str]:
    params = ["-movflags", "+faststart"]
    if settings.codec == "libx264":
        params += ["-crf", str(settings.crf), "-preset", "medium"]
    else:
        # VideoToolbox nie zna CRF — przeliczamy jakość na bitrate (≈ bity na piksel).
        bpp = 0.25 * (1.12 ** (18 - settings.crf))
        bitrate = int(settings.width * settings.height * settings.fps * bpp)
        params += ["-b:v", f"{max(bitrate, 500_000)}"]
    return params


class VideoExporter(QThread):
    progress = Signal(int, int, float)  # klatka, wszystkie klatki, szacowany pozostały czas [s]
    finished_ok = Signal(str)
    failed = Signal(str)

    def __init__(self, scene: Scene, source: FileSource, settings: ExportSettings,
                 default_image: str | None = None) -> None:
        super().__init__()
        self.scene = snapshot_scene(scene)
        self.default_image = default_image
        self.source = source
        self.settings = settings
        self._cancel = False

    def cancel(self) -> None:
        self._cancel = True

    def run(self) -> None:
        s = self.settings
        audio_tmp = None
        offscreen = None
        writer = None
        try:
            import imageio_ffmpeg  # noqa: PLC0415

            sr = self.source.sample_rate
            start = max(0.0, s.start)
            end = min(s.end, self.source.duration)
            n_frames = max(1, int(round((end - start) * s.fps)))
            if s.include_audio:
                audio_tmp = self._write_audio_segment(start, end)
            offscreen = OffscreenRenderer((s.width, s.height))
            sim = Simulation()
            analyzer = Analyzer()
            n = window_length(sr, analyzer.fft_size)
            dt = 1.0 / s.fps
            writer = imageio_ffmpeg.write_frames(
                s.path, (s.width, s.height), fps=s.fps, codec=s.codec, quality=None,
                pix_fmt_out="yuv420p", macro_block_size=1, ffmpeg_log_level="error",
                output_params=build_ffmpeg_params(s) + (["-shortest"] if audio_tmp else []),
                audio_path=audio_tmp, audio_codec="aac" if audio_tmp else None,
            )
            writer.send(None)  # uruchomienie generatora (wymóg imageio-ffmpeg)
            t0 = time.monotonic()
            for i in range(n_frames):
                if self._cancel:
                    break
                t = start + i * dt
                end_sample = int(round(t * sr))
                samples = self.source.window_at(end_sample, n)
                frame = build_frame(samples, sr, analyzer, t, dt)
                sim.update(self.scene, frame, self.default_image)
                image = offscreen.render(self.scene, frame, sim)
                writer.send(image)
                elapsed = time.monotonic() - t0
                eta = elapsed / (i + 1) * (n_frames - i - 1)
                self.progress.emit(i + 1, n_frames, eta)
            writer.close()
            writer = None
            if self._cancel:
                _remove(s.path)
                self.failed.emit("")  # pusty komunikat = anulowano
            else:
                self.finished_ok.emit(s.path)
        except Exception as exc:  # błąd ffmpeg, OpenGL, dysku…
            if writer is not None:
                try:
                    writer.close()
                except Exception:
                    pass
            _remove(s.path)
            self.failed.emit(str(exc))
        finally:
            if offscreen is not None:
                offscreen.release()
            if audio_tmp:
                _remove(audio_tmp)

    def _write_audio_segment(self, start: float, end: float) -> str:
        import soundfile as sf  # noqa: PLC0415

        sr = self.source.sample_rate
        a, b = int(start * sr), int(end * sr)
        fd, path = tempfile.mkstemp(suffix=".wav", prefix="osciviz-audio-")
        os.close(fd)
        sf.write(path, self.source.data[a:b], sr, subtype="PCM_16")
        return path


def _remove(path: str) -> None:
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except OSError:
        pass
