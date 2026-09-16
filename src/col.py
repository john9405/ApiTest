import json
import os
import threading

from PyQt5.QtCore import QPoint
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QPlainTextEdit,
)

from . import qui
from .qui import TreeView, END, ask_string, ask_yes_no, show_error, open_file, save_file
from .theme import style_role
from .utils import CodeEditor
from .dao.crud import (
    create_folder,
    create_variable,
    create_request,
    retrieve_folder,
    retrieve_request,
    create_collection,
    delete_folder,
    delete_request,
    update_request,
    update_folder,
    delete_variable,
    update_variable,
    list_variable,
    retrieve_folder_variable,
    list_collection,
    list_request,
    list_folder,
)


class CollectionWindow:
    cut_board = None

    def __init__(self, window, callback=None):
        self.window = window
        self.callback = callback

        self.root = TreeView(window)
        self.tree = self.root

        # action toolbar: create collections via a button (no heading click)
        bar = self.root.add_toolbar(34)
        bl = QHBoxLayout(bar)
        bl.setContentsMargins(4, 2, 4, 2)
        add_btn = QPushButton("+ Add", bar)
        style_role(add_btn, "primary")
        add_btn.clicked.connect(self.new_proj)
        bl.addWidget(add_btn)
        bl.addStretch(1)

        self.tree.heading("#0", text="Name")
        self.tree.column("#0", width=100)
        self.tree.bind("<Double-1>", self.on_select)
        self.tree.bind("<Button-3>", self.on_right_click)

    def open_proj(self):
        """open a program"""
        filepath = open_file(
            self.window,
            "Open",
            [("Json files", "*.json")],
            initialdir=os.path.expanduser("~"),
        )
        if filepath:
            with open(filepath, "r", encoding="utf-8") as f:
                try:
                    data = json.loads(f.read())
                    self.show_proj(data)
                except json.JSONDecodeError:
                    show_error(self.window, "Error", "The text content must be a json")

    def show_proj(self, data):
        item = None
        if "item" in data:
            item = data.pop("item")

        data_id = create_folder(
            name=data["name"],
            parent_id=0,
            pre_script=data.get("pre_script", ""),
            post_script=data.get("post_script", ""),
            description=data.get("description", ""),
        )
        node = self.tree.insert(
            "",
            END,
            text=data["name"],
            values=[data_id, "project"],
            open=False,
        )
        for var in data.get("variable", []):
            create_variable(
                name=var.get("name", ""),
                content=var.get("content", ""),
                belong_name="folder",
                belong_id=data_id,
            )

        if item is not None:
            self.show_item(node, item)

    def show_item(self, node, items):
        parent = self.tree.item(node)
        for item in items:
            if "item" in item:
                childitem = item.pop("item")
                data_id = create_folder(
                    name=item["name"],
                    parent_id=parent["values"][0],
                    pre_script=item.get("pre_script", ""),
                    post_script=item.get("post_script", ""),
                    description=item.get("description", ""),
                )
                cnode = self.tree.insert(
                    node,
                    END,
                    text=item["name"],
                    values=[data_id, "folder"],
                    open=False,
                )
                if len(childitem) > 0:
                    self.show_item(cnode, childitem)
            else:
                data_id = create_request(
                    name=item.get("name", ""),
                    url=item.get("url", ""),
                    method=item.get("method", "GET"),
                    headers=item.get("headers", {}),
                    body=item.get("body", {}),
                    params=item.get("params", {}),
                    auth=item.get("auth", {}),
                    pre_script=item.get("pre_script", ""),
                    post_script=item.get("post_script", ""),
                    folder_id=parent["values"][0],
                )
                self.tree.insert(
                    node,
                    END,
                    text=item.get("method", "GET") + " " + item["name"],
                    values=[data_id, "request"],
                )

    def export_proj(self):
        """save program"""
        if len(self.tree.selection()) <= 0:
            show_error(self.window, "Error", "Please select a collection first.")
            return
        item = self.tree.item(self.tree.selection()[0])
        bean = retrieve_folder(id=item["values"][0])

        filepath = save_file(
            self.window,
            "Save",
            [("json files", "*.json")],
            initialdir=os.path.expanduser("~"),
            initialfile=bean["name"] + ".json",
            defaultextension=".json",
        )
        if filepath:
            with open(filepath, "w", encoding="utf-8") as file:
                bean.update({"item": self.traverse_children(self.tree.selection()[0])})
                file.write(json.dumps(bean, ensure_ascii=False, indent=4))

    def traverse_children(self, item):
        long_bean = []
        children = self.tree.get_children(item)
        for child in children:
            # Process the child item
            bean = self.tree.item(child)
            if bean["values"][1] == "folder":
                # Recursive call for further traversal
                value = retrieve_folder(id=bean["values"][0])
                value.update({"item": self.traverse_children(child)})
            else:
                value = retrieve_request(id=bean["values"][0])
                if value is None:
                    # Row vanished from the database (deleted elsewhere);
                    # exporting a null entry would corrupt the JSON.
                    continue
            long_bean.append(value)
        return long_bean

    def on_select(self, event):
        if event is not None:
            region = self.tree.identify("region", event.x, event.y)
            if region == "heading":
                return

        try:
            item_id = self.tree.selection()[0]
            item = self.tree.item(item_id)
            ctag = item["values"][1]
            if ctag == "folder":
                values = retrieve_folder(id=item["values"][0])
                path = self.get_path(item_id)
            elif ctag == "request":
                values = retrieve_request(id=item["values"][0])
                path = self.get_path(item_id)
            elif ctag == "project":
                values = retrieve_folder(id=item["values"][0])
                path = ""
            else:
                return
            if values is None:
                # The underlying row is gone; there is nothing to open.
                return
            self.callback(
                data=values,
                tag=ctag,
                request_id=item["values"][0],
                tab="collection",
                active="newitem",
                item_id=item_id,
                path=path,
            )
        except IndexError:
            pass

    def on_open(self):
        self.on_select(None)

    def get_path(self, item_id):
        parent_id = self.tree.parent(item_id)
        parent = self.tree.item(parent_id)
        if parent["values"][1] == "project":
            return parent["text"] + "/"
        elif parent["values"][1] == "folder":
            return self.get_path(parent_id) + parent["text"] + "/"
        return ""

    def on_right_click(self, event):
        item = self.tree.identify_row(event.y)

        if item:
            self.tree.selection_set(item)
            tag = self.tree.item(item)["values"][1]
            menu = qui.make_menu(self.window)
            if tag == "project":
                menu.addAction("Open", self.on_open)
                menu.addAction("Paste", self.on_paste).setEnabled(self.cut_board is not None)
                menu.addAction("Add folder", self.new_col)
                menu.addAction("Add request", self.new_req)
                menu.addAction("Export", self.export_proj)
                menu.addAction("Delete", self.delete_item)
            elif tag == "folder":
                menu.addAction("Open", self.on_open)
                menu.addAction("Copy", self.on_copy)
                menu.addAction("Cut", self.on_cut)
                menu.addAction("Paste", self.on_paste).setEnabled(self.cut_board is not None)
                menu.addAction("Add folder", self.new_col)
                menu.addAction("Add request", self.new_req)
                menu.addAction("Delete", self.delete_item)
            elif tag == "request":
                menu.addAction("Open", self.on_open)
                menu.addAction("Copy", self.on_copy)
                menu.addAction("Cut", self.on_cut)
                menu.addAction("Delete", self.delete_item)
            menu.exec_(QPoint(event.x_root, event.y_root))

    def new_proj(self):
        name = ask_string(self.window, "New Collection", "Name:", "New Collection")
        if name is None:
            return
        inserted_id = create_collection(name=name if name else "New Collection")
        self.tree.insert(
            "",
            END,
            text=name if name else "New Collection",
            values=[inserted_id, "project"],
        )

    def new_col(self):
        name = ask_string(self.window, "New Folder", "Name:", "New Folder")
        if name is None:
            return
        try:
            ctag = self.tree.item(self.tree.selection()[0])["values"][1]
            if ctag in ("folder", "project"):
                selected_node = self.tree.selection()[0]
            else:
                selected_node = self.tree.parent(self.tree.selection()[0])
            inserted_id = create_folder(
                name=name if name else "New Folder",
                parent_id=self.tree.item(selected_node)["values"][0],
            )
            self.tree.insert(
                selected_node,
                END,
                text=name if name else "New Folder",
                values=[inserted_id, "folder"],
            )
        except IndexError:
            inserted_id = create_folder(
                name=name if name else "New Collection", parent_id=0
            )
            self.tree.insert(
                "",
                END,
                text=name if name else "New Collection",
                values=[inserted_id, "project"],
            )

    def new_req(self, data=None):
        if data is None:
            name = ask_string(self.window, "New Request", "Name:", "New Request")
            if name is None:
                return

            try:
                ctag = self.tree.item(self.tree.selection()[0])["values"][1]
                if ctag in ("folder", "project"):
                    selected_node = self.tree.selection()[0]
                else:
                    selected_node = self.tree.parent(self.tree.selection()[0])

                inserted_id = create_request(
                    name=name if name else "New Request",
                    folder_id=self.tree.item(selected_node)["values"][0],
                )
                x = self.tree.insert(
                    selected_node,
                    END,
                    text="GET " + name if name else "New Request",
                    values=[inserted_id, "request"],
                )
                return x
            except IndexError:
                show_error(self.window, "Error", "Save error, please select folder.")

    def save_item(self, item_id, data):
        if item_id is None:
            if len(self.tree.selection()) > 0:
                selected = self.tree.selection()[0]
                selected_node = (
                    selected
                    if self.tree.item(selected)["values"][1] in ("folder", "project")
                    else self.tree.parent(selected)
                )
                inserted_id = create_request(
                    name=data["name"],
                    body=data["body"],
                    headers=data["headers"],
                    auth=data["auth"],
                    params=data["params"],
                    method=data["method"],
                    url=data["url"],
                    pre_script=data["pre_script"],
                    post_script=data["post_script"],
                    folder_id=self.tree.item(selected_node)["values"][0],
                )
                item_id = self.tree.insert(
                    selected_node,
                    END,
                    text=data["method"] + " " + data["name"],
                    values=[inserted_id, "request"],
                )
                return item_id, inserted_id
            else:
                show_error(self.window, "Error", "Save error, please select folder.")
                return None, None

        self.tree.item(item_id, text=data["name"])
        self.callback(action="rename", name=data["name"], item_id=item_id)
        return item_id

    def delete_item(self):
        if ask_yes_no(self.window, "Confirm", "Are you sure to delete the selected target?"):
            selected_nodes = self.tree.selection()
            if len(selected_nodes) > 0:
                for selected_node in selected_nodes:
                    item = self.tree.item(selected_node)
                    if item["values"][1] != "request":
                        self.delete_child_item(selected_node)
                        delete_folder(id=item["values"][0])
                    else:
                        delete_request(id=item["values"][0])
                    self.tree.delete(selected_node)

    def delete_child_item(self, item_id):
        children = self.tree.get_children(item_id)
        for child in children:
            item = self.tree.item(child)
            if item["values"][1] == "folder":
                self.delete_child_item(child)
                delete_folder(id=item["values"][0])
            else:
                delete_request(id=item["values"][0])

    def on_copy(self):
        selected_node = self.tree.selection()
        if selected_node:
            self.cut_board = {
                "action": "copy",
                "item_id": selected_node[0],
            }

    def on_cut(self):
        selected_node = self.tree.selection()
        if selected_node:
            self.cut_board = {
                "action": "cut",
                "item_id": selected_node[0],
            }

    def on_paste(self):
        selected_node = self.tree.selection()
        if selected_node and self.cut_board is not None:
            source_item = self.tree.item(self.cut_board["item_id"])
            target_item = self.tree.item(selected_node[0])
            if self.cut_board["action"] == "copy":
                if source_item["values"][1] == "request":
                    data = retrieve_request(id=source_item["values"][0])
                    if data is None:
                        return
                    data_id = create_request(
                        name=data["name"],
                        method=data["method"],
                        url=data["url"],
                        params=data["params"],
                        headers=data["headers"],
                        body=data["body"],
                        auth=data["auth"],
                        pre_script=data["pre_script"],
                        post_script=data["post_script"],
                        folder_id=target_item["values"][0],
                    )
                    self.tree.insert(
                        selected_node[0],
                        END,
                        text=data["method"] + " " + data["name"],
                        values=[data_id, "request"],
                    )
                else:
                    # Copy directories, subdirectories, and subprojects
                    data = retrieve_folder(id=source_item["values"][0])
                    data_id = create_folder(
                        name=data["name"],
                        parent_id=target_item["values"][0],
                        pre_script=data["pre_script"],
                        post_script=data["post_script"],
                        description=data["description"],
                    )
                    item_id = self.tree.insert(
                        selected_node[0],
                        END,
                        text=data["name"],
                        values=[data_id, "folder"],
                    )
                    self.copy_child(self.cut_board["item_id"], item_id)
            elif self.cut_board["action"] == "cut":
                if source_item["values"][1] == "request":
                    update_request(
                        id=source_item["values"][0], folder_id=target_item["values"][0]
                    )
                    self.tree.insert(
                        selected_node[0],
                        END,
                        text=source_item["text"],
                        values=source_item["values"],
                    )
                else:
                    update_folder(
                        id=source_item["values"][0], parent_id=target_item["values"][0]
                    )
                    item_id = self.tree.insert(
                        selected_node[0],
                        END,
                        text=source_item["text"],
                        values=source_item["values"],
                    )
                    self.cut_child(self.cut_board["item_id"], item_id)
                self.tree.delete(self.cut_board["item_id"])

    def copy_child(self, source_item_id, target_item_id):
        target_item = self.tree.item(target_item_id)
        children = self.tree.get_children(source_item_id)
        for child in children:
            item = self.tree.item(child)
            if item["values"][1] == "folder":
                data = retrieve_folder(id=item["values"][0])
                data_id = create_folder(
                    name=data["name"],
                    pre_script=data["pre_script"],
                    post_script=data["post_script"],
                    description=data["description"],
                    parent_id=target_item["values"][0],
                )
                new_id = self.tree.insert(
                    target_item_id,
                    END,
                    text=item["text"],
                    values=[data_id, "folder"],
                )
                self.copy_child(child, new_id)
            else:
                data = retrieve_request(id=item["values"][0])
                if data is None:
                    continue
                data_id = create_request(
                    name=data["name"],
                    method=data["method"],
                    folder_id=target_item["values"][0],
                    url=data["url"],
                    params=data["params"],
                    headers=data["headers"],
                    body=data["body"],
                    auth=data["auth"],
                    pre_script=data["pre_script"],
                    post_script=data["post_script"],
                )
                self.tree.insert(
                    target_item_id,
                    END,
                    text=item["text"],
                    values=[data_id, "request"],
                )

    def cut_child(self, source_item_id, target_item_id):
        children = self.tree.get_children(source_item_id)
        for child in children:
            item = self.tree.item(child)
            if item["values"][1] == "folder":
                new_id = self.tree.insert(
                    target_item_id, END, text=item["text"], values=item["values"]
                )
                self.cut_child(child, new_id)
            else:
                self.tree.insert(
                    target_item_id, END, text=item["text"], values=item["values"]
                )

    def on_start(self):
        """Read data from the workspace (in a worker thread, applied on UI thread)."""
        def worker():
            roots = []
            for coll in list_collection():
                node = {"id": coll["id"], "name": coll["name"], "kind": "project", "children": []}
                self._load_children(coll["id"], node["children"])
                roots.append(node)
            self.root.after(0, lambda: self._insert_nodes(roots, ""))

        threading.Thread(target=worker, daemon=True).start()

    def _load_children(self, folder_id, out):
        for folder in list_folder(parent_id=folder_id):
            child = {"id": folder["id"], "name": folder["name"], "kind": "folder", "children": []}
            self._load_children(folder["id"], child["children"])
            out.append(child)
        for req in list_request(folder_id=folder_id):
            out.append({"id": req["id"], "name": req["method"] + " " + req["name"], "kind": "request"})

    def _insert_nodes(self, nodes, parent):
        for node in nodes:
            item = self.tree.insert(
                parent, END, text=node["name"],
                values=[node["id"], node["kind"]], open=False,
            )
            # request nodes have no children
            self._insert_nodes(node.get("children", []), item)

    def on_close(self):
        """auto save"""
        pass

    def get_script(self, item_id):
        if self.tree.parent(item_id):
            scripts_list = []
            item = self.tree.item(self.tree.parent(item_id))
            value = retrieve_folder(id=item["values"][0])
            scripts_list.append(
                {
                    "pre_request_script": value.get("pre_script", ""),
                    "tests": value.get("post_script", ""),
                }
            )
            x = self.get_script(self.tree.parent(item_id))
            scripts_list += x
            return scripts_list
        return []

    def get_variable(self, item_id, name):
        """Look up a collection variable.

        Returns the value, or None when the name is not defined anywhere in the
        chain.  The previous version called ``.strip()`` on the result of a
        lookup that legitimately returns None (and on the None produced by
        running off the top of the tree), so any ``{{var}}`` that was not
        defined crashed request execution with an AttributeError.
        """
        if not self.tree.parent(item_id):
            return None
        item = self.tree.item(self.tree.parent(item_id))
        if item["values"][1] == "project":
            value = retrieve_folder_variable(folder_id=item["values"][0], name=name)
            return value.strip() if value is not None else None
        value = self.get_variable(self.tree.parent(item_id), name)
        return value.strip() if value is not None else None


class ProjectWindow:
    item_id = None

    def __init__(self, **kwargs) -> None:
        self.root = kwargs.get("master")
        self.callback = kwargs.get("callback")
        self.item_id = kwargs.get("item_id")
        data = kwargs.get("data")
        self.data_id = data["id"]
        self.data_name = data["name"]
        self.filepath = self.data_name
        # Deletions are pending until Save.  This must be per-window: as a class
        # attribute the list was shared by every collection tab, so saving one
        # tab replayed another tab's deletions.
        self.delete_list = []

        layout = QVBoxLayout(self.root)
        layout.setContentsMargins(4, 4, 4, 4)

        bar = QWidget(self.root)
        blay = QHBoxLayout(bar)
        blay.setContentsMargins(0, 0, 0, 0)
        self.path_label = QLabel(self.filepath, bar)
        blay.addWidget(self.path_label)
        blay.addStretch(1)

        rename_btn = QPushButton("Rename", bar)
        style_role(rename_btn, "secondary")
        rename_btn.clicked.connect(self.on_rename)
        blay.addWidget(rename_btn)

        save_btn = QPushButton("Save", bar)
        style_role(save_btn, "primary")
        save_btn.clicked.connect(self.on_save)
        blay.addWidget(save_btn)
        layout.addWidget(bar)

        notebook = QTabWidget(self.root)
        self.overview = QPlainTextEdit(notebook)
        self.overview.setPlainText(data.get("description", ""))
        notebook.addTab(self.overview, "Overview")
        # pre-request script
        self.script_box = CodeEditor(notebook)
        self.script_box.setPlainText(data.get("pre_script", ""))
        notebook.addTab(self.script_box, "Pre-request Script")

        # tests
        self.tests_box = CodeEditor(notebook)
        self.tests_box.setPlainText(data.get("post_script", ""))
        notebook.addTab(self.tests_box, "Post-response Script")

        variable_frame = QWidget(notebook)
        vlay = QVBoxLayout(variable_frame)
        vlay.setContentsMargins(0, 0, 0, 0)
        vlay.setSpacing(0)

        # action toolbar: add variables via a button (no heading click)
        var_bar = QWidget(variable_frame)
        vbl = QHBoxLayout(var_bar)
        vbl.setContentsMargins(4, 2, 4, 2)
        vbl.addStretch(1)
        var_add_btn = QPushButton("+ Add", var_bar)
        style_role(var_add_btn, "primary")
        var_add_btn.clicked.connect(self.var_on_add)
        vbl.addWidget(var_add_btn)
        vlay.addWidget(var_bar)

        self.treeview = TreeView(variable_frame, show="headings", columns=("name", "value", "actions"))
        self.treeview.heading("#1", text="Name")
        self.treeview.heading("#2", text="Value")
        self.treeview.heading("#3", text="Actions")
        self.treeview.column("#1", width=100)
        self.treeview.column("#2", width=200)
        self.treeview.column("#3", width=10)
        self.treeview.bind("<Button-1>", self.var_on_click)
        self.treeview.bind("<Double-1>", self.var_double_click)
        vlay.addWidget(self.treeview, 1)
        notebook.addTab(variable_frame, "Variable")
        layout.addWidget(notebook, 1)

        variable_list = list_variable(belong_name="folder", belong_id=self.data_id)
        for var in variable_list:
            self.treeview.insert(
                "",
                END,
                text=var["id"],
                values=[var["name"], var["content"], "Delete"],
            )

    def on_rename(self):
        name = ask_string(self.root, "Rename", "New name:", self.data_name)
        # An empty name would make the node impossible to find in the tree, so
        # treat it the same as cancelling.
        if not name:
            return
        update_folder(id=self.data_id, name=name)
        # Keep the stored name in sync: Save uses self.data_name, so without
        # this the next Save wrote the pre-rename name back over the rename.
        self.data_name = name
        self.filepath = name
        self.path_label.setText(name)
        self.callback(item_id=self.item_id, data={"name": name})

    def on_save(self):
        name = self.data_name
        description = self.overview.toPlainText()
        pre_request_script = self.script_box.toPlainText()
        tests = self.tests_box.toPlainText()

        description = description.rstrip("\n")
        pre_request_script = pre_request_script.rstrip("\n")
        tests = tests.rstrip("\n")

        if self.item_id is None:
            show_error(self.root, "Failed", "Save failed, item id missing.")
            return

        items = self.treeview.get_children()
        for item_id in items:
            item = self.treeview.item(item_id)
            if item["text"] == "":
                # Remember the new row id, otherwise the next Save sees text ""
                # again and inserts a second copy of the same variable.
                new_id = create_variable(
                    name=item["values"][0],
                    content=item["values"][1],
                    belong_name="folder",
                    belong_id=self.data_id,
                )
                self.treeview.item(item_id, text=new_id)
            else:
                update_variable(
                    id=item["text"], name=item["values"][0], content=item["values"][1]
                )

        for item_id in self.delete_list:
            delete_variable(id=item_id)
        self.delete_list = []

        update_folder(
            id=self.data_id,
            name=name,
            description=description,
            pre_script=pre_request_script,
            post_script=tests,
        )
        self.callback(item_id=self.item_id, data={"name": name})

    def var_on_add(self):
        """Add a new variable (button handler)."""
        name = ask_string(self.treeview, "New Variable", "Name:", "key")
        if name is not None:
            value = ask_string(self.treeview, "New Variable", "Value:", "value")
            if value is not None:
                self.treeview.insert("", END, text="", values=(name, value, "Delete"))

    def var_on_click(self, event):
        region = self.treeview.identify("region", event.x, event.y)
        column = self.treeview.identify_column(event.x)
        if region == "cell" and column == "#3":
            item_id = self.treeview.identify_row(event.y)
            self.treeview.selection_set(item_id)
            item = self.treeview.item(item_id)
            if ask_yes_no(self.treeview, "Confirm", "Are you sure you want to delete this variable?"):
                self.delete_list.append(item["text"])
                self.treeview.delete(item_id)

    def var_double_click(self, event):
        region = self.treeview.identify("region", event.x, event.y)
        column = self.treeview.identify_column(event.x)
        if region == "cell":
            item_id = self.treeview.identify_row(event.y)
            item = self.treeview.item(item_id)
            if column == "#1":
                name = ask_string(self.treeview, "Edit Variable", "Name:", item["values"][0])
                if name is not None:
                    self.treeview.item(item_id, values=(name, item["values"][1], "Delete"))
            elif column == "#2":
                value = ask_string(self.treeview, "Edit Variable", "Value:", item["values"][1])
                if value is not None:
                    self.treeview.item(item_id, values=(item["values"][0], value, "Delete"))


class FolderWindow:
    """Folder properties"""

    item_id = None

    def __init__(self, **kwargs) -> None:
        self.root = kwargs.get("master")
        self.callback = kwargs.get("callback")
        self.item_id = kwargs.get("item_id")
        data = kwargs.get("data")
        self.data_id = data.get("id")
        self.data_path = kwargs.get("path", "Name:")
        self.data_name = data.get("name", "New Folder")
        self.filepath = self.data_path + self.data_name

        layout = QVBoxLayout(self.root)
        layout.setContentsMargins(4, 4, 4, 4)

        bar = QWidget(self.root)
        blay = QHBoxLayout(bar)
        blay.setContentsMargins(0, 0, 0, 0)
        self.path_label = QLabel(self.filepath, bar)
        blay.addWidget(self.path_label)
        blay.addStretch(1)

        rename_btn = QPushButton("Rename", bar)
        style_role(rename_btn, "secondary")
        rename_btn.clicked.connect(self.on_rename)
        blay.addWidget(rename_btn)

        save_btn = QPushButton("Save", bar)
        style_role(save_btn, "primary")
        save_btn.clicked.connect(self.on_save)
        blay.addWidget(save_btn)
        layout.addWidget(bar)

        notebook = QTabWidget(self.root)
        self.overview = QPlainTextEdit(notebook)
        self.overview.setPlainText(data.get("description", ""))
        notebook.addTab(self.overview, "Overview")
        # pre-request script
        self.script_box = CodeEditor(notebook)
        self.script_box.setPlainText(data.get("pre_script", ""))
        notebook.addTab(self.script_box, "Pre-request Script")

        # tests
        self.tests_box = CodeEditor(notebook)
        self.tests_box.setPlainText(data.get("post_script", ""))
        notebook.addTab(self.tests_box, "Post-response Script")

        layout.addWidget(notebook, 1)

    def on_rename(self):
        name = ask_string(self.root, "Rename", "New name:", self.data_name)
        if not name:
            return
        update_folder(id=self.data_id, name=name)
        # Save() writes self.data_name back to the database, so the rename has
        # to be recorded here or the next Save silently undid it.
        self.data_name = name
        self.filepath = self.data_path + name
        self.path_label.setText(self.filepath)
        self.callback(item_id=self.item_id, data={"name": name})

    def on_save(self):
        name = self.data_name
        description = self.overview.toPlainText()
        pre_request_script = self.script_box.toPlainText()
        tests = self.tests_box.toPlainText()

        description = description.rstrip("\n")
        pre_request_script = pre_request_script.rstrip("\n")
        tests = tests.rstrip("\n")

        if self.item_id is None:
            show_error(self.root, "Failed", "Save failed, item id missing.")
            return
        update_folder(
            id=self.data_id,
            name=name,
            description=description,
            pre_script=pre_request_script,
            post_script=tests,
        )
        self.callback(item_id=self.item_id, data={"name": name})
