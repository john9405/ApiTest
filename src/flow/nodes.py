"""Block/node type definitions for the Flow feature.

Each node type extends BaseNode and provides:
- Visual properties (color, display name, ports)
- execute(context, console) — the runtime behavior
- get_config_frame(master) — the configuration UI for the inspector
"""

import json
import re
import time

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QComboBox,
    QRadioButton,
    QButtonGroup,
    QPushButton,
    QDialog,
    QTreeWidget,
    QTreeWidgetItem,
    QDoubleSpinBox,
)

import requests

from ..utils import CodeEditor
from ..theme import style_role


class Port:
    """Describes an input or output port on a node."""

    def __init__(self, port_id, label, direction):
        self.port_id = port_id      # 'input', 'output', 'true', 'false'
        self.label = label          # display label
        self.direction = direction  # 'in' or 'out'


class BaseNode:
    """Abstract base class for all flow node types."""

    TYPE_ID = "base"
    DISPLAY_NAME = "Base"
    COLOR = "#6b7280"
    DEFAULT_WIDTH = 160
    DEFAULT_HEIGHT = 80
    INPUT_PORTS = [Port("input", "Input", "in")]
    OUTPUT_PORTS = [Port("output", "Output", "out")]

    def __init__(self, node_model):
        self.model = node_model

    def execute(self, context, console):
        """Execute this node. Returns output dict.

        context: dict of {node_id: output_dict} from upstream nodes
        console: object with .log(msg), .info(msg), .error(msg) methods
        """
        raise NotImplementedError

    def get_config_frame(self, master, on_change=None, **kwargs):
        """Return a QWidget with configuration widgets.

        on_change: callback to notify the inspector when config changes
        Extra kwargs are forwarded for type-specific needs (e.g. get_collection_requests).
        """
        frame = QWidget(master)
        layout = QVBoxLayout(frame)
        layout.addWidget(QLabel(f"No configuration needed for {self.DISPLAY_NAME}.", frame))
        return frame

    def validate_config(self):
        """Validate config. Returns (is_valid, error_message)."""
        return True, ""

    def _fill_vars(self, text, context):
        """Substitute {{ ... }} variables from the execution context."""
        if not isinstance(text, str):
            return text

        def replacer(match):
            expr = match.group(1).strip()
            try:
                # Support: {{ context.node_id.field.subfield }}
                return str(eval(expr, {"context": context, "json": json}))
            except Exception:
                return match.group(0)

        return re.sub(r"\{\{(.+?)\}\}", replacer, text)


class ApiRequestNode(BaseNode):
    """Makes an HTTP request."""

    TYPE_ID = "api_request"
    DISPLAY_NAME = "API Request"
    COLOR = "#3b82f6"
    INPUT_PORTS = [Port("input", "Input", "in")]
    OUTPUT_PORTS = [Port("output", "Output", "out")]

    def execute(self, context, console):
        cfg = self.model.config

        # If source is 'collection', load the saved request from database
        if cfg.get("source") == "collection" and cfg.get("request_id"):
            try:
                from ..dao.crud import retrieve_request
                saved = retrieve_request(id=cfg["request_id"])
                if saved:
                    url = self._fill_vars(saved.get("url", ""), context)
                    method = saved.get("method", "GET")
                    headers = saved.get("headers", {})
                    body = saved.get("body", {})
                else:
                    console.error(f"{self.model.label}: saved request #{cfg['request_id']} not found")
                    return {"error": f"Request #{cfg['request_id']} not found"}
            except Exception as e:
                console.error(f"{self.model.label}: failed to load request: {e}")
                return {"error": str(e)}
        else:
            url = self._fill_vars(cfg.get("url", ""), context)
            method = cfg.get("method", "GET")
            headers = cfg.get("headers", {})
            body = cfg.get("body", "")

        if isinstance(headers, str):
            headers = self._fill_vars(headers, context)
            try:
                headers = json.loads(headers)
            except json.JSONDecodeError:
                headers = {}
        if isinstance(body, str):
            body = self._fill_vars(body, context)

        console.info(f"{self.model.label}: {method} {url}")

        try:
            if method == "GET":
                resp = requests.get(url, headers=headers, timeout=30)
            elif method == "POST":
                resp = requests.post(url, data=body, headers=headers, timeout=30)
            elif method == "PUT":
                resp = requests.put(url, data=body, headers=headers, timeout=30)
            elif method == "PATCH":
                resp = requests.patch(url, data=body, headers=headers, timeout=30)
            elif method == "DELETE":
                resp = requests.delete(url, headers=headers, timeout=30)
            elif method == "HEAD":
                resp = requests.head(url, headers=headers, timeout=30)
            elif method == "OPTIONS":
                resp = requests.options(url, headers=headers, timeout=30)
            else:
                return {"error": f"Unsupported method: {method}"}

            try:
                resp_body = resp.json()
            except (json.JSONDecodeError, ValueError):
                resp_body = resp.text

            result = {
                "status_code": resp.status_code,
                "headers": dict(resp.headers),
                "body": resp_body,
                "elapsed_ms": round(resp.elapsed.total_seconds() * 1000),
            }
            console.info(f"{self.model.label}: {resp.status_code} ({result['elapsed_ms']}ms)")
            return result

        except requests.exceptions.RequestException as e:
            console.error(f"{self.model.label}: {str(e)}")
            return {"error": str(e)}

    def get_config_frame(self, master, on_change=None, **kwargs):
        from ..dao.crud import list_all_requests

        frame = QWidget(master)
        layout = QGridLayout(frame)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setHorizontalSpacing(6)
        layout.setVerticalSpacing(4)

        row = 0

        # ---- Source toggle ----
        layout.addWidget(QLabel("Source:", frame), row, 0)
        source_frame = QWidget(frame)
        sh = QHBoxLayout(source_frame)
        sh.setContentsMargins(0, 0, 0, 0)
        radio_inline = QRadioButton("Inline", source_frame)
        radio_collection = QRadioButton("From Collection", source_frame)
        radio_inline.setChecked(self.model.config.get("source", "inline") != "collection")
        radio_collection.setChecked(self.model.config.get("source") == "collection")
        group = QButtonGroup(source_frame)
        group.addButton(radio_inline)
        group.addButton(radio_collection)
        sh.addWidget(radio_inline)
        sh.addWidget(radio_collection)
        sh.addStretch(1)
        layout.addWidget(source_frame, row, 1)

        def _notify_change():
            if on_change:
                on_change()

        def on_source_toggled(_checked=None):
            self.model.config["source"] = "collection" if radio_collection.isChecked() else "inline"
            picker_frame.setVisible(radio_collection.isChecked())
            inline_fields.setVisible(not radio_collection.isChecked())
            if radio_collection.isChecked():
                _populate_requests()
            _notify_change()

        radio_inline.toggled.connect(on_source_toggled)
        radio_collection.toggled.connect(on_source_toggled)
        row += 1

        # ---- Collection request picker ----
        picker_frame = QWidget(frame)
        ph = QHBoxLayout(picker_frame)
        ph.setContentsMargins(0, 0, 0, 0)
        ph.addWidget(QLabel("Request:", picker_frame))
        selected_display = QLineEdit(picker_frame)
        selected_display.setReadOnly(True)
        ph.addWidget(selected_display, 1)
        browse_btn = QPushButton("...", picker_frame)
        browse_btn.setFixedWidth(34)
        ph.addWidget(browse_btn)
        layout.addWidget(picker_frame, row, 0, 1, 2)
        row += 1

        self._request_list = []
        self._popup_result = None

        def _populate_requests():
            self._request_list = []
            try:
                self._request_list = list_all_requests()
            except Exception:
                self._request_list = []
            _refresh_display()

        def _refresh_display():
            saved_id = self.model.config.get("request_id")
            for req in self._request_list:
                if req["id"] == saved_id:
                    path = req.get("path", "")
                    if path:
                        selected_display.setText(f"{req['method']} {req['name']}  [{path}]")
                    else:
                        selected_display.setText(f"{req['method']} {req['name']}")
                    return
            selected_display.setText("")

        def _save_selection(req):
            self.model.config["request_id"] = req["id"]
            _refresh_display()
            _notify_change()

        def _show_tree_popup():
            dlg = QDialog(picker_frame)
            dlg.setWindowTitle("Select Request")
            dlg.resize(500, 380)
            vl = QVBoxLayout(dlg)
            tree = QTreeWidget(dlg)
            tree.setHeaderLabels(["Requests"])
            tree.setSelectionMode(QTreeWidget.SingleSelection)
            vl.addWidget(tree, 1)

            # Group requests by folder path
            groups = {}
            ungrouped = []
            for req in self._request_list:
                path = req.get("path", "")
                if path:
                    groups.setdefault(path, []).append(req)
                else:
                    ungrouped.append(req)

            for path in sorted(groups.keys()):
                group_item = QTreeWidgetItem(tree, [path])
                group_item.setExpanded(True)
                for req in groups[path]:
                    item = QTreeWidgetItem(group_item, [f"{req['method']}  {req['name']}"])
                    item.setData(0, Qt.UserRole, req["id"])
                    item.setFlags(item.flags() | Qt.ItemIsSelectable)

            if ungrouped:
                group_item = QTreeWidgetItem(tree, ["(no folder)"])
                group_item.setExpanded(True)
                for req in ungrouped:
                    item = QTreeWidgetItem(group_item, [f"{req['method']}  {req['name']}"])
                    item.setData(0, Qt.UserRole, req["id"])

            # Select the currently saved request
            saved_id = self.model.config.get("request_id")
            if saved_id is not None:
                # MatchRecursive is required: without it findItems only walks
                # top-level items, which are the folder rows and carry no id,
                # so the saved request was never pre-selected.
                it = tree.findItems("", Qt.MatchContains | Qt.MatchRecursive)
                for item in it:
                    if item.data(0, Qt.UserRole) == saved_id:
                        tree.setCurrentItem(item)
                        tree.scrollToItem(item)
                        break

            self._popup_result = None

            def _on_select():
                current = tree.currentItem()
                if current is not None:
                    data = current.data(0, Qt.UserRole)
                    if data is not None:
                        self._popup_result = data

            def _on_double_click(item, _col):
                req = next((r for r in self._request_list if r["id"] == item.data(0, Qt.UserRole)), None)
                if req:
                    _save_selection(req)
                dlg.accept()

            def _on_ok():
                if self._popup_result is not None:
                    req = next((r for r in self._request_list if r["id"] == self._popup_result), None)
                    if req:
                        _save_selection(req)
                dlg.accept()

            def _on_clear():
                self.model.config["request_id"] = None
                selected_display.setText("")
                _notify_change()
                dlg.accept()

            tree.itemSelectionChanged.connect(_on_select)
            tree.itemDoubleClicked.connect(_on_double_click)

            btn_frame = QWidget(dlg)
            bh = QHBoxLayout(btn_frame)
            bh.setContentsMargins(0, 0, 0, 0)
            clear_btn = QPushButton("Clear", btn_frame)
            clear_btn.clicked.connect(_on_clear)
            bh.addWidget(clear_btn)
            bh.addStretch(1)
            cancel_btn = QPushButton("Cancel", btn_frame)
            cancel_btn.clicked.connect(dlg.reject)
            bh.addWidget(cancel_btn)
            ok_btn = QPushButton("OK", btn_frame)
            style_role(ok_btn, "primary")
            ok_btn.clicked.connect(_on_ok)
            bh.addWidget(ok_btn)
            vl.addWidget(btn_frame)

            dlg.exec_()

        browse_btn.clicked.connect(_show_tree_popup)
        row += 1

        # ---- Inline config fields ----
        inline_fields = QWidget(frame)
        il = QGridLayout(inline_fields)
        il.setContentsMargins(0, 0, 0, 0)
        il.setHorizontalSpacing(6)
        il.setVerticalSpacing(4)
        irow = 0

        il.addWidget(QLabel("Method:", inline_fields), irow, 0)
        method_box = QComboBox(inline_fields)
        method_box.addItems(["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"])
        method_box.setCurrentText(self.model.config.get("method", "GET"))
        method_box.currentTextChanged.connect(
            lambda text: (self.model.config.__setitem__("method", text), _notify_change())
        )
        il.addWidget(method_box, irow, 1)
        irow += 1

        il.addWidget(QLabel("URL:", inline_fields), irow, 0)
        url_entry = QLineEdit(inline_fields)
        url_entry.setText(self.model.config.get("url", ""))
        url_entry.textChanged.connect(
            lambda text: (self.model.config.__setitem__("url", text), _notify_change())
        )
        il.addWidget(url_entry, irow, 1)
        irow += 1

        il.addWidget(QLabel("Headers (JSON):", inline_fields), irow, 0)
        headers_text = QPlainTextEdit(inline_fields)
        headers_text.setFixedHeight(90)
        headers_val = self.model.config.get("headers", {})
        if isinstance(headers_val, dict):
            headers_text.setPlainText(json.dumps(headers_val, indent=2))
        else:
            headers_text.setPlainText(str(headers_val))

        def on_headers_change():
            try:
                self.model.config["headers"] = json.loads(headers_text.toPlainText())
            except json.JSONDecodeError:
                self.model.config["headers"] = headers_text.toPlainText()
            _notify_change()

        headers_text.textChanged.connect(on_headers_change)
        il.addWidget(headers_text, irow, 1)
        irow += 1

        il.addWidget(QLabel("Body:", inline_fields), irow, 0)
        body_text = QPlainTextEdit(inline_fields)
        body_text.setFixedHeight(90)
        body_text.setPlainText(str(self.model.config.get("body", "")))

        def on_body_change():
            self.model.config["body"] = body_text.toPlainText()
            _notify_change()

        body_text.textChanged.connect(on_body_change)
        il.addWidget(body_text, irow, 1)
        il.setColumnStretch(1, 1)
        layout.addWidget(inline_fields, row, 0, 1, 2)
        layout.setRowStretch(row, 1)

        # Initial visibility
        picker_frame.setVisible(radio_collection.isChecked())
        inline_fields.setVisible(not radio_collection.isChecked())
        if radio_collection.isChecked():
            _populate_requests()

        return frame


class ConditionNode(BaseNode):
    """If/else branching based on a Python expression."""

    TYPE_ID = "condition"
    DISPLAY_NAME = "Condition"
    COLOR = "#f59e0b"
    INPUT_PORTS = [Port("input", "Input", "in")]
    OUTPUT_PORTS = [Port("true", "True", "out"), Port("false", "False", "out")]

    def execute(self, context, console):
        expr = self.model.config.get("expression", "True")
        # Provide safe builtins for common operations
        safe_builtins = {
            "True": True, "False": False, "None": None,
            "len": len, "str": str, "int": int, "float": float,
            "bool": bool, "list": list, "dict": dict,
            "isinstance": isinstance, "type": type,
        }
        try:
            result = eval(expr, {"__builtins__": safe_builtins}, {"context": context})
            console.info(f"{self.model.label}: {expr} → {bool(result)}")
            return {"branch": bool(result)}
        except Exception as e:
            console.error(f"{self.model.label}: expression error: {e}")
            return {"branch": False, "error": str(e)}

    def get_config_frame(self, master, on_change=None, **kwargs):
        frame = QWidget(master)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(2, 2, 2, 2)

        layout.addWidget(QLabel("Expression (Python):", frame))
        hint = QLabel("Use: context[node_id]['field']", frame)
        hint.setStyleSheet("color: gray;")
        layout.addWidget(hint)

        editor = CodeEditor(frame)
        editor.setPlainText(self.model.config.get("expression", ""))

        def on_change_handler():
            self.model.config["expression"] = editor.toPlainText()
            if on_change:
                on_change()

        editor.textChanged.connect(on_change_handler)
        layout.addWidget(editor, 1)
        return frame


class ScriptNode(BaseNode):
    """Custom Python script execution."""

    TYPE_ID = "script"
    DISPLAY_NAME = "Script"
    COLOR = "#8b5cf6"
    INPUT_PORTS = [Port("input", "Input", "in")]
    OUTPUT_PORTS = [Port("output", "Output", "out")]

    def execute(self, context, console):
        script = self.model.config.get("script", "")
        if not script.strip():
            return {}
        local_vars = {"context": context, "console": console, "output": {}}
        try:
            exec(script, {"__builtins__": __builtins__}, local_vars)
            console.info(f"{self.model.label}: script executed")
            return local_vars.get("output", {})
        except Exception as e:
            console.error(f"{self.model.label}: script error: {e}")
            return {"error": str(e)}

    def get_config_frame(self, master, on_change=None, **kwargs):
        frame = QWidget(master)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(2, 2, 2, 2)

        layout.addWidget(QLabel("Python Script:", frame))
        hint = QLabel("Available: context, console, output", frame)
        hint.setStyleSheet("color: gray;")
        layout.addWidget(hint)

        editor = CodeEditor(frame)
        editor.setPlainText(self.model.config.get("script", ""))

        def on_change_handler():
            self.model.config["script"] = editor.toPlainText()
            if on_change:
                on_change()

        editor.textChanged.connect(on_change_handler)
        layout.addWidget(editor, 1)
        return frame


class DelayNode(BaseNode):
    """Wait/pause for a number of seconds."""

    TYPE_ID = "delay"
    DISPLAY_NAME = "Delay"
    COLOR = "#06b6d4"
    INPUT_PORTS = [Port("input", "Input", "in")]
    OUTPUT_PORTS = [Port("output", "Output", "out")]
    DEFAULT_HEIGHT = 60

    def execute(self, context, console):
        seconds = float(self.model.config.get("seconds", 1.0))
        console.info(f"{self.model.label}: waiting {seconds}s...")
        time.sleep(seconds)
        return {"status": "delayed", "seconds": seconds}

    def get_config_frame(self, master, on_change=None, **kwargs):
        frame = QWidget(master)
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(2, 4, 2, 4)

        layout.addWidget(QLabel("Seconds:", frame))
        spinbox = QDoubleSpinBox(frame)
        spinbox.setRange(0.1, 3600.0)
        spinbox.setSingleStep(0.5)
        spinbox.setDecimals(2)
        spinbox.setValue(float(self.model.config.get("seconds", 1.0)))

        # Must not be called on_change: an inner def with that name rebinds the
        # enclosing `on_change` parameter, so `if on_change: on_change()` ended
        # up calling itself with a missing argument (TypeError inside a Qt slot).
        def on_seconds_change(value):
            self.model.config["seconds"] = float(value)
            if on_change:
                on_change()

        spinbox.valueChanged.connect(on_seconds_change)
        layout.addWidget(spinbox)
        layout.addStretch(1)
        return frame


class LogNode(BaseNode):
    """Log data to the console."""

    TYPE_ID = "log"
    DISPLAY_NAME = "Log"
    COLOR = "#6b7280"
    INPUT_PORTS = [Port("input", "Input", "in")]
    OUTPUT_PORTS = [Port("output", "Output", "out")]
    DEFAULT_HEIGHT = 60

    def execute(self, context, console):
        template = self.model.config.get("template", "{{ context }}")
        message = self._fill_vars(template, context)
        console.log(f"{self.model.label}: {message}")
        return {"logged": message}

    def get_config_frame(self, master, on_change=None, **kwargs):
        frame = QWidget(master)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(2, 2, 2, 2)

        layout.addWidget(QLabel("Template:", frame))
        hint = QLabel("Use {{ context.node_id.field }} for variable substitution", frame)
        hint.setStyleSheet("color: gray;")
        layout.addWidget(hint)

        entry = QLineEdit(frame)
        entry.setText(self.model.config.get("template", ""))

        # See DelayNode: naming this `on_change` shadowed the callback parameter.
        def on_template_change(text):
            self.model.config["template"] = text
            if on_change:
                on_change()

        entry.textChanged.connect(on_template_change)
        layout.addWidget(entry)
        return frame


class DataTransformNode(BaseNode):
    """Transform data via a Python expression."""

    TYPE_ID = "data_transform"
    DISPLAY_NAME = "Data Transform"
    COLOR = "#10b981"
    INPUT_PORTS = [Port("input", "Input", "in")]
    OUTPUT_PORTS = [Port("output", "Output", "out")]

    def execute(self, context, console):
        expr = self.model.config.get("expression", "context")
        safe_builtins = {
            "True": True, "False": False, "None": None,
            "len": len, "str": str, "int": int, "float": float,
            "bool": bool, "list": list, "dict": dict,
            "isinstance": isinstance, "type": type,
            "json": json,
        }
        try:
            result = eval(expr, {"__builtins__": safe_builtins}, {"context": context})
            console.info(f"{self.model.label}: {expr} → {str(result)[:100]}")
            return {"result": result}
        except Exception as e:
            console.error(f"{self.model.label}: expression error: {e}")
            return {"error": str(e)}

    def get_config_frame(self, master, on_change=None, **kwargs):
        frame = QWidget(master)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(2, 2, 2, 2)

        layout.addWidget(QLabel("Expression (Python):", frame))
        hint = QLabel("context contains all upstream node outputs", frame)
        hint.setStyleSheet("color: gray;")
        layout.addWidget(hint)

        editor = CodeEditor(frame)
        editor.setPlainText(self.model.config.get("expression", ""))

        def on_change_handler():
            self.model.config["expression"] = editor.toPlainText()
            if on_change:
                on_change()

        editor.textChanged.connect(on_change_handler)
        layout.addWidget(editor, 1)
        return frame


# Registry mapping TYPE_ID to node class
NODE_REGISTRY = {
    "api_request": ApiRequestNode,
    "condition": ConditionNode,
    "script": ScriptNode,
    "delay": DelayNode,
    "log": LogNode,
    "data_transform": DataTransformNode,
}

# List of palette entries for the UI
PALETTE_ENTRIES = [
    {"type_id": "api_request", "name": "API Request", "color": "#3b82f6", "desc": "Make an HTTP request"},
    {"type_id": "condition", "name": "Condition", "color": "#f59e0b", "desc": "If/else branching"},
    {"type_id": "script", "name": "Script", "color": "#8b5cf6", "desc": "Custom Python script"},
    {"type_id": "delay", "name": "Delay", "color": "#06b6d4", "desc": "Wait for N seconds"},
    {"type_id": "log", "name": "Log", "color": "#6b7280", "desc": "Log data to console"},
    {"type_id": "data_transform", "name": "Data Transform", "color": "#10b981", "desc": "Transform data"},
]
