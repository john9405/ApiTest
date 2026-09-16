"""PyQt5 utility widgets: editable key/value table, Python code editor, console."""

import builtins
import importlib
import inspect
import io
import keyword
import pkgutil
import re
import sys
import tokenize
import types

from PyQt5.QtCore import Qt, QEvent, QTimer
from PyQt5.QtGui import QColor, QTextCharFormat, QTextCursor, QFont
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QDialog,
    QListWidget,
    QAbstractItemView,
)

from . import qui
from .qui import TreeView, END, show_error
from .theme import style_role


# ---------------------------------------------------------------------------
# EditorTable — a two-column editable key/value table
# ---------------------------------------------------------------------------

class EditorTable(QWidget):
    """A table with editable data (Name / Value).

    When `editable` is True an action toolbar with Add / Edit / Delete
    buttons is shown; otherwise the table is read-only.
    """

    editable = False  # Open editing

    def __init__(self, master=None, **kw):
        self.editable = kw.pop("editable") if "editable" in kw else False
        super().__init__(master)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ---- action toolbar (buttons replace mouse-driven operations) ----
        if self.editable:
            bar = QWidget(self)
            bl = QHBoxLayout(bar)
            bl.setContentsMargins(4, 2, 4, 2)
            bl.setSpacing(4)
            bl.addStretch(1)

            self.add_btn = QPushButton("+ Add", bar)
            style_role(self.add_btn, "primary")
            self.add_btn.clicked.connect(self.on_add)
            bl.addWidget(self.add_btn)

            self.edit_btn = QPushButton("Edit", bar)
            style_role(self.edit_btn, "secondary")
            self.edit_btn.setEnabled(False)
            self.edit_btn.clicked.connect(self.on_edit)
            bl.addWidget(self.edit_btn)

            self.del_btn = QPushButton("Delete", bar)
            style_role(self.del_btn, "danger")
            self.del_btn.setEnabled(False)
            self.del_btn.clicked.connect(self.on_del)
            bl.addWidget(self.del_btn)

            layout.addWidget(bar)

        self.treeview = TreeView(self, show="headings", columns=("name", "value"))
        self.treeview.heading("#1", text="Name")
        self.treeview.heading("#2", text="Value")
        self.treeview.column("#1", width=10)
        self.treeview.column("#2", width=10)
        if self.editable:
            self.treeview.tree.itemSelectionChanged.connect(self._update_buttons)
        layout.addWidget(self.treeview, 1)

    def _update_buttons(self):
        """Enable/disable Edit and Delete depending on the current selection."""
        has_selection = len(self.treeview.selection()) > 0
        self.edit_btn.setEnabled(has_selection)
        self.del_btn.setEnabled(has_selection)

    def on_add(self):
        """Add a new row (button handler)."""
        if self.editable:
            self.editor(None, "", "")

    def on_edit(self):
        """Edit the selected row (button handler)."""
        if self.editable and len(self.treeview.selection()) > 0:
            item_id = self.treeview.selection()[0]
            item = self.treeview.item(item_id)
            self.editor(item_id, item["values"][0], item["values"][1])

    def on_del(self):
        """Delete the selected row (button handler)."""
        if self.editable and len(self.treeview.selection()) > 0:
            self.treeview.delete(self.treeview.selection()[0])

    def editor(self, item_id=None, name=None, value=None):
        """Open the popup dialog for adding/editing a row."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Edit Value" if item_id else "New Value")
        dlg.setMinimumWidth(360)
        layout = QVBoxLayout(dlg)
        layout.setSpacing(8)

        name_label = QLabel("Name")
        layout.addWidget(name_label)
        name_entry = QLineEdit(dlg)
        if item_id:
            name_entry.setText(name)
        layout.addWidget(name_entry)

        value_label = QLabel("Value")
        layout.addWidget(value_label)
        value_entry = QPlainTextEdit(dlg)
        if item_id:
            value_entry.setPlainText(value)
        value_entry.setMinimumHeight(120)
        layout.addWidget(value_entry)

        action_bar = QHBoxLayout()
        action_bar.addStretch(1)
        if self.editable:
            submit = QPushButton("Submit", dlg)
            style_role(submit, "primary")
            submit.clicked.connect(lambda: self.commit(item_id, dlg, name_entry, value_entry))
            action_bar.addWidget(submit)
        cancel = QPushButton("Cancel", dlg)
        cancel.clicked.connect(dlg.reject)
        action_bar.addWidget(cancel)
        layout.addLayout(action_bar)

        dlg.exec_()

    def commit(self, item_id=None, win=None, name_entry=None, value_entry=None):
        name = name_entry.text()
        value = value_entry.toPlainText()
        if self.check_name(item_id, name):
            if item_id is None:
                self.treeview.insert("", END, values=(name, value))
            else:
                self.treeview.item(item_id, values=(name, value))
            win.accept()
        else:
            show_error(self, "error", "Duplicate key")

    def check_name(self, item_id=None, name=None) -> bool:
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
            self.treeview.insert("", END, values=(key, data[key]))

    def clear_data(self):
        self.treeview.delete(self.treeview.get_children())


# ---------------------------------------------------------------------------
# Python syntax highlighting (tokenize-based)
# ---------------------------------------------------------------------------

NORMAL_FORMAT = QTextCharFormat()
NORMAL_FORMAT.setForeground(QColor("#1f2937"))

TAG_FORMATS = {
    "keyword": QTextCharFormat(),
    "builtin": QTextCharFormat(),
    "string": QTextCharFormat(),
    "comment": QTextCharFormat(),
    "number": QTextCharFormat(),
    "function": QTextCharFormat(),
    "class": QTextCharFormat(),
    "decorator": QTextCharFormat(),
}
TAG_FORMATS["keyword"].setForeground(QColor("#7c3aed"))
TAG_FORMATS["builtin"].setForeground(QColor("#0f766e"))
TAG_FORMATS["string"].setForeground(QColor("#b45309"))
TAG_FORMATS["comment"].setForeground(QColor("#6b7280"))
TAG_FORMATS["number"].setForeground(QColor("#1d4ed8"))
TAG_FORMATS["function"].setForeground(QColor("#2563eb"))
TAG_FORMATS["class"].setForeground(QColor("#be185d"))
TAG_FORMATS["decorator"].setForeground(QColor("#0f766e"))


# ---------------------------------------------------------------------------
# CodeEditor — Python code editor with highlighting and autocompletion
# ---------------------------------------------------------------------------

# ``sys.stdlib_module_names`` was added in Python 3.10 and is guaranteed to be
# present on the versions this project supports (3.11+), so the completion set
# is read straight from the running interpreter instead of a hand-written list.
# A hardcoded list had already drifted — it advertised ``parser`` (removed in
# 3.10) and ``binhex``/``symbol`` (removed in 3.13) — and would keep drifting as
# the stdlib changes.  Deriving the set from the interpreter means completions
# can never suggest a module that is absent, nor omit one that is present.
# Which of those names the user actually gets to *see* is decided by the
# ordering in ``_completion_sort_key``.
class CodeEditor(QPlainTextEdit):
    """A Python code editor built on QPlainTextEdit."""

    HIGHLIGHT_DELAY_MS = 120
    COMPLETION_MAX_ITEMS = 12
    PYTHON_BUILTINS = frozenset(dir(builtins))
    STDLIB_MODULES = frozenset(
        name for name in sys.stdlib_module_names
        if not name.startswith("_") or name == "__future__"
    )
    # builtins + keywords + stdlib never change, so the union is built once
    # instead of on every keystroke
    STATIC_COMPLETION_NAMES = PYTHON_BUILTINS | frozenset(keyword.kwlist) | STDLIB_MODULES
    # ``import ...`` lines want module names, not the identifiers that happen to
    # appear in the buffer, and ``from x import ...`` wants the members of ``x``.
    # Both are recognized from the text left of the cursor (``from `` alone is
    # included: the module name is exactly what is missing there).
    IMPORT_STATEMENT_RE = re.compile(r"(?:^|[;\s])(?:import|from)\s+[A-Za-z0-9_\.]*$")
    FROM_IMPORT_RE = re.compile(
        r"(?:^|[;\s])from\s+([A-Za-z_][A-Za-z0-9_\.]*)"
        r"\s+import\s*(?:[A-Za-z_][A-Za-z0-9_]*)?$"
    )
    # The buffer's own imports decide what a dotted name means, and stdlib code
    # is full of names that only exist because of them: ``import os as o`` makes
    # ``o.path`` valid, and ``from datetime import datetime`` makes the *class*
    # shadow the module of the same name — resolving ``datetime.`` by import
    # alone answered with the module's members instead of the class's.  These
    # statements are read with regular expressions rather than ``ast``: the text
    # being completed is half-written most of the time, and a single parse error
    # would throw away the whole binding map.
    DOTTED_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*")
    # one match per import statement, with the bound clause(s) in group 1; the
    # ``,``-separated names and ``as`` aliases are split up afterwards.  The
    # pattern needs no closing bracket, so ``import os.path`` binds while it is
    # still being typed.  ``^[ \t]*`` also catches imports indented inside a
    # function, and ``[^\n#]`` stops at the comment so ``import os  # why``
    # binds only ``os``.
    IMPORT_BINDING_RE = re.compile(r"(?m)^[ \t]*import[ \t]+([^\n#]+)")
    # ``from x import ...``: group 1 is the module, group 2 the names.  The
    # parenthesized alternative (DOTALL, so it may span lines) covers
    # ``from x import (\n    a,\n    b,\n)`` — invalid until the ``)`` arrives,
    # which is exactly why this is not parsed with ``ast``.
    FROM_BINDING_RE = re.compile(
        r"(?m)^[ \t]*from[ \t]+([A-Za-z_][A-Za-z0-9_\.]*)[ \t]+import[ \t]+"
        r"(\([^)]*\)|[^\n#]+)",
        re.DOTALL,
    )
    # ``p = os.path`` — a plain assignment that aliases an already imported module
    MODULE_ALIAS_ASSIGN_RE = re.compile(
        r"(?m)^[ \t]*([A-Za-z_][A-Za-z0-9_]*)[ \t]*=[ \t]*"
        r"([A-Za-z_][A-Za-z0-9_\.]*)[ \t]*$"
    )
    # top-level modules that can actually be imported: the stdlib plus whatever
    # is installed next to the running interpreter (requests, bs4, ...).  Filled
    # on first use — scanning sys.path is far too slow for the class body.
    IMPORTABLE_MODULES = None
    DECORATOR_RE = re.compile(r"(?m)^[ \t]*@[\w\.]+")
    IDENTIFIER_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*$")
    COMPLETION_EXPR_RE = re.compile(
        r"(?:[A-Za-z_][A-Za-z0-9_]*)(?:\.[A-Za-z_][A-Za-z0-9_]*)*\.?$"
    )
    COMPLETION_SOURCE_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\b")

    def __init__(self, parent=None, **kwargs):
        super().__init__(parent)
        self._completion_popup = None
        self._completion_candidates = []
        self._completion_object_cache = {}
        self._completion_members_cache = {}
        self._completion_tiers_cache = {}
        self._completion_submodule_cache = {}
        self._completion_hint_cache = {}
        # name -> dotted path, rebuilt from the buffer's import statements
        self._bindings = {}
        self._bindings_source = None
        # set by Escape: keeps the suggestion list down until the next real edit
        self._completion_dismissed = False

        # one reusable timer: creating a new QTimer per keystroke leaked one
        # child object per key press and slowed the editor down over time
        self._highlight_job = QTimer(self)
        self._highlight_job.setSingleShot(True)
        self._highlight_job.timeout.connect(self.highlight_python)

        mono = QFont("Menlo" if qui.DARWIN else "Consolas", 10)
        mono.setStyleHint(QFont.Monospace)
        self.setFont(mono)
        self.setTabStopDistance(4 * self.fontMetrics().horizontalAdvance(" "))

        self.textChanged.connect(self._on_text_changed)
        self.cursorPositionChanged.connect(self._schedule_highlight)
        self.verticalScrollBar().valueChanged.connect(self._reposition_completion)
        self._schedule_highlight()

    # ------------------------------------------------------------------
    # Highlighting
    # ------------------------------------------------------------------
    def _on_text_changed(self):
        # a genuine edit: a suggestion list dismissed with Escape may come back
        self._completion_dismissed = False
        self._schedule_highlight()
        self._update_completion()

    def _schedule_highlight(self):
        self._highlight_job.start(self.HIGHLIGHT_DELAY_MS)

    def _add_format(self, cursor, start, end, fmt):
        if end <= start:
            return
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.KeepAnchor)
        cursor.setCharFormat(fmt)

    def highlight_python(self):
        self._highlight_job.stop()
        content = self.toPlainText()
        if not content:
            return

        # Re-applying character formats mutates the document, and QPlainTextEdit
        # reports that as textChanged() — i.e. the editor looked like it had just
        # been edited.  Two things followed from that, both wrong: the completion
        # list was recomputed (so it popped back up right after Escape had
        # dismissed it) and the highlighting pass rescheduled itself, re-painting
        # the whole document several times a second while the editor sat idle.
        # Colours are presentation only, so the widget's signals stay muted here;
        # real edits still arrive through the public textChanged() signal.
        signals_were_blocked = self.blockSignals(True)
        try:
            self._highlight_block(content)
        finally:
            self.blockSignals(signals_were_blocked)

    def _highlight_block(self, content):
        cursor = QTextCursor(self.document())
        cursor.select(QTextCursor.Document)
        cursor.setCharFormat(NORMAL_FORMAT)
        cursor.setPosition(0)

        # decorators
        for match in self.DECORATOR_RE.finditer(content):
            start_offset = match.start()
            end_offset = match.end()
            fmt = TAG_FORMATS["decorator"]
            self._add_format(cursor, start_offset, end_offset, fmt)

        next_name_tag = None
        reader = io.StringIO(content).readline
        try:
            tokens = tokenize.generate_tokens(reader)
            for token_info in tokens:
                token_type = token_info.type
                token_string = token_info.string
                start_offset = self._char_offset(token_info.start)
                end_offset = self._char_offset(token_info.end)
                fmt = None

                if token_type == tokenize.NAME and next_name_tag:
                    fmt = TAG_FORMATS[next_name_tag]
                    next_name_tag = None
                elif token_type == tokenize.COMMENT:
                    fmt = TAG_FORMATS["comment"]
                elif token_type == tokenize.STRING:
                    fmt = TAG_FORMATS["string"]
                elif token_type == tokenize.NUMBER:
                    fmt = TAG_FORMATS["number"]
                elif token_type == tokenize.NAME:
                    if keyword.iskeyword(token_string):
                        fmt = TAG_FORMATS["keyword"]
                        if token_string == "def":
                            next_name_tag = "function"
                        elif token_string == "class":
                            next_name_tag = "class"
                    elif token_string in self.PYTHON_BUILTINS:
                        fmt = TAG_FORMATS["builtin"]

                if fmt is not None:
                    self._add_format(cursor, start_offset, end_offset, fmt)
        except (tokenize.TokenError, IndentationError):
            pass

    def _char_offset(self, line_col):
        """Convert (line, column) 1-based line to absolute char offset."""
        line, col = line_col
        block = self.document().findBlockByNumber(line - 1)
        return block.position() + col

    # ------------------------------------------------------------------
    # Completion
    # ------------------------------------------------------------------
    def _line_prefix(self):
        """Text left of the cursor on the current line."""
        cursor = self.textCursor()
        block = self.document().findBlock(cursor.position())
        return block.text()[: cursor.positionInBlock()]

    def _current_completion_context(self):
        line_prefix = self._line_prefix()
        cursor = self.textCursor()
        fragment_match = re.search(r"[A-Za-z0-9_\.]+$", line_prefix)
        if fragment_match is None:
            return "", "", None

        expr = fragment_match.group(0)
        if self.COMPLETION_EXPR_RE.fullmatch(expr) is None:
            return "", "", None

        if "." in expr:
            object_path, prefix = expr.rsplit(".", 1)
        else:
            object_path, prefix = "", expr

        prefix_start = cursor.position() - len(prefix) if prefix else cursor.position()
        return object_path, prefix, prefix_start

    def _buffer_bindings(self):
        """Map every name the buffer's import statements bind to its dotted path.

        Names the buffer does not bind are left out entirely and keep the old
        behaviour of being resolved by import; a binding only takes over once
        ``_import_path`` has confirmed that the path behind it really resolves.
        """
        content = self.toPlainText()
        if content == self._bindings_source:
            return self._bindings

        bindings = {}
        for match in self.IMPORT_BINDING_RE.finditer(content):
            for clause in match.group(1).split(","):
                parts = clause.split()
                if not parts or self.DOTTED_NAME_RE.fullmatch(parts[0]) is None:
                    continue
                alias = parts[2] if len(parts) == 3 and parts[1] == "as" else None
                if alias is not None:
                    bindings[alias] = parts[0]
                    continue
                # ``import xml.etree.ElementTree`` binds ``xml`` but leaves the
                # whole chain usable, so every prefix is bound to itself
                segments = parts[0].split(".")
                for index in range(1, len(segments) + 1):
                    prefix_path = ".".join(segments[:index])
                    bindings[prefix_path] = prefix_path

        for match in self.FROM_BINDING_RE.finditer(content):
            module_name = match.group(1)
            clause_text = match.group(2).strip().strip("()")
            for clause in clause_text.split(","):
                parts = clause.split()
                if not parts or self.DOTTED_NAME_RE.fullmatch(parts[0]) is None:
                    continue
                # ``from os.path import join as j`` -> j is os.path.join; the
                # name of the attribute, not of the module, is what is bound
                alias = parts[2] if len(parts) == 3 and parts[1] == "as" else None
                bindings[alias or parts[0]] = f"{module_name}.{parts[0]}"

        for match in self.MODULE_ALIAS_ASSIGN_RE.finditer(content):
            target, path = match.group(1), match.group(2)
            if path.split(".")[0] in bindings:
                bindings[target] = path

        self._bindings_source = content
        if bindings != self._bindings:
            # every cached resolution was made against the previous import set
            self._completion_object_cache.clear()
            self._completion_members_cache.clear()
            self._completion_tiers_cache.clear()
            self._completion_submodule_cache.clear()
            self._completion_hint_cache.clear()
            self._bindings = bindings
        return self._bindings

    @staticmethod
    def _import_path(dotted_path: str):
        """Resolve a dotted path: import its longest module prefix, getattr the rest."""
        parts = dotted_path.split(".")
        for index in range(len(parts), 0, -1):
            try:
                resolved = importlib.import_module(".".join(parts[:index]))
            except Exception:
                continue
            try:
                for attr_name in parts[index:]:
                    resolved = getattr(resolved, attr_name)
            except Exception:
                return None
            return resolved
        return None

    def _resolve_bound_path(self, object_path: str):
        """Resolve a dotted path whose head the buffer's imports bound.

        ``o.path.join`` with ``import os as o`` becomes ``os.path.join``; the
        longest bound prefix wins so ``p`` from ``from os import path as p``
        resolves to the module behind ``os.path``.
        """
        bindings = self._buffer_bindings()
        parts = object_path.split(".")
        for index in range(len(parts), 0, -1):
            bound_path = bindings.get(".".join(parts[:index]))
            if bound_path is None:
                continue
            resolved = self._import_path(bound_path)
            if resolved is None:
                continue
            try:
                for attr_name in parts[index:]:
                    resolved = getattr(resolved, attr_name)
            except Exception:
                return None
            return resolved
        return None

    def _resolve_completion_object(self, object_path: str):
        if object_path in self._completion_object_cache:
            return self._completion_object_cache[object_path]
        # the buffer's imports are consulted first: they are what the user
        # actually wrote, and they know about aliases and shadowing that a bare
        # ``import_module`` cannot see
        resolved = self._resolve_bound_path(object_path)
        if resolved is None:
            resolved = self._import_path(object_path)
        self._completion_object_cache[object_path] = resolved
        return resolved

    def _import_completion_target(self, line_prefix: str):
        """What an ``import`` line left of the cursor is asking for.

        ``""``    the line completes module names (``import ...``, ``from ...``)
        ``"os"``  the line completes members of that module
                  (``from os import ...``)
        ``None``  the line is not an import statement
        """
        # "x = 1  # from here on" is a comment, not an import statement
        code = line_prefix.split("#", 1)[0]
        match = self.FROM_IMPORT_RE.search(code)
        if match is not None:
            return match.group(1)
        if self.IMPORT_STATEMENT_RE.search(code) is not None:
            return ""
        return None

    @classmethod
    def importable_modules(cls):
        """Top-level stdlib + installed modules that can be imported here."""
        if cls.IMPORTABLE_MODULES is None:
            names = set(cls.STDLIB_MODULES)
            try:
                names.update(
                    module.name for module in pkgutil.iter_modules()
                    if not module.name.startswith("_")
                )
            except Exception:
                pass
            cls.IMPORTABLE_MODULES = frozenset(names)
        return cls.IMPORTABLE_MODULES

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

    def _completion_submodules_for_object(self, object_path: str):
        """Importable submodules — what ``import pkg.`` and ``import os.`` need.

        ``__path__`` alone is not enough.  ``os`` is a plain module, and
        ``os.path`` is an attribute holding another module rather than a file
        inside a package directory, so ``import os.pa`` used to answer with
        nothing at all even though ``import os.path`` is perfectly legal.  The
        cross-check against ``sys.modules`` keeps that from turning into noise:
        an attribute qualifies only when it really is the module registered
        under ``<what was typed>.<name>``, which accepts ``os.path`` and rejects
        internals such as ``pathlib.os``.
        """
        if object_path in self._completion_submodule_cache:
            return self._completion_submodule_cache[object_path]
        names = set()
        resolved = self._resolve_completion_object(object_path) if object_path else None
        package_path = getattr(resolved, "__path__", None)
        if package_path is not None:
            try:
                names.update(module.name for module in pkgutil.iter_modules(package_path))
            except Exception:
                pass
        for name in self._module_attribute_names(resolved):
            if object_path and sys.modules.get(f"{object_path}.{name}") is not None:
                names.add(name)
        self._completion_submodule_cache[object_path] = names
        return names

    @staticmethod
    def _module_attribute_names(resolved):
        """Names of ``resolved``'s attributes that are modules themselves."""
        names = set()
        for name in dir(resolved):
            try:
                value = getattr(resolved, name)
            except Exception:
                continue
            if isinstance(value, types.ModuleType):
                names.add(name)
        return names

    @staticmethod
    def _exported_member_names(resolved):
        """The public API a module or class advertises through ``__all__``."""
        exported = getattr(resolved, "__all__", None)
        if isinstance(exported, (list, tuple, set, frozenset)):
            return {name for name in exported if isinstance(name, str)}
        return set()

    @staticmethod
    def _owner_module_name(resolved):
        """The module that would define a member of ``resolved``."""
        if isinstance(resolved, types.ModuleType):
            return getattr(resolved, "__name__", "")
        owner = getattr(resolved, "__module__", None)
        return owner if isinstance(owner, str) else ""

    @staticmethod
    def _member_is_defined_here(value, owner: str):
        """Whether ``value`` is part of the object's own API, not an import."""
        if not owner:
            return False
        if isinstance(value, types.ModuleType):
            # a submodule or subpackage of the object (``xml.etree`` under ``xml``)
            module_name = getattr(value, "__name__", "")
            return module_name == owner or module_name.startswith(f"{owner}.")
        value_module = getattr(value, "__module__", None)
        if not isinstance(value_module, str):
            return False
        if value_module == owner:
            return True
        # C accelerators report the module they were compiled in — ``_sqlite3``
        # for ``sqlite3.connect``, ``posixpath`` for ``os.path.join`` — so the
        # underscored twin of the owner's own name counts as well
        return value_module.lstrip("_") == owner.rpartition(".")[2].lstrip("_")

    def _completion_member_tiers(self, object_path: str):
        """Rank members by how much they belong to the object being completed.

        Coverage and relevance are separate concerns: every name ``dir()`` and
        ``pkgutil`` report is still offered, only the order changes.  Modules
        import helpers for their own use and those helpers are all public —
        ``logging`` carries ``io``, ``os``, ``re`` and ``sys``, ``sqlite3``
        carries ``time`` and ``collections`` — and because shortest-first
        ordering used to decide the twelve visible rows, they pushed the real
        API out of sight.  ``__all__`` (or failing that, being defined in the
        module) puts it back on top; the borrowed modules sink below it.
        """
        if object_path in self._completion_tiers_cache:
            return self._completion_tiers_cache[object_path]
        resolved = self._resolve_completion_object(object_path)
        tiers = {}
        if resolved is not None:
            preferred = self._exported_member_names(resolved)
            owner = self._owner_module_name(resolved)
            for name in self._completion_members_for_object(object_path):
                try:
                    value = getattr(resolved, name)
                except Exception:
                    tiers[name] = 1
                    continue
                if name in preferred or self._member_is_defined_here(value, owner):
                    tiers[name] = 0
                elif isinstance(value, types.ModuleType):
                    tiers[name] = 2
                else:
                    tiers[name] = 1
        self._completion_tiers_cache[object_path] = tiers
        return tiers

    @staticmethod
    def _completion_sort_key(item: str, prefix: str, tiers=None):
        """Order suggestions by usefulness, not just alphabetically.

        Plain alphabetical order buried the names people actually want: the
        first eight entries for ``os.`` were ``_check_methods``, ``_Environ``,
        ... and ``import o`` listed ``os`` ninth, behind every builtin starting
        with "o" — so common stdlib names never made it into the visible window.
        Private helpers and dunders go last, names the object advertises come
        first (``tiers``), exact-case matches come before case-insensitive ones,
        and shorter names win ties so the module beats its own long tail.
        """
        return (
            tiers.get(item, 1) if tiers else 0,
            item.startswith("_"),
            not item.startswith(prefix),
            len(item),
            item.lower(),
        )

    def _rank_completions(self, candidates, prefix: str, hide_private: bool = True, tiers=None):
        # matching ignores case so ``order`` finds ``OrderedDict`` and ``counter``
        # finds ``Counter``; the sort key keeps the exact-case matches on top.
        # Completions are still prefixed matches, never fuzzy ones.
        lowered = prefix.lower()
        return sorted(
            (
                item for item in candidates
                if item.lower().startswith(lowered)
                and item != prefix
                and not (hide_private and item.startswith("_"))
            ),
            key=lambda item: self._completion_sort_key(item, prefix, tiers),
        )

    def _completion_candidates_for(self, object_path: str, prefix: str, line_prefix: str = ""):
        # refresh the binding map first: it is what object resolution consults,
        # and it also drops the caches that went stale with the last edit
        self._buffer_bindings()
        target = self._import_completion_target(line_prefix)
        if target is not None:
            # an import statement completes importable names, never the
            # identifiers that happen to appear in the buffer
            if target:
                candidates = self._completion_members_for_object(target)
                return self._rank_completions(
                    candidates, prefix, tiers=self._completion_member_tiers(target),
                )
            if object_path:
                candidates = self._completion_submodules_for_object(object_path)
            else:
                candidates = self.importable_modules()
            return self._rank_completions(candidates, prefix)

        if not prefix and not object_path:
            return []
        if object_path:
            candidates = self._completion_members_for_object(object_path)
        else:
            content = self.toPlainText()
            identifiers = set(self.COMPLETION_SOURCE_RE.findall(content))
            candidates = identifiers | self.STATIC_COMPLETION_NAMES
        # private names are noise unless the user is explicitly typing one
        return self._rank_completions(
            candidates,
            prefix,
            hide_private=not prefix.startswith("_"),
            tiers=self._completion_member_tiers(object_path) if object_path else None,
        )

    def _ensure_completion_popup(self):
        """Build the suggestion list once, as a child of the editor viewport.

        It deliberately is *not* a top-level window: a Qt.Tool /
        WindowStaysOnTopHint popup took window activation away from the editor
        on macOS, so the editor lost keyboard focus as soon as a suggestion
        appeared and typing appeared to freeze while the popup stayed on
        screen.  A plain child widget cannot activate itself, is clipped to
        the editor and disappears together with its parent.
        """
        if self._completion_popup is not None:
            return
        popup = QListWidget(self.viewport())
        popup.setWindowFlags(Qt.Widget)
        popup.setFocusPolicy(Qt.NoFocus)
        popup.setAttribute(Qt.WA_ShowWithoutActivating, True)
        popup.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        popup.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        popup.setSelectionMode(QAbstractItemView.SingleSelection)
        popup.setMinimumWidth(160)
        # signatures and docstrings arrive as item tooltips; hovering a row must
        # not need a click, and 20s is long enough to read one
        popup.viewport().setMouseTracking(True)
        popup.setToolTipDuration(20000)
        popup.hide()
        popup.itemClicked.connect(lambda item: self._accept_completion())
        # Escape must close the list even if the platform hands the key to the
        # popup instead of the editor (the popup is focus-less by design, but the
        # key routing differs between platforms, so catch it on both widgets).
        popup.installEventFilter(self)
        popup.setStyleSheet(
            "QListWidget { background: white; border: 1px solid #cbd5e1; }"
            "QListWidget::item { padding: 3px 8px; }"
            "QListWidget::item:selected { background: #dbeafe; color: #0f172a; }"
        )
        self._completion_popup = popup

    def _place_completion_popup(self):
        """Move the popup under the cursor, keeping it inside the viewport."""
        popup = self._completion_popup
        if popup is None or popup.count() == 0:
            return
        viewport = self.viewport()
        width = max(160, min(320, popup.sizeHintForColumn(0) + 24))
        height = max(1, popup.sizeHintForRow(0)) * popup.count() + 4
        height = min(height, max(1, viewport.height() - 8))

        cursor_rect = self.cursorRect()
        x = max(0, min(cursor_rect.left(), viewport.width() - width))
        y = cursor_rect.bottom() + 2
        if y + height > viewport.height():
            above = cursor_rect.top() - height - 2
            y = above if above >= 0 else max(0, viewport.height() - height)
        popup.setFixedWidth(width)
        popup.setFixedHeight(height)
        popup.move(x, y)

    def _completion_hint_owner(self, object_path: str, line_prefix: str):
        """The object the visible suggestions are members of, or ``""``.

        Suggestions that are *names* rather than members — module names on an
        ``import`` line, identifiers already in the buffer — have no object to
        describe, and describing them would mean importing arbitrary modules
        just to hover a row.
        """
        target = self._import_completion_target(line_prefix)
        if target:
            return target
        if target is not None:
            return ""
        return object_path

    def _completion_hint(self, owner: str, name: str):
        """Signature and first docstring line for a suggestion, as a tooltip.

        The list is 160-320px wide, so a signature cannot be shown inline
        without pushing the names around; it rides along as the item's tooltip
        instead, which costs nothing when it is not wanted.  Only the rows that
        are actually displayed are described, and each result is cached because
        ``inspect.signature`` is far too slow to run per keystroke.
        """
        if not owner:
            return ""
        key = (owner, name)
        if key in self._completion_hint_cache:
            return self._completion_hint_cache[key]

        hint = ""
        resolved = self._resolve_completion_object(owner)
        if resolved is not None:
            try:
                value = getattr(resolved, name)
            except Exception:
                value = None
            else:
                hint = self._describe_completion_value(f"{owner}.{name}", value)
        self._completion_hint_cache[key] = hint
        return hint

    @staticmethod
    def _describe_completion_value(label: str, value):
        """``os.path.join(a, *p)`` plus the first paragraph of its docstring."""
        kind = "module" if isinstance(value, types.ModuleType) else None
        documented = True
        if callable(value):
            try:
                summary = f"{label}{inspect.signature(value)}"
            except (TypeError, ValueError):
                summary = label
        elif isinstance(value, (bool, int, float, complex, str, bytes)):
            summary = f"{label} = {value!r}"
            if len(summary) > 80:
                summary = f"{summary[:77]}..."
            # ``inspect.getdoc`` on a plain value falls back to the docstring of
            # its *type*, which would caption ``os.sep`` with the docs for
            # ``str`` — only callables and modules describe themselves
            documented = False
        else:
            summary = f"{label}  [{kind or type(value).__name__}]"
            documented = kind is not None
        if not documented:
            return summary

        doc = inspect.getdoc(value) or ""
        summary_line = doc.split("\n\n", 1)[0].replace("\n", " ").strip()
        if not summary_line:
            return summary
        if len(summary_line) > 240:
            summary_line = f"{summary_line[:237]}..."
        return f"{summary}\n\n{summary_line}"

    def _show_completion(self, candidates, owner: str = ""):
        self._ensure_completion_popup()
        self._completion_candidates = candidates
        popup = self._completion_popup
        popup.clear()
        for row, item in enumerate(candidates[: self.COMPLETION_MAX_ITEMS]):
            popup.addItem(item)
            hint = self._completion_hint(owner, item)
            if hint:
                popup.item(row).setToolTip(hint)
        if popup.count() == 0:
            self._hide_completion()
            return
        popup.setCurrentRow(0)
        self._place_completion_popup()
        popup.show()
        popup.raise_()

    def _reposition_completion(self, *args):
        if self._completion_visible():
            self._place_completion_popup()

    def _hide_completion(self, dismissed: bool = False):
        """Take the suggestion list down.

        ``dismissed`` marks a deliberate cancel (Escape): the list then stays
        down until the next real edit instead of being restored by whatever
        recomputes completions next.
        """
        self._completion_candidates = []
        if dismissed:
            self._completion_dismissed = True
        if self._completion_popup is not None:
            self._completion_popup.hide()

    def _completion_visible(self):
        return self._completion_popup is not None and self._completion_popup.isVisible()

    def _update_completion(self):
        if self._completion_dismissed:
            return
        object_path, prefix, _ = self._current_completion_context()
        line_prefix = self._line_prefix()
        candidates = self._completion_candidates_for(object_path, prefix, line_prefix)
        if not candidates:
            self._hide_completion()
            return
        self._show_completion(candidates, self._completion_hint_owner(object_path, line_prefix))

    def _move_completion_selection(self, delta):
        popup = self._completion_popup
        if popup is None:
            return
        row = popup.currentRow()
        next_row = max(0, min(popup.count() - 1, row + delta))
        popup.setCurrentRow(next_row)

    def _accept_completion(self):
        if not self._completion_visible():
            return False
        popup = self._completion_popup
        row = popup.currentRow()
        if row < 0:
            return False
        _, _, prefix_start = self._current_completion_context()
        if prefix_start is None:
            self._hide_completion()
            return False
        value = popup.item(row).text()
        cursor = self.textCursor()
        cursor.setPosition(prefix_start)
        cursor.setPosition(self.textCursor().position(), QTextCursor.KeepAnchor)
        cursor.insertText(value)
        self.setTextCursor(cursor)
        # the insert re-runs completion for the text it just wrote; a used
        # suggestion list stays down until the next keystroke
        self._hide_completion(dismissed=True)
        return True

    def eventFilter(self, watched, event):
        # Escape pressed while the platform routes keys to the suggestion list
        if (
            watched is self._completion_popup
            and event.type() == QEvent.KeyPress
            and self._is_cancel_key(event)
        ):
            self._hide_completion(dismissed=True)
            event.accept()
            return True
        return super().eventFilter(watched, event)

    @staticmethod
    def _is_cancel_key(event):
        """Escape, plus the Key_Cancel alias some platforms send instead."""
        return event.key() in (Qt.Key_Escape, Qt.Key_Cancel)

    def keyPressEvent(self, event):
        key = event.key()
        if self._completion_visible():
            if key == Qt.Key_Up:
                self._move_completion_selection(-1)
                event.accept()
                return
            if key == Qt.Key_Down:
                self._move_completion_selection(1)
                event.accept()
                return
            if key in (Qt.Key_Tab, Qt.Key_Return, Qt.Key_Enter):
                if self._accept_completion():
                    event.accept()
                    return
            if self._is_cancel_key(event):
                self._hide_completion(dismissed=True)
                event.accept()
                return
        if key == Qt.Key_Tab:
            self.textCursor().insertText("    ")
            event.accept()
            return
        super().keyPressEvent(event)

    def focusOutEvent(self, event):
        self._hide_completion()
        super().focusOutEvent(event)

    def hideEvent(self, event):
        self._hide_completion()
        super().hideEvent(event)

    def resizeEvent(self, event):
        self._hide_completion()
        super().resizeEvent(event)

    def mousePressEvent(self, event):
        self._hide_completion()
        super().mousePressEvent(event)


# ---------------------------------------------------------------------------
# ConsoleText / Console — colored console output
# ---------------------------------------------------------------------------

CONSOLE_COLORS = {
    "log": "#333333",
    "info": "#0066cc",
    "error": "#cc0000",
    "warning": "#cc8800",
}


class ConsoleText(QPlainTextEdit):
    """Read-only console with a Clear context menu and colored output."""

    def __init__(self, master=None, **kw):
        super().__init__(master)
        self.setReadOnly(True)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.on_right_click)

    def on_right_click(self, pos):
        menu = qui.make_menu(self)
        menu.addAction("Clear", self.on_clear)
        menu.exec_(self.mapToGlobal(pos))

    def on_clear(self):
        self.clear()

    def append_colored(self, text, color):
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        cursor.insertText(text, fmt)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()


class Console:
    """Console-like object writing colored lines into a ConsoleText."""

    def __init__(self, text: ConsoleText):
        self.text = text

    @staticmethod
    def to_string(*args) -> str:
        temp = ""
        for item in args:
            if isinstance(item, (str, int, float)):
                temp += f"{item} "
            elif isinstance(item, (dict, list)):
                temp += f"{json_dumps(item)}"
            elif isinstance(item, bytes):
                temp += f"{item.decode()}"
            else:
                temp += str(item)
        return temp

    def _write(self, level, *args):
        message = self.to_string(*args) + "\n"
        color = CONSOLE_COLORS.get(level, CONSOLE_COLORS["log"])
        qui.post(lambda: self.text.append_colored(message, color))

    def log(self, *args):
        self._write("log", *args)

    def info(self, *args):
        self._write("info", *args)

    def error(self, *args):
        self._write("error", *args)

    def warning(self, *args):
        self._write("warning", *args)


def json_dumps(item):
    import json
    return json.dumps(item, indent=4, ensure_ascii=False)
