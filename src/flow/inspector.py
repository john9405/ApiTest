"""Flow Inspector — right-side properties panel for editing selected nodes."""

import tkinter as tk
from tkinter import ttk

from .nodes import NODE_REGISTRY


class FlowInspector(ttk.Frame):
    """Right-side panel showing properties of the currently selected node."""

    INSPECTOR_WIDTH = 220

    def __init__(self, master, on_node_change=None):
        super().__init__(master, width=self.INSPECTOR_WIDTH)
        self.on_node_change = on_node_change
        self._current_node = None
        self._config_frame = None
        self.pack_propagate(False)

        # Header
        header = ttk.Label(self, text="Properties", font=("TkDefaultFont", 11, "bold"))
        header.pack(fill=tk.X, padx=4, pady=(4, 2))

        ttk.Separator(self, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=2)

        # Scrollable content area
        self._canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0)
        self._scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=self._scrollbar.set)
        self._scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._content = ttk.Frame(self._canvas)
        self._canvas_window = self._canvas.create_window((0, 0), window=self._content, anchor="nw")

        self._content.bind("<Configure>", self._on_content_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)

        # Default placeholder
        self._show_placeholder()

    def _on_content_configure(self, _event):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self._canvas.itemconfigure(self._canvas_window, width=event.width)

    def _show_placeholder(self):
        """Show message when no node is selected."""
        self._clear_content()
        ttk.Label(self._content, text="Select a block\nto configure",
                  foreground="#9ca3af", anchor="center", justify="center").pack(
            fill=tk.X, padx=10, pady=30)

    def _clear_content(self):
        """Remove all widgets from the content area."""
        for widget in self._content.winfo_children():
            widget.destroy()
        self._config_frame = None

    def set_node(self, node_model):
        """Display configuration for a node."""
        self._current_node = node_model
        self._clear_content()

        if node_model is None:
            self._show_placeholder()
            return

        node_cls = NODE_REGISTRY.get(node_model.node_type)
        if node_cls is None:
            ttk.Label(self._content, text=f"Unknown type: {node_model.node_type}",
                      foreground="red").pack(padx=5, pady=5)
            return

        # Node type header
        type_header = tk.Frame(self._content, bg=node_cls.COLOR)
        type_header.pack(fill=tk.X, padx=4, pady=(4, 2))
        tk.Label(type_header, text=node_cls.DISPLAY_NAME, bg=node_cls.COLOR,
                 fg="white", font=("TkDefaultFont", 10, "bold")).pack(padx=6, pady=3)

        # Common fields
        common_frame = ttk.Frame(self._content)
        common_frame.pack(fill=tk.X, padx=4, pady=4)
        common_frame.columnconfigure(1, weight=1)

        ttk.Label(common_frame, text="Label:").grid(row=0, column=0, sticky="w", padx=2, pady=2)
        label_var = tk.StringVar(value=node_model.label or "")
        label_entry = ttk.Entry(common_frame, textvariable=label_var)
        label_entry.grid(row=0, column=1, sticky="ew", padx=2, pady=2)

        def on_label_change(*args):
            node_model.label = label_var.get()
            if self.on_node_change:
                self.on_node_change()

        label_var.trace_add("write", on_label_change)
        ttk.Separator(self._content, orient=tk.HORIZONTAL).pack(fill=tk.X, padx=4, pady=2)

        # Type-specific config
        self._config_frame = ttk.Frame(self._content)
        self._config_frame.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        node_instance = node_cls(node_model)
        config_widget = node_instance.get_config_frame(
            self._config_frame,
            on_change=self.on_node_change,
        )
        config_widget.pack(fill=tk.BOTH, expand=True)

    def get_current_node(self):
        """Return the currently displayed node model."""
        return self._current_node
