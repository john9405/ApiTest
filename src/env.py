import platform
import tkinter as tk
from tkinter import  simpledialog, messagebox
import ttkbootstrap as ttk

from .dao.crud import *


class EnvironmentWindow:

    def __init__(self, master=None, **kwargs):
        self.callback = kwargs.get("callback")
        self.root = ttk.Frame(master)
        self.treeview = ttk.Treeview(self.root, show='headings', columns=("name", "status"))
        scroll_y = ttk.Scrollbar(self.root, orient=tk.VERTICAL, command=self.treeview.yview)
        self.treeview.column("#1", anchor="w", width=100)
        self.treeview.column("#2", anchor="e", width=1)
        self.treeview.heading("#1", text="Name (+)", anchor="center")
        self.treeview.heading("#2", text="Status", anchor="center")
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        self.treeview.pack(fill=tk.BOTH, expand=tk.YES)
        self.treeview.bind("<Button-1>", self.on_click)
        self.treeview.bind("<Double-1>", self.on_select)
        if platform.system() == "Darwin":
            self.treeview.bind("<Control-Button-1>", self.on_right_click)
            self.treeview.bind("<Button-2>", self.on_right_click)
        else:
            self.treeview.bind("<Button-3>", self.on_right_click)
        self.treeview.config(yscrollcommand=scroll_y.set)

    def on_start(self):
        data = list_album()
        for item in data:
            self.treeview.insert("", tk.END, text=item.get('id'), values=(
                item.get('name'), "@" if item.get('is_active') else ""))

    def on_end(self):
        pass

    def on_click(self, event):
        region = self.treeview.identify('region', event.x, event.y)
        if region == 'heading':
            column = self.treeview.identify_column(event.x)
            if column == '#1':
                self.on_add()

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
            menu = tk.Menu(self.root, tearoff=0)
            menu.add_command(label="Edit", command=lambda: self.on_select(event))
            if item["values"][0] != "Globals":
                menu.add_command(label="Active", command=lambda: self.set_active(item_id))
                menu.add_command(label="Delete", command=self.on_delete)
            menu.post(event.x_root, event.y_root)

    def on_add(self):
        name = simpledialog.askstring("New Environment", prompt="Name", initialvalue="New Environment",
                                      parent=self.root)
        if name is not None:
            if name == "Globals":
                messagebox.showwarning("Warning", "Reserved words")
                return self.on_add()

            _id = create_album(name=name)
            self.treeview.insert("", tk.END, text=_id, values=(name, ""))

    def on_delete(self):
        if len(self.treeview.selection()) > 0:
            for item_id in self.treeview.selection():
                item = self.treeview.item(item_id)
                if item["values"][0] != "Globals":
                    delete_album(id=item['text'])
                    self.treeview.delete(self.treeview.selection())

    def set_variable(self, item_id, collection):
        item = self.treeview.item(item_id)
        self.treeview.item(item_id, values=(collection, item['values'][1]))
        self.callback(
            action="rename",
            collection=collection,
            item_id=item_id)

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
        return retrieve_global_variable(name=name).strip()

    def get_variable(self, name):
        return retrieve_active_variable(name=name).strip()


class VariableWindow:
    delete_list = []

    def __init__(self, master=None, **kwargs):
        self.root = master
        frame = ttk.Frame(self.root)
        self.data_id = kwargs.get('data_id')
        self.parent_id = kwargs.get('item_id')
        self.col_name = kwargs.get('collection')
        self.callback = kwargs.get('set_variable')

        ttk.Button(frame, text='Save', command=self.on_save, bootstyle="primary").pack(side=tk.RIGHT)
        if kwargs.get("collection") != 'Globals':
            ttk.Button(frame, text="Active", bootstyle="success",
                       command=lambda: kwargs.get("set_active")(kwargs.get("item_id"))).pack(side=tk.RIGHT)
            ttk.Button(frame, text='Rename', command=self.on_rename, bootstyle="secondary").pack(side=tk.RIGHT)
        ttk.Button(frame, text='Add', command=self.on_add, bootstyle="info").pack(side=tk.RIGHT)
        frame.pack(fill=tk.X)
        self.treeview = ttk.Treeview(self.root, show='headings', columns=("name", "value", "action"))
        self.treeview.heading("#1", text="Name", anchor="center")
        self.treeview.heading("#2", text="Value", anchor="center")
        self.treeview.heading("#3", text="Action", anchor="center")
        self.treeview.column("#1", anchor="w", width=1)
        self.treeview.column("#2", anchor="w", width=3)
        self.treeview.column("#3", anchor="w", width=1)
        self.treeview.pack(fill=tk.BOTH, expand=tk.YES)
        self.treeview.bind("<Button-1>", self.on_click)
        self.treeview.bind("<Double-1>", self.on_double_click)

        data = list_variable(belong_name="album", belong_id=kwargs.get("data_id"))
        for item in data:
            self.treeview.insert("", tk.END, text=item['id'], values=(item['name'], item['content'], "Delete"))

    def on_add(self):
        name = simpledialog.askstring("New Variable", prompt="Name", initialvalue="New Variable", parent=self.root)
        if name is not None:
            value = simpledialog.askstring("New Variable", prompt="Value", initialvalue="New Value", parent=self.root)
            if value is not None:
                self.treeview.insert("", tk.END, text='', values=(name, value, "Delete"))

    def on_click(self, event):
        region = self.treeview.identify('region', event.x, event.y)
        if region == 'cell':
            column = self.treeview.identify_column(event.x)
            item_id = self.treeview.identify_row(event.y)
            item = self.treeview.item(item_id)
            if column == "#3":
                if messagebox.askyesno("Confirm", "Are you sure you want to delete this variable?"):
                    self.delete_list.append(item['text'])
                    self.treeview.delete(item_id)

    def on_double_click(self, event):
        region = self.treeview.identify('region', event.x, event.y)
        if region == 'cell':
            column = self.treeview.identify_column(event.x)
            item_id = self.treeview.identify_row(event.y)
            item = self.treeview.item(item_id)

            if column == "#1":
                value = simpledialog.askstring("Edit Variable", prompt="Name", initialvalue=item['values'][0],
                                               parent=self.root)
                if value is not None:
                    self.treeview.item(item_id, values=(value, item['values'][1], 'Delete'))

            elif column == "#2":
                value = simpledialog.askstring("Edit Variable", prompt="Value", initialvalue=item['values'][1],
                                               parent=self.root)
                if value is not None:
                    self.treeview.item(item_id, values=(item['values'][0], value, 'Delete'))

    def on_rename(self):
        value = simpledialog.askstring("Rename", prompt="New Name", initialvalue=self.col_name, parent=self.root)
        if value is not None:
            update_album(name=value, id=self.data_id)
            self.callback(self.parent_id, value)

    def on_save(self):
        items = self.treeview.get_children()
        for item_id in items:
            item = self.treeview.item(item_id)
            if item['text'] == '':
                data_id = create_variable(name=item['values'][0], content=item['values'][1], belong_name="album", belong_id=self.data_id)
                self.treeview.item(item_id, text=data_id)
            else:
                update_variable(id=item['text'], name=item['values'][0], content=item['values'][1])

        for data_id in self.delete_list:
            delete_variable(id=data_id)
