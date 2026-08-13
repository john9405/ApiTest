"""Block/node type definitions for the Flow feature.

Each node type extends BaseNode and provides:
- Visual properties (color, display name, ports)
- execute(context, console) — the runtime behavior
- get_config_frame(master) — the configuration UI for the inspector
"""

import json
import re
import threading
import time
import tkinter as tk
import ttkbootstrap as ttk
from tkinter.scrolledtext import ScrolledText

import requests

from ..utils import CodeEditor


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
        """Return a ttk.Frame with configuration widgets.

        on_change: callback to notify the inspector when config changes
        Extra kwargs are forwarded for type-specific needs (e.g. get_collection_requests).
        """
        frame = ttk.Frame(master)
        ttk.Label(frame, text=f"No configuration needed for {self.DISPLAY_NAME}.").pack(padx=5, pady=10)
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

        frame = ttk.Frame(master)
        frame.columnconfigure(1, weight=1)

        row = 0

        # ---- Source toggle ----
        ttk.Label(frame, text="Source:").grid(row=row, column=0, sticky="w", padx=2, pady=2)
        source_var = tk.StringVar(value=self.model.config.get("source", "inline"))
        source_frame = ttk.Frame(frame)
        source_frame.grid(row=row, column=1, sticky="ew", padx=2, pady=2)
        ttk.Radiobutton(source_frame, text="Inline", variable=source_var, value="inline").pack(side=tk.LEFT)
        ttk.Radiobutton(source_frame, text="From Collection", variable=source_var, value="collection").pack(side=tk.LEFT, padx=(8, 0))

        # ---- Collection request picker (shown when source == 'collection') ----
        picker_frame = ttk.Frame(frame)
        picker_frame.grid(row=row + 1, column=0, columnspan=2, sticky="ew", padx=2, pady=2)
        picker_frame.columnconfigure(1, weight=1)

        ttk.Label(picker_frame, text="Request:").grid(row=0, column=0, sticky="w", padx=2, pady=2)

        # Read-only display entry + browse button
        selected_display = tk.StringVar(value="")
        request_entry = ttk.Entry(picker_frame, textvariable=selected_display, state="readonly")
        request_entry.grid(row=0, column=1, sticky="ew", padx=2, pady=2)
        browse_btn = ttk.Button(picker_frame, text="...", width=3,
                                command=lambda: _show_tree_popup())
        browse_btn.grid(row=0, column=2, sticky="e", padx=(1, 2))

        # Store request list and picker state
        self._request_list = []
        self._picker_frame = picker_frame
        self._selected_display = selected_display

        def _populate_requests():
            """Load all requests from the database and group by folder path."""
            self._request_list = []
            try:
                self._request_list = list_all_requests()
            except Exception:
                self._request_list = []
            # Update display for the currently selected request
            _refresh_display()

        def _refresh_display():
            """Update the entry to show the currently selected request."""
            saved_id = self.model.config.get("request_id")
            for req in self._request_list:
                if req["id"] == saved_id:
                    path = req.get("path", "")
                    if path:
                        selected_display.set(f"{req['method']} {req['name']}  [{path}]")
                    else:
                        selected_display.set(f"{req['method']} {req['name']}")
                    return
            selected_display.set("")

        def _save_selection(req):
            """Store the selected request id and update display."""
            self.model.config["request_id"] = req["id"]
            _refresh_display()
            if on_change:
                on_change()

        def _show_tree_popup():
            """Open a popup dialog with requests grouped by folder."""
            popup = tk.Toplevel(picker_frame)
            popup.title("Select Request")
            popup.geometry("500x380")
            popup.transient(picker_frame.winfo_toplevel())
            popup.grab_set()

            # Treeview
            tree = ttk.Treeview(popup, show="tree", selectmode="browse")
            tree.pack(fill=tk.BOTH, expand=True, padx=8, pady=(8, 4))
            tree.heading("#0", text="Requests")

            # Scrollbar
            scroll = ttk.Scrollbar(tree, orient=tk.VERTICAL, command=tree.yview)
            tree.configure(yscrollcommand=scroll.set)
            scroll.pack(side=tk.RIGHT, fill=tk.Y)

            # Group requests by folder path
            groups = {}  # path -> list of requests
            ungrouped = []
            for req in self._request_list:
                path = req.get("path", "")
                if path:
                    groups.setdefault(path, []).append(req)
                else:
                    ungrouped.append(req)

            # Sort groups by path
            sorted_paths = sorted(groups.keys())

            # Populate tree
            for path in sorted_paths:
                group_id = tree.insert("", tk.END, text=path, open=True)
                for req in groups[path]:
                    tree.insert(group_id, tk.END, text=f"{req['method']}  {req['name']}",
                                values=[req["id"]], tags=("request",))

            # Ungrouped requests
            if ungrouped:
                group_id = tree.insert("", tk.END, text="(no folder)", open=True)
                for req in ungrouped:
                    tree.insert(group_id, tk.END, text=f"{req['method']}  {req['name']}",
                                values=[req["id"]], tags=("request",))

            # Find and select the currently saved request
            saved_id = self.model.config.get("request_id")
            if saved_id is not None:
                _select_by_id(tree, saved_id)

            # Highlight current selection
            tree.tag_configure("selected", background="#3b82f6", foreground="white")
            self._popup_tree = tree
            self._popup_result = None

            def _on_select(event):
                sel = tree.selection()
                if sel:
                    item = tree.item(sel[0])
                    if item["values"]:
                        self._popup_result = item["values"][0]

            tree.bind("<<TreeviewSelect>>", _on_select)

            def _on_double_click(event):
                if self._popup_result is not None:
                    req = next((r for r in self._request_list if r["id"] == self._popup_result), None)
                    if req:
                        _save_selection(req)
                    popup.destroy()

            tree.bind("<Double-1>", _on_double_click)

            # Button bar
            btn_frame = ttk.Frame(popup)
            btn_frame.pack(fill=tk.X, padx=8, pady=(4, 8))

            def _on_ok():
                if self._popup_result is not None:
                    req = next((r for r in self._request_list if r["id"] == self._popup_result), None)
                    if req:
                        _save_selection(req)
                popup.destroy()

            def _on_clear():
                self.model.config["request_id"] = None
                selected_display.set("")
                if on_change:
                    on_change()
                popup.destroy()

            ttk.Button(btn_frame, text="Clear", command=_on_clear).pack(side=tk.LEFT)
            ttk.Button(btn_frame, text="Cancel", command=popup.destroy).pack(side=tk.RIGHT, padx=(4, 0))
            ttk.Button(btn_frame, text="OK", command=_on_ok).pack(side=tk.RIGHT)

        def _select_by_id(tree, req_id):
            """Expand and select the tree item matching the given request id."""
            for group_id in tree.get_children():
                for child_id in tree.get_children(group_id):
                    values = tree.item(child_id, "values")
                    if values and values[0] == req_id:
                        tree.see(child_id)
                        tree.selection_set(child_id)
                        return

        def _show_hide_picker(*args):
            if source_var.get() == "collection":
                picker_frame.grid()
                _populate_requests()
            else:
                picker_frame.grid_remove()

        source_var.trace_add("write", _show_hide_picker)
        source_var.trace_add("write", lambda *a: self.model.config.update({"source": source_var.get()}) or (on_change and on_change()))

        row += 2  # skip picker row for inline fields

        # ---- Inline config fields ----
        self._inline_fields = inline_fields = ttk.Frame(frame)
        inline_fields.grid(row=row, column=0, columnspan=2, sticky="ew", padx=0, pady=0)
        inline_fields.columnconfigure(1, weight=1)
        irow = 0

        ttk.Label(inline_fields, text="Method:").grid(row=irow, column=0, sticky="w", padx=2, pady=2)
        method_var = tk.StringVar(value=self.model.config.get("method", "GET"))
        method_box = ttk.Combobox(inline_fields, textvariable=method_var,
                                  values=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"],
                                  state="readonly", width=10)
        method_box.grid(row=irow, column=1, sticky="ew", padx=2, pady=2)

        def on_method_change(*args):
            self.model.config["method"] = method_var.get()
            if on_change:
                on_change()

        method_var.trace_add("write", on_method_change)
        irow += 1

        ttk.Label(inline_fields, text="URL:").grid(row=irow, column=0, sticky="w", padx=2, pady=2)
        url_var = tk.StringVar(value=self.model.config.get("url", ""))
        url_entry = ttk.Entry(inline_fields, textvariable=url_var)
        url_entry.grid(row=irow, column=1, sticky="ew", padx=2, pady=2)

        def on_url_change(*args):
            self.model.config["url"] = url_var.get()
            if on_change:
                on_change()

        url_var.trace_add("write", on_url_change)
        irow += 1

        # Headers
        ttk.Label(inline_fields, text="Headers (JSON):").grid(row=irow, column=0, sticky="nw", padx=2, pady=2)
        headers_text = ScrolledText(inline_fields, width=30, height=4)
        headers_val = self.model.config.get("headers", {})
        if isinstance(headers_val, dict):
            headers_text.insert("1.0", json.dumps(headers_val, indent=2))
        else:
            headers_text.insert("1.0", str(headers_val))
        headers_text.grid(row=irow, column=1, sticky="ew", padx=2, pady=2)

        def on_headers_change(*args):
            try:
                self.model.config["headers"] = json.loads(headers_text.get("1.0", "end-1c"))
            except json.JSONDecodeError:
                self.model.config["headers"] = headers_text.get("1.0", "end-1c")
            if on_change:
                on_change()

        headers_text.bind("<FocusOut>", on_headers_change, add="+")
        irow += 1

        # Body
        ttk.Label(inline_fields, text="Body:").grid(row=irow, column=0, sticky="nw", padx=2, pady=2)
        body_text = ScrolledText(inline_fields, width=30, height=4)
        body_val = self.model.config.get("body", "")
        body_text.insert("1.0", str(body_val))
        body_text.grid(row=irow, column=1, sticky="ew", padx=2, pady=2)

        def on_body_change(*args):
            self.model.config["body"] = body_text.get("1.0", "end-1c")
            if on_change:
                on_change()

        body_text.bind("<FocusOut>", on_body_change, add="+")

        def _show_hide_inline(*args):
            if source_var.get() == "collection":
                inline_fields.grid_remove()
            else:
                inline_fields.grid()

        source_var.trace_add("write", _show_hide_inline)

        # Initial state
        if source_var.get() == "collection":
            inline_fields.grid_remove()
            _populate_requests()
        else:
            picker_frame.grid_remove()

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
        frame = ttk.Frame(master)
        frame.columnconfigure(0, weight=1)

        ttk.Label(frame, text="Expression (Python):").grid(row=0, column=0, sticky="w", padx=2, pady=2)
        ttk.Label(frame, text="Use: context[node_id]['field']", foreground="gray").grid(
            row=1, column=0, sticky="w", padx=2, pady=1)

        editor = CodeEditor(frame)
        editor.insert("1.0", self.model.config.get("expression", ""))
        editor.grid(row=2, column=0, sticky="nsew", padx=2, pady=2)
        frame.rowconfigure(2, weight=1)

        def on_change_handler(*args):
            self.model.config["expression"] = editor.get("1.0", "end-1c")
            if on_change:
                on_change()

        editor.bind("<FocusOut>", on_change_handler, add="+")
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
        frame = ttk.Frame(master)
        frame.columnconfigure(0, weight=1)

        ttk.Label(frame, text="Python Script:").grid(row=0, column=0, sticky="w", padx=2, pady=2)
        ttk.Label(frame, text="Available: context, console, output", foreground="gray").grid(
            row=1, column=0, sticky="w", padx=2, pady=1)

        editor = CodeEditor(frame)
        editor.insert("1.0", self.model.config.get("script", ""))
        editor.grid(row=2, column=0, sticky="nsew", padx=2, pady=2)
        frame.rowconfigure(2, weight=1)

        def on_change_handler(*args):
            self.model.config["script"] = editor.get("1.0", "end-1c")
            if on_change:
                on_change()

        editor.bind("<FocusOut>", on_change_handler, add="+")
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
        frame = ttk.Frame(master)
        ttk.Label(frame, text="Seconds:").pack(side=tk.LEFT, padx=2, pady=5)

        seconds_var = tk.StringVar(value=str(self.model.config.get("seconds", 1.0)))
        spinbox = ttk.Spinbox(frame, from_=0.1, to=3600.0, increment=0.5,
                              textvariable=seconds_var, width=10)
        spinbox.pack(side=tk.LEFT, padx=2, pady=5)

        def on_change(*args):
            try:
                self.model.config["seconds"] = float(seconds_var.get())
            except ValueError:
                pass
            if on_change:
                on_change()

        seconds_var.trace_add("write", on_change)
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
        frame = ttk.Frame(master)
        frame.columnconfigure(0, weight=1)

        ttk.Label(frame, text="Template:").grid(row=0, column=0, sticky="w", padx=2, pady=2)
        ttk.Label(frame, text="Use {{ context.node_id.field }} for variable substitution",
                  foreground="gray").grid(row=1, column=0, sticky="w", padx=2, pady=1)

        template_var = tk.StringVar(value=self.model.config.get("template", ""))
        entry = ttk.Entry(frame, textvariable=template_var)
        entry.grid(row=2, column=0, sticky="ew", padx=2, pady=2)

        def on_change(*args):
            self.model.config["template"] = template_var.get()
            if on_change:
                on_change()

        template_var.trace_add("write", on_change)
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
        frame = ttk.Frame(master)
        frame.columnconfigure(0, weight=1)

        ttk.Label(frame, text="Expression (Python):").grid(row=0, column=0, sticky="w", padx=2, pady=2)
        ttk.Label(frame, text="context contains all upstream node outputs", foreground="gray").grid(
            row=1, column=0, sticky="w", padx=2, pady=1)

        editor = CodeEditor(frame)
        editor.insert("1.0", self.model.config.get("expression", ""))
        editor.grid(row=2, column=0, sticky="nsew", padx=2, pady=2)
        frame.rowconfigure(2, weight=1)

        def on_change_handler(*args):
            self.model.config["expression"] = editor.get("1.0", "end-1c")
            if on_change:
                on_change()

        editor.bind("<FocusOut>", on_change_handler, add="+")
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
