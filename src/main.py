import threading
import uuid

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QPushButton,
    QTabWidget,
    QToolBox,
    QSplitter,
    QFrame,
)

from . import qui
from .qui import ask_yes_no
from .theme import style_role
from .his import HistoryWindow
from .req import RequestWindow
from .col import CollectionWindow, ProjectWindow, FolderWindow
from .env import EnvironmentWindow, VariableWindow
from .flow import FlowWindow, FlowEditor
from .help import HelpWindow
from .about import AboutWindow
from .tools.aes import AesGui
from .tools.b64 import Base64GUI
from .tools.md5 import MD5GUI
from .tools.pwd import GenPwdWindow
from .tools.timestamp import TimestampWindow
from .tools.regex import RegexWindow, CommonlyUsed
from .tools.RSA import RSAKeyFrame, RsaPublicKey, RSACheck, RSAEncrypt, RSADecrypt
from .tools.draft_paper import DraftPaper
from .dao.init import start_event as init_db, stop_event as close_db


# ---------------------------------------------------------------------------
# Main application window
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.root = self
        # tag_list[k] describes the tab at nbb index k.  It must be an instance
        # attribute: as a class attribute every window (and every re-created
        # window) shared one list of tags for a different set of tabs.
        self.tag_list = []
        self.setWindowTitle("HTTP Client")
        self.resize(1280, 720)

        # ---- tool registry ----
        self.tool_entries = [
            {"label": "AES",              "ui": AesGui,           "text": "AES"},
            {"label": "Base64",           "ui": Base64GUI,         "text": "Base64"},
            {"label": "DraftPaper",       "ui": DraftPaper,        "text": "DraftPaper"},
            {"label": "MD5",              "ui": MD5GUI,            "text": "MD5"},
            {"label": "Password",         "ui": GenPwdWindow,      "text": "Password"},
            {"label": "Regular Expression", "ui": RegexWindow,     "text": "Regular Expression"},
            {"label": "Regex Examples",   "ui": CommonlyUsed,      "text": "Common Regular Expressions"},
            {"label": "RSA Key",          "ui": RSAKeyFrame,       "text": "RSA Key"},
            {"label": "RSA Public Key",   "ui": RsaPublicKey,      "text": "RSA Public Key"},
            {"label": "RSA Check",        "ui": RSACheck,          "text": "RSA Check"},
            {"label": "RSA Encrypt",      "ui": RSAEncrypt,        "text": "RSA Encrypt"},
            {"label": "RSA Decrypt",      "ui": RSADecrypt,        "text": "RSA Decrypt"},
            {"label": "Timestamp",        "ui": TimestampWindow,   "text": "Timestamp"},
        ]

        central = QWidget(self)
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ---- top toolbar ----
        toolbar = QFrame(central)
        tl = QHBoxLayout(toolbar)
        tl.setContentsMargins(4, 2, 4, 2)
        tl.setSpacing(2)

        def tool_button(text, role, command):
            btn = QPushButton(text, toolbar)
            style_role(btn, role)
            btn.clicked.connect(command)
            tl.addWidget(btn)

        tool_button("📝", "link", lambda: self.new_request())
        tool_button("📁", "link", self.col_win_new_proj)
        tl.addWidget(qui.vline(toolbar))
        tool_button("📥", "link", self.col_win_open_proj)
        tool_button("📤", "link", self.col_win_export_proj)
        tl.addWidget(qui.vline(toolbar))
        tool_button("❓", "link", lambda: self.new_tab(HelpWindow, "Help"))
        tool_button("ℹ️", "link", lambda: self.new_tab(AboutWindow, "About"))
        tl.addStretch(1)
        root_layout.addWidget(toolbar)

        # ---- status bar ----
        self.statusBar().showMessage("Ready")

        # ---- main area ----
        main_frame = QWidget(central)
        mv = QVBoxLayout(main_frame)
        mv.setContentsMargins(0, 0, 0, 0)
        root_layout.addWidget(main_frame, 1)

        panel_window = QSplitter(Qt.Horizontal, main_frame)
        mv.addWidget(panel_window)

        # ==================================================================
        # Left sidebar — QToolBox with collapsible sections
        # ==================================================================
        toolbox = QToolBox(panel_window)
        toolbox.setObjectName("SidebarToolBox")
        toolbox.setMinimumWidth(240)

        # -- 1. Collections --
        col_page = QWidget(toolbox)
        col_lay = QVBoxLayout(col_page)
        col_lay.setContentsMargins(0, 0, 0, 0)
        self.col_win = CollectionWindow(col_page, **{"callback": self.collection})
        col_lay.addWidget(self.col_win.root)
        toolbox.addItem(col_page, "📁 Collections")

        # -- 2. History --
        his_page = QWidget(toolbox)
        his_lay = QVBoxLayout(his_page)
        his_lay.setContentsMargins(0, 0, 0, 0)
        self.history_window = HistoryWindow(his_page, self.history)
        his_lay.addWidget(self.history_window.root)
        toolbox.addItem(his_page, "📜 History")

        # -- 3. Environments --
        env_page = QWidget(toolbox)
        env_lay = QVBoxLayout(env_page)
        env_lay.setContentsMargins(0, 0, 0, 0)
        self.env_win = EnvironmentWindow(master=env_page, callback=self.environment)
        env_lay.addWidget(self.env_win.root)
        toolbox.addItem(env_page, "🌐 Environments")

        # -- 4. Flows --
        flow_page = QWidget(toolbox)
        flow_lay = QVBoxLayout(flow_page)
        flow_lay.setContentsMargins(0, 0, 0, 0)
        self.flow_win = FlowWindow(flow_page, callback=self.flow_callback)
        flow_lay.addWidget(self.flow_win.root)
        toolbox.addItem(flow_page, "🔄 Flows")

        # -- 5. Tools --
        tools_page = QWidget(toolbox)
        tools_lay = QVBoxLayout(tools_page)
        tools_lay.setContentsMargins(0, 0, 0, 0)
        self._build_tools_panel(tools_page)
        toolbox.addItem(tools_page, "🛠️ Tools")

        toolbox.setCurrentIndex(0)  # Collections open by default
        panel_window.addWidget(toolbox)

        # ==================================================================
        # Center — tabbed notebook
        # ==================================================================
        nbb = QTabWidget(panel_window)
        nbb.setTabsClosable(True)
        nbb.tabCloseRequested.connect(self.close_tab)
        nbb.body = nbb
        self.nbb = nbb

        panel_window.addWidget(nbb)
        panel_window.setStretchFactor(0, 2)
        panel_window.setStretchFactor(1, 10)
        panel_window.setSizes([260, 1000])

        self.on_start()

    # ------------------------------------------------------------------
    # Toolbar helpers (delegated after col_win is built)
    # ------------------------------------------------------------------
    def col_win_new_proj(self):
        self.col_win.new_proj()

    def col_win_open_proj(self):
        self.col_win.open_proj()

    def col_win_export_proj(self):
        self.col_win.export_proj()

    # ------------------------------------------------------------------
    # Tools panel helper
    # ------------------------------------------------------------------
    def _build_tools_panel(self, parent):
        """Populate the Tools collapsible section with a single-column list."""
        tools_inner = QWidget(parent)
        grid = QGridLayout(tools_inner)
        grid.setContentsMargins(4, 4, 4, 4)
        grid.setSpacing(4)

        row = 0
        for entry in self.tool_entries:
            btn = QPushButton(entry["label"], tools_inner)
            style_role(btn, "secondary")
            # clicked() emits clicked(bool checked); PyQt feeds that boolean
            # into the first parameter of the connected callable, so consume
            # it with a dedicated parameter instead of letting it clobber ui.
            btn.clicked.connect(
                lambda _checked=False, ui=entry["ui"], text=entry["text"]: self.new_tab(ui, text)
            )
            grid.addWidget(btn, row, 0)
            row += 1

        grid.setColumnStretch(0, 1)

        parent.layout().addWidget(tools_inner)

    # ------------------------------------------------------------------
    # Tab management
    # ------------------------------------------------------------------
    def new_request(self, data=None, **kwargs):
        frame = QWidget(self.nbb)
        req_win = RequestWindow(
            window=frame,
            get_script=self.col_win.get_script,
            env_variable=self.env_win.get_variable,
            glb_variable=self.env_win.get_globals,
            local_variable=self.col_win.get_variable,
            cache_history=self.history_window.on_cache,
            save_item=self.col_win.save_item,
            path=kwargs.get("path", "Name:"),
            # Bind the callback to this tab's frame.  The old code passed
            # self.request, which looked the tab up with currentIndex() — so a
            # request that finished (or was renamed) while another tab was open
            # renamed whatever tab happened to be in front.
            callback=lambda **cb_kwargs: self.request(frame, **cb_kwargs),
        )
        req_win.item_id = kwargs.get("item_id")
        # Keep the request window object alive (see new_tab).
        frame.instance = req_win
        name = "New Request"
        if data is not None:
            req_win.fill_blank(data)
            name = data.get("name", "New Request")
        self.nbb.addTab(frame, name)
        self.nbb.setCurrentWidget(frame)
        if data is None:
            self.tag_list.append(str(uuid.uuid1()))  # new request

    def on_start(self):
        init_db()
        t1 = threading.Thread(target=self.col_win.on_start, daemon=True)
        t2 = threading.Thread(target=self.env_win.on_start, daemon=True)
        t3 = threading.Thread(target=self.history_window.on_start, daemon=True)
        t4 = threading.Thread(target=self.flow_win.on_start, daemon=True)
        t1.start()
        t2.start()
        t3.start()
        t4.start()

    def write_to_disk(self):
        self.col_win.on_close()
        self.env_win.on_end()
        self.history_window.on_end()
        self.flow_win.on_end()

    def on_closing(self):
        # Stop every flow engine first: a run in progress keeps posting canvas
        # callbacks while the widgets are being torn down.
        for index in range(self.nbb.count()):
            editor = getattr(self.nbb.widget(index), "flow_editor", None)
            if editor is not None:
                editor.shutdown()
        self.write_to_disk()
        close_db()

    def closeEvent(self, event):
        self.on_closing()
        event.accept()

    def request(self, frame=None, **kwargs):
        """Retitle the request tab that `frame` belongs to.

        `frame` is the tab container the RequestWindow lives in; when it is
        omitted the active tab is used.
        """
        index = self.nbb.currentIndex() if frame is None else self.nbb.indexOf(frame)
        if index < 0:
            return
        name = kwargs.get("name")
        if name is not None:
            self.nbb.setTabText(index, name)
        item_id = kwargs.get("item_id")
        if item_id is not None and index < len(self.tag_list):
            self.tag_list[index] = f"col_{item_id}"

    def collection(self, **kwargs):
        if kwargs.get("action") == "rename":
            if f"col_{kwargs['item_id']}" in self.tag_list:
                self.nbb.setTabText(
                    self.tag_list.index(f'col_{kwargs.get("item_id")}'),
                    kwargs.get("name"),
                )
            return

        if f"col_{kwargs['item_id']}" in self.tag_list:
            self.nbb.setCurrentIndex(self.tag_list.index(f"col_{kwargs['item_id']}"))
            return

        if kwargs["tag"] == "project":
            frame = QWidget(self.nbb)
            proj_win = ProjectWindow(
                master=frame,
                item_id=kwargs["item_id"],
                callback=self.col_win.save_item,
                data=kwargs["data"],
            )
            frame.instance = proj_win  # keep the window object alive (see new_tab)
            self.nbb.addTab(frame, kwargs["data"]["name"])
            self.nbb.setCurrentWidget(frame)
        elif kwargs["tag"] == "folder":
            frame = QWidget(self.nbb)
            folder_win = FolderWindow(
                master=frame,
                item_id=kwargs["item_id"],
                callback=self.col_win.save_item,
                data=kwargs["data"],
                path=kwargs["path"],
            )
            frame.instance = folder_win  # keep the window object alive (see new_tab)
            self.nbb.addTab(frame, kwargs["data"]["name"])
            self.nbb.setCurrentWidget(frame)
        else:
            self.new_request(kwargs["data"], item_id=kwargs["item_id"], path=kwargs["path"])
        self.tag_list.append(f"col_{kwargs['item_id']}")

    def history(self, **kwargs):
        """History callback"""
        # renamed from `uuid` to avoid shadowing the uuid module imported above
        history_tag = str(kwargs["data"]["uuid"])  # DB ids are ints; keep tag_list as str
        if history_tag in self.tag_list:
            self.nbb.setCurrentIndex(self.tag_list.index(history_tag))
            return
        self.new_request(kwargs.get("data"))
        self.tag_list.append(history_tag)

    def environment(self, **kwargs):
        if kwargs.get("action") == "rename":
            if f'env_{kwargs.get("item_id")}' in self.tag_list:
                self.nbb.setTabText(
                    self.tag_list.index(f'env_{kwargs.get("item_id")}'),
                    kwargs.get("collection"),
                )
            return

        if f'env_{kwargs.get("item_id")}' in self.tag_list:
            self.nbb.setCurrentIndex(self.tag_list.index(f'env_{kwargs.get("item_id")}'))
            return

        frame = QWidget(self.nbb)
        var_win = VariableWindow(
            frame,
            item_id=kwargs.get("item_id"),
            collection=kwargs.get("collection"),
            data_id=kwargs.get("data_id"),
            set_variable=self.env_win.set_variable,
            set_active=self.env_win.set_active,
        )
        frame.instance = var_win  # keep the window object alive (see new_tab)
        self.tag_list.append(f'env_{kwargs.get("item_id")}')
        self.nbb.addTab(frame, kwargs.get("collection", "Var"))
        self.nbb.setCurrentWidget(frame)

    def flow_callback(self, **kwargs):
        """Handle flow panel events."""
        action = kwargs.get("action")
        if action == "open_flow":
            flow_id = kwargs.get("flow_id")
            tag = f"flow_{flow_id}"
            if tag in self.tag_list:
                self.nbb.setCurrentIndex(self.tag_list.index(tag))
                return
            frame = QWidget(self.nbb)
            editor = FlowEditor(
                master=frame,
                flow_id=flow_id,
                on_save=lambda: self.flow_win.refresh(),
            )
            # Same strong-reference requirement as new_tab, plus the attribute
            # close_tab() looks for to offer saving unsaved changes: without it
            # the editor could be collected (dropping its signal connections)
            # and closing the tab discarded the flow silently.
            frame.instance = editor
            frame.flow_editor = editor
            self.tag_list.append(tag)
            self.nbb.addTab(frame, editor.get_title())
            self.nbb.setCurrentWidget(frame)
            # Bind title updates
            editor.set_title_callback(lambda title: self._update_flow_tab_title(tag, title))

    def _update_flow_tab_title(self, tag, title):
        """Update the notebook tab title for a flow editor."""
        if tag in self.tag_list:
            try:
                index = self.tag_list.index(tag)
                self.nbb.setTabText(index, title)
            except Exception:
                pass

    def new_tab(self, ui, text):
        if text in self.tag_list:
            self.nbb.setCurrentIndex(self.tag_list.index(text))
            return
        frame = QWidget(self.nbb)
        fl = QVBoxLayout(frame)
        fl.setContentsMargins(0, 0, 0, 0)
        instance = ui(master=frame)
        # Keep a strong reference to the page object.  If it is left to the
        # garbage collector, PyQt silently drops every signal connection it
        # owns (e.g. buttons stop responding) while the widgets stay visible.
        frame.instance = instance
        root_widget = getattr(instance, "root", None)
        if root_widget is not None:
            fl.addWidget(root_widget, 1)
        self.tag_list.append(text)
        self.nbb.addTab(frame, text)
        self.nbb.setCurrentWidget(frame)

    def close_tab(self, index=None):
        try:
            current_index = self.nbb.currentIndex() if index is None else index
            tag = self.tag_list[current_index]
            # Check if it's a flow editor tab — prompt to save unsaved changes
            if isinstance(tag, str) and tag.startswith("flow_"):
                frame = self.nbb.widget(current_index)
                editor = getattr(frame, "flow_editor", None)
                if editor is not None:
                    if editor.is_dirty:
                        if ask_yes_no(self, "Unsaved Changes", "Save changes before closing?"):
                            editor.save()
                    # Cancel a run in progress before the canvas is destroyed.
                    editor.shutdown()
            self.tag_list.pop(current_index)
            widget = self.nbb.widget(current_index)
            self.nbb.removeTab(current_index)
            if widget is not None:
                widget.deleteLater()
        except (IndexError, KeyError):
            pass
