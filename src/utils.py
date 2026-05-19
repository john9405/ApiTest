import builtins
import importlib
import io
import keyword
import platform
import pkgutil
import re
import sys
import tkinter as tk
import tokenize
from tkinter import ttk, messagebox
from tkinter.scrolledtext import ScrolledText
from typing import Optional


class EditorTable(ttk.Frame):
    """ A table with editable data """
    editable = False  # Open Editing

    def __init__(self, master=None, **kw):
        self.editable = kw.pop("editable") if "editable" in kw else False
        super().__init__(master, **kw)

        self.treeview = ttk.Treeview(self, columns=("name", "value"), show="headings")        
        self.treeview.heading("name", text="Name (+)" if self.editable else "Name", anchor=tk.CENTER)
        self.treeview.heading("value", text="Value", anchor=tk.CENTER)
        self.treeview.column("name", width=1)
        self.treeview.column("value")
        self.treeview.bind("<Button-1>", self.on_click)
        self.treeview.bind("<Double-1>", self.on_edit)
        if platform.system() == "Darwin":
            self.treeview.bind("<Control-Button-1>", self.on_right_click)
            self.treeview.bind("<Button-2>", self.on_right_click)
        else:
            self.treeview.bind("<Button-3>", self.on_right_click)

        scroll_y = ttk.Scrollbar(self, command=self.treeview.yview)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        self.treeview.pack(fill=tk.BOTH, expand=tk.YES)
        self.treeview.config(yscrollcommand=scroll_y.set)

    def on_click(self, event):
        region = self.treeview.identify('region', event.x, event.y)
        if region == 'heading':
            column = self.treeview.identify_column(event.x)
            if column == '#1' and self.editable:
                self.on_add(event.x, event.y)

    def on_right_click(self, event):
        if self.editable:
            item = self.treeview.identify_row(event.y)
            self.treeview.selection_set(item)
            menu = tk.Menu(self, tearoff=False)
            if item:
                menu.add_command(label="Edit", command=lambda: self.on_edit(event))
                menu.add_command(label="Delete", command=self.on_del)
            else:
                menu.add_command(label="Add", command=lambda: self.on_add(event.x, event.y))
            menu.post(event.x_root, event.y_root)

    def on_add(self, x, y):
        if self.editable:
            self.editor(None, "", "", x, y)

    def on_edit(self, event):
        region = self.treeview.identify('region', event.x, event.y)
        if region != 'heading' and len(self.treeview.selection()) > 0:
            item_id = self.treeview.selection()[0]
            item = self.treeview.item(item_id)
            self.editor(item_id, item["values"][0], item["values"][1], event.x, event.y)

    def on_del(self):
        if self.editable and len(self.treeview.selection()) > 0:
            self.treeview.delete(self.treeview.selection()[0])

    def editor(self, item_id=None, name=None, value=None, x=0, y=0):
        x += self.winfo_rootx()
        y += self.winfo_rooty()

        win = tk.Toplevel(self)
        win.title("New Value")
        win.geometry(f"+{x}+{y}")
        
        back = ttk.Frame(win)
        back.pack(fill=tk.BOTH, expand=tk.YES)

        frame = ttk.Frame(back)
        frame.pack(fill=tk.BOTH, expand=tk.YES, padx=10, pady=10)

        name_label = ttk.Label(frame, text="Name")
        name_label.pack(anchor="w")
        name_entry = ttk.Entry(frame)
        if item_id:
            name_entry.insert('end', name)
        name_entry.pack(fill='x')

        value_label = ttk.Label(frame, text="Value")
        value_label.pack(anchor="w")
        value_entry = ScrolledText(frame, width=40, height=10)
        if item_id:
            value_entry.insert('end', value)
        value_entry.pack()

        action_bar = ttk.Frame(frame)
        if self.editable:
            ttk.Button(
                action_bar,
                text="Submit",
                command=lambda: self.commit(item_id, win, name_entry, value_entry),
            ).pack(side="left")
        ttk.Button(action_bar, text="Cancel", command=win.destroy).pack(side="left")
        action_bar.pack(pady=(10, 0))

    def commit(
        self,
        item_id: Optional[str] = None,
        win: Optional[tk.Toplevel] = None,
        name_entry: Optional[ttk.Entry] = None,
        value_entry: Optional[ScrolledText] = None,
    ):
        name = name_entry.get()
        value = value_entry.get('1.0', "end")[:-1]
        if self.check_name(item_id, name):
            if item_id is None:
                self.treeview.insert("", tk.END, values=(name, value))
            else:
                self.treeview.item(item_id, values=(name, value))
            win.destroy()
        else:
            messagebox.showerror("error", "Duplicate key")

    def check_name(
        self, item_id: Optional[str] = None, name: Optional[str] = None
    ) -> bool:
        if name:
            for child in self.treeview.get_children():
                if child == item_id:
                    continue
                item = self.treeview.item(child)
                if str(item["values"][0]) == name:
                    return False
            return True
        return False

    def get_data(self) -> dict:
        data = {}
        for child in self.treeview.get_children():
            item = self.treeview.item(child)
            data.update({str(item["values"][0]): str(item["values"][1])})
        return data

    def set_data(self, data: dict):
        for key in data.keys():
            self.treeview.insert("", tk.END, values=(key, data[key]))

    def clear_data(self):
        self.treeview.delete(*self.treeview.get_children())


class CodeEditor(ScrolledText):
    """ A Python code editor """
    HIGHLIGHT_DELAY_MS = 120
    COMPLETION_MAX_ITEMS = 8
    TAG_STYLES = {
        "keyword": {"foreground": "#7c3aed"},
        "builtin": {"foreground": "#0f766e"},
        "string": {"foreground": "#b45309"},
        "comment": {"foreground": "#6b7280"},
        "number": {"foreground": "#1d4ed8"},
        "function": {"foreground": "#2563eb"},
        "class": {"foreground": "#be185d"},
        "decorator": {"foreground": "#0f766e"},
    }
    PYTHON_BUILTINS = frozenset(dir(builtins))
    STDLIB_MODULES = frozenset(
        name for name in getattr(sys, "stdlib_module_names", set()) if not name.startswith("_") or name == "__future__"
    )
    DECORATOR_RE = re.compile(r"(?m)^[ \t]*@[\w\.]+")
    IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*$")
    COMPLETION_EXPR_RE = re.compile(
        r"(?:[A-Za-z_][A-Za-z0-9_]*)(?:\.[A-Za-z_][A-Za-z0-9_]*)*\.?$"
    )
    COMPLETION_SOURCE_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")

    def __init__(self, master=None, **kwargs):
        super().__init__(master, **kwargs)
        self._highlight_job = None
        self._completion_popup = None
        self._completion_list = None
        self._completion_candidates = []
        self._completion_object_cache = {}
        self._completion_members_cache = {}
        self._config_tags()
        self.bind("<<Modified>>", self._on_modified, add="+")
        self.bind("<KeyRelease>", self._on_key_release, add="+")
        self.bind("<Tab>", self._on_tab_complete, add="+")
        self.bind("<Return>", self._on_accept_completion, add="+")
        self.bind("<Escape>", self._on_cancel_completion, add="+")
        self.bind("<Down>", self._on_move_completion, add="+")
        self.bind("<Up>", self._on_move_completion, add="+")
        self.bind("<Button-1>", self._on_pointer_action, add="+")
        self.bind("<Destroy>", self._on_destroy, add="+")
        self.edit_modified(False)
        self.after_idle(self.highlight_python)

    def _config_tags(self):
        for tag_name, tag_style in self.TAG_STYLES.items():
            self.tag_configure(tag_name, **tag_style)
        self.tag_raise("function")
        self.tag_raise("class")
        self.tag_raise("decorator")

    def _on_modified(self, _event=None):
        if not self.edit_modified():
            return
        self.edit_modified(False)
        self._schedule_highlight()

    def _schedule_highlight(self):
        if self._highlight_job is not None:
            self.after_cancel(self._highlight_job)
        self._highlight_job = self.after(self.HIGHLIGHT_DELAY_MS, self.highlight_python)

    def _on_key_release(self, event):
        if event.keysym in {
            "Up",
            "Down",
            "Left",
            "Right",
            "Home",
            "End",
            "Prior",
            "Next",
            "Return",
            "Tab",
            "Escape",
            "Shift_L",
            "Shift_R",
            "Control_L",
            "Control_R",
            "Alt_L",
            "Alt_R",
            "Meta_L",
            "Meta_R",
        }:
            return
        self._update_completion()

    def _on_tab_complete(self, _event=None):
        if self._accept_completion():
            return "break"
        return None

    def _on_accept_completion(self, _event=None):
        if self._accept_completion():
            return "break"
        return None

    def _on_cancel_completion(self, _event=None):
        if self._completion_visible():
            self._hide_completion()
            return "break"
        return None

    def _on_move_completion(self, event):
        if not self._completion_visible():
            return None
        delta = -1 if event.keysym == "Up" else 1
        self._move_completion_selection(delta)
        return "break"

    def _on_pointer_action(self, _event=None):
        self._hide_completion()

    def _on_destroy(self, event):
        if event.widget is self:
            self._hide_completion()

    def _clear_highlight_tags(self):
        for tag_name in self.TAG_STYLES:
            self.tag_remove(tag_name, "1.0", tk.END)

    def _add_tag(self, tag_name, start, end):
        self.tag_add(tag_name, f"{start[0]}.{start[1]}", f"{end[0]}.{end[1]}")

    def _highlight_decorators(self, content: str):
        for match in self.DECORATOR_RE.finditer(content):
            start = f"1.0+{match.start()}c"
            end = f"1.0+{match.end()}c"
            self.tag_add("decorator", start, end)

    def highlight_python(self):
        self._highlight_job = None
        content = self.get("1.0", "end-1c")
        self._clear_highlight_tags()
        if not content:
            return

        self._highlight_decorators(content)
        next_name_tag = None
        reader = io.StringIO(content).readline
        try:
            tokens = tokenize.generate_tokens(reader)
            for token_info in tokens:
                token_type = token_info.type
                token_string = token_info.string
                start = token_info.start
                end = token_info.end

                if token_type == tokenize.NAME and next_name_tag:
                    self._add_tag(next_name_tag, start, end)
                    next_name_tag = None
                    continue

                if token_type == tokenize.COMMENT:
                    self._add_tag("comment", start, end)
                    continue

                if token_type == tokenize.STRING:
                    self._add_tag("string", start, end)
                    continue

                if token_type == tokenize.NUMBER:
                    self._add_tag("number", start, end)
                    continue

                if token_type != tokenize.NAME:
                    continue

                if keyword.iskeyword(token_string):
                    self._add_tag("keyword", start, end)
                    if token_string == "def":
                        next_name_tag = "function"
                    elif token_string == "class":
                        next_name_tag = "class"
                    continue

                if token_string in self.PYTHON_BUILTINS:
                    self._add_tag("builtin", start, end)
        except tokenize.TokenError:
            pass

    def _completion_visible(self):
        return (
            self._completion_popup is not None
            and self._completion_list is not None
            and self._completion_popup.winfo_exists()
        )

    def _current_completion_context(self):
        line_text = self.get("insert linestart", "insert")
        fragment_match = re.search(r"[A-Za-z0-9_\.]+$", line_text)
        if fragment_match is None:
            return "", "", None

        expr = fragment_match.group(0)
        if self.COMPLETION_EXPR_RE.fullmatch(expr) is None:
            return "", "", None

        if "." in expr:
            object_path, prefix = expr.rsplit(".", 1)
        else:
            object_path, prefix = "", expr

        prefix_start = self.index("insert") if not prefix else self.index(f"insert-{len(prefix)}c")
        return object_path, prefix, prefix_start

    def _resolve_completion_object(self, object_path: str):
        if object_path in self._completion_object_cache:
            return self._completion_object_cache[object_path]

        parts = object_path.split(".")
        resolved = None
        for index in range(len(parts), 0, -1):
            module_name = ".".join(parts[:index])
            try:
                resolved = importlib.import_module(module_name)
            except Exception:
                continue

            try:
                for attr_name in parts[index:]:
                    resolved = getattr(resolved, attr_name)
            except Exception:
                resolved = None
            break

        self._completion_object_cache[object_path] = resolved
        return resolved

    def _completion_members_for_object(self, object_path: str):
        if object_path in self._completion_members_cache:
            return self._completion_members_cache[object_path]

        resolved = self._resolve_completion_object(object_path)
        if resolved is None:
            self._completion_members_cache[object_path] = set()
            return set()

        members = set(dir(resolved))
        module_path = getattr(resolved, "__path__", None)
        if module_path is not None:
            try:
                members.update(module.name for module in pkgutil.iter_modules(module_path))
            except Exception:
                pass

        self._completion_members_cache[object_path] = members
        return members

    def _completion_candidates_for(self, object_path: str, prefix: str):
        if not prefix and not object_path:
            return []

        if object_path:
            candidates = self._completion_members_for_object(object_path)
        else:
            content = self.get("1.0", "end-1c")
            identifiers = set(self.COMPLETION_SOURCE_RE.findall(content))
            candidates = identifiers | self.PYTHON_BUILTINS | set(keyword.kwlist) | self.STDLIB_MODULES

        return sorted(
            (
                item
                for item in candidates
                if item.startswith(prefix) and item != prefix
            ),
            key=lambda item: (item.startswith("__"), item.lower()),
        )

    def _ensure_completion_popup(self):
        if self._completion_visible():
            return
        popup = tk.Toplevel(self)
        popup.wm_overrideredirect(True)
        popup.transient(self.winfo_toplevel())
        try:
            popup.wm_attributes("-topmost", True)
        except tk.TclError:
            pass

        border = tk.Frame(popup, borderwidth=1, relief=tk.SOLID, background="#cbd5e1")
        border.pack(fill=tk.BOTH, expand=True)
        completion_list = tk.Listbox(
            border,
            activestyle="none",
            borderwidth=0,
            exportselection=False,
            highlightthickness=0,
            selectbackground="#dbeafe",
            selectforeground="#0f172a",
        )
        completion_list.pack(fill=tk.BOTH, expand=True)
        completion_list.bind("<ButtonRelease-1>", self._on_completion_click)
        completion_list.bind("<Double-Button-1>", self._on_completion_click)

        self._completion_popup = popup
        self._completion_list = completion_list

    def _show_completion(self, candidates):
        self._ensure_completion_popup()
        self._completion_candidates = candidates
        self._completion_list.delete(0, tk.END)
        for item in candidates[: self.COMPLETION_MAX_ITEMS]:
            self._completion_list.insert(tk.END, item)

        if self._completion_list.size() == 0:
            self._hide_completion()
            return

        self._completion_list.selection_clear(0, tk.END)
        self._completion_list.selection_set(0)
        self._completion_list.activate(0)
        self._completion_list.see(0)
        self._completion_list.config(
            height=min(self._completion_list.size(), self.COMPLETION_MAX_ITEMS),
            width=max(12, min(40, max(len(item) for item in candidates[: self.COMPLETION_MAX_ITEMS]) + 2)),
        )

        bbox = self.bbox("insert")
        if bbox is None:
            x = self.winfo_rootx()
            y = self.winfo_rooty()
        else:
            x = self.winfo_rootx() + bbox[0]
            y = self.winfo_rooty() + bbox[1] + bbox[3]
        self._completion_popup.geometry(f"+{x}+{y}")
        self._completion_popup.deiconify()

    def _hide_completion(self):
        self._completion_candidates = []
        self._completion_list = None
        if self._completion_popup is not None:
            try:
                self._completion_popup.destroy()
            except tk.TclError:
                pass
        self._completion_popup = None

    def _update_completion(self):
        object_path, prefix, _ = self._current_completion_context()
        if not prefix and not object_path:
            self._hide_completion()
            return

        candidates = self._completion_candidates_for(object_path, prefix)
        if not candidates:
            self._hide_completion()
            return
        self._show_completion(candidates)

    def _move_completion_selection(self, delta):
        current = self._completion_list.curselection()
        if current:
            index = current[0]
        else:
            index = 0
        next_index = max(0, min(self._completion_list.size() - 1, index + delta))
        self._completion_list.selection_clear(0, tk.END)
        self._completion_list.selection_set(next_index)
        self._completion_list.activate(next_index)
        self._completion_list.see(next_index)

    def _accept_completion(self):
        if not self._completion_visible():
            return False

        selection = self._completion_list.curselection()
        if not selection:
            return False

        _, prefix, prefix_start = self._current_completion_context()
        if prefix_start is None:
            self._hide_completion()
            return False

        value = self._completion_list.get(selection[0])
        self.delete(prefix_start, "insert")
        self.insert(prefix_start, value)
        self.mark_set("insert", f"{prefix_start}+{len(value)}c")
        self.see("insert")
        self._hide_completion()
        return True

    def _on_completion_click(self, _event=None):
        self._accept_completion()
