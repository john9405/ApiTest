"""Flow Window — sidebar panel listing saved workflows.

Double-click a flow to open it in the FlowEditor tab.
"""

from PyQt5.QtCore import QPoint
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton

from .model import FlowModel
from .. import qui
from ..qui import TreeView, END, ask_string, ask_yes_no
from ..theme import style_role


class FlowWindow:
    """Sidebar panel that lists all saved flows.

    Follows the same pattern as EnvironmentWindow and HistoryWindow:
    - self.root is the container widget
    - TreeView for the list
    - Callback to main.py for opening flow editor tabs
    """

    def __init__(self, parent, callback=None):
        self.root = QWidget(parent)
        self.callback = callback

        layout = QVBoxLayout(self.root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar
        toolbar = QWidget(self.root)
        tl = QHBoxLayout(toolbar)
        tl.setContentsMargins(4, 2, 4, 2)
        tl.addWidget(QLabel("Flows", toolbar))
        tl.addStretch(1)
        add_btn = QPushButton("+ Add", toolbar)
        style_role(add_btn, "primary")
        add_btn.clicked.connect(self.on_new)
        tl.addWidget(add_btn)
        layout.addWidget(toolbar)

        # TreeView
        self.treeview = TreeView(self.root, show="headings", columns=("name", "modified"))
        self.treeview.heading("#1", text="Name")
        self.treeview.heading("#2", text="Modified")
        self.treeview.column("#1", width=100)
        self.treeview.column("#2", width=60)
        self.treeview.bind("<Double-1>", self.on_open)
        self.treeview.bind("<Button-3>", self.on_right_click)
        layout.addWidget(self.treeview, 1)

    def on_start(self):
        """Load flows from database on app startup."""
        flows = FlowModel.list_all()
        def populate():
            for item in flows:
                modified = item.get("modified_at", "")
                if modified and len(modified) > 10:
                    modified = modified[:10]
                self.treeview.insert("", END, iid=str(item["id"]),
                                     values=(item["name"], modified or ""))
        self.treeview.after(0, populate)

    def on_end(self):
        """Called on app close; nothing to persist here."""
        pass

    def refresh(self):
        """Reload the treeview from database."""
        self.treeview.delete(self.treeview.get_children())
        self.on_start()

    def on_open(self, event=None):
        """Open the selected flow in the editor."""
        selection = self.treeview.selection()
        if not selection:
            return
        flow_id = int(str(selection[0]))
        if self.callback:
            self.callback(action="open_flow", flow_id=flow_id)

    def on_new(self):
        """Create a new flow."""
        name = ask_string(self.root, "New Flow", "Enter flow name:", "")
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
        flow_id = int(str(selection[0]))
        item = self.treeview.item(selection[0])
        old_name = item["values"][0]
        new_name = ask_string(self.root, "Rename Flow", "Enter new name:", old_name)
        if new_name and new_name != old_name:
            from ..dao.crud import update_flow
            update_flow(id=flow_id, name=new_name)
            self.refresh()

    def on_delete(self):
        """Delete the selected flow."""
        selection = self.treeview.selection()
        if not selection:
            return
        flow_id = int(str(selection[0]))
        item = self.treeview.item(selection[0])
        name = item["values"][0]
        if ask_yes_no(self.root, "Delete Flow", f'Delete flow "{name}"?'):
            FlowModel.delete(flow_id)
            self.refresh()

    def on_duplicate(self):
        """Duplicate the selected flow."""
        selection = self.treeview.selection()
        if not selection:
            return
        flow_id = int(str(selection[0]))
        original = FlowModel.load(flow_id)
        if original is None:
            return
        original.name = f"{original.name} (copy)"
        original.id = None
        # Nodes need fresh *temporary* ids, and the edges have to be remapped to
        # them.  Setting every node id to None made save() key its id_map on
        # None while the connections still held the original database ids, so
        # Duplicate raised KeyError (and had already inserted half a copy).
        id_map = {}
        for index, node in enumerate(original.nodes, start=1):
            id_map[node.id] = -index
            node.id = -index
        original._next_id = len(original.nodes) + 1
        for conn in original.connections:
            conn.id = None
            conn.source_node_id = id_map.get(conn.source_node_id, conn.source_node_id)
            conn.target_node_id = id_map.get(conn.target_node_id, conn.target_node_id)
        original.save()
        self.refresh()

    def on_right_click(self, event):
        """Show context menu."""
        item = self.treeview.identify_row(event.y)
        if item:
            self.treeview.selection_set(item)
        menu = qui.make_menu(self.root)
        if item:
            menu.addAction("Open", self.on_open)
            menu.addAction("Rename", self.on_rename)
            menu.addAction("Duplicate", self.on_duplicate)
            menu.addSeparator()
            menu.addAction("Delete", self.on_delete)
        else:
            menu.addAction("New Flow", self.on_new)
        menu.exec_(QPoint(event.x_root, event.y_root))
