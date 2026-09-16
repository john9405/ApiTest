import secrets
import string

from PyQt5.QtWidgets import (
    QWidget,
    QGridLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QCheckBox,
    QPushButton,
)

from ..theme import style_role


class GenPwdWindow:
    """ 随即密码生成器 """

    def __init__(self, master=None) -> None:
        self.root = QWidget(master)
        grid = QGridLayout(self.root)
        grid.setContentsMargins(8, 8, 8, 8)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)

        grid.addWidget(QLabel("Length:", self.root), 0, 0)
        self.l = QSpinBox(self.root)
        self.l.setRange(1, 100)
        self.l.setValue(8)
        grid.addWidget(self.l, 0, 1, 1, 4)

        grid.addWidget(QLabel("Complexity:", self.root), 1, 0)
        self.dcb = QCheckBox("0-9", self.root)
        self.dcb.setChecked(True)
        grid.addWidget(self.dcb, 1, 1)
        self.lccb = QCheckBox("a-z", self.root)
        self.lccb.setChecked(True)
        grid.addWidget(self.lccb, 1, 2)
        self.uccb = QCheckBox("A-Z", self.root)
        self.uccb.setChecked(True)
        grid.addWidget(self.uccb, 1, 3)
        self.pcb = QCheckBox("other", self.root)
        grid.addWidget(self.pcb, 1, 4)

        generate_button = QPushButton("Generate", self.root)
        style_role(generate_button, "primary")
        generate_button.clicked.connect(self.generate_password)
        grid.addWidget(generate_button, 2, 1, 1, 4)

        grid.addWidget(QLabel("Generated:", self.root), 3, 0)
        self.pwd_entry = QLineEdit(self.root)
        self.pwd_entry.setMinimumWidth(220)
        grid.addWidget(self.pwd_entry, 3, 1, 1, 3)

        copy_button = QPushButton("Copy", self.root)
        style_role(copy_button, "info")
        copy_button.clicked.connect(self.copy_password)
        grid.addWidget(copy_button, 3, 4)

        # bottom spring: absorb the leftover height so the fields stay
        # top-aligned and compact instead of being spread out vertically
        grid.setRowStretch(4, 1)

    def generate_password(self):
        password_length = self.l.value()
        sets = [
            charset for charset, box in (
                (string.digits, self.dcb),
                (string.ascii_lowercase, self.lccb),
                (string.ascii_uppercase, self.uccb),
                (string.punctuation, self.pcb),
            ) if box.isChecked()
        ]
        if not sets:
            self.pwd_entry.clear()
            return

        # Seed one character from every selected class before filling the rest.
        # Sampling the concatenated alphabet alone left ~24% of 8-character
        # passwords without a digit even with 0-9 checked, so the result could
        # fail a site's "must contain a digit" rule.
        classes = sets[:password_length]
        chars = [secrets.choice(charset) for charset in classes]
        alphabet = "".join(sets)
        chars += [secrets.choice(alphabet) for _ in range(password_length - len(chars))]
        # Shuffle with a CSPRNG so the seeded characters are not always first.
        secrets.SystemRandom().shuffle(chars)
        self.pwd_entry.setText("".join(chars))

    def copy_password(self):
        """将生成的密码复制到剪贴板"""
        QApplication_clipboard(self.pwd_entry.text())


def QApplication_clipboard(text):
    from PyQt5.QtWidgets import QApplication
    QApplication.clipboard().setText(text)
