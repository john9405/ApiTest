from PyQt5.QtCore import QPoint
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
)

from . import qui
from .qui import TreeView, END, ask_string, show_warning, ask_yes_no
from .theme import style_role
from .dao.crud import (
    list_album,
    create_album,
    delete_album,
    active_album,
    retrieve_global_variable,
    retrieve_active_variable,
    list_variable,
    create_variable,
    update_variable,
    delete_variable,
    update_album,
)


class EnvironmentWindow:

    def __init__(self, master=None, **kwargs):
        self.callback = kwargs.get("callback")
        self.root = TreeView(master, show="headings", columns=("name", "status"))
        self.treeview = self.root

        # action toolbar: add environments via a button (no heading click)
        bar = self.root.add_toolbar(34)
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(4, 2, 4, 2)
        add_btn = QPushButton("+ Add", bar)
        style_role(add_btn, "primary")
        add_btn.clicked.connect(self.on_add)
        bl.addWidget(add_btn)
        bl.addStretch(1)

        self.treeview.column("#1", anchor="w", width=100)
        self.treeview.column("#2", anchor="e", width=10)
        self.treeview.heading("#1", text="Name")
        self.treeview.heading("#2", text="Status")
        self.treeview.bind("<Double-1>", self.on_select)
        self.treeview.bind("<Button-3>", self.on_right_click)

    def on_start(self):
        data = list_album()
        def populate():
            for item in data:
                self.treeview.insert("", END, text=item.get('id'),
                                     values=(item.get('name'), "@" if item.get('is_active') else ""))
        self.root.after(0, populate)

    def on_end(self):
        pass

    def on_select(self, event):
        item_id = self.treeview.identify_row(event.y)
        if item_id:
            self.treeview.selection_set(item_id)
            item = self.treeview.item(item_id)
            self.callback(action="edit", collection=item['values'][0], data_id=item['text'], item_id=item_id)

    def on_right_click(self, event):
        item_id = self.treeview.identify_row(event.y)
        if item_id:
            self.treeview.selection_set(item_id)
            item = self.treeview.item(item_id)
            menu = qui.make_menu(self.root)
            menu.addAction("Edit", lambda: self.on_select(event))
            if item["values"][0] != "Globals":
                menu.addAction("Active", lambda: self.set_active(item_id))
                menu.addAction("Delete", self.on_delete)
            menu.exec_(QPoint(event.x_root, event.y_root))

    def on_add(self):
        name = ask_string(self.root, "New Environment", "Name", "New Environment")
        if name is not None:
            if name == "Globals":
                show_warning(self.root, "Warning", "Reserved words")
                return self.on_add()
            _id = create_album(name=name)
            self.treeview.insert("", END, text=_id, values=(name, ""))

    def on_delete(self):
        if len(self.treeview.selection()) > 0:
            for item_id in self.treeview.selection():
                item = self.treeview.item(item_id)
                if item["values"][0] != "Globals":
                    delete_album(id=item['text'])
                    self.treeview.delete(item_id)

    def set_variable(self, item_id, collection):
        item = self.treeview.item(item_id)
        self.treeview.item(item_id, values=(collection, item['values'][1]))
        self.callback(action="rename", collection=collection, item_id=item_id)

    def set_active(self, item_id):
        item = self.treeview.item(item_id)
        if item["values"][0] == 'Globals':
            return

        # 去除活动标记
        for child_id in self.treeview.get_children():
            child = self.treeview.item(child_id)
            self.treeview.item(child_id, values=(child['values'][0], ""))

        # 标记活动
        self.treeview.item(item_id, values=(item["values"][0], "@"))
        active_album(id=item['text'])

    def get_globals(self, name):
        """Global variable value, or None when it is not defined."""
        value = retrieve_global_variable(name=name)
        return value.strip() if value is not None else None

    def get_variable(self, name):
        """Active-environment variable value, or None when not defined."""
        value = retrieve_active_variable(name=name)
        return value.strip() if value is not None else None


class VariableWindow:

    def __init__(self, master=None, **kwargs):
        self.root = master
        layout = QVBoxLayout(self.root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.data_id = kwargs.get('data_id')
        self.parent_id = kwargs.get('item_id')
        self.col_name = kwargs.get('collection')
        self.callback = kwargs.get('set_variable')
        # Pending deletions are per-tab: a class-level list was shared by every
        # environment tab, so one tab's Save replayed another tab's deletions.
        self.delete_list = []

        bar = QWidget(self.root)
        blay = QHBoxLayout(bar)
        blay.setContentsMargins(4, 4, 4, 4)
        blay.addStretch(1)

        def make_button(text, role, command):
            btn = QPushButton(text, bar)
            style_role(btn, role)
            btn.clicked.connect(command)
            blay.addWidget(btn)

        make_button('Save', "primary", self.on_save)
        if kwargs.get("collection") != 'Globals':
            make_button("Active", "success", lambda: kwargs.get("set_active")(kwargs.get("item_id")))
            make_button('Rename', "secondary", self.on_rename)
        make_button('Add', "info", self.on_add)
        layout.addWidget(bar)

        self.treeview = TreeView(self.root, show="headings", columns=("name", "value", "action"))
        self.treeview.heading("#1", text="Name")
        self.treeview.heading("#2", text="Value")
        self.treeview.heading("#3", text="Action")
        self.treeview.column("#1", width=10)
        self.treeview.column("#2", width=30)
        self.treeview.column("#3", width=10)
        self.treeview.bind("<Button-1>", self.on_click)
        self.treeview.bind("<Double-1>", self.on_double_click)
        layout.addWidget(self.treeview, 1)

        data = list_variable(belong_name="album", belong_id=kwargs.get("data_id"))
        for item in data:
            self.treeview.insert("", END, text=item['id'], values=(item['name'], item['content'], "Delete"))

    def on_add(self):
        name = ask_string(self.root, "New Variable", "Name", "New Variable")
        if name is not None:
            value = ask_string(self.root, "New Variable", "Value", "New Value")
            if value is not None:
                self.treeview.insert("", END, text='', values=(name, value, "Delete"))

    def on_click(self, event):
        region = self.treeview.identify('region', event.x, event.y)
        if region == 'cell':
            column = self.treeview.identify_column(event.x)
            item_id = self.treeview.identify_row(event.y)
            item = self.treeview.item(item_id)
            if column == "#3":
                if ask_yes_no(self.root, "Confirm", "Are you sure you want to delete this variable?"):
                    self.delete_list.append(item['text'])
                    self.treeview.delete(item_id)

    def on_double_click(self, event):
        region = self.treeview.identify('region', event.x, event.y)
        if region == 'cell':
            column = self.treeview.identify_column(event.x)
            item_id = self.treeview.identify_row(event.y)
            item = self.treeview.item(item_id)

            if column == "#1":
                value = ask_string(self.root, "Edit Variable", "Name", item['values'][0])
                if value is not None:
                    self.treeview.item(item_id, values=(value, item['values'][1], 'Delete'))

            elif column == "#2":
                value = ask_string(self.root, "Edit Variable", "Value", item['values'][1])
                if value is not None:
                    self.treeview.item(item_id, values=(item['values'][0], value, 'Delete'))

    def on_rename(self):
        value = ask_string(self.root, "Rename", "New Name", self.col_name)
        if value is not None:
            update_album(name=value, id=self.data_id)
            self.callback(self.parent_id, value)

    def on_save(self):
        items = self.treeview.get_children()
        for item_id in items:
            item = self.treeview.item(item_id)
            if item['text'] == '':
                data_id = create_variable(name=item['values'][0], content=item['values'][1],
                                          belong_name="album", belong_id=self.data_id)
                self.treeview.item(item_id, text=data_id)
            else:
                update_variable(id=item['text'], name=item['values'][0], content=item['values'][1])

        for data_id in self.delete_list:
            delete_variable(id=data_id)
        # The deletions have been applied; keeping them queued made every later
        # Save re-issue them.
        self.delete_list = []
