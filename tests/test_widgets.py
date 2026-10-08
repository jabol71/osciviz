"""Pola liczbowe z arkuszem stylów motywu muszą mieć edytowalne pole tekstowe.

Qt 6.12.0 ma błąd: gdy arkusz stylów ustawia ramkę lub odstępy pola liczbowego
bez strzałek (``NoButtons``), wewnętrzne pole tekstowe dostaje szerokość 1 px —
wartość jest niewidoczna i nie da się nic wpisać. Ten test wychwyci ten błąd
po aktualizacji PySide6 (stąd ograniczenie wersji w requirements.txt).
"""

import pytest

from osciviz.gui.theme import build_stylesheet
from osciviz.gui.widgets import SliderSpin


@pytest.mark.parametrize("theme_name", ["dark", "light", "high_contrast"])
def test_spinbox_editor_is_usable(qapp, theme_name):
    widget = SliderSpin(0.0, 1.0)
    widget.setStyleSheet(build_stylesheet(theme_name))
    widget.resize(240, 32)
    widget.show()
    qapp.processEvents()
    spin = widget.spin
    editor = spin.lineEdit()
    assert editor.width() > spin.width() // 2, (editor.geometry(), spin.geometry())
    widget.close()
