import json
import os
import platform
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk, simpledialog
from tkinter.scrolledtext import ScrolledText
import time
import re
import xml.dom.minidom
from io import BytesIO
import urllib.parse
from typing import Optional

import requests
from requests.auth import HTTPBasicAuth
from requests.auth import HTTPDigestAuth
from requests_oauthlib import OAuth1
from oauthlib.oauth1 import (
    SIGNATURE_HMAC_SHA1,
    SIGNATURE_HMAC_SHA256,
    SIGNATURE_HMAC_SHA512,
    SIGNATURE_RSA_SHA1,
    SIGNATURE_RSA_SHA256,
    SIGNATURE_RSA_SHA512,
    SIGNATURE_PLAINTEXT,
    SIGNATURE_TYPE_AUTH_HEADER,
    SIGNATURE_TYPE_QUERY,
    SIGNATURE_TYPE_BODY,
)
from bs4 import BeautifulSoup
from PIL import Image, ImageTk

from .dao.crud import update_request
from .utils import EditorTable, CodeEditor


class ParamsFrame(EditorTable):
    def __init__(self, master=None, **kw):
        self.cb = kw.pop("cb")
        super().__init__(master, **kw)

    def commit(
        self,
        item_id: Optional[str] = None,
        win: Optional[tk.Toplevel] = None,
        name_entry: Optional[ttk.Entry] = None,
        value_entry: Optional[ScrolledText] = None,
    ):
        name = name_entry.get()
        value = value_entry.get("1.0", "end")
        if self.check_name(item_id, name):
            if item_id is None:
                self.treeview.insert("", tk.END, values=(name, value))
            else:
                self.treeview.item(item_id, values=(name, value))
            win.destroy()
            self.cb(str(urllib.parse.urlencode(self.get_data())))
        else:
            messagebox.showerror("error", "Duplicate key")

    def on_del(self):
        if self.editable and len(self.treeview.selection()) > 0:
            self.treeview.delete(self.treeview.selection()[0])
            self.cb(str(urllib.parse.urlencode(self.get_data())))


class OauthFrame(ttk.Frame):
    def __init__(self, master=None, **kw):
        super().__init__(master, **kw)

        self.main_frame = None
        self.rsa_key_text = None
        self.client_key = tk.StringVar(self)
        self.client_secret = tk.StringVar(self)
        self.resource_owner_key = tk.StringVar(self)
        self.resource_owner_secret = tk.StringVar(self)
        self.signature_type = tk.StringVar(self, value=SIGNATURE_TYPE_AUTH_HEADER)
        self.signature_method = tk.StringVar(self, value=SIGNATURE_HMAC_SHA1)
        self.signature_method.trace_add("write", self.change_page)
        self.cpage = "hmac_page"

        self.canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.content_frame = ttk.Frame(self.canvas)
        self.content_window = self.canvas.create_window((0, 0), window=self.content_frame, anchor="nw")
        self.content_frame.bind("<Configure>", self._on_content_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        frame = ttk.Frame(self.content_frame)
        frame.columnconfigure(1, weight=1)
        ttk.Label(frame, text="Add authorization data to", width=22).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Combobox(
            frame,
            values=(
                SIGNATURE_TYPE_AUTH_HEADER,
                SIGNATURE_TYPE_QUERY,
                SIGNATURE_TYPE_BODY,
            ),
            textvariable=self.signature_type,
            state="readonly",
        ).grid(row=0, column=1, sticky="ew")
        ttk.Label(frame, text="Signature Method").grid(row=1, column=0, sticky="w", pady=3)
        ttk.Combobox(
            frame,
            values=(
                SIGNATURE_HMAC_SHA1,
                SIGNATURE_HMAC_SHA256,
                SIGNATURE_HMAC_SHA512,
                SIGNATURE_RSA_SHA1,
                SIGNATURE_RSA_SHA256,
                SIGNATURE_RSA_SHA512,
                SIGNATURE_PLAINTEXT,
            ),
            textvariable=self.signature_method,
            state="readonly",
        ).grid(row=1, column=1, sticky="ew")
        frame.pack(fill="x", padx=5, pady=5)
        self._bind_scroll_events(frame)

        self.page_container = ttk.Frame(self.content_frame)
        self.page_container.pack(fill="both", expand=True, padx=5, pady=(0, 5))
        self.hmac_page()
        self._bind_scroll_events(self.main_frame)
        self.after_idle(self._refresh_scroll_region)

    def change_page(self, *args):
        if self.signature_method.get() in (
            SIGNATURE_HMAC_SHA1,
            SIGNATURE_HMAC_SHA256,
            SIGNATURE_HMAC_SHA512,
            SIGNATURE_PLAINTEXT,
        ):
            new_page = "hmac_page"
        else:
            new_page = "rsa_page"
        if self.cpage != new_page:
            self._build_page(new_page)

    def _on_content_configure(self, _event=None):
        self._refresh_scroll_region()

    def _on_canvas_configure(self, event):
        self.canvas.itemconfigure(self.content_window, width=event.width)
        self._refresh_scroll_region()

    def _refresh_scroll_region(self):
        self.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _bind_scroll_events(self, widget):
        if isinstance(widget, ScrolledText):
            return
        widget.bind("<MouseWheel>", self._on_mousewheel, add="+")
        widget.bind("<Button-4>", self._on_mousewheel, add="+")
        widget.bind("<Button-5>", self._on_mousewheel, add="+")
        for child in widget.winfo_children():
            self._bind_scroll_events(child)

    def _on_mousewheel(self, event):
        if event.num == 4:
            self.canvas.yview_scroll(-1, "units")
            return "break"
        if event.num == 5:
            self.canvas.yview_scroll(1, "units")
            return "break"
        if event.delta:
            self.canvas.yview_scroll(int(-event.delta / 120), "units")
            return "break"
        return None

    def _build_page(self, page_name):
        if self.main_frame is not None:
            self.main_frame.destroy()
            self.main_frame = None
            self.rsa_key_text = None
        if page_name == "hmac_page":
            self.hmac_page()
        else:
            self.rsa_page()
        self.cpage = page_name
        self.canvas.yview_moveto(0)
        self._bind_scroll_events(self.main_frame)
        self.after_idle(self._refresh_scroll_region)

    def hmac_page(self):
        self.main_frame = ttk.Frame(self.page_container)
        self.main_frame.columnconfigure(1, weight=1)
        ttk.Label(self.main_frame, text="Consumer Key", width=22).grid(row=0, column=0, sticky="w")
        ttk.Entry(self.main_frame, textvariable=self.client_key).grid(row=0, column=1, sticky="ew")
        ttk.Label(self.main_frame, text="Consumer Secret").grid(row=1, column=0, sticky="w", pady=3)
        ttk.Entry(self.main_frame, textvariable=self.client_secret).grid(row=1, column=1, sticky="ew")
        ttk.Label(self.main_frame, text="Access Token").grid(row=2, column=0, sticky="w")
        ttk.Entry(self.main_frame, textvariable=self.resource_owner_key).grid(row=2, column=1, sticky="ew")
        ttk.Label(self.main_frame, text="Token Secret").grid(row=3, column=0, sticky="w", pady=3)
        ttk.Entry(self.main_frame, textvariable=self.resource_owner_secret).grid(row=3, column=1, sticky="ew")
        self.main_frame.pack(fill="x")

    def rsa_page(self):
        self.main_frame = ttk.Frame(self.page_container)
        self.main_frame.columnconfigure(1, weight=1)
        ttk.Label(self.main_frame, text="Consumer Key", width=22).grid(row=0, column=0, sticky="w")
        ttk.Entry(self.main_frame, textvariable=self.client_key).grid(row=0, column=1, sticky="ew")
        ttk.Label(self.main_frame, text="Access Token").grid(row=1, column=0, sticky="w", pady=3)
        ttk.Entry(self.main_frame, textvariable=self.resource_owner_key).grid(row=1, column=1, sticky="ew")
        ttk.Label(self.main_frame, text="Private key").grid(row=2, column=0, sticky="w")
        ttk.Button(self.main_frame, text="Select File", command=self.on_open).grid(row=2, column=1, sticky="w")
        self.rsa_key_text = ScrolledText(self.main_frame, width=40, height=30)
        self.rsa_key_text.grid(row=3, column=1, sticky="nsew")
        self.main_frame.pack(fill="both", expand=True)

    def on_open(self):
        filepath = filedialog.askopenfilename(initialdir=os.path.expanduser("~"))
        if filepath:
            with open(filepath, "r", encoding="utf-8") as f:
                self.rsa_key_text.delete("1.0", "end")
                self.rsa_key_text.insert(tk.END, f.read())

    def set(self, data: dict):
        signature_method = data.get("signature_method", SIGNATURE_HMAC_SHA1)
        if signature_method in (
            SIGNATURE_HMAC_SHA1,
            SIGNATURE_HMAC_SHA256,
            SIGNATURE_HMAC_SHA512,
            SIGNATURE_PLAINTEXT,
        ):
            self._build_page("hmac_page")
            self.client_key.set(data.get("client_key", ""))
            self.client_secret.set(data.get("client_secret", ""))
            self.resource_owner_key.set(data.get("resource_owner_key", ""))
            self.resource_owner_secret.set(data.get("resource_owner_secret", ""))
            self.signature_type.set(data.get("signature_type", SIGNATURE_TYPE_AUTH_HEADER))
            self.signature_method.set(signature_method)
        else:
            self._build_page("rsa_page")
            self.client_key.set(data.get("client_key", ""))
            self.resource_owner_key.set(data.get("resource_owner_key", ""))
            self.rsa_key_text.delete("1.0", "end")
            self.rsa_key_text.insert("1.0", data.get("rsa_key", ""))
            self.signature_type.set(data.get("signature_type", SIGNATURE_TYPE_AUTH_HEADER))
            self.signature_method.set(signature_method)

    def get(self):
        if self.signature_method.get() in (
            SIGNATURE_HMAC_SHA1,
            SIGNATURE_HMAC_SHA256,
            SIGNATURE_HMAC_SHA512,
            SIGNATURE_PLAINTEXT,
        ):
            data = {
                "client_key": self.client_key.get(),
                "client_secret": self.client_secret.get(),
                "resource_owner_key": self.resource_owner_key.get(),
                "resource_owner_secret": self.resource_owner_secret.get(),
                "signature_type": self.signature_type.get(),
                "signature_method": self.signature_method.get(),
            }
        else:
            data = {
                "signature_type": self.signature_type.get(),
                "signature_method": self.signature_method.get(),
                "client_key": self.client_key.get(),
                "resource_owner_key": self.resource_owner_key.get(),
                "rsa_key": self.rsa_key_text.get("1.0", "end-1c"),
            }
        return data


class AuthFrame(ttk.Frame):
    def __init__(self, master=None, **kw):
        super().__init__(master, **kw)
        self.cpage = "noauth"
        self.auth_type = tk.StringVar(self, value="noauth")
        self.auth_type.trace_add("write", self.change_page)
        frame = ttk.Frame(self)
        ttk.Label(frame, text="Type:").grid(row=0, column=0)
        ttk.Combobox(
            frame,
            values=("noauth", "base", "digest", "oauth1"),
            textvariable=self.auth_type,
            state="readonly",
        ).grid(row=0, column=1)
        frame.pack(fill="x", padx=5, pady=5)
        self.main_frame = ttk.Frame(self)
        ttk.Label(self.main_frame, text="This request does not use any authorization.").pack()
        self.main_frame.pack()
        self.username = tk.StringVar(self)
        self.password = tk.StringVar(self)
        self.oauth_frame = None

    def change_page(self, *args):
        if self.cpage != self.auth_type.get():
            self.main_frame.forget()
            if self.auth_type.get() == "oauth1":
                self.oauth1_page()
            elif self.auth_type.get() == "base" or self.auth_type.get() == "digest":
                self.base_digest_page()
            else:
                self.no_auth_page()
            self.cpage = self.auth_type.get()

    def no_auth_page(self):
        self.main_frame = ttk.Frame(self)
        ttk.Label(self.main_frame, text="This request does not use any authorization.").pack()
        self.main_frame.pack()

    def base_digest_page(self):
        self.main_frame = ttk.Frame(self)
        ttk.Label(self.main_frame, text="username:").grid(row=0, column=0)
        ttk.Entry(self.main_frame, textvariable=self.username).grid(row=0, column=1)
        ttk.Label(self.main_frame, text="password:").grid(row=1, column=0, pady=3)
        ttk.Entry(self.main_frame, textvariable=self.password).grid(row=1, column=1)
        self.main_frame.pack()

    def oauth1_page(self):
        self.main_frame = ttk.Frame(self)
        self.oauth_frame = OauthFrame(self.main_frame)
        self.oauth_frame.pack(fill="both", expand=True)
        self.main_frame.pack(fill="both", expand=True)

    def get(self) -> dict:
        res = {"type": self.auth_type.get()}
        if res["type"] == "oauth1":
            res.update({"oauth1": self.oauth_frame.get()})
        elif res["type"] == "base":
            res.update(
                {
                    "base": {
                        "username": self.username.get(),
                        "password": self.password.get(),
                    }
                }
            )
        elif res["type"] == "digest":
            res.update(
                {
                    "digest": {
                        "username": self.username.get(),
                        "password": self.password.get(),
                    }
                }
            )
        return res

    def set(self, data: dict):
        self.auth_type.set(data.get("type", "noauth"))
        if self.auth_type.get() == "oauth1":
            self.oauth_frame.set(data.get("oauth1", {}))
        elif self.auth_type.get() == "base":
            self.username.set(data.get("base", {}).get("username", ""))
            self.password.set(data.get("base", {}).get("password", ""))
        elif self.auth_type.get() == "digest":
            self.username.set(data.get("digest", {}).get("username", ""))
            self.password.set(data.get("digest", {}).get("password", ""))


class BodyFrame:
    current_date_type = "none"

    def __init__(self, **kwargs) -> None:
        self.root = ttk.Frame(kwargs.get("master"))
        self.mode = tk.StringVar()
        self.mode.set(self.current_date_type)
        self.mode.trace_add("write", self.on_data_type_change)
        self.toolbar = ttk.Frame(self.root)
        ttk.Radiobutton(
            self.toolbar, text="none", variable=self.mode, value="none"
        ).pack(side="left")
        ttk.Radiobutton(
            self.toolbar,
            text="urlencoded",
            variable=self.mode,
            value="urlencoded",
        ).pack(side="left")
        ttk.Radiobutton(self.toolbar, text="raw", variable=self.mode, value="raw").pack(
            side="left"
        )
        self.toolbar.pack(fill=tk.X)

        self.toolbar_right = None
        self.main_frame = ttk.Frame(self.root)
        ttk.Label(self.main_frame, text="This request does not have a body").pack()
        self.main_frame.pack()
        self.edit_table = None
        self.options = None
        self.scrolled_text = None

    def on_data_type_change(self, *args):
        if self.mode.get() != self.current_date_type:
            if self.toolbar_right:
                self.toolbar_right.forget()

            if self.main_frame:
                self.main_frame.forget()

            if self.mode.get() == "none":
                self.main_frame = ttk.Frame(self.root)
                ttk.Label(self.main_frame, text="This request does not have a body").pack()
                self.main_frame.pack()
                self.current_date_type = "none"

            elif self.mode.get() == "urlencoded":
                self.show_urlencoded()
                self.current_date_type = "urlencoded"

            elif self.mode.get() == "raw":
                self.show_raw()
                self.current_date_type = "raw"

    def show_urlencoded(self):
        self.main_frame = ttk.Frame(self.root)
        self.edit_table = EditorTable(self.main_frame, editable=True)
        self.edit_table.pack(fill=tk.BOTH, expand=tk.YES)
        self.main_frame.pack(fill=tk.BOTH, expand=tk.YES)

    def show_raw(self):
        self.toolbar_right = ttk.Frame(self.toolbar)
        self.options = ttk.Combobox(
            self.toolbar_right, values=["Text", "JSON", "XML", "HTML"], width=6
        )
        self.options.current(0)
        self.options["state"] = "readonly"
        self.options.pack(side="left")
        self.toolbar_right.pack(side="left")

        self.main_frame = ttk.Frame(self.root)
        self.scrolled_text = ScrolledText(self.main_frame)
        self.scrolled_text.pack(fill=tk.BOTH, expand=True)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

    def insert(self, kw):
        if kw.get("mode") == "urlencoded":
            self.mode.set("urlencoded")
            self.edit_table.set_data(kw.get("urlencoded"))
        elif kw.get("mode") == "raw":
            self.mode.set("raw")
            index = ["Text", "JSON", "XML", "HTML"].index(kw.get("options"))
            self.options.current(index)
            self.scrolled_text.delete("1.0", "end")
            self.scrolled_text.insert("end", kw.get("raw"))
        else:
            self.mode.set("none")

    def get(self):
        return {
            "mode": self.mode.get(),
            "options": self.options.get() if self.options else "",
            "raw": self.scrolled_text.get("1.0", "end") if self.scrolled_text else "",
            "urlencoded": self.edit_table.get_data() if self.edit_table else {},
        }


class RequestWindow:
    item_id = None
    data_id = None
    data_name = 'New Request'
    data_path = ''
    method_list = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]

    def __init__(self, **kwargs):
        self.root = kwargs.get("window")
        window = ttk.Frame(self.root)
        window.pack(fill='both', expand=tk.YES, padx=5, pady=5)
        self.get_script = kwargs.get("get_script")
        self.env_variable = kwargs.get("env_variable")
        self.glb_variable = kwargs.get('glb_variable')
        self.local_variable = kwargs.get("local_variable")
        self.cache_history = kwargs.get('cache_history')
        self.save_item = kwargs.get('save_item')
        self.callback = kwargs.get("callback")
        self.data_path = kwargs.get('path', '')
        self.filepath = tk.StringVar(value=self.data_path + self.data_name)

        ff = ttk.Frame(window)
        ff.pack(fill=tk.X)
        ttk.Label(ff, textvariable=self.filepath).pack(side=tk.LEFT)
        save_btn = ttk.Button(ff, text="Save", command=self.save_handler)
        save_btn.pack(side=tk.RIGHT)
        ttk.Button(ff, text='Rename', command=self.on_rename).pack(side=tk.RIGHT)

        north = ttk.Frame(window)
        north.pack(fill=tk.X)
        # Create request mode drop-down box and URL input box
        self.method_box = ttk.Combobox(north, width=8, values=self.method_list)
        self.method_box.current(0)
        self.method_box["state"] = "readonly"
        self.method_box.pack(side=tk.LEFT)
        sub_btn = ttk.Button(north, text="Send")  # Send request button
        sub_btn.config(command=self.send_request)  # Bind the event handler to send the request button
        sub_btn.pack(side=tk.RIGHT)
        self.url = tk.StringVar()
        self.url.trace("w", self.change_url)
        url_box = ttk.Entry(north, textvariable=self.url)
        url_box.pack(fill=tk.BOTH, pady=3)

        # Create a PanedWindow
        paned_window = ttk.PanedWindow(window, orient=tk.VERTICAL)
        paned_window.pack(fill=tk.BOTH, expand=tk.YES)

        # Create notebook
        notebook = ttk.Notebook(paned_window)
        paned_window.add(notebook, weight=1)

        # Create a query parameter page
        self.params_frame = ParamsFrame(
            master=notebook, editable=True, cb=self.update_url
        )
        notebook.add(self.params_frame, text="Params")
        self.auth_frame = AuthFrame(master=notebook)
        notebook.add(self.auth_frame, text="Authorization")
        # Create the request header page
        self.headers_frame = EditorTable(master=notebook, editable=True)
        notebook.add(self.headers_frame, text="Headers")

        # Create the request body page
        self.body_box = BodyFrame(master=notebook)
        notebook.add(self.body_box.root, text="Body")

        # pre-request script
        self.script_box = CodeEditor(notebook)
        notebook.add(self.script_box, text="Pre-request Script")

        # tests
        self.tests_box = CodeEditor(notebook)
        notebook.add(self.tests_box, text="Post-response Script")

        # Create response area
        res_note = ttk.Notebook(paned_window)
        paned_window.add(res_note, weight=1)

        self.res_body_box = ScrolledText(res_note)
        res_note.add(self.res_body_box, text="Body")

        self.res_cookie_table = EditorTable(res_note)
        res_note.add(self.res_cookie_table, text="Cookies")

        self.res_header_table = EditorTable(res_note)
        res_note.add(self.res_header_table, text="Headers")

        self.res_tests_box = ConsoleText(res_note)
        res_note.add(self.res_tests_box, text="Console")

    def on_rename(self):
        if self.data_id is None:
            messagebox.showwarning("Warning", "Please save it first.")
            return
        name = simpledialog.askstring("Rename", "Enter new name:", initialvalue=self.data_name, parent=self.root)
        if name is not None:
            update_request(**{"id": self.data_id, "name": name})
            self.data_name = name
            self.filepath.set(self.data_path + self.data_name)
            self.save_item(self.item_id, {'name': name})
            self.callback(name=name, item_id=self.item_id)

    def save_handler(self):
        """Save test script"""
        name = self.data_name
        method = self.method_box.get()
        url = self.url.get()
        params = self.params_frame.get_data()
        headers = self.headers_frame.get_data()
        body = self.body_box.get()
        pre_request_script = self.script_box.get("1.0", tk.END)
        tests = self.tests_box.get("1.0", tk.END)
        opt_auth = self.auth_frame.get()
        pre_request_script = pre_request_script.rstrip("\n")
        tests = tests.rstrip("\n")

        if name == "" and url > "":
            name = url
        elif name == "":
            name = "New Request"
        if self.data_id is None:
            self.item_id, self.data_id = self.save_item(self.item_id, {
                "method": method,
                "url": url,
                "params": params,
                "headers": headers,
                "body": body,
                "pre_script": pre_request_script,
                "post_script": tests,
                "name": name,
                "auth": opt_auth,
            })
        else:
            update_request(**{
                "method": method,
                "url": url,
                "params": json.dumps(params),
                "headers": json.dumps(headers),
                "body": json.dumps(body),
                "pre_script": pre_request_script,
                "post_script": tests,
                "name": name,
                "auth": json.dumps(opt_auth),
                "id": self.data_id
            })
            self.save_item(self.item_id, {'name': name})
        self.callback(name=name, item_id=self.item_id)

    def fill_blank(self, data):
        self.data_id = data.get("id")
        self.method_box.current(self.method_list.index(data.get("method", "GET")))
        self.url.set(data.get("url", ""))
        self.headers_frame.set_data(data.get("headers", {}))
        self.body_box.insert(data.get("body", {}))
        self.script_box.delete("1.0", tk.END)
        self.script_box.insert(tk.END, data.get("pre_script", ""))
        self.tests_box.delete("1.0", tk.END)
        self.tests_box.insert(tk.END, data.get("post_script", ""))
        self.data_name = data.get("name", "New Request")
        self.filepath.set(self.data_path + self.data_name)
        self.auth_frame.set(data.get("auth", {}))

    def send_request(self):
        thread = threading.Thread(target=self.http_handle)
        thread.start()

    def fill_var(self, data):
        varlist = re.finditer(r"\{\{[^{}]*\}\}", data)
        for var in varlist:
            val = self.local_variable(self.item_id, var.group()[2:-2])
            if val is None:
                val = self.glb_variable(var.group()[2:-2])
            if val is not None:
                data = data.replace(var.group(), val)
        return data

    def http_handle(self):
        """Define the function that sends the request"""
        console = Console(self.res_tests_box)
        # Gets the request method and URL
        method = self.method_box.get()
        url = self.url.get()
        if url is None or url == "":
            messagebox.showerror("Error", "Please enter the request address")
            return

        url = self.fill_var(url)

        # Gets query parameters, request headers, and request bodies
        headers = self.headers_frame.get_data()
        headers = json.dumps(headers)
        headers = self.fill_var(headers)
        headers = json.loads(headers)

        req_options = self.body_box.get()
        if req_options.get("mode") == "raw":
            body = req_options.get("raw")
        elif req_options.get("mode") == "urlencoded":
            body = req_options.get("urlencoded")
            body = json.dumps(body)
        else:
            body = ""
        body = self.fill_var(body)

        if req_options.get("mode") == "urlencoded" or (req_options.get("mode") == "raw" and req_options.get("options") == "JSON"):
            try:
                body = json.loads(body)
            except json.JSONDecodeError:
                body = {}

        if self.item_id is not None:
            script_list = self.get_script(self.item_id)
        else:
            script_list = []

        pre_request_script = self.script_box.get("1.0", tk.END)
        tests = self.tests_box.get("1.0", tk.END)
        opt_auth = self.auth_frame.get()
        for item in opt_auth.keys():
            if isinstance(opt_auth[item], dict):
                for citem in opt_auth[item]:
                    temp = opt_auth[item][citem]
                    temp = self.fill_var(temp)
                    opt_auth[item][citem] = temp
        auth = None
        if opt_auth["type"] == "base":
            auth = HTTPBasicAuth(opt_auth["base"]["username"], opt_auth["base"]["password"])
        elif opt_auth["type"] == "digest":
            auth = HTTPDigestAuth(opt_auth["digest"]["username"], opt_auth["digest"]["password"])
        elif opt_auth["type"] == "oauth1":
            if opt_auth["oauth1"]["signature_method"] in (
                SIGNATURE_HMAC_SHA1,
                SIGNATURE_HMAC_SHA256,
                SIGNATURE_HMAC_SHA512,
                SIGNATURE_PLAINTEXT,
            ):
                auth = OAuth1(
                    opt_auth["oauth1"]["client_key"],
                    opt_auth["oauth1"]["client_secret"],
                    opt_auth["oauth1"]["resource_owner_key"],
                    opt_auth["oauth1"]["resource_owner_secret"],
                    signature_method=opt_auth["oauth1"]["signature_method"],
                    signature_type=opt_auth["oauth1"]["signature_type"],
                )
            else:
                auth = OAuth1(
                    opt_auth["oauth1"]["client_key"],
                    resource_owner_key=opt_auth["oauth1"]["resource_owner_key"],
                    rsa_key=opt_auth["oauth1"]["rsa_key"],
                    signature_method=opt_auth["oauth1"]["signature_method"],
                    signature_type=opt_auth["oauth1"]["signature_type"],
                )

        try:
            exec(pre_request_script, {
                "req": {"body": body, "headers": headers, "url": url},
                "globals": self.glb_variable,
                "collectionVariables": lambda x: self.local_variable(self.item_id, x),
                "environment": self.env_variable,
                "console": console
            })
        except Exception as error:
            console.error(str(error))

        for script in script_list:
            try:
                exec(script["pre_request_script"], {
                    "req": {"body": body, "headers": headers, "url": url},
                    "globals": self.glb_variable,
                    "collectionVariables": lambda x: self.local_variable(self.item_id, x),
                    "environment": self.env_variable,
                    "console": console
                })
            except Exception as error:
                console.error(str(error))
        start_time = time.time()

        if req_options.get("mode") == "urlencoded":
            headers.update({"Content-Type": "application/x-www-form-urlencoded"})
        elif req_options.get("mode") == "raw":
            if req_options.get("options") == "JSON":
                body = json.dumps(body)
                headers.update({"Content-Type": "application/json"})
            elif req_options.get("options") == "Text":
                headers.update({"Content-Type": "text/plain"})
            elif req_options.get("options") == "XML":
                headers.update({"Content-Type": "application/xml"})
            elif req_options.get("options") == "HTML":
                headers.update({"Content-Type": "text/html"})

        # 发送网络请求
        try:
            if method == "GET":
                response = requests.get(url, headers=headers, auth=auth)
            elif method == "POST":
                response = requests.post(url, data=body, headers=headers, auth=auth)
            elif method == "PUT":
                response = requests.put(url, data=body, headers=headers, auth=auth)
            elif method == "PATCH":
                response = requests.patch(url, data=body, headers=headers, auth=auth)
            elif method == "DELETE":
                response = requests.delete(url, headers=headers, auth=auth)
            elif method == "HEAD":
                response = requests.head(url, headers=headers, auth=auth)
            elif method == "OPTIONS":
                response = requests.options(url, headers=headers, auth=auth)
            else:
                messagebox.showerror("Error", "Unsupported request type")
                return
        except requests.exceptions.MissingSchema:
            messagebox.showerror("Error", "Request error")
            return
        except requests.exceptions.SSLError:
            messagebox.showerror("Error", "SSL certificate verify failed")
            return
        except requests.exceptions.ConnectionError:
            messagebox.showerror("Error", "Connection refused")
            return
        except requests.exceptions.Timeout:
            messagebox.showerror("Error", "Request timeout")
            return
        except requests.exceptions.RequestException as error:
            messagebox.showerror("Error", str(error))
            return

        cost_time = time.time() - start_time
        if cost_time < 1:
            cost_time = f"{round(cost_time * 1000)}ms"
        else:
            cost_time = f"{round(cost_time)}s"
        # 将响应显示在响应区域
        self.res_cookie_table.clear_data()
        self.res_cookie_table.set_data(dict(response.cookies))
        self.res_header_table.clear_data()
        self.res_header_table.set_data(dict(response.headers))
        content_type = response.headers.get("Content-Type")

        self.res_body_box.delete("1.0", tk.END)
        if "application/json" in content_type:
            self.res_body_box.insert(tk.END, json.dumps(response.json(), indent=2, ensure_ascii=False))
        elif "text/html" in content_type:
            response.encoding = "utf-8"
            soup = BeautifulSoup(response.text, "html.parser")
            self.res_body_box.insert(tk.END, soup.prettify())
        elif "text/xml" in content_type or "application/xml" in content_type:
            response.encoding = "utf-8"
            dom = xml.dom.minidom.parseString(response.text)
            self.res_body_box.insert(tk.END, dom.toprettyxml(indent="  "))
        elif "image" in content_type:
            data_stream = BytesIO(response.content)
            pil_image = Image.open(data_stream)
            tk_image = ImageTk.PhotoImage(pil_image)
            self.res_body_box.image_create(tk.END, image=tk_image)
        else:
            self.res_body_box.insert(tk.END, response.text)

        console.info(f"{method} {url} {response.status_code} {cost_time}")
        try:
            exec(tests, {
                "res": response,
                "globals": self.glb_variable,
                "collectionVariables": lambda x: self.local_variable(self.item_id, x),
                "environment": self.env_variable,
                "console": console
            })
        except Exception as error:
            console.error(str(error))

        for script in script_list:
            try:
                exec(script["tests"], {
                    "res": response,
                    "globals": self.glb_variable,
                    "collectionVariables": lambda x: self.local_variable(self.item_id, x),
                    "environment": self.env_variable,
                    "console": console
                })
            except Exception as error:
                console.error(str(error))

        self.cache_history({
                    "method": method,
                    "url": url,
                    "params": self.get_params(),
                    "headers": headers,
                    "body": req_options,
                    "pre_request_script": pre_request_script,
                    "tests": tests,
                    "auth": opt_auth,
        })
        if self.item_id is not None:
            self.save_handler()

    def get_params(self):
        x = urllib.parse.urlparse(self.url.get())
        y = urllib.parse.parse_qs(x.query, keep_blank_values=True)
        data = {}
        for item in y.keys():
            if len(y[item]) == 1:
                data.update({item: y[item][0]})
            else:
                data.update({item: json.dumps(y[item])})
        return data

    def change_url(self, *args):
        self.params_frame.clear_data()
        self.params_frame.set_data(self.get_params())

    def update_url(self, query: str):
        x = urllib.parse.urlparse(self.url.get())
        scheme = x.scheme
        netloc = x.netloc
        path = x.path
        params = x.params
        fragment = x.fragment
        self.url.set(urllib.parse.urlunparse((scheme, netloc, path, params, query, fragment)))


class ConsoleText(ScrolledText):
    def __init__(self, master=None, **kw):
        super().__init__(master, **kw)

        if platform.system() == "Darwin":
            self.bind("<Control-Button-1>", self.on_right_click)
            self.bind("<Button-2>", self.on_right_click)
        else:
            self.bind("<Button-3>", self.on_right_click)

    def on_right_click(self, event):
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Clear", command=self.on_clear)
        menu.post(event.x_root, event.y_root)

    def on_clear(self):
        self.delete("1.0", tk.END)


class Console:
    def __init__(self, text: ScrolledText):
        self.text = text

    @staticmethod
    def to_string(*args) -> str:
        temp = ""
        for item in args:
            if isinstance(item, (str, int, float)):
                temp += f"{item} "
            elif isinstance(item, (dict, list)):
                temp += f"{json.dumps(item, indent=4, ensure_ascii=False)}"
            elif isinstance(item, bytes):
                temp += f"{item.decode()}"
            else:
                temp += str(temp)
        return temp

    def log(self, *args):
        self.text.insert(tk.END, self.to_string(*args))
        self.text.insert(tk.END, "\n")

    def info(self, *args):
        self.text.insert(tk.END, self.to_string(*args))
        line_start = self.text.index("insert linestart")
        line_end = self.text.index("insert lineend")
        self.text.tag_config("error", foreground="blue")
        self.text.tag_add("error", line_start, line_end)
        self.text.insert(tk.END, "\n")

    def error(self, *args):
        self.text.insert(tk.END, self.to_string(*args))
        line_start = self.text.index("insert linestart")
        line_end = self.text.index("insert lineend")
        self.text.tag_config("error", foreground="red")
        self.text.tag_add("error", line_start, line_end)
        self.text.insert(tk.END, "\n")

    def warning(self, *args):
        self.text.insert(tk.END, self.to_string(*args))
        line_start = self.text.index("insert linestart")
        line_end = self.text.index("insert lineend")
        self.text.tag_config("warning", foreground="orange")
        self.text.tag_add("warning", line_start, line_end)
        self.text.insert(tk.END, "\n")
