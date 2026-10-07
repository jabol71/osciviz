# Projekty i eksport

## Projekt `.osv`

**Plik → Zapisz** (⌘S) zapisuje cały projekt w jednym pliku `.osv`: ustawienia płótna, wszystkie
warstwy, **kopię pliku audio** i **obrazy warstw cząsteczek**. Projekt można więc przenieść na
inny komputer bez szukania plików. Zapis jest bezpieczny — przerwany zapis nie niszczy
poprzedniej wersji.

## Zrzut PNG

Ikona aparatu lub **⇧⌘S** — bieżąca klatka w rozdzielczości 4K (dłuższy bok zgodny z proporcjami),
bez siatki, uchwytów i ramek.

## Wideo MP4

**Eksport** (⌘E) otwiera okno eksportu:

| Opcja | Opis |
|---|---|
| Rozdzielczość | 720p, 1080p, 1440p lub 4K, dopasowane do proporcji płótna |
| Klatki na sekundę | 30 lub 60 |
| Jakość (CRF) | 12–32; mniej = lepsza jakość. 18 to jakość wizualnie bezstratna |
| Koder | *libx264* (najlepsza jakość) lub *VideoToolbox* (sprzętowy, dużo szybszy na Macu) |
| Od → do | Zakres czasu w sekundach |
| Dołącz dźwięk | Ścieżka AAC przycięta do zakresu |

Eksport działa w tle — możesz dalej korzystać z aplikacji. Pasek pokazuje postęp i szacowany
pozostały czas; **Anuluj** przerywa eksport i usuwa niedokończony plik. Wynik (H.264 + AAC,
`yuv420p`, `faststart`) odtwarza się w QuickTime, przeglądarkach i mediach społecznościowych.

Eksport liczy wszystko od początku zakresu ze stałym krokiem czasu, więc ten sam projekt zawsze
daje identyczne wideo (ziarno losowości cząsteczek jest zapisane w projekcie).

## Presety warstw

- **Zapisz jako preset** (ikona dyskietki w inspektorze lub prawy przycisk na warstwie) —
  zapamiętuje parametry warstwy (bez położenia).
- **Plik → Eksportuj preset warstwy…** — zapis do pliku `.json`, np. dla kolegi z zespołu.
- **Plik → Importuj preset warstwy…** — dodaje preset do listy (i od razu stosuje go do
  zaznaczonej warstwy tego samego typu).
