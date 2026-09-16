import datetime
import re
import time

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import (
    QWidget,
    QGridLayout,
    QLabel,
    QLineEdit,
    QPushButton,
)

from ..qui import show_info
from ..theme import style_role


def datetime_to_timestamp(_input, output, parent=None):
    date_str = _input.text()
    m = re.search(r"^\d{4}-\d{1,2}-\d{1,2}\s\d{1,2}:\d{1,2}:\d{1,2}$", date_str)
    if m is None:
        show_info(parent, "Warning", "Invalid datetime format!")
        return

    try:
        dt = datetime.datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
        timestamp = int(dt.timestamp())
        output.setText(str(timestamp))
    except (ValueError, OSError, OverflowError):
        show_info(parent, "Warning", "Invalid datetime format!")


def timestamp_to_datetime(_input, output, parent=None):
    timestamp = _input.text()
    if re.search(r"^-?\d+$", timestamp) is None:
        show_info(parent, "Warning", "Invalid timestamp!")
        return

    timestamp = int(timestamp)
    try:
        dt = datetime.datetime.fromtimestamp(timestamp)
    except (ValueError, OSError, OverflowError):
        # A value past the platform time_t limit (a millisecond/nanosecond
        # epoch, say) reaches C and comes back as OSError/OverflowError, not
        # ValueError — the ValueError-only handler let it escape the slot.
        show_info(parent, "Warning", "Invalid timestamp!")
        return
    output.setText(str(dt))


class TimestampWindow:
    """时间戳转换工具"""

    def __init__(self, master=None):
        self.root = QWidget(master)
        grid = QGridLayout(self.root)
        grid.setContentsMargins(8, 8, 8, 8)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)

        # 时间戳转日期时间
        grid.addWidget(QLabel("Timestamp:", self.root), 0, 0)
        self.timestamp_entry = QLineEdit(self.root)
        grid.addWidget(self.timestamp_entry, 0, 1)
        btn1 = QPushButton("->", self.root)
        btn1.setFixedWidth(40)
        style_role(btn1, "primary")
        btn1.clicked.connect(
            lambda: timestamp_to_datetime(self.timestamp_entry, self.datetime_entry, self.root)
        )
        grid.addWidget(btn1, 0, 2)
        grid.addWidget(QLabel("Datetime:", self.root), 0, 3)
        self.datetime_entry = QLineEdit(self.root)
        grid.addWidget(self.datetime_entry, 0, 4)

        # 日期时间转时间戳
        grid.addWidget(QLabel("DateTime:", self.root), 1, 0)
        self.datetime_input = QLineEdit(self.root)
        grid.addWidget(self.datetime_input, 1, 1)
        btn2 = QPushButton("->", self.root)
        btn2.setFixedWidth(40)
        style_role(btn2, "primary")
        btn2.clicked.connect(
            lambda: datetime_to_timestamp(self.datetime_input, self.timestamp_input, self.root)
        )
        grid.addWidget(btn2, 1, 2)
        grid.addWidget(QLabel("Timestamp:", self.root), 1, 3)
        self.timestamp_input = QLineEdit(self.root)
        grid.addWidget(self.timestamp_input, 1, 4)
        grid.addWidget(QLabel("(YYYY-MM-DD HH:MM:SS)", self.root), 2, 1)

        # 现在的时间
        grid.addWidget(QLabel("Now:", self.root), 3, 0)
        self.now_timestamp = QLineEdit(self.root)
        self.now_timestamp.setReadOnly(True)
        grid.addWidget(self.now_timestamp, 3, 1)
        copy1 = QPushButton("Copy", self.root)
        style_role(copy1, "info")
        copy1.clicked.connect(lambda: self._copy_to_clipboard(self.now_timestamp))
        grid.addWidget(copy1, 3, 2)
        grid.addWidget(QLabel("Date:", self.root), 4, 0)
        self.now_datetime = QLineEdit(self.root)
        self.now_datetime.setReadOnly(True)
        grid.addWidget(self.now_datetime, 4, 1)
        copy2 = QPushButton("Copy", self.root)
        style_role(copy2, "info")
        copy2.clicked.connect(lambda: self._copy_to_clipboard(self.now_datetime))
        grid.addWidget(copy2, 4, 2)

        # bottom spring: absorb the leftover height so the conversion rows
        # keep their compact top-aligned rhythm instead of being spread out
        grid.setRowStretch(5, 1)

        self._timer = QTimer(self.root)
        self._timer.timeout.connect(self._update_now)
        self._timer.start(1000)
        self._update_now()

    def _update_now(self):
        self.now_timestamp.setText(str(round(time.time())))
        self.now_datetime.setText(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    def _copy_to_clipboard(self, entry):
        """复制 Entry 中的内容到剪贴板"""
        from PyQt5.QtWidgets import QApplication
        QApplication.clipboard().setText(entry.text())
