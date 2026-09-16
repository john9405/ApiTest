from PyQt5.QtWidgets import QPlainTextEdit

from . import __version__


class AboutWindow:
    """关于窗口"""

    def __init__(self, master=None):
        self.root = QPlainTextEdit(master)
        # Read from src.__init__ instead of a hardcoded literal that had already
        # drifted from pyproject.toml.
        self.root.setPlainText(f"""Http Client
{__version__}
""")
        self.root.setReadOnly(True)
