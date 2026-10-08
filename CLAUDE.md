# OsciViz — wizualizator dźwięku (projekt GK i GUI)

Ten plik jest specyfikacją i planem pracy dla Claude Code. Czytaj go na początku każdej sesji.

## 0. Jak pracować z tym plikiem (instrukcje dla Claude Code)

- Realizuj projekt **etapami z sekcji 12**, po kolei. Nie implementuj funkcji z późniejszych etapów, dopóki bieżący nie spełnia kryteriów akceptacji.
- Przed większą zmianą przedstaw krótki plan i listę plików, które zmienisz.
- Po każdym etapie: uruchom `pytest`, uruchom aplikację, sprawdź kryteria akceptacji, zaproponuj commit z opisem po polsku.
- **Zasada przedmiotu:** w zespole musi być osoba, która bez AI rozumie i umie zmodyfikować każdy fragment kodu. Dlatego:
  - pisz kod prosty i czytelny, bez „sprytnych” konstrukcji, gdy prostsza wersja działa równie dobrze,
  - każdy moduł ma docstring wyjaśniający, CO robi i DLACZEGO tak,
  - nietrywialna matematyka (FFT, macierze transformacji, fizyka cząsteczek, shadery) ma komentarze krok po kroku,
  - po zakończeniu modułu dopisz krótkie wyjaśnienie do `docs/technical/<moduł>.md`.
- Platformy docelowe: **macOS 13+ (Apple Silicon i Intel)** oraz **Windows 10/11 (x64)**. Kod jest wspólny; różnice platform trzymaj w nielicznych, opisanych miejscach (`gui/keys.py`, `app.py`, `core/audio_source.py`, `packaging/`) — zob. `docs/technical/build.md`.
- Język kodu: identyfikatory po angielsku, komentarze i docstringi po polsku, teksty UI przez system tłumaczeń (PL domyślnie, EN dodatkowo).

## 1. Kontekst przedmiotu

Projekt zaliczeniowy z przedmiotu „Grafika Komputerowa i GUI” (grupa 5 osób). Wymagania prowadzącego:

- aplikacja z GUI,
- główna funkcjonalność oparta na układzie współrzędnych 2D,
- interakcja z elementami: zaznaczanie, przesuwanie, skalowanie, obracanie,
- motywy: ciemny, jasny, wysoki kontrast; wybór języka interfejsu (bonus),
- sterowanie myszą i klawiaturą,
- zapis i odczyt projektu oraz import i eksport,
- dokumentacja techniczna i instrukcja obsługi,
- historia pracy w Git (GitHub).

## 2. Koncepcja aplikacji

Desktopowy edytor wizualizacji audio działający jak programowy oscyloskop. Użytkownik:

1. wybiera proporcje płótna (1:1, 16:9, 9:16, 5:4, 4:3, 21:9),
2. wczytuje plik audio **albo** przechwytuje dźwięk na żywo z FL Studio,
3. układa na płótnie **warstwy** reagujące na dźwięk i edytuje je myszą oraz klawiaturą,
4. ogląda podgląd na żywo, robi zrzuty PNG i eksportuje wideo MP4 z dźwiękiem.

### Typy warstw

| Warstwa | Opis | Główne parametry |
|---|---|---|
| `WaveformLayer` | Oscyloskop czasowy: fragment sygnału jako linia | grubość, kolor/gradient, okno w ms, wzmocnienie, liczba kopii i ich przesunięcie, glow, kanał (L/R/mono) |
| `XYLayer` | Oscyloskop XY: L → oś X, R → oś Y | grubość, kolor, długość śladu, zanikanie (persistence), wzmocnienie |
| `SpectrumLayer` | Widmo FFT: słupki lub koło | liczba pasm, zakres Hz, skala log, wygładzanie, kolor |
| `ParticleLayer` | Obraz zamieniony na cząsteczki reagujące na bas | metoda próbkowania, liczba cząsteczek, zakres pasma basu, siła, sprężystość, tłumienie, rozmiar |

Każda warstwa ma: `transform` (pozycja, skala X/Y, rotacja), `opacity`, `blend_mode` (normal/additive), `visible`, `locked`, `name`.

## 3. Mapowanie wymagań na funkcje

| Wymaganie | Realizacja |
|---|---|
| GUI | PySide6: okno główne, panel warstw, inspektor właściwości, oś czasu, pasek narzędzi |
| Układ współrzędnych 2D | Płótno ze współrzędnymi znormalizowanymi, siatka, linijki, przyciąganie do siatki |
| Interakcja | Zaznaczanie (także wielu elementów), przeciąganie, uchwyty skalowania i rotacji, undo/redo |
| Motywy | `dark.qss`, `light.qss`, `high_contrast.qss`, wybór zapamiętany w `QSettings` |
| Język | PL/EN przez Qt Linguist (`.ts` → `.qm`), przełączanie bez restartu |
| Mysz + klawiatura | Skróty z sekcji 7 |
| Zapis/odczyt | Plik projektu `.osv` |
| Import/eksport | Import audio i obrazów; eksport MP4, PNG, presetów warstw `.json` |
| Dokumentacja | MkDocs: `docs/technical/` + `docs/user-guide/` |

## 4. Stos technologiczny

- **Python 3.12**, zarządzanie zależnościami przez `uv` lub `venv` + `requirements.txt`.
- **PySide6** — GUI.
- **moderngl** — renderowanie OpenGL w `QOpenGLWidget`.
- **numpy** — FFT i wektoryzacja.
- **soundfile** — wczytywanie WAV/FLAC/MP3/OGG.
- **sounddevice** — odtwarzanie i przechwytywanie na żywo (CoreAudio).
- **opencv-python** + **Pillow** — przetwarzanie obrazu.
- **imageio-ffmpeg** — binarka ffmpeg do MP4 (fallback: `brew install ffmpeg`).
- **pytest**, **ruff** — testy i linting.
- **PyInstaller** — paczka `.app`.
- **MkDocs** — dokumentacja.

### Uwagi specyficzne dla macOS (ważne!)

1. **OpenGL na macOS** obsługuje maksymalnie wersję **4.1 Core Profile**. Przed utworzeniem `QApplication` ustaw:
   ```python
   fmt = QSurfaceFormat()
   fmt.setVersion(4, 1)
   fmt.setProfile(QSurfaceFormat.CoreProfile)
   fmt.setSamples(4)
   QSurfaceFormat.setDefaultFormat(fmt)
   ```
   Shadery piszemy w `#version 410 core`. Nie używamy compute shaderów (niedostępne w 4.1).
2. **Retina:** rozmiar framebuffera = rozmiar widgetu × `devicePixelRatio()`. Viewport i przeliczanie pozycji myszy muszą to uwzględniać.
3. W `QOpenGLWidget` moderngl łączy się z kontekstem Qt przez `moderngl.create_context()` wywołane w `initializeGL`. Domyślnym framebufferem jest FBO widgetu: używaj `ctx.detect_framebuffer(self.defaultFramebufferObject())`.
4. **Uprawnienia mikrofonu:** przechwytywanie z BlackHole wymaga zgody na mikrofon. W paczce `.app` dodaj `NSMicrophoneUsageDescription` do `Info.plist` (opcja w specyfikacji PyInstaller).
5. **Kodowanie MP4:** domyślnie `libx264`; opcjonalnie sprzętowy `h264_videotoolbox` (szybszy na Macu) jako wybór w oknie eksportu.

## 5. Przechwytywanie dźwięku z FL Studio na macOS

macOS nie udostępnia prostego „loopbacku” systemowego, dlatego używamy darmowego wirtualnego sterownika **BlackHole**.

### Konfiguracja (do instrukcji obsługi)

1. `brew install blackhole-2ch` (lub instalator ze strony Existential Audio), restart lub ponowne zalogowanie.
2. **Audio MIDI Setup** → `+` → **Create Multi-Output Device** → zaznacz głośniki/słuchawki **oraz** BlackHole 2ch. Głośniki jako urządzenie główne (master), BlackHole z włączoną korekcją dryfu (Drift Correction).
3. **FL Studio** → Options → Audio settings → urządzenie wyjściowe: utworzone Multi-Output Device. Dźwięk słychać normalnie, a jednocześnie trafia do BlackHole.
4. **OsciViz** → źródło: „Na żywo” → urządzenie wejściowe: BlackHole 2ch.

### W kodzie

- `LiveSource` otwiera `sounddevice.InputStream` (stereo, 48000 Hz lub częstotliwość urządzenia, `blocksize=512`).
- Callback kopiuje próbki do **bufora kołowego** (ok. 2 s, numpy, zabezpieczony `threading.Lock`). Callback nie może robić nic poza kopiowaniem — żadnej analizy, alokacji ani logowania.
- Wizualizacja co klatkę czyta **najnowsze** N próbek z bufora.
- Lista urządzeń wejściowych w GUI z automatycznym podświetleniem BlackHole, jeśli jest dostępny. Jeśli nie ma — komunikat z linkiem do instrukcji z `docs/user-guide/`.
- **Nagrywanie sesji na żywo:** przycisk REC zapisuje przychodzące audio do WAV (`soundfile.SoundFile` w trybie zapisu, zapis w osobnym wątku przez kolejkę). Nagranie można potem wyeksportować do MP4 tak jak zwykły plik — eksport zawsze odbywa się offline z pliku, co gwarantuje płynne wideo w pełnej jakości.

Rozszerzenie na później (poza zakresem podstawowym): natywne Core Audio Process Taps (macOS 14.2+) przez helper w Swift, bez potrzeby instalowania BlackHole.

## 6. Architektura

```
osciviz/
├── app.py                    # punkt wejścia, QSurfaceFormat, QApplication
├── core/
│   ├── audio_source.py       # abstrakcja AudioSource + FileSource, LiveSource
│   ├── audio_player.py       # odtwarzanie pliku (sounddevice OutputStream), zegar
│   ├── ring_buffer.py        # bufor kołowy dla trybu na żywo
│   ├── recorder.py           # nagrywanie sesji na żywo do WAV
│   ├── analysis.py           # okna sygnału, FFT, energie pasm, obwiednie
│   └── image_to_points.py    # OpenCV → chmura punktów + kolory
├── scene/
│   ├── scene.py              # Scene: proporcje, tło, lista warstw, sygnały zmian
│   ├── layers.py             # klasy warstw (czyste dane + parametry)
│   ├── transform.py          # Transform, macierze 3x3, odwrotność, hit test
│   ├── particles.py          # stan i fizyka cząsteczek (numpy)
│   └── commands.py           # QUndoCommand dla każdej edycji
├── render/
│   ├── renderer.py           # Renderer: render(scene, frame_ctx, target_fbo)
│   ├── line_mesh.py          # generowanie pasków trójkątów z linii (grubość)
│   ├── postfx.py             # glow (blur + additive), persistence
│   └── shaders/              # *.vert, *.frag, #version 410 core
├── gui/
│   ├── main_window.py
│   ├── canvas_widget.py      # QOpenGLWidget: podgląd, kamera, mysz, uchwyty, siatka
│   ├── layer_panel.py
│   ├── inspector.py          # dynamiczny formularz parametrów warstwy
│   ├── timeline.py           # pasek czasu, play/pauza, przewijanie
│   ├── source_panel.py       # wybór źródła: plik / na żywo, urządzenie, REC
│   ├── export_dialog.py
│   ├── settings_dialog.py    # motyw, język
│   └── themes/               # dark.qss, light.qss, high_contrast.qss
├── io/
│   ├── project_io.py         # zapis/odczyt .osv
│   ├── presets.py            # import/eksport presetów warstw
│   └── exporter.py           # PNG + MP4 (QThread, postęp, anulowanie)
├── i18n/                     # osciviz_pl.ts, osciviz_en.ts, *.qm
├── tests/
└── docs/
    ├── technical/
    └── user-guide/
```

### Zasady architektury

- **Scena to czyste dane** — moduł `scene/` nie importuje OpenGL ani widgetów Qt (wyjątek: `commands.py` używa `QUndoCommand`, a `scene.py` może używać `QObject` i sygnałów).
- **Renderer jest bezstanowy względem GUI** — dostaje scenę, kontekst klatki (`FrameContext`: czas, próbki, wyniki analizy) i docelowe FBO. Ten sam kod renderuje podgląd, PNG i MP4.
- **GUI zmienia scenę wyłącznie przez komendy undo** — nigdy bezpośrednio.
- **Źródło audio za interfejsem** `AudioSource` z metodą `get_window(n_samples) -> np.ndarray` (kształt `(n, 2)`, float32), dzięki czemu analiza i warstwy nie wiedzą, czy dźwięk jest z pliku, czy na żywo.

## 7. Układ współrzędnych i interakcja

### Współrzędne

- Przestrzeń sceny: krótszy bok płótna ma zakres `[-1, 1]`, dłuższy jest skalowany proporcjami (np. 16:9 → X w `[-16/9, 16/9]`, Y w `[-1, 1]`). Oś Y w górę.
- Projekt wygląda identycznie w każdej rozdzielczości eksportu.
- Kamera podglądu (zoom kółkiem względem kursora, przesuwanie środkowym przyciskiem lub Spacja+przeciąganie) jest **niezależna** od kadru eksportu, pokazanego jako ramka z przyciemnionym otoczeniem.
- Siatka z regulowanym krokiem, linijki na krawędziach, osie przez środek.

### Transformacje

- `Transform(x, y, sx, sy, rotation_deg)` → macierz 3×3 (translacja · rotacja · skala).
- Hit test: punkt kliknięcia → przestrzeń sceny → macierz odwrotna warstwy → test z lokalnym prostokątem ograniczającym warstwy.
- Kolejność zaznaczania: od najwyższej warstwy.

### Mysz

| Akcja | Efekt |
|---|---|
| Klik | Zaznacz warstwę |
| Shift+klik | Dodaj/usuń z zaznaczenia |
| Przeciąganie po pustym | Zaznaczanie prostokątem |
| Przeciąganie warstwy | Przesuń |
| Uchwyty narożne/boczne | Skaluj (Shift: zachowaj proporcje, Alt: względem środka) |
| Uchwyt rotacji | Obróć (Ctrl: co 15°) |
| Kółko | Zoom widoku |
| Środkowy przycisk / Spacja+lewy | Przesuń widok |
| Prawy przycisk | Menu kontekstowe (duplikuj, usuń, w górę/w dół, zapisz preset) |

### Klawiatura

| Skrót | Akcja |
|---|---|
| Strzałki / Shift+strzałki | Przesuń o mały / duży krok |
| R / Shift+R | Obróć o +5° / −5° |
| + / − | Skaluj |
| Delete / Backspace | Usuń zaznaczone |
| Cmd+D | Duplikuj |
| Cmd+Z / Cmd+Shift+Z | Cofnij / Ponów |
| Cmd+S / Cmd+O / Cmd+N | Zapisz / Otwórz / Nowy |
| Cmd+E | Eksport MP4 |
| Cmd+Shift+S | Zrzut PNG |
| Spacja | Play/pauza (gdy płótno nie przeciąga) |
| G | Pokaż/ukryj siatkę |
| Tab | Następna warstwa |

Skróty definiowane przez `QKeySequence` — na macOS `Ctrl` w Qt mapuje się na Cmd automatycznie.

## 8. Analiza audio i synchronizacja

### Tryb plik

- Cały plik wczytany do numpy `(n, 2)` float32 (mono → duplikacja kanału).
- `AudioPlayer` odtwarza przez `sounddevice.OutputStream`; callback przesuwa licznik próbek. **Licznik próbek to zegar nadrzędny.**
- `QTimer` ~60 Hz w GUI: odczytaj pozycję → pobierz okno → analiza → `update()` płótna.

### Tryb na żywo

- Zegar = „teraz”; okno to najnowsze próbki z bufora kołowego.
- Oś czasu pokazuje tylko status (na żywo / nagrywanie + czas nagrania).

### Analiza (`analysis.py`)

- Okno Hann, FFT przez `np.fft.rfft`, rozmiar 2048 (konfigurowalny).
- Energie pasm: bas (domyślnie 20–150 Hz), średnie (150–2000 Hz), wysokie (2000–16000 Hz), w dB, znormalizowane do `[0, 1]`.
- Obwiednia z osobnym attack i release (wygładzanie wykładnicze).
- Funkcje czyste tam, gdzie to możliwe — łatwe testy jednostkowe na sygnałach syntetycznych (sinus o znanej częstotliwości).

### Determinizm eksportu

Stan zależny od historii (obwiednie, fizyka cząsteczek, persistence XY) przy eksporcie jest liczony klatka po klatce od początku zakresu ze stałym krokiem `dt = 1/fps`. Ziarno losowości (`np.random.default_rng(seed)`) zapisane w projekcie.

## 9. Tryb cząsteczek (przetwarzanie obrazu)

### Przygotowanie (`image_to_points.py`, raz po wczytaniu obrazu)

1. `cv2.imread` (z kanałem alfa), skalowanie do maks. 1024 px na dłuższym boku, konwersja BGR→RGB.
2. Metoda próbkowania (wybór w inspektorze):
   - **jasność** — prawdopodobieństwo wylosowania piksela proporcjonalne do jasności (opcja odwrócenia),
   - **krawędzie** — `cv2.GaussianBlur` + `cv2.Canny`, próbkowanie z pikseli krawędzi,
   - **alfa** — piksele z alfą > progu (logo w PNG).
3. Losowanie N punktów (1k–100k) bez pętli: `rng.choice` na spłaszczonych indeksach z wagami.
4. Wynik: `rest_pos (N, 2)` w lokalnych współrzędnych warstwy, `colors (N, 4)`.
5. Wynik cache'owany (ponowne obliczenie tylko przy zmianie obrazu, metody lub N).

### Symulacja (`scene/particles.py`, co klatkę)

```
force = push(direction, strength * bass_energy) + k * (rest_pos - pos) - damping * vel
vel  += force * dt
pos  += vel * dt
```

- Kierunki wypychania do wyboru: promieniowo od środka, wzdłuż szumu (pole wektorowe), losowy jitter.
- Opcjonalnie: średnie pasmo → jasność, wysokie pasmo → rozmiar punktów.
- Wszystko jako operacje numpy na całych tablicach. **Zero pętli Pythona po cząsteczkach.**
- Render: jeden VBO z pozycjami i kolorami, `ctx.POINTS`, okrągłe punkty z miękką krawędzią w fragment shaderze, mieszanie additive.

## 10. Renderowanie

- Linie z grubością: nie używamy `glLineWidth` (na macOS Core Profile obsługuje tylko szerokość 1). `line_mesh.py` generuje pasek trójkątów: dla każdego punktu normalna × połowa grubości, wierzchołki po obu stronach, połączenia miter z ograniczeniem.
- Glow: render warstwy do osobnego FBO → rozmycie Gaussa (2 przebiegi, poziomy i pionowy) → nałożenie additive.
- Persistence XY: FBO akumulacyjne, co klatkę przyciemniane mnożnikiem `< 1`.
- Antyaliasing: MSAA 4×.
- Kolejność rysowania = kolejność warstw w panelu.
- Uchwyty, siatka i ramka zaznaczenia rysowane wyłącznie w podglądzie (flaga `editor_overlay`), nigdy w eksporcie.

## 11. Zapis, import i eksport

### Plik projektu `.osv`

Archiwum ZIP:
```
project.json        # format_version, aspect_ratio, background, seed, layers[], audio_ref
assets/
  audio.<ext>       # kopia pliku audio lub nagrania
  images/*.png      # obrazy warstw cząsteczek
```
- `format_version` + funkcja migracji starszych wersji.
- Walidacja przy odczycie; czytelny komunikat błędu zamiast wyjątku.
- Zapis atomowy (plik tymczasowy → zamiana).

### Presety

Pojedyncza warstwa jako `.json` (parametry bez transformacji), import i eksport z menu kontekstowego. Kilka presetów wbudowanych (np. „Neon”, „CRT zielony”, „Retro XY”).

### Eksport PNG

Render sceny do offscreen FBO w docelowej rozdzielczości → `fbo.read()` → odwrócenie osi Y → Pillow → zapis.

### Eksport MP4

- Okno: rozdzielczość (presety zależne od proporcji, np. 16:9 → 1280×720 / 1920×1080 / 3840×2160), FPS (30/60), jakość (CRF), koder (`libx264` / `h264_videotoolbox`), zakres czasu, ścieżka.
- Działa w `QThread` z **własnym** kontekstem moderngl (`moderngl.create_standalone_context()`), aby nie blokować GUI i nie kolidować z kontekstem podglądu.
- Dla każdej klatki `t = start + i / fps`: analiza → symulacja → render do FBO → surowe RGB do potoku ffmpeg (`imageio_ffmpeg.write_frames`).
- Po zakończeniu: dołączenie ścieżki audio z pliku źródłowego (przycięcie do zakresu) → H.264 + AAC, `-pix_fmt yuv420p`, `-movflags +faststart`.
- Pasek postępu, szacowany czas, anulowanie (z usunięciem niekompletnego pliku).
- W trybie na żywo eksport dostępny po nagraniu sesji (sekcja 5).

## 12. Etapy realizacji (pod harmonogram 7 spotkań)

### Etap 1 — przed spotkaniem 1 (prezentacja planu)
- Repozytorium, struktura katalogów, `requirements.txt`, `ruff`, `pytest`, `.gitignore`, README.
- Mockupy okna (Figma lub szkic).
- **Akceptacja:** `python -m osciviz` otwiera puste okno główne z menu i panelami-zaślepkami.

### Etap 2 — przed spotkaniem 2
- `QSurfaceFormat` 4.1 Core, `CanvasWidget` z moderngl, obsługa Retiny.
- `FileSource` + `AudioPlayer`, przycisk play/pauza.
- Pierwsza `WaveformLayer` renderowana na żywo (na razie linia o grubości 1).
- **Akceptacja:** wczytany WAV/MP3 gra, a fala na ekranie porusza się zgodnie z dźwiękiem, bez opóźnień widocznych gołym okiem.

### Etap 3 — przed spotkaniem 3
- `Scene`, `Transform`, lista warstw, proporcje płótna, siatka, kamera podglądu.
- Zaznaczanie i przesuwanie myszą, hit test, ramka zaznaczenia.
- `line_mesh.py` — linie z grubością.
- Testy jednostkowe: transformacje, hit test, analiza na sinusach.
- **Akceptacja:** można dodać kilka fal, zmienić proporcje płótna i przeciągać fale myszą.

### Etap 4 — przed spotkaniem 4 (pierwszy prototyp)
- `XYLayer`, `SpectrumLayer`, inspektor właściwości, panel warstw.
- Motywy (3), `QSettings`.
- `LiveSource` + BlackHole, panel źródła.
- Zapis/odczyt `.osv` (podstawowy).
- Pierwszy test paczki `.app` przez PyInstaller.
- **Akceptacja:** demo z FL Studio na żywo — trzy typy warstw reagują na muzykę; projekt zapisuje się i wczytuje.

### Etap 5 — przed spotkaniem 5
- `image_to_points.py` (3 metody próbkowania), `ParticleLayer`, fizyka, shader punktów.
- Uchwyty skalowania i rotacji, undo/redo dla wszystkich operacji, skróty klawiszowe.
- **Akceptacja:** obraz rozpada się w cząsteczki reagujące na stopę; każdą edycję da się cofnąć.

### Etap 6 — przed spotkaniem 6
- Eksport PNG i MP4 (wątek, postęp, anulowanie, audio w pliku).
- Nagrywanie sesji na żywo do WAV.
- Glow, persistence, presety.
- Tłumaczenie EN, przełączanie języka.
- **Akceptacja:** 30-sekundowy fragment eksportuje się do MP4 1080p60 z dźwiękiem, odtwarzalny w QuickTime.

### Etap 7 — przed spotkaniem 7 (finał)
- Optymalizacja wydajności (profilowanie `cProfile`), poprawki błędów.
- Paczka `.app` z uprawnieniem mikrofonu, testy na czystym Macu.
- Dokumentacja techniczna i instrukcja obsługi (w tym konfiguracja BlackHole) ze zrzutami ekranu.
- **Akceptacja:** pełne demo na prezentacji bez uruchamiania z terminala.

## 13. Podział ról (5 osób)

| Rola | Zakres (właściciel modułów) |
|---|---|
| **1. Lider — scena i interakcja** | `scene/scene.py`, `transform.py`, `commands.py`, interakcja w `canvas_widget.py`, integracja, code review, raporty na spotkania |
| **2. Audio** | `core/audio_*`, `ring_buffer.py`, `recorder.py`, `analysis.py`, konfiguracja BlackHole, muxowanie audio w MP4 |
| **3. Renderowanie** | `render/` (renderer, shadery, linie, glow, persistence), warstwy Waveform/XY/Spectrum, eksport PNG, kontekst offscreen do MP4 |
| **4. Obraz i cząsteczki** | `image_to_points.py`, `scene/particles.py`, `ParticleLayer` i jej shader, pipeline klatek w eksporcie MP4 |
| **5. GUI i dokumentacja** | `gui/` (poza interakcją na płótnie), inspektor, oś czasu, motywy, i18n, `project_io.py`, `presets.py`, MkDocs, paczka `.app` |

Zasady współpracy:
- Gałąź na funkcję (`feature/<nazwa>`), Pull Request do `main`, **każdy PR przegląda inna osoba**.
- GitHub Issues + Projects jako tablica zadań — z niej powstają 5-minutowe raporty lidera.
- Każdy właściciel opisuje swój moduł w `docs/technical/` własnymi słowami.

## 14. Testy

- `tests/test_transform.py` — złożenie i odwrotność macierzy, hit test po rotacji i skali.
- `tests/test_analysis.py` — sinus 60 Hz daje maksimum energii w paśmie basu; sinus 5 kHz — w paśmie wysokim.
- `tests/test_ring_buffer.py` — zawijanie, odczyt najnowszych próbek.
- `tests/test_image_to_points.py` — liczba punktów, zakres współrzędnych, kolory z obrazu testowego.
- `tests/test_project_io.py` — zapis → odczyt daje identyczną scenę; obsługa uszkodzonego pliku.
- `tests/test_particles.py` — bez basu cząsteczki wracają do pozycji spoczynkowych.

## 15. Ryzyka

| Ryzyko | Ograniczenie |
|---|---|
| Wydajność Pythona | Tylko numpy na całych tablicach, rysowanie na GPU, niższy limit cząsteczek w podglądzie niż w eksporcie |
| OpenGL 4.1 na macOS | Brak compute shaderów — fizyka w numpy; grube linie jako trójkąty |
| Retina | Konsekwentne mnożenie przez `devicePixelRatio()` w viewport i myszy |
| Brak zgody na mikrofon | `NSMicrophoneUsageDescription`, komunikat w GUI, instrukcja w dokumentacji |
| BlackHole nie zainstalowany | Wykrywanie urządzenia, czytelny komunikat, tryb plikowy działa niezależnie |
| Dryf audio z FL Studio | Korekcja dryfu w Multi-Output Device; tryb na żywo nie zależy od zegara pliku |
| Pakowanie `.app` | Pierwszy test w etapie 4, nie tuż przed finałem |
| Wymóg zrozumienia kodu bez AI | Właściciel modułu, review przez drugą osobę, dokumentacja modułów |
