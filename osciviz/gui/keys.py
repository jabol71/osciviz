"""Skróty klawiszowe zapisane tak, jak wyświetla je system.

Skróty definiujemy przenośnie („Ctrl+Z”). Qt na macOS mapuje ``Ctrl`` na
klawisz Command, a ``QKeySequence.toString(NativeText)`` zamienia zapis na
natywny: „⌘Z” na macOS i „Ctrl+Z” na Windows. Dzięki temu podpowiedzi
w interfejsie nie są na sztywno „makowe”.
"""

from __future__ import annotations

import sys

from PySide6.QtGui import QKeySequence

IS_MAC = sys.platform == "darwin"
IS_WINDOWS = sys.platform == "win32"


def native(portable: str) -> str:
    """Zwraca skrót w natywnym zapisie systemu, np. ``"Ctrl+Shift+S"`` → ``"⇧⌘S"`` na macOS."""
    return QKeySequence(portable).toString(QKeySequence.NativeText)


def with_keys(text: str, portable: str) -> str:
    """Tekst podpowiedzi z dopisanym skrótem: ``"Cofnij (Ctrl+Z)"``."""
    return f"{text} ({native(portable)})"


def modifier_name() -> str:
    """Nazwa głównego modyfikatora: ⌘ na macOS, Ctrl gdzie indziej."""
    return "⌘" if IS_MAC else "Ctrl"
