"""Rendered HTML preview for HTML responses.

A response body is shown as source text in the request tab; this module backs
the "预览" button that shows the same document rendered.  Three back ends are
supported, in order of preference:

- ``webengine``   -- QtWebEngine (Chromium: full HTML/CSS/JavaScript)
- ``webkit``      -- the legacy QtWebKit ``QWebView``
- ``textbrowser`` -- Qt's own rich-text engine, which needs no extra package
                     but runs no JavaScript and supports only a subset of
                     HTML/CSS

The probe runs at import time on purpose: PyQt5 flips
``Qt::AA_ShareOpenGLContexts`` while importing QtWebEngine, and doing that
once a ``QApplication`` exists leaves the embedded Chromium unable to render.
The modules are therefore imported here (before the application is built) and
the view itself is created later, when the user asks for a preview.
"""

from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtWidgets import QDialog, QLabel, QTextBrowser, QVBoxLayout

try:  # PyQtWebEngine: the Chromium-based back end
    from PyQt5 import QtWebEngineWidgets as WEBENGINE
except Exception:  # not installed, or its native libraries are missing
    WEBENGINE = None

if WEBENGINE is None:
    try:  # QtWebKit, dropped from Qt 5.6 but still shipped by some builds
        from PyQt5 import QtWebKitWidgets as WEBKIT
    except Exception:
        WEBKIT = None
else:
    WEBKIT = None


def backend_name() -> str:
    """Name the back end a preview will use."""
    if WEBENGINE is not None:
        return "webengine"
    if WEBKIT is not None:
        return "webkit"
    return "textbrowser"


def describe_backend() -> str:
    """Describe the active back end, for the Preview button's tooltip."""
    name = backend_name()
    if name == "webengine":
        return "用内置浏览器预览该 HTML 响应"
    if name == "webkit":
        return "用内置 QWebView 预览该 HTML 响应"
    return "用 Qt 内置富文本引擎预览该 HTML 响应（不执行 JavaScript，仅支持 HTML/CSS 子集）"


class HtmlPreviewWindow(QDialog):
    """Show an HTML document in a non-modal window.

    One instance is reused per request: :meth:`set_content` swaps the document,
    so clicking Preview again refreshes the window instead of stacking a new
    one on top of it.
    """

    def __init__(self, parent=None, title="Preview", html="", base_url=""):
        super().__init__(parent)
        self.backend = backend_name()
        self.html = ""
        self.setWindowTitle(title)
        self.setModal(False)
        self.resize(900, 700)
        # Qt adds a help button on some platforms; it means nothing here, while
        # a page is easier to inspect in a window that can be maximised.
        self.setWindowFlags(
            (self.windowFlags() | Qt.WindowMaximizeButtonHint)
            & ~Qt.WindowContextHelpButtonHint
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        if self.backend == "textbrowser":
            note = QLabel(
                "未安装 QtWebEngine / QtWebKit，正在使用 Qt 内置富文本引擎预览："
                "不执行 JavaScript，且只支持 HTML/CSS 的一个子集。",
                self,
            )
            note.setWordWrap(True)
            note.setMargin(6)
            layout.addWidget(note)

        self.view = self._build_view()
        layout.addWidget(self.view, 1)
        self.set_content(html, base_url)

    def _build_view(self):
        if self.backend == "webengine":
            return WEBENGINE.QWebEngineView(self)
        if self.backend == "webkit":
            return WEBKIT.QWebView(self)
        view = QTextBrowser(self)
        # The preview is meant to inspect one response, not to browse away from
        # it, so links go to the system browser instead of navigating here.
        view.setOpenExternalLinks(True)
        return view

    def set_content(self, html, base_url=""):
        """Render `html`, resolving relative links against `base_url`."""
        self.html = html or ""
        url = QUrl(base_url) if base_url else QUrl()
        if self.backend == "textbrowser":
            # QTextEdit.setHtml() takes no base URL, and it leaves whatever the
            # document already had, so the base is always set explicitly here;
            # without it relative links and images would resolve against
            # nothing, or against the document previewed before this one.
            self.view.setHtml(self.html)
            self.view.document().setBaseUrl(url)
        elif url.isEmpty():
            self.view.setHtml(self.html)
        else:
            self.view.setHtml(self.html, url)
