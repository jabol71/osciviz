# Architektura

```
osciviz/
├── app.py            # punkt wejścia: QSurfaceFormat 4.1 Core, QApplication, motyw, język
├── core/             # audio i obraz — bez GUI
│   ├── audio_source.py   AudioSource / FileSource / LiveSource / lista urządzeń
│   ├── audio_player.py   odtwarzanie pliku; licznik próbek = zegar nadrzędny
│   ├── ring_buffer.py    bufor kołowy trybu na żywo
│   ├── recorder.py       nagrywanie sesji do WAV (wątek + kolejka)
│   ├── analysis.py       okno Hanna, FFT, pasma, obwiednie
│   ├── frame.py          FrameContext — wszystko o dźwięku dla jednej klatki
│   ├── image_to_points.py obraz → chmura punktów (OpenCV)
│   └── demo.py           syntetyczny utwór demonstracyjny
├── scene/            # czyste dane projektu
│   ├── scene.py          Scene (QObject + sygnały): proporcje, tło, ziarno, warstwy, zaznaczenie
│   ├── layers.py         Waveform/XY/Spectrum/ParticleLayer + schemat parametrów
│   ├── params.py         ParamSpec — opis parametru dla inspektora
│   ├── transform.py      Transform, macierze 3×3, hit test
│   ├── particles.py      fizyka cząsteczek (numpy)
│   ├── simulation.py     stan zależny od historii (widmo, cząsteczki)
│   └── commands.py       QUndoCommand dla każdej edycji
├── render/           # OpenGL (moderngl), wspólny dla podglądu, PNG i MP4
│   ├── renderer.py, geometry.py, line_mesh.py, postfx.py, shaders/*.vert|frag
├── gui/              # widżety PySide6
├── io/               # project_io.py (.osv), presets.py, exporter.py (PNG/MP4)
├── i18n/             # osciviz_pl.ts/.qm, osciviz_en.ts/.qm
└── resources/presets # presety wbudowane (.json)
```

## Zasady

1. **Scena to czyste dane.** `scene/` nie importuje OpenGL ani widżetów. Wyjątki zgodne ze
   specyfikacją: `commands.py` używa `QUndoCommand`, a `scene.py` — `QObject` i sygnałów.
2. **GUI zmienia scenę wyłącznie przez komendy undo.** Dzięki temu każda edycja (także z
   klawiatury i inspektora) jest cofalna. Wyjątek: zaznaczenie (nie jest częścią projektu).
3. **Renderer nie zna GUI.** Dostaje `scene`, `FrameContext`, `Simulation`, docelowy
   framebuffer i macierz widoku. Ten sam kod rysuje podgląd, PNG i MP4.
4. **Źródło audio za interfejsem.** `AudioSource.get_window(n) -> (n, 2) float32` —
   analiza i warstwy nie wiedzą, czy dźwięk jest z pliku, czy na żywo.

## Przepływ jednej klatki (podgląd)

```
QTimer 16 ms ─► MainWindow._tick
                 ├─ zegar: player.position (plik) albo perf_counter (na żywo)
                 ├─ samples = source.window_at(pos, n) / live.get_window(n)
                 ├─ frame = build_frame(samples, sr, analyzer, t, dt)   # FFT, pasma, obwiednie
                 ├─ sim.update(scene, frame)                            # widmo, cząsteczki
                 └─ canvas.set_frame(frame) → update() → paintGL → Renderer.render(...)
```

Eksport MP4 robi to samo w pętli `t = start + i/fps`, z własnym `Analyzer`, `Simulation`
i kontekstem OpenGL w wątku `QThread`.
