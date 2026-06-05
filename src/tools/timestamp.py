from tkinter import ttk, messagebox
import tkinter as tk
import datetime
import re
import time
import threading


def update_now(var, var2):
    while True:
        try:
            var.delete(0, tk.END)
            var.insert(0, str(round(time.time())))
            var2.delete(0, tk.END)
            var2.insert(0, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
            time.sleep(1)
        except RuntimeError:
            return


def datetime_to_timestamp(_input, output):
    date_str = _input.get()
    m = re.search(r"^\d{4}-\d{1,2}-\d{1,2}\s\d{1,2}:\d{1,2}:\d{1,2}$", date_str)
    if m is None:
        messagebox.showinfo("Warning", "Invalid datetime format!")
        return

    try:
        dt = datetime.datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
        timestamp = int(dt.timestamp())
        output.delete(0, tk.END)
        output.insert(0, str(timestamp))
    except ValueError:
        messagebox.showinfo("Warning", "Invalid datetime format!")


def timestamp_to_datetime(_input, output):
    timestamp = _input.get()
    if re.search(r"^\d+$", timestamp) is None:
        messagebox.showinfo("Warning", "Invalid timestamp!")
        return

    timestamp = int(timestamp)
    try:
        dt = datetime.datetime.fromtimestamp(timestamp)
        output.delete(0, tk.END)
        output.insert(0, str(dt))
    except ValueError:
        messagebox.showinfo("Warning", "Invalid timestamp!")


class TimestampWindow:
    """时间戳转换工具"""

    def __init__(self, master=None):
        self.root = ttk.Frame(master)
        self.root.pack(fill='both', expand=True, padx=5, pady=5)
        self.t2d()
        self.d2t()
        self.now()

    def t2d(self):
        # 时间戳转日期时间
        ttk.Label(self.root, text="Timestamp:").grid(row=0, column=0, sticky='w')
        timestamp_entry = ttk.Entry(self.root)
        timestamp_entry.grid(row=0, column=1)
        ttk.Label(self.root, text="Datetime:").grid(row=0, column=3, sticky='w')
        datetime_entry = ttk.Entry(self.root)
        btn = ttk.Button(
            self.root, text="->", width=4,
            command=lambda: timestamp_to_datetime(timestamp_entry, datetime_entry)
        )
        btn.grid(row=0, column=2)
        datetime_entry.grid(row=0, column=4)

    def d2t(self):
        # 日期时间转时间戳
        ttk.Label(self.root, text="DateTime:").grid(row=1, column=0, sticky='w')
        datetime_entry = ttk.Entry(self.root)
        datetime_entry.grid(row=1, column=1)
        ttk.Label(self.root, text="Timestamp:").grid(row=1, column=3, sticky='w')
        timestamp_entry = ttk.Entry(self.root)
        btn = ttk.Button(
            self.root, text="->", width=4,
            command=lambda: datetime_to_timestamp(datetime_entry, timestamp_entry)
        )
        btn.grid(row=1, column=2)
        timestamp_entry.grid(row=1, column=4)
        ttk.Label(self.root, text="(YYYY-MM-DD HH:MM:SS)").grid(row=2, column=1)

    def now(self):
        # 现在的时间
        ttk.Label(self.root, text="Now:").grid(row=3, column=0, sticky='w')
        timestamp_entry = ttk.Entry(self.root)
        timestamp_entry.grid(row=3, column=1)
        ttk.Button(
            self.root, text="Copy", width=5,
            command=lambda: self._copy_to_clipboard(timestamp_entry)
        ).grid(row=3, column=2)
        ttk.Label(self.root, text="Date:").grid(row=4, column=0, sticky='w')
        datetime_entry = ttk.Entry(self.root)
        datetime_entry.grid(row=4, column=1, pady=3)
        ttk.Button(
            self.root, text="Copy", width=5,
            command=lambda: self._copy_to_clipboard(datetime_entry)
        ).grid(row=4, column=2)
        thread = threading.Thread(target=update_now, args=(timestamp_entry, datetime_entry,))
        thread.start()

    def _copy_to_clipboard(self, entry):
        """复制 Entry 中的内容到剪贴板"""
        self.root.clipboard_clear()
        self.root.clipboard_append(entry.get())
