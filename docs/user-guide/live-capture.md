# Przechwytywanie dźwięku z FL Studio (na żywo)

macOS nie pozwala aplikacjom „podsłuchać” dźwięku innego programu, dlatego używamy darmowego
wirtualnego urządzenia audio **BlackHole**. FL Studio gra jednocześnie na głośniki i do
BlackHole, a OsciViz czyta BlackHole jak mikrofon.

## Jednorazowa konfiguracja

1. **Zainstaluj BlackHole 2ch**
   ```bash
   brew install blackhole-2ch
   ```
   albo pobierz instalator ze strony [Existential Audio](https://existential.audio/blackhole/).
   Po instalacji wyloguj się i zaloguj ponownie (lub uruchom Maca ponownie).
2. **Utwórz urządzenie wielowyjściowe** — otwórz *Konfiguracja audio MIDI* (Audio MIDI Setup),
   kliknij **+** → **Utwórz urządzenie wielowyjściowe** (*Create Multi-Output Device*) i zaznacz:
    - swoje głośniki lub słuchawki — ustaw je jako **urządzenie główne** (*Primary/Master*),
    - **BlackHole 2ch** — z włączoną **korekcją dryfu** (*Drift Correction*).
3. **FL Studio** → *Options → Audio settings* → urządzenie wyjściowe: utworzone
   *Multi-Output Device*. Dźwięk słychać normalnie, a jednocześnie trafia do BlackHole.

## W OsciViz

1. W panelu **Źródło dźwięku** wybierz **Na żywo**.
2. Na liście urządzeń BlackHole jest wybierany automatycznie (oznaczony ikoną nadawania).
3. Kliknij **Rozpocznij nasłuch**. Przy pierwszym razie macOS zapyta o dostęp do mikrofonu —
   zezwól. Jeśli przypadkiem odmówiłeś: *Ustawienia systemowe → Prywatność i ochrona →
   Mikrofon* → włącz OsciViz.
4. Graj w FL Studio — warstwy reagują na żywo.

## Nagrywanie sesji i eksport

Eksport MP4 zawsze odbywa się z pliku (offline), co gwarantuje płynne wideo w pełnej jakości.
Aby wyeksportować występ na żywo:

1. Podczas nasłuchu kliknij **● REC**. Oś czasu pokaże czas nagrania.
2. Kliknij **● REC** ponownie, aby zakończyć. Nagranie trafia do `~/Music/OsciViz/session-….wav`.
3. OsciViz zapyta, czy użyć nagrania jako dźwięku projektu — wybierz **Tak** i eksportuj jak zwykły plik.

## Rozwiązywanie problemów

| Problem | Rozwiązanie |
|---|---|
| „Nie znaleziono BlackHole” | Zainstaluj BlackHole i uruchom Maca ponownie, potem kliknij ikonę odświeżania obok listy urządzeń |
| Warstwy się nie ruszają | Sprawdź, czy FL Studio gra na *Multi-Output Device*, a nie bezpośrednio na głośniki |
| Brak dostępu do mikrofonu | Ustawienia systemowe → Prywatność i ochrona → Mikrofon → OsciViz |
| Trzaski lub rozjechany dźwięk | W Multi-Output Device włącz korekcję dryfu dla BlackHole |
