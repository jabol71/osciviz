# Zapis, presety i eksport (`io/`)

## Format `.osv`

Archiwum ZIP:

```
project.json        # format_version, aspect_ratio, background, seed, audio_ref, layers[]
assets/
  audio.<ext>       # kopia pliku audio (bez kompresji — szybciej)
  images/<id>.<ext> # obrazy warstw cząsteczek
```

Każda warstwa w `layers[]`: `type`, `id`, `name`, `transform {x, y, sx, sy, rotation}`,
`opacity`, `blend_mode`, `visible`, `locked`, `params {…}`.

- **Zapis atomowy**: plik tymczasowy w tym samym katalogu → `os.replace` (atomowa zamiana).
- **Walidacja**: nieznany typ warstwy, uszkodzony ZIP lub JSON, brakujący zasób →
  `ProjectError` z czytelnym komunikatem (GUI pokazuje okno zamiast wyjątku). Wartości
  parametrów są przycinane do zakresów (`coerce`).
- **Migracje**: `migrate()` podnosi stare wersje formatu (np. v1 → v2: `aspect` → `aspect_ratio`).
- **Bezpieczeństwo**: zasoby są wypakowywane po samej nazwie pliku — ścieżki typu `../../`
  z archiwum nie wyjdą poza katalog roboczy.

## Presety

JSON z typem i parametrami warstwy (bez transformacji). Wbudowane: `resources/presets/`.
Użytkownika: `~/Library/Application Support/OsciViz/presets/`.

## Eksport PNG

`OffscreenRenderer` tworzy FBO w docelowej rozdzielczości (w kontekście podglądu),
renderuje scenę, `fbo.read()` → odwrócenie wierszy (OpenGL ma początek na dole) → Pillow.

## Eksport MP4

`VideoExporter(QThread)`:

1. kopia sceny (edycje w GUI nie wpływają na trwający eksport),
2. przycięty fragment audio → tymczasowy WAV,
3. **własny kontekst** `moderngl.create_standalone_context(require=410)` — nie blokuje GUI
   i nie koliduje z kontekstem podglądu,
4. dla `i = 0 … N−1`: `t = start + i/fps` → próbki → analiza → symulacja (`dt = 1/fps`) →
   render → surowe RGB do `imageio_ffmpeg.write_frames`,
5. ffmpeg od razu dołącza audio: H.264 (`libx264` z CRF lub `h264_videotoolbox` z bitrate),
   AAC, `yuv420p`, `-movflags +faststart`, `-shortest`,
6. sygnały postępu (klatka, ETA); anulowanie zamyka potok i usuwa niedokończony plik.
