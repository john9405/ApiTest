import os
import json

from PyQt5.QtCore import QPoint

from . import WORK_DIR
from . import qui
from .qui import TreeView
from .dao.crud import list_history, create_history, delete_history, retrieve_history, delete_all_history


class HistoryWindow:
    """History window"""

    history_list = []  # History list
    cache_file = os.path.join(WORK_DIR, "history.json")

    def __init__(self, window, callback=None):
        self.window = window
        self.callback = callback

        self.root = TreeView(window, show="headings", columns=("method", "url"))
        self.root.heading("#1", text="Method")
        self.root.heading("#2", text="URL")
        self.root.column("#1", width=10)
        self.root.column("#2", width=100)
        self.root.bind("<Double-1>", self.on_select)
        self.root.bind("<Button-3>", self.on_right_click)

    def on_delete(self):
        if len(self.root.selection()) > 0:
            for item_id in self.root.selection():
                item = self.root.item(item_id)
                delete_history(**{"id": item["text"]})
                self.root.delete(item_id)

    def on_clear(self):
        self.root.delete(self.root.get_children())
        delete_all_history()

    def on_select(self, event):
        item_id = self.root.identify_row(event.y)
        if item_id:
            item = self.root.item(item_id)
            data = retrieve_history(**{"id": item["text"]})
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
        region = self.root.identify('region', event.x, event.y)
        menu = qui.make_menu(self.window)
        if region == 'cell':
            if len(self.root.selection()) <= 0:
                item_id = self.root.identify_row(event.y)
                self.root.selection_set(item_id)
            menu.addAction("Open", lambda: self.on_select(event))
            menu.addAction("Delete", self.on_delete)
            menu.addAction("Clear", self.on_clear)
        elif region == 'nothing':
            menu.addAction("Clear", self.on_clear)
        menu.exec_(QPoint(event.x_root, event.y_root))

    def on_start(self):
        data = list_history()
        def populate():
            for item in data:
                self.root.insert("", 0, text=item['id'],
                                 values=(item.get('method', ''), item.get('url', '')))
        self.root.after(0, populate)

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
            "post_script": data.get("tests", ""),
            "res_body": "",
            "res_headers": "",
            "res_cookies": ""
        })
        self.root.insert("", 0, text=inserted_id,
                         values=(data.get('method', ''), data.get('url', '')))
