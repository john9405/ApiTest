import os
import json
import platform
import tkinter as tk
import ttkbootstrap as ttk

from . import WORK_DIR
from .dao.crud import list_history, create_history, delete_history, retrieve_history, delete_all_history


class HistoryWindow:
    """History window"""

    history_list = []  # History list
    cache_file = os.path.join(WORK_DIR, "history.json")

    def __init__(self, window, callback=None):
        self.window = window
        self.callback = callback

        self.treeview = ttk.Treeview(window, show='headings', columns=("method", "url"))
        self.treeview.heading("#1", text="Method")
        self.treeview.heading("#2", text="URL")
        self.treeview.column("#1", width=1)
        self.treeview.column("#2", width=100)
        scrollbar = ttk.Scrollbar(window, command=self.treeview.yview)
        scrollbar.pack(fill=tk.Y, side=tk.RIGHT)
        self.treeview.pack(side=tk.LEFT, fill=tk.BOTH, expand=tk.YES)
        self.treeview.config(yscrollcommand=scrollbar.set)
        self.treeview.bind("<Double-Button-1>", self.on_select)
        if platform.system() == "Darwin":
            self.treeview.bind("<Control-Button-1>", self.on_right_click)
            self.treeview.bind("<Button-2>", self.on_right_click)
        else:
            self.treeview.bind("<Button-3>", self.on_right_click)

    def on_delete(self):
        if len(self.treeview.selection()) > 0:
            for item_id in self.treeview.selection():
                item = self.treeview.item(item_id)
                delete_history(**{"id": item['text']})
                self.treeview.delete(item_id)

    def on_clear(self):
        self.treeview.delete(*self.treeview.get_children())
        delete_all_history()

    def on_select(self, event):
        item_id = self.treeview.identify_row(event.y)
        if item_id:
            item = self.treeview.item(item_id)
            data = retrieve_history(**{"id": item['text']})
            if data is None:
                return
            self.callback(data={
                "uuid": data['id'],
                'method': data['method'],
                'url': data['url'],
                'params': json.loads(data['params']),
                'headers': json.loads(data['headers']),
                'body': json.loads(data['body']),
                'auth': json.loads(data['auth']),
                'pre_script': data['pre_script'],
                'post_script': data['post_script']
            })

    def on_right_click(self, event):
        region = self.treeview.identify('region', event.x, event.y)
        menu = tk.Menu(self.window, tearoff=0)
        if region == 'cell':
            if len(self.treeview.selection()) <= 0:
                item_id = self.treeview.identify_row(event.y)
                self.treeview.selection_set(item_id)
            menu.add_command(label="Open", command=lambda: self.on_select(event))
            menu.add_command(label="Delete", command=self.on_delete)
            menu.add_command(label="Clear", command=self.on_clear)
        elif region == 'nothing':
            menu.add_command(label="Clear", command=self.on_clear)
        menu.post(event.x_root, event.y_root)

    def on_start(self):
        data = list_history()
        for item in data:
            self.treeview.insert("", 0, text=item['id'], values=(item.get('method', ''), item.get('url', '')))

    def on_end(self):
        pass

    def on_cache(self, data):
        inserted_id = create_history(**{
            "method": data.get('method', ''),
            "url": data.get('url', ''),
            "params": json.dumps(data.get('params', {})),
            "headers": json.dumps(data.get('headers', {})),
            "body": json.dumps(data.get('body', {})),
            "auth": json.dumps(data.get('auth', {})),
            "pre_script": data.get('pre_request_script', ''),
            "post_script":data.get("tests", ""),
            "res_body":"",
            "res_headers":"",
            "res_cookies":""
        })
        self.treeview.insert("", 0, text=inserted_id, values=(data.get('method', ''), data.get('url', '')))
