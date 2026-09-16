import json
import os
import threading
import time
import re
import xml.dom.minidom
from io import BytesIO
import urllib.parse

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QComboBox,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QSplitter,
    QScrollArea,
    QRadioButton,
    QButtonGroup,
    QStackedWidget,
    QFrame,
)

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
from PIL import Image

from . import qui
from . import webview
from .qui import END, ask_string, show_error, show_warning, open_file
from .theme import style_role
from .dao.crud import update_request
from .utils import EditorTable, CodeEditor, ConsoleText, Console


class ParamsFrame(EditorTable):
    def __init__(self, master=None, **kw):
        self.cb = kw.pop("cb")
        super().__init__(master, **kw)

    def commit(self, item_id=None, win=None, name_entry=None, value_entry=None):
        name = name_entry.text()
        value = value_entry.toPlainText()
        if self.check_name(item_id, name):
            if item_id is None:
                self.treeview.insert("", END, values=(name, value))
            else:
                self.treeview.item(item_id, values=(name, value))
            win.accept()
            self.cb(str(urllib.parse.urlencode(self.get_data())))
        else:
            show_error(self, "error", "Duplicate key")

    def on_del(self):
        if self.editable and len(self.treeview.selection()) > 0:
            self.treeview.delete(self.treeview.selection()[0])
            self.cb(str(urllib.parse.urlencode(self.get_data())))


class OauthFrame(QWidget):
    """OAuth 1.0 configuration panel (HMAC / RSA pages)."""

    def __init__(self, master=None, **kw):
        super().__init__(master)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.client_key = ""
        self.client_secret = ""
        self.resource_owner_key = ""
        self.resource_owner_secret = ""
        self.rsa_key = ""
        self.cpage = "hmac_page"

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        layout.addWidget(scroll)

        content = QWidget(scroll)
        content.setObjectName("OauthContent")
        scroll.setWidget(content)
        vbox = QVBoxLayout(content)
        vbox.setContentsMargins(4, 8, 4, 8)
        vbox.setSpacing(8)

        # ---- header rows ----
        row1 = QWidget(content)
        h1 = QHBoxLayout(row1)
        h1.setContentsMargins(0, 0, 0, 0)
        h1.addWidget(QLabel("Add authorization data to", row1))
        self.signature_type = QComboBox(row1)
        self.signature_type.addItems(
            (SIGNATURE_TYPE_AUTH_HEADER, SIGNATURE_TYPE_QUERY, SIGNATURE_TYPE_BODY)
        )
        h1.addWidget(self.signature_type, 1)
        vbox.addWidget(row1)

        row2 = QWidget(content)
        h2 = QHBoxLayout(row2)
        h2.setContentsMargins(0, 0, 0, 0)
        h2.addWidget(QLabel("Signature Method", row2))
        self.signature_method = QComboBox(row2)
        self.signature_method.addItems(
            (
                SIGNATURE_HMAC_SHA1,
                SIGNATURE_HMAC_SHA256,
                SIGNATURE_HMAC_SHA512,
                SIGNATURE_RSA_SHA1,
                SIGNATURE_RSA_SHA256,
                SIGNATURE_RSA_SHA512,
                SIGNATURE_PLAINTEXT,
            )
        )
        self.signature_method.currentTextChanged.connect(self.change_page)
        h2.addWidget(self.signature_method, 1)
        vbox.addWidget(row2)

        # ---- pages ----
        self.stack = QStackedWidget(content)
        vbox.addWidget(self.stack, 1)

        self.hmac_page_widget = self._build_hmac_page(content)
        self.rsa_page_widget = self._build_rsa_page(content)
        self.stack.addWidget(self.hmac_page_widget)
        self.stack.addWidget(self.rsa_page_widget)

        self.hmac_fields = (
            self._hmac_client_key, self._hmac_client_secret,
            self._hmac_token, self._hmac_token_secret,
        )
        self.rsa_fields = (self._rsa_client_key, self._rsa_token, self._rsa_key_text)
        self.change_page()

    # ------------------------------------------------------------------
    # Pages
    # ------------------------------------------------------------------
    def _field_row(self, parent, grid, row, label, echo=None):
        grid.addWidget(QLabel(label, parent), row, 0)
        edit = QLineEdit(parent)
        if echo == "password":
            edit.setEchoMode(QLineEdit.Password)
        grid.addWidget(edit, row, 1)
        return edit

    def _build_hmac_page(self, parent):
        page = QWidget(parent)
        grid = QGridLayout(page)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(8)
        self._hmac_client_key = self._field_row(page, grid, 0, "Consumer Key")
        self._hmac_client_secret = self._field_row(page, grid, 1, "Consumer Secret")
        self._hmac_token = self._field_row(page, grid, 2, "Access Token")
        self._hmac_token_secret = self._field_row(page, grid, 3, "Token Secret")
        grid.setColumnStretch(1, 1)
        # absorb leftover height below the fields so rows keep an even,
        # compact 8px rhythm instead of being spread out by the layout
        grid.setRowStretch(4, 1)
        return page

    def _build_rsa_page(self, parent):
        page = QWidget(parent)
        grid = QGridLayout(page)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(8)
        self._rsa_client_key = self._field_row(page, grid, 0, "Consumer Key")
        self._rsa_token = self._field_row(page, grid, 1, "Access Token")
        grid.addWidget(QLabel("Private key", page), 2, 0)
        btn = QPushButton("Select File", page)
        style_role(btn, "info")
        btn.clicked.connect(self.on_open)
        grid.addWidget(btn, 2, 1, alignment=Qt.AlignLeft)
        self._rsa_key_text = QPlainTextEdit(page)
        self._rsa_key_text.setMinimumHeight(160)
        grid.addWidget(self._rsa_key_text, 3, 1)
        grid.setColumnStretch(1, 1)
        grid.setRowStretch(3, 1)
        return page

    def change_page(self, *args):
        method = self.signature_method.currentText()
        if method in (
            SIGNATURE_HMAC_SHA1,
            SIGNATURE_HMAC_SHA256,
            SIGNATURE_HMAC_SHA512,
            SIGNATURE_PLAINTEXT,
        ):
            new_page = "hmac_page"
        else:
            new_page = "rsa_page"
        if self.cpage != new_page:
            self.cpage = new_page
        self.stack.setCurrentWidget(
            self.hmac_page_widget if new_page == "hmac_page" else self.rsa_page_widget
        )

    def on_open(self):
        filepath = open_file(self, "Open", [("All Files", "*.*")],
                             initialdir=os.path.expanduser("~"))
        if filepath:
            with open(filepath, "r", encoding="utf-8") as f:
                self._rsa_key_text.setPlainText(f.read())

    # ------------------------------------------------------------------
    # Load / save
    # ------------------------------------------------------------------
    def set(self, data: dict):
        signature_method = data.get("signature_method", SIGNATURE_HMAC_SHA1)
        self.signature_type.setCurrentText(data.get("signature_type", SIGNATURE_TYPE_AUTH_HEADER))
        self.signature_method.setCurrentText(signature_method)
        self.change_page()
        if self.cpage == "hmac_page":
            self._hmac_client_key.setText(data.get("client_key", ""))
            self._hmac_client_secret.setText(data.get("client_secret", ""))
            self._hmac_token.setText(data.get("resource_owner_key", ""))
            self._hmac_token_secret.setText(data.get("resource_owner_secret", ""))
        else:
            self._rsa_client_key.setText(data.get("client_key", ""))
            self._rsa_token.setText(data.get("resource_owner_key", ""))
            self._rsa_key_text.setPlainText(data.get("rsa_key", ""))

    def get(self):
        if self.cpage == "hmac_page":
            data = {
                "client_key": self._hmac_client_key.text(),
                "client_secret": self._hmac_client_secret.text(),
                "resource_owner_key": self._hmac_token.text(),
                "resource_owner_secret": self._hmac_token_secret.text(),
                "signature_type": self.signature_type.currentText(),
                "signature_method": self.signature_method.currentText(),
            }
        else:
            data = {
                "signature_type": self.signature_type.currentText(),
                "signature_method": self.signature_method.currentText(),
                "client_key": self._rsa_client_key.text(),
                "resource_owner_key": self._rsa_token.text(),
                "rsa_key": self._rsa_key_text.toPlainText(),
            }
        return data


class AuthFrame(QWidget):
    def __init__(self, master=None, **kw):
        super().__init__(master)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        row = QWidget(self)
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)
        h.addWidget(QLabel("Type:", row))
        self.auth_type = QComboBox(row)
        self.auth_type.addItems(("noauth", "base", "digest", "oauth1"))
        h.addWidget(self.auth_type, 1)
        h.addStretch(2)
        layout.addWidget(row)

        self.stack = QStackedWidget(self)
        layout.addWidget(self.stack, 1)

        # noauth page
        noauth = QWidget(self.stack)
        nl = QVBoxLayout(noauth)
        nl.addWidget(QLabel("This request does not use any authorization.", noauth))
        nl.addStretch(1)
        self.stack.addWidget(noauth)

        # base / digest page
        cred = QWidget(self.stack)
        grid = QGridLayout(cred)
        grid.addWidget(QLabel("username:", cred), 0, 0)
        self.username = QLineEdit(cred)
        grid.addWidget(self.username, 0, 1)
        grid.addWidget(QLabel("password:", cred), 1, 0)
        self.password = QLineEdit(cred)
        self.password.setEchoMode(QLineEdit.Password)
        grid.addWidget(self.password, 1, 1)
        grid.setColumnStretch(1, 1)
        grid.setRowStretch(2, 1)
        self.stack.addWidget(cred)

        # oauth1 page
        oauth_page = QWidget(self.stack)
        ol = QVBoxLayout(oauth_page)
        ol.setContentsMargins(0, 0, 0, 0)
        self.oauth_frame = OauthFrame(oauth_page)
        ol.addWidget(self.oauth_frame)
        self.stack.addWidget(oauth_page)

        self.auth_type.currentTextChanged.connect(self._on_type_change)

    def _on_type_change(self, text):
        if text == "oauth1":
            self.stack.setCurrentIndex(2)
        elif text in ("base", "digest"):
            self.stack.setCurrentIndex(1)
        else:
            self.stack.setCurrentIndex(0)

    def get(self) -> dict:
        res = {"type": self.auth_type.currentText()}
        if res["type"] == "oauth1":
            res.update({"oauth1": self.oauth_frame.get()})
        elif res["type"] == "base":
            res.update({"base": {"username": self.username.text(), "password": self.password.text()}})
        elif res["type"] == "digest":
            res.update({"digest": {"username": self.username.text(), "password": self.password.text()}})
        return res

    def set(self, data: dict):
        self.auth_type.setCurrentText(data.get("type", "noauth"))
        if self.auth_type.currentText() == "oauth1":
            self.oauth_frame.set(data.get("oauth1", {}))
        elif self.auth_type.currentText() in ("base", "digest"):
            self.username.setText(data.get(self.auth_type.currentText(), {}).get("username", ""))
            self.password.setText(data.get(self.auth_type.currentText(), {}).get("password", ""))


class BodyFrame(QWidget):
    current_date_type = "none"

    def __init__(self, **kwargs) -> None:
        super().__init__(kwargs.get("master"))
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self.current_date_type = "none"
        self.mode = "none"

        self.toolbar = QWidget(self)
        tl = QHBoxLayout(self.toolbar)
        tl.setContentsMargins(0, 0, 0, 0)
        self.radio_group = QButtonGroup(self)
        self.radio_none = QRadioButton("none", self.toolbar)
        self.radio_url = QRadioButton("urlencoded", self.toolbar)
        self.radio_raw = QRadioButton("raw", self.toolbar)
        self.radio_none.setChecked(True)
        for radio in (self.radio_none, self.radio_url, self.radio_raw):
            self.radio_group.addButton(radio)
            tl.addWidget(radio)
        self.radio_group.buttonToggled.connect(self.on_data_type_change)

        self.options = QComboBox(self.toolbar)
        self.options.addItems(["Text", "JSON", "XML", "HTML"])
        self.options.setCurrentIndex(0)
        self.options.setVisible(False)
        tl.addWidget(self.options)
        tl.addStretch(1)

        self.format_btn = QPushButton("格式化", self.toolbar)
        self.format_btn.setVisible(False)
        self.format_btn.clicked.connect(self.on_format_raw)
        tl.addWidget(self.format_btn)

        layout.addWidget(self.toolbar)

        self.stack = QStackedWidget(self)
        layout.addWidget(self.stack, 1)

        # none page
        none_page = QWidget(self.stack)
        n = QVBoxLayout(none_page)
        n.addWidget(QLabel("This request does not have a body", none_page))
        n.addStretch(1)
        self.stack.addWidget(none_page)

        # urlencoded page
        self.urlencoded_page = QWidget(self.stack)
        ul = QVBoxLayout(self.urlencoded_page)
        ul.setContentsMargins(0, 0, 0, 0)
        self.edit_table = EditorTable(self.urlencoded_page, editable=True)
        ul.addWidget(self.edit_table)
        self.stack.addWidget(self.urlencoded_page)

        # raw page
        self.raw_page = QWidget(self.stack)
        rl = QVBoxLayout(self.raw_page)
        rl.setContentsMargins(0, 0, 0, 0)
        self.scrolled_text = QPlainTextEdit(self.raw_page)
        self.scrolled_text.setFont(self.scrolled_text.font())
        rl.addWidget(self.scrolled_text)
        self.stack.addWidget(self.raw_page)

    def on_data_type_change(self, button, checked):
        if not checked:
            return
        mode = "none" if button is self.radio_none else (
            "urlencoded" if button is self.radio_url else "raw"
        )
        if mode != self.current_date_type:
            self.current_date_type = mode
        self.options.setVisible(mode == "raw")
        self.format_btn.setVisible(mode == "raw")
        if mode == "none":
            self.stack.setCurrentIndex(0)
        elif mode == "urlencoded":
            self.stack.setCurrentIndex(1)
        else:
            self.stack.setCurrentIndex(2)

    def insert(self, kw):
        if kw.get("mode") == "urlencoded":
            self.radio_url.setChecked(True)
            self.edit_table.set_data(kw.get("urlencoded"))
        elif kw.get("mode") == "raw":
            self.radio_raw.setChecked(True)
            # An imported body can carry a preset this build does not know;
            # fall back to Text instead of raising ValueError.
            index = self.options.findText(kw.get("options") or "")
            self.options.setCurrentIndex(index if index >= 0 else 0)
            self.scrolled_text.setPlainText(kw.get("raw"))
        else:
            self.radio_none.setChecked(True)

    def get(self):
        return {
            "mode": self.current_date_type,
            "options": self.options.currentText() if self.current_date_type == "raw" else "",
            "raw": self.scrolled_text.toPlainText(),
            "urlencoded": self.edit_table.get_data(),
        }

    # ------------------------------------------------------------------
    # Raw body formatting
    # ------------------------------------------------------------------
    def on_format_raw(self):
        """Pretty-print the raw body according to the selected type."""
        kind = self.options.currentText()
        text = self.scrolled_text.toPlainText()
        if not text.strip():
            return
        try:
            if kind == "JSON":
                out = json.dumps(json.loads(text), indent=2, ensure_ascii=False)
            elif kind == "XML":
                dom = xml.dom.minidom.parseString(text)
                out = dom.toprettyxml(indent="  ")
            elif kind == "HTML":
                soup = BeautifulSoup(text, "html.parser")
                out = soup.prettify()
            else:  # Text — nothing to format
                return
        except Exception as error:
            show_warning(self, "Format", f"Cannot format as {kind}.\n{error}")
            return
        self.scrolled_text.setPlainText(out)


class PathLabel(QLabel):
    doubleClicked = pyqtSignal()

    def mouseDoubleClickEvent(self, event):
        self.doubleClicked.emit()
        super().mouseDoubleClickEvent(event)


class RequestWindow:
    item_id = None
    data_id = None
    data_name = 'New Request'
    data_path = ''
    method_list = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]

    def __init__(self, **kwargs):
        self.root = kwargs.get("window")
        # These are per-window state, so they belong on the instance: leaving
        # them as class attributes means every unsaved request tab shares (and
        # can overwrite) the same identity.
        self.item_id = None
        self.data_id = None
        self.data_name = 'New Request'
        self.data_path = ''
        layout = QVBoxLayout(self.root)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(4)

        self.get_script = kwargs.get("get_script")
        self.env_variable = kwargs.get("env_variable")
        self.glb_variable = kwargs.get("glb_variable")
        self.local_variable = kwargs.get("local_variable")
        self.cache_history = kwargs.get("cache_history")
        self.save_item = kwargs.get("save_item")
        self.callback = kwargs.get("callback")
        self.data_path = kwargs.get("path", "")
        self.filepath = self.data_path + self.data_name

        # ---- path / save bar ----
        ff = QWidget(self.root)
        fl = QHBoxLayout(ff)
        fl.setContentsMargins(0, 0, 0, 0)
        self.path_label = PathLabel(self.filepath, ff)
        self.path_label.setCursor(Qt.PointingHandCursor)
        self.path_label.doubleClicked.connect(self.on_rename)
        fl.addWidget(self.path_label)
        fl.addStretch(1)
        save_btn = QPushButton("Save", ff)
        style_role(save_btn, "primary")
        save_btn.clicked.connect(self.save_handler)
        fl.addWidget(save_btn)
        layout.addWidget(ff)

        # ---- method / url / send ----
        north = QWidget(self.root)
        nl = QHBoxLayout(north)
        nl.setContentsMargins(0, 0, 0, 0)
        self.method_box = QComboBox(north)
        self.method_box.addItems(self.method_list)
        self.method_box.setCurrentIndex(0)
        self.method_box.setFixedWidth(96)
        nl.addWidget(self.method_box)
        self.url = QLineEdit(north)
        self.url.textChanged.connect(self.change_url)
        nl.addWidget(self.url, 1)
        sub_btn = QPushButton("Send", north)
        style_role(sub_btn, "success")
        sub_btn.clicked.connect(self.send_request)
        nl.addWidget(sub_btn)
        layout.addWidget(north)

        # ---- splitter: request | response ----
        paned_window = QSplitter(Qt.Vertical, self.root)
        layout.addWidget(paned_window, 1)

        notebook = QTabWidget(paned_window)
        self.params_frame = ParamsFrame(master=notebook, editable=True, cb=self.update_url)
        notebook.addTab(self.params_frame, "Params")
        self.auth_frame = AuthFrame(master=notebook)
        notebook.addTab(self.auth_frame, "Authorization")
        self.headers_frame = EditorTable(master=notebook, editable=True)
        notebook.addTab(self.headers_frame, "Headers")
        self.body_box = BodyFrame(master=notebook)
        notebook.addTab(self.body_box, "Body")
        self.script_box = CodeEditor(notebook)
        notebook.addTab(self.script_box, "Pre-request Script")
        self.tests_box = CodeEditor(notebook)
        notebook.addTab(self.tests_box, "Post-response Script")
        paned_window.addWidget(notebook)

        # response area
        res_note = QTabWidget(paned_window)

        # The Body tab holds the source view plus the Preview action, which
        # only means anything for an HTML response, so _display_response
        # reveals the whole bar or leaves it hidden.
        body_page = QWidget(res_note)
        body_layout = QVBoxLayout(body_page)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(2)
        self.preview_bar = QWidget(body_page)
        preview_layout = QHBoxLayout(self.preview_bar)
        preview_layout.setContentsMargins(2, 2, 2, 0)
        preview_layout.addStretch(1)
        self.preview_btn = QPushButton("预览", self.preview_bar)
        self.preview_btn.setToolTip(webview.describe_backend())
        self.preview_btn.clicked.connect(self.open_html_preview)
        preview_layout.addWidget(self.preview_btn)
        self.preview_bar.setVisible(False)
        body_layout.addWidget(self.preview_bar)

        self.res_body_box = QPlainTextEdit(body_page)
        self.res_body_box.setReadOnly(True)
        body_layout.addWidget(self.res_body_box, 1)
        res_note.addTab(body_page, "Body")

        # Last HTML response, kept for the preview window (set by
        # _display_response).
        self.preview_html = None
        self.preview_base_url = ""
        self.preview_window = None
        self.res_cookie_table = EditorTable(res_note)
        res_note.addTab(self.res_cookie_table, "Cookies")
        self.res_header_table = EditorTable(res_note)
        res_note.addTab(self.res_header_table, "Headers")
        self.res_tests_box = ConsoleText(res_note)
        res_note.addTab(self.res_tests_box, "Console")
        paned_window.addWidget(res_note)

        paned_window.setStretchFactor(0, 3)
        paned_window.setStretchFactor(1, 2)

    # ------------------------------------------------------------------
    # Rename / save
    # ------------------------------------------------------------------
    def on_rename(self):
        if self.data_id is None:
            show_warning(self.root, "Warning", "Please save it first.")
            return
        name = ask_string(self.root, "Rename", "Enter new name:", self.data_name)
        if name is not None:
            update_request(**{"id": self.data_id, "name": name})
            self.data_name = name
            self.filepath = self.data_path + self.data_name
            self.path_label.setText(self.filepath)
            self.save_item(self.item_id, {'name': name})
            self.callback(name=name, item_id=self.item_id)

    def save_handler(self):
        """Save test script"""
        name = self.data_name
        method = self.method_box.currentText()
        url = self.url.text()
        params = self.params_frame.get_data()
        headers = self.headers_frame.get_data()
        body = self.body_box.get()
        pre_request_script = self.script_box.toPlainText()
        tests = self.tests_box.toPlainText()
        opt_auth = self.auth_frame.get()
        pre_request_script = pre_request_script.rstrip("\n")
        tests = tests.rstrip("\n")

        if name == "" and url:
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
        method = data.get("method", "GET")
        # Imported collections / old history rows can hold a verb this build
        # does not offer; a bare list.index() raised ValueError and the request
        # could not be opened at all.
        self.method_box.setCurrentIndex(
            self.method_list.index(method) if method in self.method_list else 0
        )
        self.url.setText(data.get("url", ""))
        self.headers_frame.set_data(data.get("headers", {}))
        self.body_box.insert(data.get("body", {}))
        self.script_box.setPlainText(data.get("pre_script", ""))
        self.tests_box.setPlainText(data.get("post_script", ""))
        self.data_name = data.get("name", "New Request")
        self.filepath = self.data_path + self.data_name
        self.path_label.setText(self.filepath)
        self.auth_frame.set(data.get("auth", {}))

    # ------------------------------------------------------------------
    # Sending
    # ------------------------------------------------------------------
    def send_request(self):
        spec = self._collect_request_spec()
        if spec is None:
            return
        thread = threading.Thread(target=self.http_handle, args=(spec,), daemon=True)
        thread.start()

    def _collect_request_spec(self):
        """Read all widget state and resolve variables on the UI thread."""
        method = self.method_box.currentText()
        url = self.url.text()
        if url is None or url == "":
            show_error(self.root, "Error", "Please enter the request address")
            return None

        url = self.fill_var(url)

        headers = self.headers_frame.get_data()
        headers = json.dumps(headers)
        headers = self.fill_var(headers)
        try:
            headers = json.loads(headers)
        except json.JSONDecodeError:
            headers = {}

        req_options = self.body_box.get()
        if req_options.get("mode") == "raw":
            body = req_options.get("raw")
        elif req_options.get("mode") == "urlencoded":
            body = json.dumps(req_options.get("urlencoded"))
        else:
            body = ""
        body = self.fill_var(body)

        if req_options.get("mode") == "urlencoded" or (
                req_options.get("mode") == "raw" and req_options.get("options") == "JSON"):
            try:
                body = json.loads(body)
            except json.JSONDecodeError:
                body = {}

        pre_request_script = self.script_box.toPlainText()
        tests = self.tests_box.toPlainText()
        opt_auth = self.auth_frame.get()
        for key in opt_auth.keys():
            if isinstance(opt_auth[key], dict):
                for ckey in opt_auth[key]:
                    temp = opt_auth[key][ckey]
                    temp = self.fill_var(temp)
                    opt_auth[key][ckey] = temp

        script_list = []
        if self.item_id is not None:
            script_list = self.get_script(self.item_id) or []

        return {
            "method": method,
            "url": url,
            "headers": headers,
            "body": body,
            "options": req_options,
            "pre_request_script": pre_request_script,
            "tests": tests,
            "auth": opt_auth,
            "script_list": script_list,
        }

    def fill_var(self, data):
        varlist = re.finditer(r"\{\{[^{}]*\}\}", data)
        for var in varlist:
            val = self.local_variable(self.item_id, var.group()[2:-2])
            if val is None:
                val = self.glb_variable(var.group()[2:-2])
            if val is not None:
                data = data.replace(var.group(), val)
        return data

    def http_handle(self, spec):
        """Define the function that sends the request (runs in a worker thread)."""
        console = Console(self.res_tests_box)
        method = spec["method"]
        url = spec["url"]
        headers = dict(spec["headers"])
        body = spec["body"]
        req_options = spec["options"]
        opt_auth = spec["auth"]
        pre_request_script = spec["pre_request_script"]
        tests = spec["tests"]
        script_list = spec["script_list"]

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

        # ``req`` is exposed to the scripts as the request being built, and the
        # built-in help documents assigning to it ("req['body']['username'] =
        # 'x'").  A fresh literal per exec() meant such writes were thrown away
        # (in-place edits to the shared body/headers dicts happened to leak
        # through; rebinding req["url"] never did).  One dict is reused and its
        # contents are copied back below.
        req_data = {"body": body, "headers": headers, "url": url}

        def _script_scope():
            return {
                "req": req_data,
                "globals": self.glb_variable,
                "collectionVariables": lambda x: self.local_variable(self.item_id, x),
                "environment": self.env_variable,
                "console": console,
            }

        try:
            exec(pre_request_script, _script_scope())
        except Exception as error:
            console.error(str(error))

        for script in script_list:
            try:
                exec(script["pre_request_script"], _script_scope())
            except Exception as error:
                console.error(str(error))

        if isinstance(req_data.get("url"), str):
            url = req_data["url"]
        if isinstance(req_data.get("headers"), dict):
            headers = req_data["headers"]
        if "body" in req_data:
            body = req_data["body"]

        start_time = time.time()

        if req_options.get("mode") == "urlencoded":
            headers.update({"Content-Type": "application/x-www-form-urlencoded"})
        elif req_options.get("mode") == "raw":
            if req_options.get("options") == "JSON":
                # A pre-request script may already have produced the JSON text;
                # serialising a str again would send a quoted string.
                if not isinstance(body, str):
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
                qui.post(lambda: show_error(self.root, "Error", "Unsupported request type"))
                return
        except requests.exceptions.MissingSchema:
            qui.post(lambda: show_error(self.root, "Error", "Request error"))
            return
        except requests.exceptions.SSLError:
            qui.post(lambda: show_error(self.root, "Error", "SSL certificate verify failed"))
            return
        except requests.exceptions.ConnectionError:
            qui.post(lambda: show_error(self.root, "Error", "Connection refused"))
            return
        except requests.exceptions.Timeout:
            qui.post(lambda: show_error(self.root, "Error", "Request timeout"))
            return
        except requests.exceptions.RequestException as error:
            # ``error`` is unbound by the time the lambda runs: Python deletes
            # the ``except ... as`` name at the end of the block, so the closure
            # raised NameError instead of reporting the failure.  Capture the
            # text now and let the lambda close over the string.
            message = str(error)
            qui.post(lambda: show_error(self.root, "Error", message))
            return

        cost_time = time.time() - start_time
        if cost_time < 1:
            cost_time = f"{round(cost_time * 1000)}ms"
        else:
            cost_time = f"{round(cost_time)}s"

        # 将响应显示在响应区域 (UI thread)
        response_body = self._prepare_response_body(response)
        qui.post(lambda: self._display_response(response_body, dict(response.cookies),
                                                dict(response.headers),
                                                response.status_code, method, url, cost_time))

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

        def finish():
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

        qui.post(finish)

    def _prepare_response_body(self, response):
        """Compute what the Body tab shows (runs in the worker thread).

        Returns a dict:
          kind      -- "text" or "image"
          payload   -- the text to display, or a PIL image
          html      -- the raw HTML document when the response is a web page,
                       otherwise None; it is what the Preview button renders
          base_url  -- the URL relative links in that document resolve against
        """
        content_type = (response.headers.get("Content-Type") or "").lower()
        # A server that sends no Content-Type at all can still return a web
        # page; without this the Preview button would be lost on it.  The sniff
        # reads the raw bytes rather than response.text, which would decode the
        # whole body (an untyped response is often a large binary download).
        if not content_type:
            head = response.content[:512].lstrip().lower()
            if head.startswith(b"<!doctype html") or head.startswith(b"<html"):
                content_type = "text/html"

        if "application/json" in content_type:
            try:
                payload = json.dumps(response.json(), indent=2, ensure_ascii=False)
            except Exception:
                payload = response.text
            return {"kind": "text", "payload": payload, "html": None, "base_url": ""}
        elif "text/html" in content_type or "application/xhtml+xml" in content_type:
            response.encoding = "utf-8"
            html = response.text
            return {
                "kind": "text",
                # The source view gets indented markup, but the preview keeps
                # the original text: re-indenting can change how
                # whitespace-sensitive markup (pre, textarea) renders.
                "payload": BeautifulSoup(html, "html.parser").prettify(),
                "html": html,
                "base_url": response.url,
            }
        elif "text/xml" in content_type or "application/xml" in content_type:
            response.encoding = "utf-8"
            try:
                payload = xml.dom.minidom.parseString(response.text).toprettyxml(indent="  ")
            except Exception:
                payload = response.text
            return {"kind": "text", "payload": payload, "html": None, "base_url": ""}
        elif "image" in content_type:
            try:
                payload = Image.open(BytesIO(response.content))
                return {"kind": "image", "payload": payload, "html": None, "base_url": ""}
            except Exception:
                return {
                    "kind": "text",
                    "payload": response.content[:4096].decode("utf-8", errors="replace"),
                    "html": None,
                    "base_url": "",
                }
        else:
            return {"kind": "text", "payload": response.text, "html": None, "base_url": ""}

    def _display_response(self, body, cookies, headers, status_code, method, url, cost_time):
        self.res_cookie_table.clear_data()
        self.res_cookie_table.set_data(cookies)
        self.res_header_table.clear_data()
        self.res_header_table.set_data(headers)

        self.res_body_box.clear()
        if body["kind"] == "image":
            qimage = qui.pil_to_qimage(body["payload"])
            cursor = self.res_body_box.textCursor()
            cursor.movePosition(cursor.End)
            cursor.insertImage(qimage)
            self.res_body_box.setTextCursor(cursor)
        else:
            self.res_body_box.setPlainText(body["payload"])
        self._set_preview(body.get("html"), body.get("base_url"))

    # ------------------------------------------------------------------
    # HTML preview
    # ------------------------------------------------------------------
    def _set_preview(self, html, base_url):
        """Offer the Preview button only while the response is HTML."""
        self.preview_html = html
        self.preview_base_url = base_url or ""
        self.preview_bar.setVisible(bool(html))
        if not html and self.preview_window is not None:
            # The preview shows the response currently on screen, so a new,
            # non-HTML response makes it stale — close it instead of leaving
            # the previous page up.
            self.preview_window.hide()

    def open_html_preview(self):
        """Render the last HTML response in the preview window."""
        if not self.preview_html:
            return
        title = f"Preview - {self.data_name}"
        if self.preview_window is None:
            self.preview_window = webview.HtmlPreviewWindow(
                self.root, title=title, html=self.preview_html,
                base_url=self.preview_base_url)
        else:
            self.preview_window.setWindowTitle(title)
            self.preview_window.set_content(self.preview_html, self.preview_base_url)
        self.preview_window.show()
        self.preview_window.raise_()
        self.preview_window.activateWindow()

    def get_params(self):
        x = urllib.parse.urlparse(self.url.text())
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
        x = urllib.parse.urlparse(self.url.text())
        scheme = x.scheme
        netloc = x.netloc
        path = x.path
        params = x.params
        fragment = x.fragment
        self.url.setText(urllib.parse.urlunparse((scheme, netloc, path, params, query, fragment)))
