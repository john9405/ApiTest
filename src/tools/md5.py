import hashlib

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QPlainTextEdit,
    QGroupBox,
    QPushButton,
)

from ..qui import show_info
from ..theme import style_role


class MD5GUI:
    """ MD5 Window """

    def __init__(self, master=None):
        self.root = QWidget(master)
        outer = QVBoxLayout(self.root)
        outer.setContentsMargins(5, 5, 5, 5)

        init_data_label = QGroupBox("Input", self.root)
        in_lay = QVBoxLayout(init_data_label)
        self.init_data_text = QPlainTextEdit(init_data_label)
        self.init_data_text.setMinimumHeight(120)
        in_lay.addWidget(self.init_data_text)
        outer.addWidget(init_data_label, 1)

        btn = QPushButton("MD5", self.root)
        btn.setFixedWidth(90)
        style_role(btn, "primary")
        btn.clicked.connect(self.str_trans_to_md5)
        outer.addWidget(btn, 0, alignment=Qt.AlignHCenter)

        result_data_label = QGroupBox("Output", self.root)
        out_lay = QVBoxLayout(result_data_label)
        self.result_data_text = QPlainTextEdit(result_data_label)
        self.result_data_text.setMinimumHeight(120)
        out_lay.addWidget(self.result_data_text)
        outer.addWidget(result_data_label, 1)

    def str_trans_to_md5(self):
        # Hash exactly what is in the box.  The old code did
        # ``.strip().replace("\n", "")``, which folded "hello\n", "hello " and
        # "\thello\t" onto the same digest as "hello" — a silently wrong answer
        # for a tool people use to reproduce an API's body/signature hash.
        src = self.init_data_text.toPlainText().encode("utf-8")
        try:
            hasher = hashlib.md5()
            hasher.update(src)
            res = hasher.hexdigest()
            self.result_data_text.setPlainText(res + "\n" + res.upper())
        except Exception as e:
            self.result_data_text.clear()
            show_info(self.root, "Error", str(e))
