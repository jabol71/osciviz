# Audio (`core/audio_*.py`, `ring_buffer.py`, `recorder.py`)

## Źródła

- `FileSource` wczytuje cały plik przez `soundfile` do tablicy `(n, 2)` float32 (mono jest
  duplikowane). `window_at(end, n)` zwraca `n` próbek kończących się na `end`, z zerami poza
  plikiem — dzięki temu początek i koniec utworu nie wymagają specjalnej obsługi.
- `LiveSource` otwiera `sounddevice.InputStream` (stereo, częstotliwość urządzenia,
  `blocksize=512`). Callback **tylko kopiuje** blok do bufora kołowego (i ewentualnie do kolejki
  nagrywarki). W wątku audio nie wolno analizować, alokować ani logować — groziłoby to
  przerwami w dźwięku.

## Zegar i synchronizacja

`AudioPlayer` odtwarza plik przez `sounddevice.OutputStream`. Callback kopiuje kolejny blok
i przesuwa **licznik próbek** — to on jest zegarem nadrzędnym. GUI co klatkę czyta licznik,
więc obraz zawsze pokazuje to, co właśnie słychać. Gdy PortAudio jest niedostępne (np. w CI),
odtwarzacz liczy czas z `time.perf_counter()` — wizualizacja działa bez dźwięku.

## Bufor kołowy

Stała tablica `(capacity, 2)` i indeks zapisu. Zapis bloku dłuższego niż miejsce do końca
tablicy dzieli się na dwie części (koniec + początek). `latest(n)` odtwarza kolejność
„od najstarszej” tym samym podziałem. Obie operacje są chronione `threading.Lock` — sekcja
krytyczna to tylko kopiowanie, więc blokada trwa mikrosekundy.

## Nagrywanie

`Recorder.push()` (wywoływane z callbacku) wrzuca kopię bloku do `queue.Queue`. Osobny
wątek wyjmuje bloki i dopisuje je do `soundfile.SoundFile` (WAV 24-bit). `stop()` wstawia
znacznik końca i czeka na zapis reszty kolejki.
