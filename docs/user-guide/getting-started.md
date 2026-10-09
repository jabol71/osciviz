# Pierwsze kroki

## Instalacja

### Gotowa aplikacja — macOS (.app)

1. Pobierz `OsciViz-macOS-arm64.zip` (Apple Silicon) lub `OsciViz-macOS-x86_64.zip` (Intel)
   z **Releases** albo z zakładki **Actions → Build macOS app** (artefakt ostatniego przebiegu).
2. Rozpakuj i przeciągnij `OsciViz.app` do folderu **Programy**.
3. Przy pierwszym uruchomieniu kliknij aplikację prawym przyciskiem → **Otwórz** (aplikacja
   nie jest podpisana certyfikatem Apple, więc Gatekeeper zapyta o zgodę).

### Gotowa aplikacja — Windows 10/11

1. Pobierz z **Releases** albo z zakładki **Actions → Build Windows app** jedną z wersji:
    - `OsciViz-Windows-x64-setup.exe` — instalator: skrót w menu Start, skojarzenie plików `.osv`,
      odinstalowanie z Ustawień systemu,
    - `OsciViz-Windows-x64.zip` — wersja przenośna: rozpakuj i uruchom `OsciViz.exe`.
2. Program nie jest podpisany certyfikatem, więc SmartScreen może pokazać ostrzeżenie
   „System Windows ochronił komputer”. Kliknij **Więcej informacji → Uruchom mimo to**.
3. Potrzebna jest karta graficzna ze sterownikiem obsługującym OpenGL 4.1 (każda karta z ostatnich
   ~10 lat). W maszynie wirtualnej albo przez Pulpit zdalny podgląd może być niedostępny.

### Ze źródeł

macOS:

```bash
git clone https://github.com/jabol71/osciviz.git
cd osciviz
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m osciviz
```

Windows (PowerShell, Python 3.12 z python.org lub Microsoft Store):

```powershell
git clone https://github.com/jabol71/osciviz.git
cd osciviz
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m osciviz
```

## Pierwsze uruchomienie

Przy pierwszym starcie otwiera się **projekt demonstracyjny**: syntetyczny utwór (stopa,
bas, akordy, arpeggio) i po jednej warstwie każdego typu. Naciśnij **Spację** albo
przycisk ▶ na osi czasu — wszystkie warstwy zaczną reagować na muzykę.
Projekt demonstracyjny możesz otworzyć ponownie z menu **Plik → Wczytaj projekt demonstracyjny**.

## Twoja pierwsza wizualizacja w 5 krokach

1. **Plik → Nowy projekt** (⌘N, na Windows Ctrl+N).
2. W panelu **Płótno** (widoczny, gdy nic nie jest zaznaczone) wybierz proporcje, np. 9:16
   dla rolek lub 16:9 dla YouTube.
3. **Plik → Importuj audio…** (⌘I / Ctrl+I) i wybierz plik WAV, FLAC, MP3, OGG lub AIFF.
4. Dodaj warstwy przyciskami u góry okna: **Fala**, **Oscyloskop XY**, **Widmo**, **Cząsteczki**.
   Przeciągaj je po płótnie, skaluj uchwytami, zmieniaj parametry w inspektorze po prawej.
5. **Eksport** (⌘E / Ctrl+E) → wybierz rozdzielczość i FPS → gotowy plik MP4 z dźwiękiem.

!!! tip "Presety"
    Lista **Presety…** w inspektorze ma gotowe style: „Neon”, „CRT zielony”, „Retro XY”,
    „Goniometr”, „Pierścień”, „Puls basu” i inne. Własne ustawienia zapiszesz ikoną dyskietki obok.
