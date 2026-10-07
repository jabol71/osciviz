# Analiza sygnału (`core/analysis.py`)

## FFT krok po kroku

1. **Mono** — średnia kanałów L i R.
2. **Okno Hanna** `w[k] = 0.5 − 0.5·cos(2πk/(N−1))`. FFT zakłada, że fragment powtarza się
   w nieskończoność; bez okna skok na brzegach „rozlewa” energię po całym widmie (przeciek).
   Okno wygasza brzegi do zera.
3. `np.fft.rfft` — widmo dla częstotliwości `0 … fs/2` (dla sygnału rzeczywistego druga
   połowa jest lustrzana). Rozdzielczość: `fs / N` (48 kHz / 2048 ≈ 23 Hz na prążek).
4. **Skalowanie amplitudy**: `|X| · 2 / Σw`. Dzięki temu sinus o amplitudzie 1 daje w swoim
   prążku ≈ 1 (test `test_amplitude_scaling_of_spectrum_peak`).
5. **dB i normalizacja**: `db = 20·log10(a)`, potem `(db + 80) / 80` przycięte do `[0, 1]` —
   −80 dB to cisza (0), 0 dB to pełna skala (1).

## Energie pasm

`band_energy` sumuje kwadraty amplitud w paśmie i bierze pierwiastek (energia niezależna
od liczby prążków), potem przelicza na znormalizowane dB. Domyślne pasma: bas 20–150 Hz,
średnie 150–2000 Hz, wysokie 2000–16000 Hz.

`log_bands` dzieli widmo na N pasm o granicach rozłożonych logarytmicznie
(`np.geomspace`) — tak słyszy człowiek. Sumy w przedziałach liczymy wektorowo przez sumy
skumulowane: `E(a..b) = S[b] − S[a]`.

## Obwiednia (attack/release)

`y += (x − y) · (1 − e^(−dt/τ))`, gdzie `τ = attack`, gdy sygnał rośnie, i `τ = release`,
gdy maleje. Krótki attack daje szybką reakcję na stopę, dłuższy release — płynne wygasanie.
Wzór zależy od `dt`, więc działa tak samo przy 30 i 60 FPS.
