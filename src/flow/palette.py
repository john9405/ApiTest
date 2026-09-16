"""Node Palette — side panel with click-to-stamp node creation."""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QFrame,
)

from .nodes import PALETTE_ENTRIES


class _PaletteItem(QFrame):
    """One clickable palette entry with a colored indicator bar."""

    def __init__(self, palette, entry):
        super().__init__(palette)
        self.palette = palette
        self.entry = entry
        self.setObjectName("PaletteItem")
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(self._style(False))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        bar = QFrame(self)
        bar.setFixedWidth(4)
        bar.setStyleSheet(f"background: {entry['color']};")
        layout.addWidget(bar)

        text_frame = QWidget(self)
        tl = QVBoxLayout(text_frame)
        tl.setContentsMargins(6, 4, 6, 4)
        tl.setSpacing(0)
        name_label = QLabel(entry["name"], text_frame)
        name_label.setStyleSheet("background: transparent; font-weight: bold;")
        tl.addWidget(name_label)
        desc_label = QLabel(entry["desc"], text_frame)
        desc_label.setStyleSheet("background: transparent; color: #6b7280; font-size: 8pt;")
        tl.addWidget(desc_label)
        layout.addWidget(text_frame, 1)

    @staticmethod
    def _style(selected):
        border = "#3b82f6" if selected else "#d1d5db"
        width = 2 if selected else 1
        return (
            f"QFrame#PaletteItem {{ background: #f3f4f6; border: {width}px solid {border}; }}"
            f"QFrame#PaletteItem:hover {{ background: #e5e7eb; }}"
        )

    def set_selected(self, selected):
        self.setStyleSheet(self._style(selected))

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.palette.select_type(self.entry["type_id"])
        super().mousePressEvent(event)


class NodePalette(QWidget):
    """Sidebar showing available block types.

    User clicks a block type to select it as a "stamp", then clicks
    the canvas to place a new node of that type.
    """

    PALETTE_WIDTH = 150

    def __init__(self, master, on_select_type=None):
        super().__init__(master)
        self.setFixedWidth(self.PALETTE_WIDTH)
        self.on_select_type = on_select_type
        self._selected_type = None
        self._items = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)

        header = QLabel("Blocks", self)
        header.setObjectName("SectionHeader")
        layout.addWidget(header)

        for entry in PALETTE_ENTRIES:
            item = _PaletteItem(self, entry)
            self._items[entry["type_id"]] = item
            layout.addWidget(item)
        layout.addStretch(1)

    def select_type(self, type_id):
        """Select a node type as the active stamp."""
        self._selected_type = type_id
        for tid, frame in self._items.items():
            frame.set_selected(tid == type_id)
        if self.on_select_type:
            self.on_select_type(type_id)

    def get_selected_type(self):
        """Return the currently selected type_id, or None."""
        return self._selected_type

    def clear_selection(self):
        """Deselect the current type."""
        self._selected_type = None
        for frame in self._items.values():
            frame.set_selected(False)
