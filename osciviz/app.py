"""Punkt wejścia aplikacji.

Kolejność jest ważna: format powierzchni OpenGL (4.1 Core Profile — maksimum
na macOS, a na Windows wspierane przez każdą współczesną kartę; MSAA 4×) musi być ustawiony **przed** utworzeniem ``QApplication``,
inaczej Qt utworzy domyślny (stary) kontekst OpenGL 2.1.
"""

from __future__ import annotations

import sys

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QFont, QSurfaceFormat
from PySide6.QtWidgets import QApplication

from osciviz import APP_NAME, ORG_NAME, __version__


def configure_opengl() -> None:
    fmt = QSurfaceFormat()
    fmt.setVersion(4, 1)
    fmt.setProfile(QSurfaceFormat.CoreProfile)
    fmt.setSamples(4)
    fmt.setSwapInterval(1)  # synchronizacja z odświeżaniem ekranu (brak „rwania” obrazu)
    fmt.setDepthBufferSize(0)
    QSurfaceFormat.setDefaultFormat(fmt)


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv if argv is None else argv
    configure_opengl()
    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
    app = QApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    app.setApplicationVersion(__version__)
    app.setStyle("Fusion")  # przewidywalna baza pod arkusze stylów na każdej platformie
    if sys.platform == "darwin":
        app.setFont(QFont(".AppleSystemUIFont", 13))
    elif sys.platform == "win32":
        # Segoe UI Variable to systemowa czcionka Windows 11; na Windows 10 Qt
        # automatycznie użyje zwykłego Segoe UI.
        font = QFont("Segoe UI Variable Text", 10)
        font.setFamilies(["Segoe UI Variable Text", "Segoe UI"])
        app.setFont(font)

    # Import po utworzeniu QApplication (moduły GUI tworzą ikony przy imporcie).
    from osciviz.gui.main_window import MainWindow, install_translator  # noqa: PLC0415
    from osciviz.gui.theme import theme  # noqa: PLC0415

    settings = QSettings()
    theme.apply(app, settings.value("ui/theme", "dark"))
    language = settings.value("ui/language", "pl")

    class _Holder:
        translator = None

    holder = _Holder()
    install_translator(app, language, holder)
    window = MainWindow(app)
    window.translator = holder.translator
    window.language = language
    window.retranslate()
    for act in window.lang_group.actions():
        act.setChecked(act.data() == language)

    if "--self-test" in argv:
        # Używane przez CI po spakowaniu: okno powstało, więc wszystkie moduły
        # i pliki danych (shadery, motywy, tłumaczenia, presety) dały się wczytać.
        return _self_test()

    # Plik projektu z linii poleceń albo — przy pierwszym uruchomieniu — demo.
    files = [a for a in argv[1:] if a.lower().endswith(".osv")]
    if files:
        window.open_project(files[0])
    elif settings.value("ui/first_run_done", False, type=bool) is False:
        window.load_demo()
        settings.setValue("ui/first_run_done", True)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())


def _self_test() -> int:
    """Sprawdza obecność plików danych w (spakowanej) aplikacji. 0 = wszystko jest."""
    from osciviz.gui.main_window import I18N_DIR  # noqa: PLC0415
    from osciviz.gui.theme import THEMES_DIR  # noqa: PLC0415
    from osciviz.io.presets import PresetManager  # noqa: PLC0415
    from osciviz.render.renderer import load_shader  # noqa: PLC0415

    checks = {
        "shaders": bool(load_shader("mesh.vert")),
        "themes": all((THEMES_DIR / f"{n}.qss").exists() for n in ("dark", "light", "high_contrast")),
        "translations": all((I18N_DIR / f"osciviz_{c}.qm").exists() for c in ("pl", "en")),
        "presets": len(PresetManager().all()) > 0,
    }
    if sys.platform == "win32":
        from osciviz.core import loopback  # noqa: PLC0415

        checks["loopback"] = loopback.available()  # PyAudioWPatch dołączony do paczki
    for name, ok in checks.items():
        print(f"{name}: {'ok' if ok else 'BRAK'}")
    return 0 if all(checks.values()) else 1
