# Scena, transformacje i undo (`scene/`)

## Układ współrzędnych

Krótszy bok kadru ma zakres `[−1, 1]`, dłuższy — proporcjonalnie (`scene_extent`).
16:9 → X ∈ [−16/9, 16/9], Y ∈ [−1, 1]; 9:16 → X ∈ [−1, 1], Y ∈ [−16/9, 16/9]. Oś Y w górę.
Grubości linii i rozmiary punktów są w „pikselach przy wysokości 1080”, czyli w jednostkach
sceny `px · 2/1080` — projekt wygląda tak samo w każdej rozdzielczości.

## Macierze 3×3

Punkt `(x, y)` zapisujemy jednorodnie jako `[x, y, 1]`, dzięki czemu przesunięcie też jest
mnożeniem macierzy:

```
M = T(x, y) · R(θ) · S(sx, sy)
```

Kolejność czytamy od prawej: skala wokół środka warstwy, obrót wokół środka, przesunięcie.
Odwrotność liczymy analitycznie: `M⁻¹ = S(1/sx, 1/sy) · R(−θ) · T(−x, −y)`
(test porównuje ją z `np.linalg.inv`).

## Hit test

Kliknięcie (piksel) → scena (kamera podglądu) → **lokalny układ warstwy** (`M⁻¹`) →
sprawdzenie prostokąta `|lx| ≤ hx, |ly| ≤ hy`, gdzie `(hx, hy) = layer.half_extent()`.
Warstwy sprawdzamy od najwyższej, więc klik wybiera tę, która jest na wierzchu.

## Skalowanie uchwytem

1. Kursor przenosimy do obróconego układu warstwy: `l = R(−θ)·(p − pozycja)`.
2. Przeciwległy bok/narożnik (kotwica) stoi w miejscu: nowy rozmiar = odległość kursora od
   kotwicy, nowy środek = środek odcinka kotwica–kursor, z powrotem obrócony `R(θ)`.
3. Alt — skalowanie od środka (rozmiar = 2·|l|); Shift — ten sam współczynnik w obu osiach.

## Komendy undo

Każda edycja to `QUndoCommand` z wartościami „przed” i „po”. Gest (przeciąganie, suwak) ma
identyfikator `gesture`; kolejne komendy z tym samym gestem łączą się przez `mergeWith`,
więc ⌘Z cofa cały gest naraz. Komendy: dodanie/usunięcie/kolejność warstw, transformacje
(wiele warstw), parametr, właściwość (nazwa, krycie, mieszanie, widoczność, blokada),
ustawienie sceny (proporcje, tło, ziarno), zastosowanie presetu.

## Schemat parametrów

Każda warstwa deklaruje listę `ParamSpec(key, kind, default, label, min, max, step, …)`.
Inspektor buduje z niej formularz automatycznie, `coerce()` rzutuje i przycina wartości
z plików i GUI. Dodanie parametru to jedna linijka w `layers.py` + użycie go w `render/geometry.py`.
