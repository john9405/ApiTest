import json
import os
import tkinter as tk
import platform
import threading
from tkinter import ttk, filedialog, messagebox, simpledialog
from tkinter.scrolledtext import ScrolledText

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
from .utils import CodeEditor


class CollectionWindow:
    cut_board = None

    def __init__(self, window, callback=None):
        self.window = window
        self.callback = callback

        self.tree = ttk.Treeview(window)
        scroll_y = ttk.Scrollbar(window, command=self.tree.yview)
        self.tree.heading("#0", text="Name(+)")
        self.tree.column("#0", width=100)
        scroll_y.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Button-1>", self.on_click)
        self.tree.bind("<Double-1>", self.on_select)
        if platform.system() == "Darwin":
            self.tree.bind("<Control-Button-1>", self.on_right_click)
            self.tree.bind("<Button-2>", self.on_right_click)
        else:
            self.tree.bind("<Button-3>", self.on_right_click)
        self.tree.config(yscrollcommand=scroll_y.set)

    def open_proj(self):
        """open a program"""
        filepath = filedialog.askopenfilename(
            filetypes=(("Json files", "*.json"),),
            initialdir=os.path.expanduser("~"),
            parent=self.window,
        )
        if filepath:
            with open(filepath, "r", encoding="utf-8") as f:
                try:
                    data = json.loads(f.read())
                    self.show_proj(data)
                except json.JSONDecodeError:
                    messagebox.showerror("Error", "The text content must be a json")

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
            tk.END,
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
                    tk.END,
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
                    tk.END,
                    text=item.get("method", "GET") + " " + item["name"],
                    values=[data_id, "request"],
                )

    def export_proj(self):
        """save program"""
        item = self.tree.item(self.tree.selection()[0])
        bean = retrieve_folder(id=item["values"][0])

        filepath = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("json files", "*.json")],
            initialdir=os.path.expanduser("~"),
            initialfile=bean["name"] + ".json",
            parent=self.window,
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
            long_bean.append(value)
        return long_bean

    def on_click(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region == "heading":
            self.new_proj()

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
            menu = tk.Menu(self.window, tearoff=0)
            if tag == "project":
                menu.add_command(label="Open", command=self.on_open)
                menu.add_command(
                    label="Paste",
                    command=self.on_paste,
                    state="disabled" if self.cut_board is None else "normal",
                )
                menu.add_command(label="Add folder", command=self.new_col)
                menu.add_command(label="Add request", command=self.new_req)
                menu.add_command(label="Export", command=self.export_proj)
                menu.add_command(label="Delete", command=self.delete_item)
            elif tag == "folder":
                menu.add_command(label="Open", command=self.on_open)
                menu.add_command(label="Copy", command=self.on_copy)
                menu.add_command(label="Cut", command=self.on_cut)
                menu.add_command(
                    label="Paste",
                    command=self.on_paste,
                    state="disabled" if self.cut_board is None else "normal",
                )
                menu.add_command(label="Add folder", command=self.new_col)
                menu.add_command(label="Add request", command=self.new_req)
                menu.add_command(label="Delete", command=self.delete_item)
            elif tag == "request":
                menu.add_command(label="Open", command=self.on_open)
                menu.add_command(label="Copy", command=self.on_copy)
                menu.add_command(label="Cut", command=self.on_cut)
                menu.add_command(label="Delete", command=self.delete_item)
            menu.post(event.x_root, event.y_root)

    def new_proj(self):
        name = simpledialog.askstring(
            "New Collection", "Name:", initialvalue="New Collection", parent=self.window
        )
        if name is None:
            return
        inserted_id = create_collection(name=name if name > "" else "New Collection")
        self.tree.insert(
            "",
            tk.END,
            text=name if name > "" else "New Collection",
            values=[inserted_id, "project"],
        )

    def new_col(self):
        name = simpledialog.askstring(
            "New Folder", "Name:", initialvalue="New Folder", parent=self.window
        )
        if name is None:
            return
        try:
            ctag = self.tree.item(self.tree.selection()[0])["values"][1]
            if ctag in ("folder", "project"):
                selected_node = self.tree.selection()[0]
            else:
                selected_node = self.tree.parent(self.tree.selection()[0])
            inserted_id = create_folder(
                name=name if name > "" else "New Folder",
                parent_id=self.tree.item(selected_node)["values"][0],
            )
            self.tree.insert(
                selected_node,
                tk.END,
                text=name if name > "" else "New Folder",
                values=[inserted_id, "folder"],
            )
        except IndexError:
            inserted_id = create_folder(
                name=name if name > "" else "New Collection", parent_id=0
            )
            self.tree.insert(
                "",
                tk.END,
                text=name if name > "" else "New Collection",
                values=[inserted_id, "project"],
            )

    def new_req(self, data=None):
        if data is None:
            name = simpledialog.askstring(
                "New Request", "Name:", initialvalue="New Request", parent=self.window
            )
            if name is None:
                return

            try:
                ctag = self.tree.item(self.tree.selection()[0])["values"][1]
                if ctag in ("folder", "project"):
                    selected_node = self.tree.selection()[0]
                else:
                    selected_node = self.tree.parent(self.tree.selection()[0])

                inserted_id = create_request(
                    name=name if name > "" else "New Request",
                    folder_id=self.tree.item(selected_node)["values"][0],
                )
                x = self.tree.insert(
                    selected_node,
                    tk.END,
                    text="GET " + name if name > "" else "New Request",
                    values=[inserted_id, "request"],
                )
                return x
            except IndexError:
                messagebox.showerror("Error", "Save error, please select folder.")

    def save_item(self, item_id, data):
        if item_id is None:
            if len(self.tree.selection()) > 0:
                selected_node = (
                    self.tree.selection()[0]
                    if self.tree.item(self.tree.selection()[0])["values"][1]
                    in ("folder", "project")
                    else self.tree.parent(self.tree.selection()[0])
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
                    tk.END,
                    text=data["method"] + " " + data["name"],
                    values=[inserted_id, "request"],
                )
                return item_id, inserted_id
            else:
                messagebox.showerror("Error", "Save error, please select folder.")
                return None, None

        self.tree.item(item_id, text=data["name"])
        self.callback(action="rename", name=data["name"], item_id=item_id)
        return item_id

    def delete_item(self):
        if messagebox.askyesno(
            "Confirm", "Are you sure to delete the selected target?"
        ):
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
                        tk.END,
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
                        tk.END,
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
                        tk.END,
                        text=source_item["text"],
                        values=source_item["values"],
                    )
                else:
                    update_folder(
                        id=source_item["values"][0], parent_id=target_item["values"][0]
                    )
                    item_id = self.tree.insert(
                        selected_node[0],
                        tk.END,
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
                    tk.END,
                    text=item["text"],
                    values=[data_id, "folder"],
                )
                self.copy_child(child, new_id)
            else:
                data = retrieve_request(id=item["values"][0])
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
                    tk.END,
                    text=item["text"],
                    values=[data_id, "request"],
                )

    def cut_child(self, source_item_id, target_item_id):
        children = self.tree.get_children(source_item_id)
        for child in children:
            item = self.tree.item(child)
            if item["values"][1] == "folder":
                new_id = self.tree.insert(
                    target_item_id, tk.END, text=item["text"], values=item["values"]
                )
                self.cut_child(child, new_id)
            else:
                self.tree.insert(
                    target_item_id, tk.END, text=item["text"], values=item["values"]
                )

    def on_start_child(self, data_id, item_id):
        data = list_folder(parent_id=data_id)
        for folder in data:
            new_id = self.tree.insert(
                item_id, tk.END, text=folder["name"], values=[folder["id"], "folder"]
            )
            thread = threading.Thread(
                target=self.on_start_child,
                args=(
                    folder["id"],
                    new_id,
                ),
            )
            thread.start()
        data = list_request(folder_id=data_id)
        for request in data:
            self.tree.insert(
                item_id,
                tk.END,
                text=request["method"] + " " + request["name"],
                values=[request["id"], "request"],
            )

    def on_start(self):
        """Read data from the workspace"""
        self.tree.delete(*self.tree.get_children())
        data = list_collection()
        for coll in data:
            new_id = self.tree.insert(
                "",
                tk.END,
                text=coll["name"],
                values=(
                    coll["id"],
                    "project",
                ),
            )
            thread = threading.Thread(
                target=self.on_start_child,
                args=(
                    coll["id"],
                    new_id,
                ),
            )
            thread.start()

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
        if self.tree.parent(item_id):
            item = self.tree.item(self.tree.parent(item_id))
            if item["values"][1] == "project":
                return retrieve_folder_variable(folder_id=item["values"][0], name=name)
            return self.get_variable(self.tree.parent(item_id), name)


class ProjectWindow:
    item_id = None
    delete_list = []

    def __init__(self, **kwargs) -> None:
        self.root = kwargs.get("master")
        self.callback = kwargs.get("callback")
        self.item_id = kwargs.get("item_id")
        data = kwargs.get("data")
        self.data_id = data["id"]
        self.data_name = data["name"]
        self.filepath = tk.StringVar(value=self.data_name)

        frame = ttk.Frame(self.root)
        frame.pack(fill=tk.X)
        ttk.Label(frame, textvariable=self.filepath).pack(side=tk.LEFT)
        save_btn = ttk.Button(frame, text="Save", command=self.on_save)
        save_btn.pack(side=tk.RIGHT)
        ttk.Button(frame, text="Rename", command=self.on_rename).pack(side=tk.RIGHT)

        notebook = ttk.Notebook(self.root)
        self.overview = ScrolledText(notebook)
        self.overview.insert(tk.END, data.get("description", ""))
        notebook.add(self.overview, text="Overview")
        # pre-request script
        self.script_box = CodeEditor(notebook)
        self.script_box.insert(tk.END, data.get("pre_script", ""))
        notebook.add(self.script_box, text="Pre-request Script")

        # tests
        self.tests_box = CodeEditor(notebook)
        self.tests_box.insert(tk.END, data.get("post_script", ""))
        notebook.add(self.tests_box, text="Post-response Script")

        variable_frame = ttk.Frame(notebook)
        self.treeview = ttk.Treeview(
            variable_frame, columns=("name", "value", "actions"), show="headings"
        )
        self.treeview.heading("#1", text="Name(+)")
        self.treeview.heading("#2", text="Value")
        self.treeview.heading("#3", text="Actions")
        self.treeview.column("#1", width=100)
        self.treeview.column("#2", width=200)
        self.treeview.column("#3", width=1)
        self.treeview.bind("<Button-1>", self.var_on_click)
        self.treeview.bind("<Double-1>", self.var_double_click)
        scrollbar = ttk.Scrollbar(variable_frame, command=self.treeview.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.treeview.pack(fill=tk.BOTH, expand=tk.YES)
        notebook.add(variable_frame, text="Variable")
        notebook.pack(expand=tk.YES, fill=tk.BOTH)

        variable_list = list_variable(belong_name="folder", belong_id=self.data_id)
        for var in variable_list:
            self.treeview.insert(
                "",
                tk.END,
                text=var["id"],
                values=[var["name"], var["content"], "Delete"],
            )

    def on_rename(self):
        name = simpledialog.askstring(
            "Rename", "New name:", initialvalue=self.data_name, parent=self.root
        )
        if name is not None:
            update_folder(id=self.data_id, name=name)
            self.filepath.set(name)
            self.callback(item_id=self.item_id, data={"name": name})

    def on_save(self):
        name = self.data_name
        description = self.overview.get("1.0", tk.END)
        pre_request_script = self.script_box.get("1.0", tk.END)
        tests = self.tests_box.get("1.0", tk.END)

        description = description.rstrip("\n")
        pre_request_script = pre_request_script.rstrip("\n")
        tests = tests.rstrip("\n")

        if self.item_id is None:
            messagebox.showerror("Failed", "Save failed, item id missing.")
            return

        items = self.treeview.get_children()
        for item_id in items:
            item = self.treeview.item(item_id)
            if item["text"] == "":
                create_variable(
                    name=item["values"][0],
                    content=item["values"][1],
                    belong_name="folder",
                    belong_id=self.data_id,
                )
            else:
                update_variable(
                    id=item["text"], name=item["values"][0], content=item["values"][1]
                )

        for item_id in self.delete_list:
            delete_variable(id=item_id)

        update_folder(
            id=self.data_id,
            name=name,
            description=description,
            pre_script=pre_request_script,
            post_script=tests,
        )
        self.callback(item_id=self.item_id, data={"name": name})

    def var_on_click(self, event):
        region = self.treeview.identify("region", event.x, event.y)
        column = self.treeview.identify_column(event.x)
        if region == "heading" and column == "#1":
            name = simpledialog.askstring(
                "New Variable", "Name:", initialvalue="key", parent=self.treeview
            )
            if name is not None:
                value = simpledialog.askstring(
                    "New Variable", "Value:", initialvalue="value", parent=self.treeview
                )
                if value is not None:
                    self.treeview.insert(
                        "", tk.END, text="", values=(name, value, "Delete")
                    )
        elif region == "cell" and column == "#3":
            item_id = self.treeview.identify_row(event.y)
            self.treeview.selection_set(item_id)
            item = self.treeview.item(item_id)
            if messagebox.askyesno(
                "Confirm", "Are you sure you want to delete this variable?"
            ):
                self.delete_list.append(item["text"])
                self.treeview.delete(item_id)

    def var_double_click(self, event):
        region = self.treeview.identify("region", event.x, event.y)
        column = self.treeview.identify_column(event.x)
        if region == "cell":
            item_id = self.treeview.identify_row(event.y)
            item = self.treeview.item(item_id)
            if column == "#1":
                name = simpledialog.askstring(
                    "Edit Variable",
                    "Name:",
                    initialvalue=item["values"][0],
                    parent=self.treeview,
                )
                if name is not None:
                    self.treeview.item(
                        item_id, values=(name, item["values"][1], "Delete")
                    )
            elif column == "#2":
                value = simpledialog.askstring(
                    "Edit Variable",
                    "Value:",
                    initialvalue=item["values"][1],
                    parent=self.treeview,
                )
                if value is not None:
                    self.treeview.item(
                        item_id, values=(item["values"][0], value, "Delete")
                    )


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
        self.filepath = tk.StringVar(value=self.data_path + self.data_name)

        frame = ttk.Frame(self.root)
        frame.pack(fill=tk.X)
        ttk.Label(frame, textvariable=self.filepath).pack(side=tk.LEFT)
        save_btn = ttk.Button(frame, text="Save", command=self.on_save)
        save_btn.pack(side=tk.RIGHT)
        rename_btn = ttk.Button(frame, text="Rename", command=self.on_rename)
        rename_btn.pack(side=tk.RIGHT)

        notebook = ttk.Notebook(self.root)
        self.overview = ScrolledText(notebook)
        self.overview.insert(tk.END, data.get("description", ""))
        notebook.add(self.overview, text="Overview")
        # pre-request script
        self.script_box = CodeEditor(notebook)
        self.script_box.insert(tk.END, data.get("pre_script", ""))
        notebook.add(self.script_box, text="Pre-request Script")

        # tests
        self.tests_box = CodeEditor(notebook)
        self.tests_box.insert(tk.END, data.get("post_script", ""))
        notebook.add(self.tests_box, text="Post-response Script")

        notebook.pack(expand=tk.YES, fill=tk.BOTH)

    def on_rename(self):
        name = simpledialog.askstring(
            "Rename", "New name:", initialvalue=self.data_name, parent=self.root
        )
        if name is not None:
            update_folder(id=self.data_id, name=name)
            self.filepath.set(self.data_path + name)
            self.callback(item_id=self.item_id, data={"name": name})

    def on_save(self):
        name = self.data_name
        description = self.overview.get("1.0", tk.END)
        pre_request_script = self.script_box.get("1.0", tk.END)
        tests = self.tests_box.get("1.0", tk.END)

        description = description.rstrip("\n")
        pre_request_script = pre_request_script.rstrip("\n")
        tests = tests.rstrip("\n")

        if self.item_id is None:
            messagebox.showerror("Failed", "Save failed, item id missing.")
            return
        update_folder(
            id=self.data_id,
            name=name,
            description=description,
            pre_script=pre_request_script,
            post_script=tests,
        )
        self.callback(item_id=self.item_id, data={"name": name})
