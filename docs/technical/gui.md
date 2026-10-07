# GUI, motywy i tłumaczenia (`gui/`, `i18n/`)

## Układ okna

`MainWindow` składa pływające panele (karty z zaokrągleniem) na tle aplikacji: pasek górny,
źródło dźwięku + warstwy (lewo), płótno (środek), inspektor (prawo), oś czasu (dół).
Zegar `QTimer` (16 ms, `PreciseTimer`) napędza podgląd.

| Moduł | Rola |
|---|---|
| `canvas_widget.py` | `QOpenGLWidget`: kamera, przeliczanie współrzędnych, mysz, klawiatura, uchwyty, siatka, linijki |
| `layer_panel.py` | lista warstw (najwyższa na górze), widoczność, blokada, zmiana nazwy, przeciąganie |
| `inspector.py` | formularz budowany ze schematu `ParamSpec`; bez zaznaczenia — ustawienia płótna |
| `timeline.py` | play/pauza, czas, miniatura przebiegu (min/max na kolumnę) z przewijaniem |
| `source_panel.py` | plik / na żywo, urządzenia (auto-wybór BlackHole), REC |
| `export_dialog.py` | ustawienia MP4, postęp, ETA, anulowanie |
| `settings_dialog.py` | motyw (kafelki z podglądem) i język |
| `widgets.py` | suwak z polem, wybór koloru, przełącznik, kontrolka segmentowa, zwijane sekcje |
| `icons.py` | ikony SVG zapisane w kodzie, kolorowane wg motywu |

## Motywy

Kolory motywu to słownik tokenów w `theme.py` (`bg`, `surface`, `border`, `text`, `accent`…).
`themes/base.qss.template` zawiera jeden arkusz z `{{token}}`; `python -m osciviz.gui.theme`
generuje z niego `dark.qss`, `light.qss` i `high_contrast.qss`. Tokeny są też używane w kodzie
rysującym (płótno, oś czasu, ikony). Wybór jest zapamiętywany w `QSettings` (`ui/theme`).

## Tłumaczenia

Teksty w kodzie są po angielsku i przechodzą przez `self.tr()` /
`QCoreApplication.translate()`. Etykiety parametrów w `scene/layers.py` są oznaczone
`QT_TRANSLATE_NOOP("Params", …)` (scena nie zależy od GUI), a tłumaczone w inspektorze.

Aktualizacja tłumaczeń:

```bash
pyside6-lupdate $(find osciviz -name "*.py") -ts osciviz/i18n/osciviz_pl.ts osciviz/i18n/osciviz_en.ts
pyside6-linguist osciviz/i18n/osciviz_pl.ts      # edycja tłumaczeń
pyside6-lrelease osciviz/i18n/osciviz_pl.ts osciviz/i18n/osciviz_en.ts
```

Zmiana języka instaluje nowy `QTranslator` i wywołuje `retranslate()` w oknie i panelach —
bez restartu. Domyślny język to polski (`QSettings`: `ui/language`).
