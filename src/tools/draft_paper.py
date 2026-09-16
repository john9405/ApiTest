from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QPlainTextEdit


class DraftPaper:
    def __init__(self, master=None):
        self.root = QWidget(master)
        outer = QVBoxLayout(self.root)
        outer.setContentsMargins(5, 5, 5, 5)
        outer.addWidget(QLabel("No content will be saved", self.root))
        self.text = QPlainTextEdit(self.root)
        self.text.setMinimumHeight(200)
        outer.addWidget(self.text, 1)
