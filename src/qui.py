"""Shared PyQt5 helper widgets used across the application.

Contains:
- Event: minimal event object carrying the mouse coordinates our handlers use
- ask_* / show_* / file dialogs: thin wrappers over native Qt dialogs
- post(): thread-safe "run on the UI thread" helper
- TreeView: QTreeWidget-based widget exposing a tree-list API
- Canvas: QPainter-based widget exposing a drawing API
- pil_to_qimage: convert a PIL image to QImage
"""

import platform

from PyQt5.QtCore import Qt, QPoint, QPointF, QRectF, QObject, QTimer, pyqtSignal
from PyQt5.QtGui import (
    QPainter,
    QColor,
    QPen,
    QBrush,
    QFont,
    QFontMetrics,
    QCursor,
    QImage,
    QPolygonF,
    QPainterPath,
)
from PyQt5.QtWidgets import (
    QWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QHeaderView,
    QMenu,
    QInputDialog,
    QMessageBox,
    QFileDialog,
    QVBoxLayout,
    QFrame,
)

DARWIN = platform.system() == "Darwin"
END = -1  # sentinel matching tk.END usage


# ---------------------------------------------------------------------------
# Event object
# ---------------------------------------------------------------------------

class Event:
    """Minimal event object carrying the attributes our handlers use."""

    def __init__(self, x=0, y=0, x_root=0, y_root=0, num=None, delta=0, keysym=None):
        self.x = x
        self.y = y
        self.x_root = x_root
        self.y_root = y_root
        self.num = num
        self.delta = delta
        self.keysym = keysym


# ---------------------------------------------------------------------------
# Dialogs
# ---------------------------------------------------------------------------

def ask_string(parent, title, prompt, initialvalue=""):
    """Ask for a single string; returns the value or None when cancelled."""
    text, ok = QInputDialog.getText(parent, title, prompt, text=initialvalue or "")
    return text if ok else None


def ask_yes_no(parent, title, message):
    box = QMessageBox(QMessageBox.Question, title, message,
                      QMessageBox.Yes | QMessageBox.No, parent)
    box.setDefaultButton(QMessageBox.No)
    return box.exec_() == QMessageBox.Yes


def show_error(parent, title, message):
    QMessageBox.critical(parent, title, message)


def show_warning(parent, title, message):
    QMessageBox.warning(parent, title, message)


def show_info(parent, title, message):
    QMessageBox.information(parent, title, message)


def open_file(parent=None, title="Open", filetypes=None, initialdir="", initialfile=""):
    """Open-file dialog; returns the chosen path or ''."""
    if filetypes is None:
        filetypes = [("All Files", "*.*")]
    name_filter = ";;".join(f"{label} ({pattern})" for label, pattern in filetypes)
    path, _ = QFileDialog.getOpenFileName(parent, title, initialdir or "", name_filter)
    return path or ""


def save_file(parent=None, title="Save", filetypes=None, initialdir="",
              initialfile="", defaultextension=""):
    """Save-file dialog; returns the chosen path or ''."""
    if filetypes is None:
        filetypes = [("All Files", "*.*")]
    name_filter = ";;".join(f"{label} ({pattern})" for label, pattern in filetypes)
    path, _ = QFileDialog.getSaveFileName(parent, title, initialdir or "", name_filter)
    return path or ""


# ---------------------------------------------------------------------------
# Thread-safe UI dispatch
# ---------------------------------------------------------------------------

class _UiCall(QObject):
    call = pyqtSignal(object)


_UI_CALL = _UiCall()


def post(callback):
    """Schedule `callback` to run on the UI thread (thread-safe)."""
    _UI_CALL.call.emit(callback)


def _ui_dispatch(callback):
    callback()


_UI_CALL.call.connect(_ui_dispatch)


def pil_to_qimage(pil_image):
    """Convert a PIL Image to a QImage (RGB888 copy)."""
    img = pil_image.convert("RGB")
    data = img.tobytes("raw", "RGB")
    qimg = QImage(data, img.width, img.height, img.width * 3, QImage.Format_RGB888)
    return qimg.copy()


def hline(parent=None):
    """A horizontal separator line (QFrame)."""
    line = QFrame(parent)
    line.setFrameShape(QFrame.HLine)
    line.setFrameShadow(QFrame.Plain)
    line.setObjectName("HLine")
    line.setFixedHeight(1)
    return line


def vline(parent=None):
    """A vertical separator line (QFrame)."""
    line = QFrame(parent)
    line.setFrameShape(QFrame.VLine)
    line.setFrameShadow(QFrame.Plain)
    line.setObjectName("VLine")
    line.setFixedWidth(1)
    return line


# ---------------------------------------------------------------------------
# TreeView — ttk.Treeview-like API over QTreeWidget
# ---------------------------------------------------------------------------

class _TreeWidget(QTreeWidget):
    """QTreeWidget subclass that forwards mouse events to the TreeView facade."""

    def __init__(self, view):
        super().__init__()
        self._view = view
        self.setContextMenuPolicy(Qt.DefaultContextMenu)

    def _fire(self, kind, x, y, gx, gy):
        self._view._emit(kind, x, y, gx, gy)

    def mousePressEvent(self, event):
        x, y = event.pos().x(), event.pos().y()
        gx, gy = event.globalPos().x(), event.globalPos().y()
        button = event.button()
        mods = event.modifiers()
        if button == Qt.RightButton:
            self._fire("right", x, y, gx, gy)
        elif button == Qt.MiddleButton:
            if DARWIN:  # on macOS the middle button is the right button
                self._fire("right", x, y, gx, gy)
        elif button == Qt.LeftButton:
            if DARWIN and (mods & Qt.ControlModifier):
                self._fire("right", x, y, gx, gy)
            else:
                self._fire("click", x, y, gx, gy)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        x, y = event.pos().x(), event.pos().y()
        gx, gy = event.globalPos().x(), event.globalPos().y()
        self._fire("double", x, y, gx, gy)
        super().mouseDoubleClickEvent(event)


class TreeView(QWidget):
    """A QTreeWidget wrapped with the ttk.Treeview API used by this app.

    Item identifiers are QTreeWidgetItems, except items inserted with an
    explicit `iid` (which are addressed by that string).
    """

    def __init__(self, parent=None, show="tree", columns=(), selectmode="extended"):
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

        self.tree = _TreeWidget(self)
        self.tree.setAlternatingRowColors(False)
        self.tree.setAnimated(True)
        self.tree.setUniformRowHeights(True)
        self.tree.setSelectionMode(
            QTreeWidget.SingleSelection if selectmode == "browse" else QTreeWidget.ExtendedSelection
        )
        self.tree.setExpandsOnDoubleClick(True)

        self._show = show
        self._columns = list(columns)
        if show == "headings":
            self.tree.setColumnCount(1 + len(columns))
            self.tree.setHeaderLabels([""] + list(columns))
            self.tree.setColumnHidden(0, True)
            self.tree.setRootIsDecorated(False)
            self.tree.setIndentation(0)
            # Table widgets: share the available width evenly among the
            # visible columns so content is not squeezed into fixed widths.
            header = self.tree.header()
            header.setStretchLastSection(False)
            for section in range(1, 1 + len(columns)):
                header.setSectionResizeMode(section, QHeaderView.Stretch)
        else:
            self.tree.setColumnCount(1)
            self.tree.setHeaderLabels([""])
            self.tree.header().setStretchLastSection(True)

        self._layout.addWidget(self.tree)

        self._iid_map = {}    # explicit iid str -> QTreeWidgetItem
        self._bindings = {}   # normalized kind -> [handlers]
        self._tag_styles = {}  # tag name -> dict of style kwargs

        # selection-changed pseudo binding (ttk <<TreeviewSelect>>)
        self.tree.itemSelectionChanged.connect(self._on_selection_changed)

    # ------------------------------------------------------------------
    # Layout helpers
    # ------------------------------------------------------------------
    def add_toolbar(self, height=30):
        """Insert a toolbar strip above the tree (used by FlowWindow)."""
        bar = QFrame(self)
        bar.setObjectName("TreeToolbar")
        bar.setFixedHeight(height)
        self._layout.insertWidget(0, bar)
        return bar

    # ------------------------------------------------------------------
    # Bindings
    # ------------------------------------------------------------------
    def bind(self, key, handler, add=None):
        if key in ("<Button-1>",):
            kind = "click"
        elif key in ("<Double-1>", "<Double-Button-1>"):
            kind = "double"
        elif key in ("<Button-3>", "<Button-2>", "<Control-Button-1>"):
            kind = "right"
        elif key == "<<TreeviewSelect>>":
            kind = "select"
        else:
            return
        self._bindings.setdefault(kind, []).append(handler)

    def _emit(self, kind, x, y, gx, gy):
        ev = Event(x=x, y=y, x_root=gx, y_root=gy)
        for handler in self._bindings.get(kind, []):
            handler(ev)

    def _on_selection_changed(self):
        for handler in self._bindings.get("select", []):
            handler(Event())

    # ------------------------------------------------------------------
    # Identity helpers
    # ------------------------------------------------------------------
    def _ident(self, item):
        """Return the explicit iid string for an item, or the item itself."""
        iid = item.data(0, Qt.UserRole)
        return iid if iid is not None else item

    def _resolve(self, item_id):
        if item_id is None or item_id == "":
            return None
        if isinstance(item_id, QTreeWidgetItem):
            return item_id
        return self._iid_map.get(str(item_id))

    # ------------------------------------------------------------------
    # ttk.Treeview API
    # ------------------------------------------------------------------
    def heading(self, col_id, **kwargs):
        idx = self._col_index(col_id)
        if "text" in kwargs:
            self.tree.headerItem().setText(idx, kwargs["text"])

    def column(self, col_id, **kwargs):
        if self._show == "headings":
            # Column widths are managed globally: every visible column
            # shares the available width evenly (see __init__), so the
            # legacy per-column widths passed by callers are ignored.
            return None
        idx = self._col_index(col_id)
        width = kwargs.get("width")
        if width is None:
            return self.tree.columnWidth(idx)
        if width < 10:
            self.tree.header().setSectionResizeMode(idx, QHeaderView.ResizeToContents)
        else:
            self.tree.header().setSectionResizeMode(idx, QHeaderView.Interactive)
            self.tree.setColumnWidth(idx, int(width))
        return None

    def _col_index(self, col_id):
        if col_id == "#0":
            return 0
        if isinstance(col_id, str) and col_id.startswith("#"):
            return int(col_id[1:])
        try:
            return self._columns.index(col_id) + 1
        except ValueError:
            return 0

    def config(self, **kwargs):
        return None

    def insert(self, parent, index=END, text="", values=(), iid=None, open=True, tags=()):
        if parent == "" or parent is None:
            parent_item = None
        else:
            parent_item = self._resolve(parent)

        values = tuple(values)
        # make sure enough columns exist for the values
        needed = 1 + len(values)
        if needed > self.tree.columnCount():
            self.tree.setColumnCount(needed)
            if self._show == "tree":
                # tree mode only displays the tree column
                for c in range(1, needed):
                    self.tree.setColumnHidden(c, True)

        item = QTreeWidgetItem(parent_item)
        item.setText(0, str(text))
        for i, value in enumerate(values, start=1):
            item.setText(i, str(value))

        # apply tag styles
        for tag in tags or ():
            style = self._tag_styles.get(tag)
            if style:
                bg = style.get("background")
                fg = style.get("foreground")
                if bg:
                    for c in range(self.tree.columnCount()):
                        item.setBackground(c, QBrush(QColor(bg)))
                if fg:
                    for c in range(self.tree.columnCount()):
                        item.setForeground(c, QBrush(QColor(fg)))

        item.setExpanded(bool(open))

        if parent_item is None:
            if index == END or index >= self.tree.topLevelItemCount():
                self.tree.addTopLevelItem(item)
            else:
                self.tree.insertTopLevelItem(int(index), item)
        else:
            if index == END or index >= parent_item.childCount():
                parent_item.addChild(item)
            else:
                parent_item.insertChild(int(index), item)

        if iid is not None:
            iid = str(iid)
            item.setData(0, Qt.UserRole, iid)
            self._iid_map[iid] = item
            return iid
        return item

    def item(self, item_id, *props, **kw):
        if item_id == "" or item_id is None:
            item = None
        else:
            item = self._resolve(item_id)
        if kw:
            if item is None:
                return None
            if "text" in kw:
                item.setText(0, str(kw["text"]))
            if "values" in kw:
                for i, value in enumerate(kw["values"], start=1):
                    item.setText(i, str(value))
            if "open" in kw:
                item.setExpanded(bool(kw["open"]))
            return None
        if item is None:
            return {"text": "", "values": []}
        values = [item.text(i) for i in range(1, self.tree.columnCount())]
        if props:
            if props[0] == "text":
                return item.text(0)
            if props[0] == "values":
                return values
            if props[0] == "open":
                return item.isExpanded()
        return {"text": item.text(0), "values": values}

    def delete(self, item_id):
        ids = item_id if isinstance(item_id, (list, tuple)) else [item_id]
        for iid in ids:
            item = self._resolve(iid)
            if item is None:
                continue
            self._drop_recursive(item)
            index = self.tree.indexOfTopLevelItem(item)
            if index >= 0:
                self.tree.takeTopLevelItem(index)
            else:
                parent_item = item.parent()
                if parent_item is not None:
                    parent_item.removeChild(item)

    def _drop_recursive(self, item):
        for i in range(item.childCount()):
            self._drop_recursive(item.child(i))
        iid = item.data(0, Qt.UserRole)
        if iid is not None:
            self._iid_map.pop(iid, None)

    def get_children(self, item_id=""):
        if item_id == "" or item_id is None:
            return [self._ident(self.tree.topLevelItem(i))
                    for i in range(self.tree.topLevelItemCount())]
        item = self._resolve(item_id)
        if item is None:
            return []
        return [self._ident(item.child(i)) for i in range(item.childCount())]

    def parent(self, item_id):
        item = self._resolve(item_id)
        if item is None:
            return ""
        p = item.parent()
        if p is None:
            return ""
        return self._ident(p)

    def selection(self):
        return [self._ident(item) for item in self.tree.selectedItems()]

    def selection_set(self, item_id):
        item = self._resolve(item_id)
        if item is None:
            return
        self.tree.clearSelection()
        item.setSelected(True)
        self.tree.setCurrentItem(item)

    def selection_add(self, item_id):
        item = self._resolve(item_id)
        if item is not None:
            item.setSelected(True)

    def see(self, item_id):
        item = self._resolve(item_id)
        if item is not None:
            self.tree.scrollToItem(item)

    def identify_row(self, y):
        item = self.tree.itemAt(QPoint(0, int(y)))
        if item is None:
            return ""
        return self._ident(item)

    def identify_column(self, x):
        idx = self.tree.columnAt(int(x))
        return f"#{idx}" if idx >= 0 else "#0"

    def identify(self, region, x, y):
        # Event coordinates are viewport-relative; header clicks never reach
        # the viewport in Qt, so only 'cell' / 'nothing' are possible.
        item = self.tree.itemAt(QPoint(int(x), int(y)))
        if item is not None:
            return "cell"
        return "nothing"

    def tag_configure(self, tag, **kwargs):
        self._tag_styles[tag] = kwargs

    def focus(self, item_id=None):
        if item_id is not None:
            item = self._resolve(item_id)
            if item is not None:
                self.tree.setCurrentItem(item)
        self.tree.setFocus()

    # ------------------------------------------------------------------
    # Thread-safe deferred call (used from worker threads)
    # ------------------------------------------------------------------
    def after(self, ms, callback):
        if ms == 0:
            post(callback)
        else:
            QTimer.singleShot(ms, callback)


# ---------------------------------------------------------------------------
# Canvas — QPainter-based drawing widget with a tk.Canvas-like API subset
# ---------------------------------------------------------------------------

class _CanvasUi(QObject):
    call = pyqtSignal(object)


class Canvas(QWidget):
    """A QPainter canvas exposing the small tk.Canvas API the flow editor uses.

    Items are stored as dicts and redrawn in `paintEvent`. `after()` is
    thread-safe (queued signal), so worker threads can refresh the canvas.
    """

    def __init__(self, parent=None, bg="#fafafa", **kwargs):
        super().__init__(parent)
        self.setAttribute(Qt.WA_OpaquePaintEvent, True)
        self.setMinimumSize(100, 100)
        self._bg = QColor(bg)
        self._items = []
        self._bindings = {}
        self._ui = _CanvasUi()
        self._ui.call.connect(self._run_callback)
        self._cursor_map = {
            "crosshair": Qt.CrossCursor,
            "hand2": Qt.PointingHandCursor,
            "": Qt.ArrowCursor,
            "arrow": Qt.ArrowCursor,
        }

    # ------------------------------------------------------------------
    # Thread-safe deferred call
    # ------------------------------------------------------------------
    def after(self, ms, callback):
        if ms == 0:
            self._ui.call.emit(callback)
        else:
            QTimer.singleShot(ms, callback)

    def _run_callback(self, callback):
        callback()

    # ------------------------------------------------------------------
    # tk.Canvas-like metrics
    # ------------------------------------------------------------------
    def winfo_width(self):
        return self.width()

    def winfo_height(self):
        return self.height()

    def winfo_rootx(self):
        return self.mapToGlobal(QPoint(0, 0)).x()

    def winfo_rooty(self):
        return self.mapToGlobal(QPoint(0, 0)).y()

    def winfo_pointerx(self):
        return QCursor.pos().x()

    def winfo_pointery(self):
        return QCursor.pos().y()

    def update_idletasks(self):
        from PyQt5.QtWidgets import QApplication
        QApplication.processEvents()

    # ------------------------------------------------------------------
    # Event bindings
    # ------------------------------------------------------------------
    def bind(self, key, handler, add=None):
        self._bindings.setdefault(key, []).append(handler)

    def _dispatch(self, key, event):
        for handler in self._bindings.get(key, []):
            handler(event)

    # ------------------------------------------------------------------
    # Drawing API (tk.Canvas subset)
    # ------------------------------------------------------------------
    def delete(self, tag_or_id):
        if tag_or_id == "all":
            self._items.clear()

    def _add_item(self, item):
        item["id"] = len(self._items)
        self._items.append(item)
        return item["id"]

    def create_rectangle(self, x1, y1, x2, y2, **opts):
        return self._add_item({
            "type": "rect",
            "x1": x1, "y1": y1, "x2": x2, "y2": y2,
            "opts": opts,
        })

    def create_line(self, *points, **opts):
        pts = list(points)
        if len(pts) > 2 and isinstance(pts[0], (list, tuple)):
            pts = [coord for pt in pts for coord in pt]
        return self._add_item({
            "type": "line",
            "points": pts,
            "opts": opts,
        })

    def create_oval(self, x1, y1, x2, y2, **opts):
        return self._add_item({
            "type": "oval",
            "x1": x1, "y1": y1, "x2": x2, "y2": y2,
            "opts": opts,
        })

    def create_text(self, x, y, **opts):
        return self._add_item({
            "type": "text",
            "x": x, "y": y,
            "opts": opts,
        })

    def create_polygon(self, *points, **opts):
        pts = list(points)
        if len(pts) > 2 and isinstance(pts[0], (list, tuple)):
            pts = [coord for pt in pts for coord in pt]
        return self._add_item({
            "type": "polygon",
            "points": pts,
            "opts": opts,
        })

    def create_image(self, x, y, **opts):
        return self._add_item({
            "type": "image",
            "x": x, "y": y,
            "opts": opts,
        })

    # ------------------------------------------------------------------
    # Painting
    # ------------------------------------------------------------------
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.fillRect(self.rect(), self._bg)
        for item in self._items:
            self._paint_item(painter, item)
        painter.end()

    @staticmethod
    def _color(value):
        return QColor(value) if value else QColor(0, 0, 0, 0)

    def _pen(self, opts, default_color="#000000", default_width=1):
        outline = opts.get("outline")
        color = self._color(outline) if outline not in (None, "") else QColor(default_color)
        pen = QPen(color)
        pen.setWidth(int(opts.get("width", default_width)))
        dash = opts.get("dash")
        if dash:
            pen.setDashPattern([float(d) for d in dash])
        return pen

    def _font(self, opts, default_size=9):
        font_tuple = opts.get("font")
        size = default_size
        bold = False
        if isinstance(font_tuple, (tuple, list)) and len(font_tuple) >= 2:
            try:
                size = int(font_tuple[1])
            except (TypeError, ValueError):
                size = default_size
            bold = len(font_tuple) > 2 and font_tuple[2] == "bold"
        elif isinstance(font_tuple, QFont):
            return font_tuple
        font = QFont(self.font())
        font.setPointSize(max(6, size))
        font.setBold(bold)
        return font

    @staticmethod
    def _anchor_flags(anchor):
        flags = Qt.AlignLeft | Qt.AlignVCenter
        if anchor in ("center",):
            flags = Qt.AlignCenter
        elif anchor in ("n",):
            flags = Qt.AlignHCenter | Qt.AlignTop
        elif anchor in ("s",):
            flags = Qt.AlignHCenter | Qt.AlignBottom
        elif anchor in ("e",):
            flags = Qt.AlignRight | Qt.AlignVCenter
        elif anchor in ("w",):
            flags = Qt.AlignLeft | Qt.AlignVCenter
        elif anchor in ("nw",):
            flags = Qt.AlignLeft | Qt.AlignTop
        elif anchor in ("ne",):
            flags = Qt.AlignRight | Qt.AlignTop
        elif anchor in ("sw",):
            flags = Qt.AlignLeft | Qt.AlignBottom
        elif anchor in ("se",):
            flags = Qt.AlignRight | Qt.AlignBottom
        return flags

    def _paint_item(self, painter, item):
        opts = item["opts"]
        itype = item["type"]
        if itype == "rect":
            fill = opts.get("fill")
            painter.setPen(self._pen(opts, default_color="#000000"))
            painter.setBrush(self._color(fill) if fill not in (None, "") else Qt.NoBrush)
            painter.drawRect(QRectF(item["x1"], item["y1"],
                                    item["x2"] - item["x1"], item["y2"] - item["y1"]))
        elif itype == "line":
            fill = opts.get("fill", "#000000")
            painter.setPen(self._pen(opts, default_color=fill))
            painter.setBrush(Qt.NoBrush)
            points = item["points"]
            path = QPainterPath()
            path.moveTo(points[0], points[1])
            for i in range(2, len(points), 2):
                path.lineTo(points[i], points[i + 1])
            painter.drawPath(path)
        elif itype == "oval":
            fill = opts.get("fill")
            painter.setPen(self._pen(opts, default_color="#000000"))
            painter.setBrush(self._color(fill) if fill not in (None, "") else Qt.NoBrush)
            painter.drawEllipse(QRectF(item["x1"], item["y1"],
                                       item["x2"] - item["x1"], item["y2"] - item["y1"]))
        elif itype == "polygon":
            fill = opts.get("fill")
            poly = QPolygonF()
            pts = item["points"]
            for i in range(0, len(pts), 2):
                poly.append(QPointF(pts[i], pts[i + 1]))
            painter.setPen(self._pen(opts, default_color="#000000"))
            painter.setBrush(self._color(fill) if fill not in (None, "") else Qt.NoBrush)
            painter.drawPolygon(poly)
        elif itype == "text":
            text = opts.get("text", "")
            font = self._font(opts)
            painter.setFont(font)
            painter.setPen(self._color(opts.get("fill", "#000000")))
            fm = QFontMetrics(font)
            w = fm.horizontalAdvance(text)
            h = fm.height()
            x, y = item["x"], item["y"]
            flags = self._anchor_flags(opts.get("anchor"))
            if flags & Qt.AlignRight:
                x -= w
            elif not (flags & Qt.AlignHCenter):
                pass  # left-aligned
            else:
                x -= w / 2
            if flags & Qt.AlignBottom:
                y -= h
            elif not (flags & Qt.AlignVCenter):
                pass  # top-aligned
            else:
                y -= h / 2
            rect = QRectF(x, y, w, h)
            painter.drawText(rect, int(Qt.AlignLeft | Qt.AlignTop), text)
        elif itype == "image":
            image = opts.get("image")
            if image is not None:
                painter.drawImage(int(item["x"] - image.width() / 2),
                                  int(item["y"] - image.height() / 2), image)

    # ------------------------------------------------------------------
    # Mouse / wheel / key events
    # ------------------------------------------------------------------
    def _make_event(self, event):
        return Event(x=event.pos().x(), y=event.pos().y(),
                     x_root=event.globalPos().x(), y_root=event.globalPos().y())

    def mousePressEvent(self, event):
        ev = self._make_event(event)
        button = event.button()
        mods = event.modifiers()
        if button == Qt.LeftButton:
            if mods & Qt.ControlModifier:
                self._dispatch("<Control-Button-1>", ev)
            else:
                self._dispatch("<Button-1>", ev)
        elif button == Qt.MiddleButton:
            self._dispatch("<Button-2>", ev)
        elif button == Qt.RightButton:
            self._dispatch("<Button-3>", ev)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        ev = self._make_event(event)
        buttons = event.buttons()
        mods = event.modifiers()
        if buttons & Qt.LeftButton:
            if mods & Qt.ControlModifier:
                self._dispatch("<Control-B1-Motion>", ev)
            else:
                self._dispatch("<B1-Motion>", ev)
        elif buttons & Qt.MiddleButton:
            self._dispatch("<B2-Motion>", ev)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        ev = self._make_event(event)
        button = event.button()
        mods = event.modifiers()
        if button == Qt.LeftButton:
            if mods & Qt.ControlModifier:
                self._dispatch("<Control-ButtonRelease-1>", ev)
            else:
                self._dispatch("<ButtonRelease-1>", ev)
        elif button == Qt.MiddleButton:
            self._dispatch("<ButtonRelease-2>", ev)
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        angle = event.angleDelta().y()
        if angle > 0:
            ev = Event(num=4, delta=120)
        else:
            ev = Event(num=5, delta=-120)
        self._dispatch("<MouseWheel>", ev)
        if event.modifiers() & Qt.ShiftModifier:
            self._dispatch("<Shift-MouseWheel>", ev)
        self._dispatch("<Button-4>" if angle > 0 else "<Button-5>", ev)
        super().wheelEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete:
            self._dispatch("<Delete>", Event())
        elif event.key() == Qt.Key_Backspace:
            self._dispatch("<BackSpace>", Event())
        super().keyPressEvent(event)

    # ------------------------------------------------------------------
    # configure()
    # ------------------------------------------------------------------
    def configure(self, **kwargs):
        cursor = kwargs.get("cursor")
        if cursor is not None:
            self.setCursor(self._cursor_map.get(cursor, Qt.ArrowCursor))


def make_menu(parent=None):
    """Create a Metro-styled QMenu."""
    return QMenu(parent)
