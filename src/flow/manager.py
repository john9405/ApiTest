"""Flow Window — sidebar panel listing saved workflows.

Double-click a flow to open it in the FlowEditor tab.
"""

import platform
import tkinter as tk
from tkinter import  messagebox, simpledialog
import ttkbootstrap as ttk

from .model import FlowModel


class FlowWindow:
    """Sidebar panel that lists all saved flows.

    Follows the same pattern as EnvironmentWindow and HistoryWindow:
    - self.root is the ttk.Frame
    - TreeView for the list
    - Callback to main.py for opening flow editor tabs
    """

    def __init__(self, parent, callback=None):
        self.root = ttk.Frame(parent)
        self.callback = callback

        # Toolbar
        toolbar = ttk.Frame(self.root)
        toolbar.pack(fill=tk.X, padx=2, pady=2)
        ttk.Label(toolbar, text="Flows").pack(side=tk.LEFT)
        add_btn = ttk.Button(toolbar, text="+", width=3, command=self.on_new)
        add_btn.pack(side=tk.RIGHT)

        # TreeView
        self.treeview = ttk.Treeview(self.root, show="headings", columns=("name", "modified"))
        self.treeview.heading("name", text="Name (+)")
        self.treeview.heading("modified", text="Modified")
        self.treeview.column("name", width=100)
        self.treeview.column("modified", width=60)

        scroll_y = ttk.Scrollbar(self.root, orient=tk.VERTICAL, command=self.treeview.yview)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        self.treeview.pack(fill=tk.BOTH, expand=True)
        self.treeview.config(yscrollcommand=scroll_y.set)

        # Bindings
        self.treeview.bind("<Button-1>", self.on_click)
        self.treeview.bind("<Double-1>", self.on_open)
        if platform.system() == "Darwin":
            self.treeview.bind("<Control-Button-1>", self.on_right_click)
            self.treeview.bind("<Button-2>", self.on_right_click)
        else:
            self.treeview.bind("<Button-3>", self.on_right_click)

    def on_start(self):
        """Load flows from database on app startup."""
        flows = FlowModel.list_all()
        for item in flows:
            modified = item.get("modified_at", "")
            if modified and len(modified) > 10:
                modified = modified[:10]
            self.treeview.insert("", tk.END, iid=str(item["id"]),
                                 values=(item["name"], modified or ""))

    def on_end(self):
        """Called on app close; nothing to persist here."""
        pass

    def refresh(self):
        """Reload the treeview from database."""
        self.treeview.delete(*self.treeview.get_children())
        self.on_start()

    def on_click(self, event):
        region = self.treeview.identify("region", event.x, event.y)
        if region == "heading":
            column = self.treeview.identify_column(event.x)
            if column == "#1":
                self.on_new()

    def on_open(self, event=None):
        """Open the selected flow in the editor."""
        selection = self.treeview.selection()
        if not selection:
            return
        flow_id = int(selection[0])
        if self.callback:
            self.callback(action="open_flow", flow_id=flow_id)

    def on_new(self):
        """Create a new flow."""
        name = simpledialog.askstring("New Flow", "Enter flow name:", parent=self.root)
        if name is None:
            return
        # Create via CRUD directly
        from ..dao.crud import create_flow
        flow_id = create_flow(name=name)
        self.refresh()
        if self.callback:
            self.callback(action="open_flow", flow_id=flow_id)

    def on_rename(self):
        """Rename the selected flow."""
        selection = self.treeview.selection()
        if not selection:
            return
        flow_id = int(selection[0])
        item = self.treeview.item(selection[0])
        old_name = item["values"][0]
        new_name = simpledialog.askstring("Rename Flow", "Enter new name:",
                                          initialvalue=old_name, parent=self.root)
        if new_name and new_name != old_name:
            from ..dao.crud import update_flow
            update_flow(id=flow_id, name=new_name)
            self.refresh()

    def on_delete(self):
        """Delete the selected flow."""
        selection = self.treeview.selection()
        if not selection:
            return
        flow_id = int(selection[0])
        item = self.treeview.item(selection[0])
        name = item["values"][0]
        if messagebox.askyesno("Delete Flow", f'Delete flow "{name}"?',
                               parent=self.root):
            FlowModel.delete(flow_id)
            self.refresh()

    def on_duplicate(self):
        """Duplicate the selected flow."""
        selection = self.treeview.selection()
        if not selection:
            return
        flow_id = int(selection[0])
        original = FlowModel.load(flow_id)
        if original is None:
            return
        original.name = f"{original.name} (copy)"
        original.id = None
        for node in original.nodes:
            node.id = None
        for conn in original.connections:
            conn.id = None
        original.save()
        self.refresh()

    def on_right_click(self, event):
        """Show context menu."""
        item = self.treeview.identify_row(event.y)
        if item:
            self.treeview.selection_set(item)
        menu = tk.Menu(self.root, tearoff=False)
        if item:
            menu.add_command(label="Open", command=self.on_open)
            menu.add_command(label="Rename", command=self.on_rename)
            menu.add_command(label="Duplicate", command=self.on_duplicate)
            menu.add_separator()
            menu.add_command(label="Delete", command=self.on_delete)
        else:
            menu.add_command(label="New Flow", command=self.on_new)
        menu.post(event.x_root, event.y_root)
