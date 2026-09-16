import os
import sys
import traceback

from PyQt5.QtWidgets import QApplication, QMessageBox

import src
from src.main import MainWindow
from src.theme import apply_theme


def _handle_uncaught(exc_type, exc_value, exc_tb):
    """Global handler for exceptions raised inside Qt slots / the UI thread.

    PyQt5's default behaviour for an unhandled Python exception in a slot is
    qFatal() -> abort(), which kills the app and loses the traceback.  PyQt
    routes the exception to sys.excepthook instead when a *custom* hook is
    installed, so this handler logs the full traceback to disk and shows it in
    a dialog, keeping the application alive.
    """
    text = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    try:
        log_path = os.path.join(src.WORK_DIR, "error.log")
        with open(log_path, "a", encoding="utf-8") as log_file:
            log_file.write("\n" + text)
    except Exception:
        pass
    print(text, file=sys.stderr, flush=True)
    try:
        if QApplication.instance() is not None:
            QMessageBox.critical(
                None,
                "Unhandled error",
                text[-4000:] if len(text) > 4000 else text,
            )
    except Exception:
        pass


def main():
    sys.excepthook = _handle_uncaught

    app = QApplication(sys.argv)
    app.setApplicationName("HTTP Client")
    app.setOrganizationName("apitest")
    apply_theme(app)

    win = MainWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
