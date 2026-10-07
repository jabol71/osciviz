# Warstwy

Każda warstwa ma wspólne właściwości: **nazwę**, **transformację** (pozycja X/Y, szerokość
i wysokość jako skala, kąt), **krycie**, **tryb mieszania** (*normalne* — zasłania warstwy
pod spodem; *addytywne* — rozjaśnia, jak światło), **widoczność** i **blokadę**.

## Fala (oscyloskop czasowy)

Fragment sygnału narysowany jako linia — klasyczny widok oscyloskopu.

| Parametr | Znaczenie |
|---|---|
| Kolor, gradient | Kolor linii; gradient płynnie przechodzi od lewej do prawej |
| Grubość | W pikselach przy wysokości 1080 (skaluje się z rozdzielczością) |
| Liczba kopii, przesunięcie | Kilka równoległych, coraz bledszych kopii — efekt „echa” |
| Kanał | Mono, lewy lub prawy |
| Okno czasu | Ile milisekund sygnału widać naraz (krótkie okno = pojedyncze okresy) |
| Wzmocnienie | Mnożnik amplitudy |
| Wyzwalanie | Jak *trigger* w oscyloskopie: wyrównuje falę do zbocza, więc stały ton „stoi” |
| Poświata | Siła i promień świecenia linii |

## Oscyloskop XY

Lewy kanał steruje osią X, prawy osią Y. Dźwięk stereo rysuje figury Lissajous.

| Parametr | Znaczenie |
|---|---|
| Powidok | Jak długo ślad gaśnie (0 = brak, 0,95 = długa smuga jak w lampie CRT) |
| Długość śladu | Ile milisekund sygnału rysujemy w każdej klatce |
| Mid/side (obrót 45°) | Tryb goniometru: dźwięk mono staje się pionową kreską |

## Widmo

Widmo częstotliwości (FFT) jako słupki, słupki lustrzane albo pierścień.

| Parametr | Znaczenie |
|---|---|
| Tryb | Słupki, koło, słupki lustrzane |
| Liczba pasm, min./maks. częstotliwość | Ile słupków i jaki zakres Hz pokazują |
| Skala logarytmiczna | Pasma rozłożone jak słyszy człowiek (zalecane) |
| Wygładzanie | Słupki rosną od razu, a opadają płynnie |
| Próg szumu | Odcina najcichsze poziomy, żeby słupki „oddychały” |
| Promień wewnętrzny | Tylko dla koła |

## Cząsteczki

Obraz zamieniony na tysiące punktów, które **bas wypycha**, a sprężyna ściąga z powrotem.
Bez własnego obrazu używany jest napis „OSCIVIZ”.

| Parametr | Znaczenie |
|---|---|
| Obraz | PNG/JPG; dla logo z przezroczystością wybierz próbkowanie *kanał alfa* |
| Próbkowanie | *Jasność* (więcej punktów w jasnych miejscach), *krawędzie* (kontury), *kanał alfa* |
| Odwróć, próg | Odwrócenie jasności; próg dla krawędzi i alfy |
| Liczba cząsteczek | 1 000 – 100 000 (podgląd pokazuje maks. 40 000, eksport — wszystkie) |
| Bas od / do | Zakres częstotliwości, który „pcha” cząsteczki (np. 20–150 Hz = stopa) |
| Próg czułości | Poniżej tego poziomu bas nie rusza obrazu — tylko wyraźne uderzenia |
| Kierunek wypychania | Promieniowo od środka, wzdłuż pola szumu albo losowe drgania |
| Średnie → jasność, wysokie → rozmiar | Dodatkowe reakcje na inne pasma |
| Siła, sztywność, tłumienie | Fizyka: jak mocno pcha bas, jak szybko wracają, jak bardzo drgają |
