"""Panel warstw: lista (najwyższa warstwa na górze), widoczność, blokada,
zmiana nazwy, kolejność (przeciąganie lub przyciski) i dodawanie warstw.

Panel nie zmienia sceny bezpośrednio — wszystko przez komendy undo.
Zaznaczenie jest synchronizowane w obie strony z płótnem przez ``Scene``.
"""

from __future__ import annotations

from PySide6.QtCore import QCoreApplication, QSize, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from osciviz.gui.icons import LAYER_ICONS, icon
from osciviz.gui.keys import IS_MAC, with_keys
from osciviz.gui.theme import theme
from osciviz.gui.widgets import label, tool_button
from osciviz.scene import commands as cmd
from osciviz.scene.layers import LAYER_TYPES


class LayerRow(QWidget):
    """Wiersz listy: ikona typu, nazwa (edytowalna dwuklikiem), oko, kłódka."""

    def __init__(self, panel: LayerPanel, layer) -> None:
        super().__init__()
        self.panel = panel
        self.layer_id = layer.id
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 4, 4)
        layout.setSpacing(8)
        badge = QLabel()
        badge.setFixedSize(26, 26)
        badge.setAlignment(Qt.AlignCenter)
        badge.setStyleSheet(
            f"background: {theme.tokens['surface3']}; border-radius: 7px;")
        badge.setPixmap(icon(LAYER_ICONS[layer.TYPE], theme.tokens["accent"]).pixmap(16, 16))
        layout.addWidget(badge)
        self.stack = QStackedWidget()
        self.name_label = QLabel(layer.name)
        self.name_label.setStyleSheet("font-weight: 500;")
        if not layer.visible:
            self.name_label.setStyleSheet(f"color: {theme.tokens['faint']};")
        self.name_edit = QLineEdit(layer.name)
        self.name_edit.editingFinished.connect(self._commit_name)
        self.stack.addWidget(self.name_label)
        self.stack.addWidget(self.name_edit)
        self.stack.setFixedHeight(26)
        layout.addWidget(self.stack, 1)
        buttons = (("locked", "lock", "unlock", QCoreApplication.translate("LayerPanel", "Lock")),
                   ("visible", "eye", "eye-off", QCoreApplication.translate("LayerPanel", "Show / hide")))
        for prop, icon_on, icon_off, tip in buttons:
            on = getattr(layer, prop)
            b = tool_button(icon_on if on else icon_off, tip, size=15, color="text" if on else "faint")
            b.clicked.connect(lambda _=False, p=prop: panel.toggle_prop(self.layer_id, p))
            b.setFixedSize(26, 26)
            layout.addWidget(b)

    def start_rename(self) -> None:
        self.stack.setCurrentIndex(1)
        self.name_edit.setFocus()
        self.name_edit.selectAll()

    def _commit_name(self) -> None:
        self.stack.setCurrentIndex(0)
        self.panel.rename(self.layer_id, self.name_edit.text().strip())


class LayerList(QListWidget):
    """Lista z przeciąganiem wierszy; po upuszczeniu zgłasza nową pozycję."""

    moved = Signal(str, int)  # id warstwy, nowy indeks wiersza (0 = góra)

    def dropEvent(self, event) -> None:  # noqa: N802
        item = self.currentItem()
        if item is None:
            return
        layer_id = item.data(Qt.UserRole)
        target = self.itemAt(event.position().toPoint())
        row = self.row(target) if target else self.count() - 1
        event.ignore()  # listę przebudujemy sami ze sceny
        self.moved.emit(layer_id, row)


class LayerPanel(QFrame):
    addLayerRequested = Signal(str)

    def __init__(self, scene, undo_stack, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("Panel")
        self.scene = scene
        self.undo = undo_stack
        self._syncing = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)
        header = QHBoxLayout()
        self.title = label("", "title")
        header.addWidget(self.title)
        header.addStretch(1)
        self.add_btn = tool_button("plus", "", size=16)
        self.add_btn.setPopupMode(self.add_btn.ToolButtonPopupMode.InstantPopup)
        self.add_menu = QMenu(self)
        self.add_btn.setMenu(self.add_menu)
        header.addWidget(self.add_btn)
        layout.addLayout(header)

        self.list = LayerList()
        self.list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.list.setDragDropMode(QAbstractItemView.InternalMove)
        self.list.setDefaultDropAction(Qt.MoveAction)
        self.list.setSpacing(1)
        self.list.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.list.itemSelectionChanged.connect(self._on_list_selection)
        self.list.itemDoubleClicked.connect(self._on_double_click)
        self.list.moved.connect(self._on_moved)
        layout.addWidget(self.list, 1)
        self.empty = label("", "empty")
        self.empty.setAlignment(Qt.AlignCenter)
        self.empty.setWordWrap(True)
        layout.addWidget(self.empty)

        footer = QHBoxLayout()
        footer.setSpacing(2)
        self.up_btn = tool_button("chevron-up", "", size=16)
        self.down_btn = tool_button("chevron-down", "", size=16)
        self.dup_btn = tool_button("copy", "", size=16)
        self.del_btn = tool_button("trash", "", size=16)
        self.up_btn.clicked.connect(lambda: self._restack(1))
        self.down_btn.clicked.connect(lambda: self._restack(-1))
        for b in (self.up_btn, self.down_btn):
            footer.addWidget(b)
        footer.addStretch(1)
        for b in (self.dup_btn, self.del_btn):
            footer.addWidget(b)
        layout.addLayout(footer)

        scene.layers_changed.connect(self.rebuild)
        scene.selection_changed.connect(self._sync_selection)
        self.retranslate()
        self.rebuild()

    def retranslate(self) -> None:
        self.title.setText(self.tr("Layers"))
        self.add_btn.setToolTip(self.tr("Add layer"))
        self.up_btn.setToolTip(self.tr("Bring forward"))
        self.down_btn.setToolTip(self.tr("Send backward"))
        self.dup_btn.setToolTip(with_keys(self.tr("Duplicate"), "Ctrl+D"))
        self.del_btn.setToolTip(with_keys(self.tr("Delete"), "Backspace" if IS_MAC else "Del"))
        self.empty.setText(self.tr("No layers yet.\nUse + or the buttons at the top\nto add your first visual."))
        self.add_menu.clear()
        for type_name, cls in LAYER_TYPES.items():
            self.add_menu.addAction(icon(LAYER_ICONS[type_name], theme.tokens["text"]),
                                    QCoreApplication.translate("LayerTypes", cls.DISPLAY_NAME),
                                    lambda t=type_name: self.addLayerRequested.emit(t))
        self.rebuild()

    def rebuild(self) -> None:
        self._syncing = True
        self.list.clear()
        for layer in reversed(self.scene.layers):
            item = QListWidgetItem()
            item.setData(Qt.UserRole, layer.id)
            item.setSizeHint(QSize(10, 36))
            self.list.addItem(item)
            self.list.setItemWidget(item, LayerRow(self, layer))
        self.empty.setVisible(not self.scene.layers)
        self.list.setVisible(bool(self.scene.layers))
        self._syncing = False
        self._sync_selection()

    def _sync_selection(self) -> None:
        self._syncing = True
        selected = set(self.scene.selection)
        for i in range(self.list.count()):
            item = self.list.item(i)
            item.setSelected(item.data(Qt.UserRole) in selected)
        has = bool(selected)
        for b in (self.up_btn, self.down_btn, self.dup_btn, self.del_btn):
            b.setEnabled(has)
        self._syncing = False

    def _on_list_selection(self) -> None:
        if self._syncing:
            return
        ids = [item.data(Qt.UserRole) for item in self.list.selectedItems()]
        self.scene.set_selection(ids)

    def _on_double_click(self, item) -> None:
        row = self.list.itemWidget(item)
        if row:
            row.start_rename()

    def _on_moved(self, layer_id: str, row: int) -> None:
        # Wiersz 0 = najwyższa warstwa = ostatni indeks w scenie.
        new_index = len(self.scene.layers) - 1 - row
        if new_index != self.scene.index_of(layer_id):
            self.undo.push(cmd.MoveLayerCommand(self.scene, layer_id, new_index))
        else:
            self.rebuild()

    def _restack(self, direction: int) -> None:
        command = cmd.restack_command(self.scene, direction)
        if command is not None:
            self.undo.push(command)

    def toggle_prop(self, layer_id: str, prop: str) -> None:
        layer = self.scene.layer(layer_id)
        if layer is not None:
            self.undo.push(cmd.SetLayerPropCommand(self.scene, [layer_id], prop, not getattr(layer, prop)))

    def rename(self, layer_id: str, name: str) -> None:
        layer = self.scene.layer(layer_id)
        if layer is not None and name and name != layer.name:
            self.undo.push(cmd.SetLayerPropCommand(self.scene, [layer_id], "name", name))
        else:
            self.rebuild()
