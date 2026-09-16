import base64

from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPlainTextEdit,
    QGroupBox,
    QPushButton,
)

from ..qui import show_error
from ..theme import style_role


class Base64GUI:
    """ base64 Window """

    def __init__(self, master=None) -> None:
        self.root = QWidget(master)
        outer = QVBoxLayout(self.root)
        outer.setContentsMargins(5, 5, 5, 5)

        input_group = QGroupBox("Input", self.root)
        in_lay = QVBoxLayout(input_group)
        self.input_box = QPlainTextEdit(input_group)
        self.input_box.setMinimumHeight(120)
        in_lay.addWidget(self.input_box)
        outer.addWidget(input_group, 1)

        bframe = QWidget(self.root)
        blay = QHBoxLayout(bframe)
        blay.setContentsMargins(0, 4, 0, 4)
        ebtn = QPushButton("Encrypt", bframe)
        style_role(ebtn, "primary")
        ebtn.clicked.connect(self.encrypto)
        blay.addWidget(ebtn)
        dbtn = QPushButton("Decrypt", bframe)
        style_role(dbtn, "secondary")
        dbtn.clicked.connect(self.decrypto)
        blay.addWidget(dbtn)
        blay.addStretch(1)
        outer.addWidget(bframe)

        output_group = QGroupBox("Output", self.root)
        out_lay = QVBoxLayout(output_group)
        self.output_box = QPlainTextEdit(output_group)
        self.output_box.setMinimumHeight(120)
        out_lay.addWidget(self.output_box)
        outer.addWidget(output_group, 1)

    def encrypto(self):
        input_text = self.input_box.toPlainText()
        res = base64.b64encode(input_text.encode("utf-8")).decode("utf-8")
        self.output_box.setPlainText(res)

    def decrypto(self):
        try:
            # Whitespace is stripped (base64 is routinely pasted with line
            # breaks), then the input is validated: without validate=True
            # b64decode quietly discards anything it does not recognise, so
            # "aGVsbG8=###garbage" decoded to "hello" instead of erroring.
            compact = b"".join(self.input_box.toPlainText().encode("utf-8").split())
            compact += b"=" * (-len(compact) % 4)  # tolerate missing padding
            res = base64.b64decode(compact, validate=True).decode("utf-8")
            self.output_box.setPlainText(res)
        except Exception as e:
            self.output_box.clear()
            show_error(self.root, "Error", str(e))
