"""OsciViz — programowy oscyloskop i edytor wizualizacji audio.

Pakiet jest podzielony na warstwy odpowiedzialności:

- ``core``   — audio (pliki, przechwytywanie na żywo, analiza) i obraz,
- ``scene``  — czyste dane sceny: warstwy, transformacje, komendy undo, fizyka,
- ``render`` — renderowanie OpenGL (moderngl) wspólne dla podglądu i eksportu,
- ``gui``    — okno główne i widżety PySide6,
- ``io``     — zapis/odczyt projektu, presety, eksport PNG/MP4.
"""

__version__ = "1.0.0"
APP_NAME = "OsciViz"
ORG_NAME = "OsciViz"
