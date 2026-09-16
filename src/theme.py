"""No global custom theme.

Widgets use the Qt / platform default appearance and fonts. The previous
Metro QSS stylesheet and custom base-font settings have been removed.

Helpers are kept for API compatibility: `apply_theme` is a no-op, and
`style_role` / `metro_button` no longer change any colors (there is no
global stylesheet referencing the `role` property anymore).
"""

from PyQt5.QtWidgets import QPushButton


def apply_theme(app):
    """No-op: keep Qt/system-default widget styles and fonts."""
    return None


def style_role(widget, role):
    """No-op kept for compatibility (no global QSS uses the role)."""
    return None


def metro_button(text="", parent=None, role=None, command=None):
    """Create a plain QPushButton (kept for API compatibility)."""
    btn = QPushButton(text, parent)
    if command is not None:
        btn.clicked.connect(command)
    return btn
