# Renderowanie (`render/`)

## Kontekst OpenGL

macOS obsługuje maksymalnie **OpenGL 4.1 Core Profile**, więc `app.py` ustawia
`QSurfaceFormat(4.1, CoreProfile, samples=4)` przed utworzeniem `QApplication`. Shadery są
w `#version 410 core`, bez compute shaderów (fizyka liczy się w numpy). W `CanvasWidget`
moderngl dołącza się do kontekstu Qt (`moderngl.create_context()` w `initializeGL`), a celem
jest FBO widżetu: `ctx.detect_framebuffer(self.defaultFramebufferObject())`.

**Retina**: framebuffer ma rozmiar `widżet × devicePixelRatio()`. Kamera i mysz liczą
w pikselach logicznych, a renderer dostaje rozmiar w pikselach urządzenia i
`px_per_unit = zoom · dpr`.

## Potok klatki (`Renderer.render`)

1. Tło kadru → tekstura sceny (RGBA16F — jasności > 1 nie są przycinane przed kompozycją).
2. Dla każdej widocznej warstwy:
    1. geometria → **bufor MSAA 4×** → `copy_framebuffer` (uśrednienie próbek) do tekstury warstwy,
    2. XY: akumulacja powidoku,
    3. poświata (jeśli > 0),
    4. nałożenie na scenę z kryciem: *normal* `(ONE, 1−SRC_ALPHA)`, *additive* `(ONE, ONE)`.
3. Scena → cel (ekran lub FBO eksportu) z lekkim mapowaniem tonów (Reinhard dla nadmiaru jasności).

Kolory w całym potoku mają **premnożoną alfę** (`rgb·a, a`) — krycie warstwy to po prostu
mnożenie wektora, a mieszanie jest poprawne bez artefaktów na krawędziach.

Siatka, linijki, ramki zaznaczenia i uchwyty są rysowane **tylko w podglądzie**, przez
`QPainter` na wierzchu (`beginNativePainting/endNativePainting` rozdziela stan OpenGL Qt
i moderngl). Eksport ich nie zawiera.

## Grube linie (`line_mesh.py`)

`glLineWidth` na macOS Core Profile obsługuje tylko 1 px, dlatego linie to paski trójkątów:

1. kierunek każdego odcinka `d` i normalna `n = (−d.y, d.x)`,
2. w wierzchołku — uśredniona styczna sąsiednich odcinków, prostopadły do niej kierunek *miter*,
3. długość miter `= hw / cos(α) = hw / dot(miter, n)`, ograniczona (`miter_limit`) przy ostrych kątach,
4. wierzchołki `P ± miter·długość`, dwa trójkąty na odcinek.

Każdy wierzchołek ma `u` (pozycja wzdłuż linii → gradient) i `v = ±1` (strona → miękka
krawędź w shaderze, ok. 1,2 px wygładzenia niezależnie od zoomu).

## Poświata (`postfx.py`)

Obraz warstwy → połowa rozdzielczości → rozmycie Gaussa w **dwóch przebiegach** (poziomy,
pionowy). Gauss jest separowalny, więc 2·N próbek zamiast N². Promień w „px przy 1080”
przeliczamy na piksele bieżącego celu, więc poświata wygląda tak samo w podglądzie i eksporcie.

## Powidok XY

Dwie tekstury akumulacji (ping-pong): `nowa = stara · decay + bieżąca`, gdzie
`decay = persistence^(dt·60)` — zanikanie nie zależy od liczby klatek na sekundę.

## Geometria warstw (`geometry.py`)

- **Fala**: okno `window_ms` z wybranego kanału; *wyzwalanie* szuka ostatniego przejścia
  przez zero „z dołu do góry” (jak trigger oscyloskopu), więc okresowy dźwięk stoi w miejscu.
  Maks. 1600 punktów (więcej nie da się zobaczyć).
- **XY**: L→X, R→Y (opcjonalnie obrót 45° — goniometr), starsza część śladu bledsza.
- **Widmo**: prostokąty (słupki) albo trapezy na okręgu; współrzędne liczone wektorowo.
