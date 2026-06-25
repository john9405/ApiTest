"""Flow package — low-code visual workflow builder.

Provides:
- FlowWindow: sidebar panel listing saved workflows
- FlowEditor: visual canvas editor for building workflows
- FlowModel: in-memory data model with persistence
- FlowEngine: threaded execution engine
"""

from .manager import FlowWindow
from .editor import FlowEditor, FlowCanvas
from .model import FlowModel, NodeModel, ConnectionModel
from .engine import FlowEngine
from .nodes import NODE_REGISTRY, PALETTE_ENTRIES
