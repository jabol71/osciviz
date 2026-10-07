# Cząsteczki (`core/image_to_points.py`, `scene/particles.py`)

## Obraz → punkty

1. Wczytanie z alfą (`cv2.imdecode(..., IMREAD_UNCHANGED)` — działa też ze ścieżkami
   z polskimi znakami), zmniejszenie do 1024 px na dłuższym boku, BGR(A) → RGBA.
2. **Wagi pikseli**:
    - *jasność* — `0.2126 R + 0.7152 G + 0.0722 B` (Rec. 709) razy alfa; opcja odwrócenia,
    - *krawędzie* — `GaussianBlur` (odszumienie) + `Canny`; próg sterowany suwakiem,
    - *alfa* — piksele z alfą powyżej progu.
3. **Losowanie bez pętli**: `rng.choice(liczba_pikseli, N, p=wagi/Σwagi)` na spłaszczonej
   tablicy, potem `divmod(indeks, szerokość)` → (wiersz, kolumna).
4. Losowe przesunięcie w obrębie piksela (żeby nie było widać siatki) i przeliczenie:
   środek obrazu → (0, 0), dłuższy bok → [−1, 1], oś Y odwrócona.
5. Wynik jest cache'owany (`lru_cache`) — przeliczenie tylko przy zmianie obrazu,
   metody, liczby, progu lub ziarna.

## Fizyka

```
F   = kierunek · siła · bas · w      # wypchnięcie (w ∈ [0.5, 1.5] — indywidualna czułość)
    + k · (rest − pos)                # sprężyna do pozycji w obrazie
    − c · vel                         # tłumienie
vel += F · dt                         # półjawny Euler: najpierw prędkość,
pos += vel · dt                       # potem pozycja nową prędkością
```

Półjawny Euler jest stabilniejszy niż zwykły dla sprężyn. Gdy `dt·√k > 0.25`, krok dzielimy
na podkroki. Wszystko to operacje numpy na tablicach `(N, 2)` — **zero pętli po cząsteczkach**.

**Kierunki**: promieniowo (wektor jednostkowy od środka, liczony raz), pole szumu
(kąt `θ = π·(sin(3.1x + 0.9t) + cos(2.7y − 0.6t))`) albo losowe drgania.

**Sterowanie basem**: energia pasma `bas od–do` przechodzi przez **bramkę czułości**
`max(0, e − próg)/(1 − próg)`, jest podnoszona do kwadratu (wyraźne uderzenia, spokój
między nimi) i wygładzana obwiednią (attack 8 ms, release 120 ms).

## Rysowanie

Jeden VBO `(N, 6)`: pozycja lokalna + kolor RGBA. Vertex shader mnoży przez macierz warstwy
i widoku, `gl_PointSize` = rozmiar w pikselach. Fragment shader robi okrągły punkt z miękką
krawędzią (`gl_PointCoord`), mieszanie addytywne — gęste skupiska świecą mocniej.
