"""Node Palette — side panel with click-to-stamp node creation."""

import tkinter as tk
import ttkbootstrap as ttk

from .nodes import PALETTE_ENTRIES


class NodePalette(ttk.Frame):
    """Sidebar showing available block types.

    User clicks a block type to select it as a "stamp", then clicks
    the canvas to place a new node of that type.
    """

    PALETTE_WIDTH = 140

    def __init__(self, master, on_select_type=None):
        super().__init__(master, width=self.PALETTE_WIDTH)
        self.on_select_type = on_select_type
        self._selected_type = None
        self._buttons = {}

        self.pack_propagate(False)

        # Header
        header = ttk.Label(self, text="Blocks", font=("TkDefaultFont", 11, "bold"))
        header.pack(fill=tk.X, padx=4, pady=(4, 2))

        ttk.Separator(self, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=2)

        # Block type items
        for entry in PALETTE_ENTRIES:
            self._create_item(entry)

    def _create_item(self, entry):
        """Create a clickable palette item for one node type."""
        type_id = entry["type_id"]
        color = entry["color"]
        name = entry["name"]
        desc = entry["desc"]

        # Container frame with color indicator
        item_frame = tk.Frame(
            self,
            bg="#f3f4f6",
            highlightbackground="#d1d5db",
            highlightthickness=1,
            cursor="hand2",
        )

        # Color bar on the left
        color_bar = tk.Frame(item_frame, bg=color, width=4)
        color_bar.pack(side=tk.LEFT, fill=tk.Y)
        color_bar.config(height=36)

        # Text area
        text_frame = tk.Frame(item_frame, bg="#f3f4f6")
        text_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=4, pady=2)

        name_label = tk.Label(text_frame, text=name, bg="#f3f4f6",
                              fg="#1f2937", font=("TkDefaultFont", 10),
                              anchor="w")
        name_label.pack(fill=tk.X)

        desc_label = tk.Label(text_frame, text=desc, bg="#f3f4f6",
                              fg="#6b7280", font=("TkDefaultFont", 8),
                              anchor="w")
        desc_label.pack(fill=tk.X)

        item_frame.pack(fill=tk.X, padx=4, pady=2)

        # Bind click to select
        def on_click(e, tid=type_id, frm=item_frame):
            self.select_type(tid)

        for widget in [item_frame, color_bar, text_frame, name_label, desc_label]:
            widget.bind("<Button-1>", on_click)
            widget.bind("<Enter>", lambda e, f=item_frame: f.configure(bg="#e5e7eb"))
            widget.bind("<Leave>", lambda e, f=item_frame: f.configure(bg="#f3f4f6"))

        self._buttons[type_id] = item_frame

    def select_type(self, type_id):
        """Select a node type as the active stamp."""
        self._selected_type = type_id

        # Update visual selection state
        for tid, frame in self._buttons.items():
            if tid == type_id:
                frame.configure(highlightbackground="#3b82f6", highlightthickness=2)
            else:
                frame.configure(highlightbackground="#d1d5db", highlightthickness=1)

        if self.on_select_type:
            self.on_select_type(type_id)

    def get_selected_type(self):
        """Return the currently selected type_id, or None."""
        return self._selected_type

    def clear_selection(self):
        """Deselect the current type."""
        self._selected_type = None
        for frame in self._buttons.values():
            frame.configure(highlightbackground="#d1d5db", highlightthickness=1)
