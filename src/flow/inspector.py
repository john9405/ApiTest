"""Flow Inspector — right-side properties panel for editing selected nodes."""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QFrame,
)

from .nodes import NODE_REGISTRY
from .. import qui


class FlowInspector(QWidget):
    """Right-side panel showing properties of the currently selected node."""

    INSPECTOR_WIDTH = 230

    def __init__(self, master, on_node_change=None):
        super().__init__(master)
        self.setFixedWidth(self.INSPECTOR_WIDTH)
        self.on_node_change = on_node_change
        self._current_node = None
        self._config_frame = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QLabel("Properties", self)
        header.setObjectName("SectionHeader")
        layout.addWidget(header)

        layout.addWidget(qui.hline(self))

        # Scrollable content area
        self._scroll = QScrollArea(self)
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.NoFrame)
        layout.addWidget(self._scroll, 1)

        self._content = QWidget(self._scroll)
        self._content.setObjectName("InspectorContent")
        self._scroll.setWidget(self._content)
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(4, 4, 4, 4)
        self._content_layout.setSpacing(4)

        self._show_placeholder()

    def _clear_content(self):
        """Remove all widgets from the content area."""
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._config_frame = None

    def _show_placeholder(self):
        """Show message when no node is selected."""
        self._clear_content()
        label = QLabel("Select a block\nto configure", self._content)
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("color: #9ca3af; padding: 20px 4px;")
        self._content_layout.addWidget(label)
        self._content_layout.addStretch(1)

    def set_node(self, node_model):
        """Display configuration for a node."""
        self._current_node = node_model
        self._clear_content()

        if node_model is None:
            self._show_placeholder()
            return

        node_cls = NODE_REGISTRY.get(node_model.node_type)
        if node_cls is None:
            label = QLabel(f"Unknown type: {node_model.node_type}", self._content)
            label.setStyleSheet("color: red;")
            self._content_layout.addWidget(label)
            return

        # Node type header (Metro color tile)
        type_header = QLabel(node_cls.DISPLAY_NAME, self._content)
        type_header.setStyleSheet(
            f"background: {node_cls.COLOR}; color: white;"
            "font-weight: bold; padding: 6px 8px;"
        )
        self._content_layout.addWidget(type_header)

        # Common fields
        common_row = QWidget(self._content)
        ch = QVBoxLayout(common_row)
        ch.setContentsMargins(0, 4, 0, 0)
        ch.addWidget(QLabel("Label:", common_row))
        label_entry = QLineEdit(common_row)
        label_entry.setText(node_model.label or "")
        label_entry.textChanged.connect(
            lambda text: self._on_label_change(node_model, text)
        )
        ch.addWidget(label_entry)
        self._content_layout.addWidget(common_row)

        self._content_layout.addWidget(qui.hline(self._content))

        # Type-specific config
        self._config_frame = QWidget(self._content)
        self._content_layout.addWidget(self._config_frame, 1)

        node_instance = node_cls(node_model)
        config_widget = node_instance.get_config_frame(
            self._config_frame,
            on_change=self.on_node_change,
        )
        cfg_layout = QVBoxLayout(self._config_frame)
        cfg_layout.setContentsMargins(0, 0, 0, 0)
        cfg_layout.addWidget(config_widget)
        self._content_layout.addStretch(1)

    def _on_label_change(self, node_model, text):
        node_model.label = text
        if self.on_node_change:
            self.on_node_change()

    def get_current_node(self):
        """Return the currently displayed node model."""
        return self._current_node
