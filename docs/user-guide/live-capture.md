# Przechwytywanie dźwięku z FL Studio (na żywo)

OsciViz może wizualizować dźwięk, który właśnie gra w FL Studio. Sposób zależy od systemu:

| System | Jak | Instalacja dodatkowa |
|---|---|---|
| **Windows** | **Dźwięk systemu** (WASAPI loopback) — przechwytuje to, co gra na głośnikach | nie |
| Windows (opcjonalnie) | **VB-Cable** — wirtualny kabel, tylko dźwięk z FL Studio | tak |
| **macOS** | **BlackHole** — wirtualny kabel | tak |

## Windows: dźwięk systemu (bez instalacji)

1. W panelu **Źródło dźwięku** wybierz **Na żywo**.
2. Na liście jest wybrana pozycja **Dźwięk systemu: *Twoje głośniki*** (ikona głośnika) — to
   domyślne wyjście Windows. Jeśli FL Studio gra na innym wyjściu (np. słuchawkach USB),
   wybierz jego pozycję.
3. Kliknij **Rozpocznij nasłuch** i graj w FL Studio.

Ten sposób przechwytuje **wszystko**, co gra na danym wyjściu — także przeglądarkę czy
powiadomienia. Gdy nic nie gra, warstwy pokazują ciszę.

!!! warning "Sterownik ASIO w FL Studio"
    Loopback widzi tylko dźwięk przechodzący przez mikser Windows. W FL Studio
    (*Options → Audio settings → Device*) wybierz **FL Studio ASIO** albo **Primary Sound Driver**.
    Sterownik ASIO interfejsu audio (np. Focusrite USB ASIO) omija mikser Windows — wtedy
    użyj VB-Cable albo wejścia „loopback” w panelu sterowania samego interfejsu.

## Windows: VB-Cable (tylko FL Studio)

Jeśli chcesz wizualizować wyłącznie FL Studio, bez innych dźwięków systemu:

1. Pobierz i zainstaluj **VB-CABLE Virtual Audio Device** ze strony
   [vb-audio.com/Cable](https://vb-audio.com/Cable/) (instalator jako administrator), uruchom
   komputer ponownie.
2. **FL Studio** → *Options → Audio settings* → wyjście: **CABLE Input (VB-Audio Virtual Cable)**.
3. Żeby nadal słyszeć dźwięk: *Panel sterowania → Dźwięk → Nagrywanie → CABLE Output →
   Właściwości → Nasłuchiwanie* → zaznacz **Słuchaj tego urządzenia** i wybierz swoje głośniki.
4. W OsciViz wybierz na liście **CABLE Output** (podświetlone ikoną nadawania) i kliknij
   **Rozpocznij nasłuch**.

## macOS: BlackHole

macOS nie pozwala aplikacjom „podsłuchać” dźwięku innego programu, dlatego używamy darmowego
wirtualnego urządzenia audio **BlackHole**. FL Studio gra jednocześnie na głośniki i do
BlackHole, a OsciViz czyta BlackHole jak mikrofon.

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
4. W OsciViz: **Źródło dźwięku → Na żywo**. BlackHole jest wybierany automatycznie (ikona
   nadawania). Kliknij **Rozpocznij nasłuch**. Przy pierwszym razie macOS zapyta o dostęp do
   mikrofonu — zezwól.

## Nagrywanie sesji i eksport

Eksport MP4 zawsze odbywa się z pliku (offline), co gwarantuje płynne wideo w pełnej jakości.
Aby wyeksportować występ na żywo:

1. Podczas nasłuchu kliknij **● REC**. Oś czasu pokaże czas nagrania.
2. Kliknij **● REC** ponownie, aby zakończyć. Nagranie trafia do folderu *Muzyka/OsciViz*
   (`~/Music/OsciViz` na macOS, `C:\Users\<Ty>\Music\OsciViz` na Windows) jako `session-….wav`.
3. OsciViz zapyta, czy użyć nagrania jako dźwięku projektu — wybierz **Tak** i eksportuj jak zwykły plik.

## Rozwiązywanie problemów

| Problem | Rozwiązanie |
|---|---|
| Windows: warstwy się nie ruszają przy „Dźwięku systemu” | Sprawdź, czy wybrane jest wyjście, na którym gra FL Studio, i czy FL Studio nie używa sterownika ASIO interfejsu audio (patrz wyżej) |
| Windows: brak dostępu do mikrofonu (VB-Cable, mikrofon) | Ustawienia → Prywatność i zabezpieczenia → Mikrofon → włącz „Zezwalaj aplikacjom klasycznym na dostęp do mikrofonu” |
| Windows: nie widać CABLE Output | Zainstaluj VB-Cable jako administrator, uruchom komputer ponownie i kliknij ikonę odświeżania obok listy |
| macOS: „Nie znaleziono BlackHole” | Zainstaluj BlackHole i uruchom Maca ponownie, potem kliknij ikonę odświeżania obok listy urządzeń |
| macOS: warstwy się nie ruszają | Sprawdź, czy FL Studio gra na *Multi-Output Device*, a nie bezpośrednio na głośniki |
| macOS: brak dostępu do mikrofonu | Ustawienia systemowe → Prywatność i ochrona → Mikrofon → OsciViz |
| Trzaski lub rozjechany dźwięk (macOS) | W Multi-Output Device włącz korekcję dryfu dla BlackHole |
