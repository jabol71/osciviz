# Budowanie, testy i paczka .app

## Środowisko deweloperskie

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
python -m osciviz          # uruchomienie
pytest                     # testy
ruff check .               # linting
mkdocs serve               # podgląd dokumentacji na http://127.0.0.1:8000
```

## Testy

| Plik | Co sprawdza |
|---|---|
| `test_transform.py` | złożenie i odwrotność macierzy, hit test po obrocie i skali |
| `test_analysis.py` | sinus 60 Hz → maksimum w basie, 5 kHz → w wysokich; skala amplitudy; obwiednia |
| `test_ring_buffer.py` | zawijanie, kolejność, dopełnianie zerami, blok większy niż bufor |
| `test_image_to_points.py` | liczba punktów, zakres współrzędnych, kolory z obrazu, wszystkie metody |
| `test_particles.py` | bez basu cząsteczki wracają do spoczynku; stabilność przy dużym kroku |
| `test_project_io.py` | zapis → odczyt daje identyczną scenę; uszkodzony plik; migracja v1 |
| `test_commands.py` | undo/redo, łączenie gestu w jeden krok, przycinanie parametrów |
| `test_render.py` | siatka linii, miter, wyzwalanie fali, render offscreen (gdy jest OpenGL) |

## Paczka `.app` (PyInstaller)

```bash
pip install pyinstaller
pyinstaller packaging/osciviz.spec --noconfirm
open dist/OsciViz.app
```

Specyfikacja dodaje do `Info.plist` **`NSMicrophoneUsageDescription`** (bez niego macOS nie
pozwoli czytać BlackHole), dołącza shadery, motywy, tłumaczenia i presety. Ikona
`packaging/OsciViz.icns` powstaje skryptem `python packaging/make_icon.py`.

Workflow **Build macOS app** (GitHub Actions) buduje paczkę na runnerze macOS i udostępnia
ją jako artefakty `OsciViz-macOS-arm64.zip` i `OsciViz-macOS-x86_64.zip` (oraz w wydaniu, gdy
wypchniesz tag `v*`) — można je pobrać bez instalowania Pythona.

## Profilowanie

```bash
python -m cProfile -o profile.out -m osciviz
python -c "import pstats; pstats.Stats('profile.out').sort_stats('cumtime').print_stats(25)"
```

Najcięższe elementy to rysowanie cząsteczek i rozmycie poświaty; w podglądzie liczba
cząsteczek jest ograniczona do 40 000 (`PREVIEW_MAX_PARTICLES`), eksport używa pełnej liczby.
