import threading
import tkinter as tk
import uuid
from tkinter import font as tkfont
from tkinter import ttk

from .his import HistoryWindow
from .req import RequestWindow
from .col import CollectionWindow, ProjectWindow, FolderWindow
from .env import EnvironmentWindow, VariableWindow
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


def _put_rect(image, color, x1, y1, x2, y2):
    image.put(color, to=(x1, y1, x2, y2))


def _put_scaled_rect(image, color, size, x1, y1, x2, y2, base=30):
    scale = size / base
    sx1 = max(0, min(size, round(x1 * scale)))
    sy1 = max(0, min(size, round(y1 * scale)))
    sx2 = max(0, min(size, round(x2 * scale)))
    sy2 = max(0, min(size, round(y2 * scale)))
    if sx2 > sx1 and sy2 > sy1:
        _put_rect(image, color, sx1, sy1, sx2, sy2)


def _create_folder_icon(size=30):
    image = tk.PhotoImage(width=size, height=size)
    _put_scaled_rect(image, "#d08a1d", size, 4, 11, 26, 24)
    _put_scaled_rect(image, "#f0b64a", size, 4, 13, 26, 24)
    _put_scaled_rect(image, "#ffd27a", size, 7, 8, 16, 13)
    _put_scaled_rect(image, "#ffe0a8", size, 6, 14, 24, 22)
    return image


def _create_env_icon(size=30):
    image = tk.PhotoImage(width=size, height=size)
    _put_scaled_rect(image, "#8b96a3", size, 4, 8, 26, 10)
    _put_scaled_rect(image, "#8b96a3", size, 4, 14, 26, 16)
    _put_scaled_rect(image, "#8b96a3", size, 4, 20, 26, 22)
    _put_scaled_rect(image, "#3f83f8", size, 8, 5, 13, 13)
    _put_scaled_rect(image, "#f97316", size, 16, 11, 21, 19)
    _put_scaled_rect(image, "#10b981", size, 11, 17, 16, 25)
    return image


def _create_history_icon(size=30):
    image = tk.PhotoImage(width=size, height=size)
    _put_scaled_rect(image, "#7ba8ff", size, 11, 4, 19, 6)
    _put_scaled_rect(image, "#7ba8ff", size, 7, 6, 23, 8)
    _put_scaled_rect(image, "#7ba8ff", size, 5, 8, 25, 10)
    _put_scaled_rect(image, "#7ba8ff", size, 4, 10, 26, 20)
    _put_scaled_rect(image, "#7ba8ff", size, 5, 20, 25, 22)
    _put_scaled_rect(image, "#7ba8ff", size, 7, 22, 23, 24)
    _put_scaled_rect(image, "#7ba8ff", size, 11, 24, 19, 26)
    _put_scaled_rect(image, "#ffffff", size, 8, 10, 22, 20)
    _put_scaled_rect(image, "#ffffff", size, 9, 8, 21, 22)
    _put_scaled_rect(image, "#315ea8", size, 14, 10, 16, 16)
    _put_scaled_rect(image, "#315ea8", size, 15, 14, 21, 16)
    return image


def _create_tool_icon(size=30):
    image = tk.PhotoImage(width=size, height=size)
    _put_scaled_rect(image, "#475569", size, 6, 8, 11, 24)
    _put_scaled_rect(image, "#94a3b8", size, 9, 6, 15, 12)
    _put_scaled_rect(image, "#94a3b8", size, 9, 20, 15, 26)
    _put_scaled_rect(image, "#475569", size, 14, 10, 24, 20)
    _put_scaled_rect(image, "#cbd5e1", size, 22, 8, 26, 12)
    _put_scaled_rect(image, "#cbd5e1", size, 22, 18, 26, 22)
    _put_scaled_rect(image, "#cbd5e1", size, 16, 6, 20, 10)
    _put_scaled_rect(image, "#cbd5e1", size, 16, 20, 20, 24)
    return image


class CanvasSidebarTabs:
    NAV_WIDTH = 44
    BUTTON_SIZE = 28
    BUTTON_GAP = 20
    PADDING_Y = 12
    NAV_BG = "#eef2f6"
    ACTIVE_BG = "#ffffff"
    INACTIVE_BG = "#dde5ec"
    ACTIVE_FG = "#1f2933"
    INACTIVE_FG = "#52606d"
    BORDER_COLOR = "#c8d0d8"

    def __init__(self, canvas_master, body_master):
        self.body = ttk.Frame(body_master)
        self._tabs = []
        self._current_index = None
        self._regions = []

        self.nav_canvas = tk.Canvas(
            canvas_master,
            width=self.NAV_WIDTH,
            background=self.NAV_BG,
            borderwidth=0,
            highlightthickness=0,
        )
        self.nav_canvas.pack(fill=tk.Y, expand=False)

        self.nav_canvas.bind("<Configure>", self._on_configure)
        self.nav_canvas.bind("<Button-1>", self._on_click)
        self._redraw()

    def add(self, child, text="", image=None):
        self._tabs.append({"frame": child, "text": text, "image": image})
        if self._current_index is None:
            self.select(0)
            return
        self._redraw()

    def select(self, tab_id=None):
        if tab_id is None:
            if self._current_index is None:
                return ""
            return self._tabs[self._current_index]["frame"]

        index = self._resolve_index(tab_id)
        if self._current_index == index:
            self._redraw()
            return self._tabs[index]["frame"]

        if self._current_index is not None and self._tabs:
            self._tabs[self._current_index]["frame"].pack_forget()

        frame = self._tabs[index]["frame"]
        frame.pack(fill=tk.BOTH, expand=True)
        self._current_index = index
        self._redraw()
        return frame

    def index(self, tab_id):
        return self._resolve_index(tab_id)

    def _resolve_index(self, tab_id):
        if tab_id == "current":
            if self._current_index is None:
                raise tk.TclError("No current tab")
            return self._current_index

        if isinstance(tab_id, int):
            if 0 <= tab_id < len(self._tabs):
                return tab_id
            raise tk.TclError("Tab index out of range")

        for index, tab in enumerate(self._tabs):
            if tab["frame"] is tab_id:
                return index

        raise tk.TclError("Tab not found")

    def _redraw(self):
        self.nav_canvas.delete("all")
        self._regions.clear()
        height = max(self.nav_canvas.winfo_height(), 1)
        self.nav_canvas.create_rectangle(0, 0, self.NAV_WIDTH, height, fill=self.NAV_BG, outline=self.NAV_BG)

        x1 = (self.NAV_WIDTH - self.BUTTON_SIZE) / 2
        x2 = x1 + self.BUTTON_SIZE
        y = self.PADDING_Y
        for index, tab in enumerate(self._tabs):
            y1 = y
            y2 = y1 + self.BUTTON_SIZE
            selected = index == self._current_index
            fill = self.ACTIVE_BG if selected else self.INACTIVE_BG
            self.nav_canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline=self.BORDER_COLOR, width=1)
            if tab["image"] is not None:
                self.nav_canvas.create_image((x1 + x2) / 2, (y1 + y2) / 2, image=tab["image"])
            self._regions.append({"index": index, "rect": (x1, y1, x2, y2)})
            y = y2 + self.BUTTON_GAP

    def _inside(self, x, y, rect):
        x1, y1, x2, y2 = rect
        return x1 <= x <= x2 and y1 <= y <= y2

    def _on_click(self, event):
        for region in self._regions:
            if self._inside(event.x, event.y, region["rect"]):
                self.select(region["index"])
                return

    def _on_configure(self, _event):
        self._redraw()


class ToolListFrame(ttk.Frame):
    def __init__(self, master, tools, open_tool):
        super().__init__(master)
        self._tools = tools
        self._open_tool = open_tool

        header = ttk.Frame(self)
        ttk.Label(header, text="工具列表").pack(side=tk.LEFT)
        ttk.Button(header, text="打开", command=self.open_selected).pack(side=tk.RIGHT)
        header.pack(fill=tk.X, padx=8, pady=(8, 4))

        self.tool_list = tk.Listbox(self, activestyle="none")
        self.tool_list.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))
        self.tool_list.bind("<Double-Button-1>", self.open_selected)
        self.tool_list.bind("<Return>", self.open_selected)

        for item in tools:
            self.tool_list.insert(tk.END, item["label"])

        if tools:
            self.tool_list.selection_set(0)

    def open_selected(self, _event=None):
        selection = self.tool_list.curselection()
        if not selection:
            return
        tool = self._tools[selection[0]]
        self._open_tool(tool["ui"], tool["text"])


class CanvasNotebook(ttk.Frame):
    TAB_HEIGHT = 36
    TAB_GAP = 6
    TAB_PADDING_X = 10
    TAB_PADDING_Y = 4
    TAB_NAME_LIMIT = 10
    CLOSE_BOX_SIZE = 14
    CLOSE_GAP = 8
    BAR_PADDING = 8
    BUTTON_WIDTH = 24
    BUTTON_GAP = 6
    BACKGROUND = "#f3f4f6"
    TAB_ACTIVE_BG = "#ffffff"
    TAB_INACTIVE_BG = "#e7ebef"
    TAB_ACTIVE_FG = "#20262e"
    TAB_INACTIVE_FG = "#4f5b67"
    BORDER_COLOR = "#c8d0d8"
    BUTTON_BG = "#ffffff"
    BUTTON_DISABLED_BG = "#eef1f4"
    BUTTON_FG = "#20262e"
    BUTTON_DISABLED_FG = "#9aa5b1"

    def __init__(self, master, add_command=None, close_command=None):
        super().__init__(master)
        self.add_command = add_command
        self.close_command = close_command
        self.body = ttk.Frame(self)
        self._tabs = []
        self._current_index = None
        self._offset = 0
        self._tab_regions = []
        self._control_regions = {}
        self._tab_font = tkfont.nametofont("TkDefaultFont")
        self._tab_width = (
            self._tab_font.measure("0" * self.TAB_NAME_LIMIT)
            + (self.TAB_PADDING_X * 2)
            + self.CLOSE_BOX_SIZE
            + self.CLOSE_GAP
        )

        self.canvas = tk.Canvas(
            self,
            height=self.TAB_HEIGHT,
            background=self.BACKGROUND,
            borderwidth=0,
            highlightthickness=0,
        )
        self.canvas.pack(side=tk.TOP, fill=tk.X)
        ttk.Separator(self, orient=tk.HORIZONTAL).pack(side=tk.TOP, fill=tk.X)
        self.body.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.canvas.bind("<Configure>", self._on_configure)
        self.canvas.bind("<Button-1>", self._on_click)
        self._redraw()

    def add(self, child, text=""):
        self._tabs.append({"frame": child, "text": text})
        if self._current_index is None:
            self.select(0)
            return
        self._ensure_visible(len(self._tabs) - 1)
        self._redraw()

    def select(self, tab_id=None):
        if tab_id is None:
            if self._current_index is None:
                return ""
            return self._tabs[self._current_index]["frame"]

        index = self._resolve_index(tab_id)
        if self._current_index == index:
            self._ensure_visible(index)
            self._redraw()
            return self._tabs[index]["frame"]

        if self._current_index is not None and self._tabs:
            self._tabs[self._current_index]["frame"].pack_forget()

        frame = self._tabs[index]["frame"]
        frame.pack(fill=tk.BOTH, expand=True)
        self._current_index = index
        self._ensure_visible(index)
        self._redraw()
        return frame

    def tab(self, tab_id, **kwargs):
        index = self._resolve_index(tab_id)
        if "text" in kwargs:
            self._tabs[index]["text"] = kwargs["text"]
            self._redraw()
        return {"text": self._tabs[index]["text"]}

    def forget(self, tab_id):
        index = self._resolve_index(tab_id)
        current_frame = self._tabs[index]["frame"]
        if current_frame.winfo_exists():
            current_frame.pack_forget()
            current_frame.destroy()
        self._tabs.pop(index)

        if not self._tabs:
            self._current_index = None
            self._offset = 0
            self._redraw()
            return

        if self._current_index is not None:
            if index < self._current_index:
                self._current_index -= 1
            elif index == self._current_index:
                self._current_index = None
                self.select(min(index, len(self._tabs) - 1))
                return

        self._clamp_offset()
        self._redraw()

    def index(self, tab_id):
        if tab_id == "end":
            return len(self._tabs)
        return self._resolve_index(tab_id)

    def previous_tab(self):
        if len(self._tabs) <= 1:
            return
        self.select((self.index("current") - 1) % len(self._tabs))

    def next_tab(self):
        if len(self._tabs) <= 1:
            return
        self.select((self.index("current") + 1) % len(self._tabs))

    def _resolve_index(self, tab_id):
        if tab_id == "current":
            if self._current_index is None:
                raise tk.TclError("No current tab")
            return self._current_index

        if isinstance(tab_id, int):
            if 0 <= tab_id < len(self._tabs):
                return tab_id
            raise tk.TclError("Tab index out of range")

        for index, tab in enumerate(self._tabs):
            if tab["frame"] is tab_id:
                return index

        raise tk.TclError("Tab not found")

    def _truncate_text(self, text, max_width):
        if len(text) > self.TAB_NAME_LIMIT:
            text = f"{text[:self.TAB_NAME_LIMIT - 3]}..."
        if self._tab_font.measure(text) <= max_width:
            return text

        suffix = "..."
        available = max(max_width - self._tab_font.measure(suffix), 0)
        while text and self._tab_font.measure(text) > available:
            text = text[:-1]
        return f"{text}{suffix}" if text else suffix

    def _control_area_width(self):
        return (self.BUTTON_WIDTH * 3) + (self.BUTTON_GAP * 2) + self.BAR_PADDING

    def _visible_capacity(self):
        width = max(self.canvas.winfo_width(), 1)
        available = max(width - self._control_area_width() - (self.BAR_PADDING * 2), 0)
        return max(1, available // (self._tab_width + self.TAB_GAP))

    def _clamp_offset(self):
        max_offset = max(len(self._tabs) - self._visible_capacity(), 0)
        self._offset = max(0, min(self._offset, max_offset))

    def _ensure_visible(self, index):
        capacity = self._visible_capacity()
        if index < self._offset:
            self._offset = index
        elif index >= self._offset + capacity:
            self._offset = index - capacity + 1
        self._clamp_offset()

    def _draw_button(self, x1, y1, x2, y2, label, enabled=True):
        fill = self.BUTTON_BG if enabled else self.BUTTON_DISABLED_BG
        fg = self.BUTTON_FG if enabled else self.BUTTON_DISABLED_FG
        self.canvas.create_rectangle(x1, y1, x2, y2, fill=fill, outline=self.BORDER_COLOR, width=1)
        self.canvas.create_text((x1 + x2) / 2, (y1 + y2) / 2, text=label, fill=fg, font=self._tab_font)

    def _redraw(self):
        self.canvas.delete("all")
        self._tab_regions.clear()
        self._control_regions.clear()

        width = max(self.canvas.winfo_width(), 1)
        self.canvas.create_rectangle(0, 0, width, self.TAB_HEIGHT, fill=self.BACKGROUND, outline=self.BACKGROUND)

        button_top = self.TAB_PADDING_Y
        button_bottom = self.TAB_HEIGHT - self.TAB_PADDING_Y
        control_x = width - self.BAR_PADDING - ((self.BUTTON_WIDTH * 3) + (self.BUTTON_GAP * 2))
        buttons = [
            ("previous", "<", len(self._tabs) > 1),
            ("next", ">", len(self._tabs) > 1),
            ("add", "+", True),
        ]

        for action, label, enabled in buttons:
            x1 = control_x
            x2 = x1 + self.BUTTON_WIDTH
            self._draw_button(x1, button_top, x2, button_bottom, label, enabled=enabled)
            self._control_regions[action] = (x1, button_top, x2, button_bottom, enabled)
            control_x = x2 + self.BUTTON_GAP

        tab_area_right = width - self._control_area_width()
        self._clamp_offset()

        tab_x = self.BAR_PADDING
        tab_y1 = self.TAB_PADDING_Y
        tab_y2 = self.TAB_HEIGHT - self.TAB_PADDING_Y
        visible_tabs = self._tabs[self._offset : self._offset + self._visible_capacity()]
        for index, tab in enumerate(visible_tabs, start=self._offset):
            x1 = tab_x
            x2 = x1 + self._tab_width
            if x2 > tab_area_right:
                break

            selected = index == self._current_index
            fill = self.TAB_ACTIVE_BG if selected else self.TAB_INACTIVE_BG
            fg = self.TAB_ACTIVE_FG if selected else self.TAB_INACTIVE_FG
            self.canvas.create_rectangle(x1, tab_y1, x2, tab_y2, fill=fill, outline=self.BORDER_COLOR, width=1)

            close_x2 = x2 - self.TAB_PADDING_X
            close_x1 = close_x2 - self.CLOSE_BOX_SIZE
            close_y1 = (self.TAB_HEIGHT - self.CLOSE_BOX_SIZE) / 2
            close_y2 = close_y1 + self.CLOSE_BOX_SIZE
            text_x = x1 + self.TAB_PADDING_X
            text_max_width = max(close_x1 - text_x - self.CLOSE_GAP, 0)
            text = self._truncate_text(tab["text"], text_max_width)
            self.canvas.create_text(
                text_x,
                self.TAB_HEIGHT / 2,
                anchor="w",
                fill=fg,
                font=self._tab_font,
                text=text,
            )

            self.canvas.create_rectangle(close_x1, close_y1, close_x2, close_y2, fill=fill, outline=self.BORDER_COLOR, width=1)
            self.canvas.create_line(close_x1 + 4, close_y1 + 4, close_x2 - 4, close_y2 - 4, fill=fg, width=1)
            self.canvas.create_line(close_x1 + 4, close_y2 - 4, close_x2 - 4, close_y1 + 4, fill=fg, width=1)

            self._tab_regions.append(
                {
                    "index": index,
                    "tab_rect": (x1, tab_y1, x2, tab_y2),
                    "close_rect": (close_x1, close_y1, close_x2, close_y2),
                }
            )
            tab_x = x2 + self.TAB_GAP

    def _inside(self, x, y, rect):
        x1, y1, x2, y2 = rect
        return x1 <= x <= x2 and y1 <= y <= y2

    def _on_click(self, event):
        for action, region in self._control_regions.items():
            x1, y1, x2, y2, enabled = region
            if enabled and self._inside(event.x, event.y, (x1, y1, x2, y2)):
                if action == "add" and self.add_command is not None:
                    self.add_command()
                elif action == "previous":
                    self.previous_tab()
                elif action == "next":
                    self.next_tab()
                return

        for region in self._tab_regions:
            if self._inside(event.x, event.y, region["close_rect"]):
                if self.close_command is not None:
                    self.close_command(region["index"])
                else:
                    self.forget(region["index"])
                return

            if self._inside(event.x, event.y, region["tab_rect"]):
                self.select(region["index"])
                return

    def _on_configure(self, _event):
        self._redraw()


class MainWindow:
    tag_list = []  # List of enabled labels

    def __init__(self):
        self.root = tk.Tk()
        # Create main window
        self.root.title("HTTP Client")
        self.root.geometry("1280x720")

        self.tool_entries = [
            {"label": "AES", "ui": AesGui, "text": "AES"},
            {"label": "Base64", "ui": Base64GUI, "text": "Base64"},
            {"label": "DraftPaper", "ui": DraftPaper, "text": "DraftPaper"},
            {"label": "MD5", "ui": MD5GUI, "text": "MD5"},
            {"label": "Password", "ui": GenPwdWindow, "text": "Password"},
            {"label": "Regular Expression", "ui": RegexWindow, "text": "Regular Expression "},
            {"label": "Regular Expression Example", "ui": CommonlyUsed, "text": "Common Regular Expressions"},
            {"label": "RSA Key", "ui": RSAKeyFrame, "text": "RSA Key"},
            {"label": "RSA Public Key", "ui": RsaPublicKey, "text": "RSA Public Key"},
            {"label": "RSA Check", "ui": RSACheck, "text": "RSA Check"},
            {"label": "RSA Encrypt", "ui": RSAEncrypt, "text": "RSA Encrypt"},
            {"label": "RSA Decrypt", "ui": RSADecrypt, "text": "RSA Decrypt"},
            {"label": "Timestamp", "ui": TimestampWindow, "text": "Timestamp"},
        ]

        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True)
        sidebar_frame = ttk.Frame(main_frame)
        sidebar_frame.pack(side=tk.LEFT, fill=tk.Y)
        ttk.Separator(main_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y)
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        panel_window = ttk.PanedWindow(content_frame, orient="horizontal")
        self.sidebar_icons = {
            "col": _create_folder_icon(size=28),
            "env": _create_env_icon(size=28),
            "his": _create_history_icon(size=28),
            "tool": _create_tool_icon(size=28),
        }
        nba = CanvasSidebarTabs(sidebar_frame, panel_window)
        col_top = ttk.Frame(nba.body)
        self.col_win = CollectionWindow(col_top, **{"callback": self.collection})
        nba.add(col_top, text="Col", image=self.sidebar_icons["col"])
        self.env_win = EnvironmentWindow(master=nba.body, callback=self.environment)
        nba.add(self.env_win.root, text="Env", image=self.sidebar_icons["env"])
        history_top = ttk.Frame(nba.body)
        self.history_window = HistoryWindow(history_top, self.history)
        nba.add(history_top, text="His", image=self.sidebar_icons["his"])
        tool_top = ToolListFrame(nba.body, self.tool_entries, self.new_tab)
        nba.add(tool_top, text="工具", image=self.sidebar_icons["tool"])
        panel_window.add(nba.body, weight=1)
        nbb = CanvasNotebook(panel_window, add_command=self.new_request, close_command=self.close_tab)
        self.nbb = nbb
        panel_window.add(nbb, weight=10)
        panel_window.pack(fill='both', expand=True)

        menu = tk.Menu(self.root)
        file_menu = tk.Menu(menu, tearoff=False)
        file_menu.add_command(label="New request", command=self.new_request)
        file_menu.add_command(label="New collection", command=self.col_win.new_proj)
        file_menu.add_command(label="Import", command=self.col_win.open_proj)
        file_menu.add_command(label="Export", command=self.col_win.export_proj)
        file_menu.add_command(label="Exit", command=self.on_closing)
        menu.add_cascade(label="File", menu=file_menu)
        help_menu = tk.Menu(menu, tearoff=False)
        help_menu.add_command(label="Help", command=lambda: self.new_tab(HelpWindow, "Help"))
        help_menu.add_command(label="About", command=lambda: self.new_tab(AboutWindow, "About"))
        menu.add_cascade(label="Help", menu=help_menu)
        self.root.config(menu=menu)

        self.on_start()

    def new_request(self, data=None, **kwargs):
        tl = ttk.Frame(self.nbb.body)
        req_win = RequestWindow(
            window=tl,
            get_script=self.col_win.get_script,
            env_variable=self.env_win.get_variable,
            glb_variable=self.env_win.get_globals,
            local_variable=self.col_win.get_variable,
            cache_history=self.history_window.on_cache,
            save_item=self.col_win.save_item,
            path=kwargs.get('path', "Name:"),
            callback=self.request,
        )
        req_win.item_id = kwargs.get("item_id")
        name = "New Request"
        if data is not None:
            req_win.fill_blank(data)
            name = data.get("name", "New Request")
        self.nbb.add(tl, text=name)
        self.nbb.select(tl)
        if data is None:
            self.tag_list.append(str(uuid.uuid1()))  # new request

    def on_start(self):
        init_db()
        t1 = threading.Thread(target=self.col_win.on_start)
        t2 = threading.Thread(target=self.env_win.on_start)
        t3 = threading.Thread(target=self.history_window.on_start)
        t1.start()
        t2.start()
        t3.start()

    def write_to_disk(self):
        self.col_win.on_close()
        self.env_win.on_end()
        self.history_window.on_end()

    def on_closing(self):
        close_db()
        self.root.destroy()

    def request(self, **kwargs):
        name = kwargs.get('name')
        if name is not None:
            self.nbb.tab(self.nbb.index("current"), text=name)
        item_id = kwargs.get('item_id')
        if item_id is not None:
            index = self.nbb.index("current")
            self.tag_list[index] = f"col_{kwargs['item_id']}"

    def collection(self, **kwargs):
        if kwargs.get('action') == 'rename':
            if f"col_{kwargs['item_id']}" in self.tag_list:
                self.nbb.tab(self.tag_list.index(f'col_{kwargs.get("item_id")}'), text=kwargs.get('name'))
            return

        if f"col_{kwargs['item_id']}" in self.tag_list:
            self.nbb.select(self.tag_list.index(f"col_{kwargs['item_id']}"))
            return

        if kwargs["tag"] == "project":
            frame = ttk.Frame(self.nbb.body)
            ProjectWindow(
                master=frame,
                item_id=kwargs["item_id"],
                callback=self.col_win.save_item,
                data=kwargs["data"],
            )
            self.nbb.add(frame, text=kwargs["data"]['name'])
            self.nbb.select(frame)
        elif kwargs["tag"] == "folder":
            frame = ttk.Frame(self.nbb.body)
            FolderWindow(
                master=frame,
                item_id=kwargs["item_id"],
                callback=self.col_win.save_item,
                data=kwargs["data"],
                path=kwargs['path'],
            )
            self.nbb.add(frame, text=kwargs["data"]['name'])
            self.nbb.select(frame)
        else:
            self.new_request(kwargs["data"], item_id=kwargs["item_id"], path=kwargs['path'], )
        self.tag_list.append(f"col_{kwargs['item_id']}")

    def history(self, **kwargs):
        """History callback"""
        if kwargs['data']['uuid'] in self.tag_list:
            self.nbb.select(self.tag_list.index(kwargs['data']['uuid']))
            return
        self.new_request(kwargs.get("data"))
        self.tag_list.append(kwargs['data']['uuid'])

    def environment(self, **kwargs):
        if kwargs.get('action') == 'rename':
            if f'env_{kwargs.get("item_id")}' in self.tag_list:
                self.nbb.tab(self.tag_list.index(f'env_{kwargs.get("item_id")}'), text=kwargs.get('collection'))
            return

        if f'env_{kwargs.get("item_id")}' in self.tag_list:
            self.nbb.select(self.tag_list.index(f'env_{kwargs.get("item_id")}'))
            return

        frame = ttk.Frame(self.nbb.body)
        VariableWindow(
            frame,
            item_id=kwargs.get('item_id'),
            collection=kwargs.get("collection"),
            data_id=kwargs.get("data_id"),
            set_variable=self.env_win.set_variable,
            set_active=self.env_win.set_active,
        )
        self.tag_list.append(f'env_{kwargs.get("item_id")}')
        self.nbb.add(frame, text=kwargs.get("collection", "Var"))
        self.nbb.select(frame)

    def previous_tab(self):
        try:
            # 获取当前选中的选项卡的索引
            current_tab_index = self.nbb.index("current")
            # 计算上一个选项卡的索引
            previous_tab_index = (current_tab_index - 1) % self.nbb.index("end")
            # 选中上一个选项卡
            self.nbb.select(previous_tab_index)
        except tk.TclError:
            pass

    def next_tab(self):
        try:
            current_tab_index = self.nbb.index("current")
            next_tab_index = (current_tab_index + 1) % self.nbb.index("end")
            self.nbb.select(next_tab_index)
        except tk.TclError:
            pass

    def new_tab(self, ui, text):
        if text in self.tag_list:
            self.nbb.select(self.tag_list.index(text))
            return
        frame = ttk.Frame(self.nbb.body)
        ui(master=frame)
        self.tag_list.append(text)
        self.nbb.add(frame, text=text)
        self.nbb.select(frame)

    def close_tab(self, index=None):
        try:
            current_index = self.nbb.index('current') if index is None else index
            self.tag_list.pop(current_index)
            self.nbb.forget(current_index)
        except (IndexError, tk.TclError):
            pass
