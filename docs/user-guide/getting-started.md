# Pierwsze kroki

## Instalacja

### Gotowa aplikacja (.app)

1. Pobierz `OsciViz-macOS-arm64.zip` (Apple Silicon) lub `OsciViz-macOS-x86_64.zip` (Intel)
   z **Releases** albo z zakładki **Actions → Build macOS app** (artefakt ostatniego przebiegu).
2. Rozpakuj i przeciągnij `OsciViz.app` do folderu **Programy**.
3. Przy pierwszym uruchomieniu kliknij aplikację prawym przyciskiem → **Otwórz** (aplikacja
   nie jest podpisana certyfikatem Apple, więc Gatekeeper zapyta o zgodę).

### Ze źródeł

```bash
git clone https://github.com/jabol71/osciviz.git
cd osciviz
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m osciviz
```

## Pierwsze uruchomienie

Przy pierwszym starcie otwiera się **projekt demonstracyjny**: syntetyczny utwór (stopa,
bas, akordy, arpeggio) i po jednej warstwie każdego typu. Naciśnij **Spację** albo
przycisk ▶ na osi czasu — wszystkie warstwy zaczną reagować na muzykę.
Projekt demonstracyjny możesz otworzyć ponownie z menu **Plik → Wczytaj projekt demonstracyjny**.

## Twoja pierwsza wizualizacja w 5 krokach

1. **Plik → Nowy projekt** (⌘N).
2. W panelu **Płótno** (widoczny, gdy nic nie jest zaznaczone) wybierz proporcje, np. 9:16
   dla rolek lub 16:9 dla YouTube.
3. **Plik → Importuj audio…** (⌘I) i wybierz plik WAV, FLAC, MP3, OGG lub AIFF.
4. Dodaj warstwy przyciskami u góry okna: **Fala**, **Oscyloskop XY**, **Widmo**, **Cząsteczki**.
   Przeciągaj je po płótnie, skaluj uchwytami, zmieniaj parametry w inspektorze po prawej.
5. **Eksport** (⌘E) → wybierz rozdzielczość i FPS → gotowy plik MP4 z dźwiękiem.

!!! tip "Presety"
    Lista **Presety…** w inspektorze ma gotowe style: „Neon”, „CRT zielony”, „Retro XY”,
    „Goniometr”, „Pierścień”, „Puls basu” i inne. Własne ustawienia zapiszesz ikoną dyskietki obok.
