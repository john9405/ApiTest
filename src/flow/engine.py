"""Flow Engine — threaded workflow execution with real-time canvas visualization.

Traverses the flow graph, executes each node in order, and updates the canvas
to show execution progress in real time.
"""

import threading

from .nodes import NODE_REGISTRY


class FlowEngine:
    """Orchestrates execution of a flow graph.

    Runs in a background thread to keep the UI responsive.
    Canvas updates are dispatched via widget.after(0, callback).
    """

    def __init__(self, model, canvas, editor):
        """
        Args:
            model: FlowModel instance
            canvas: FlowCanvas instance (for real-time highlighting)
            editor: FlowEditor instance (for console, stop flag access)
        """
        self.model = model
        self.canvas = canvas
        self.editor = editor
        self.on_complete = None    # callback when execution finishes

        # Execution state
        self.context = {}          # node_id -> output dict
        self.visited = set()
        self.cancelled = False
        self._thread = None

    def run(self):
        """Start execution in a background thread."""
        self.cancelled = False
        self.context = {}
        self.visited = set()
        self._thread = threading.Thread(target=self._execute, daemon=True)
        self._thread.start()

    def stop(self):
        """Signal the engine to stop (called from UI thread)."""
        self.cancelled = True

    def _execute(self):
        """Main execution loop — runs in background thread."""
        # Find start nodes: nodes with no incoming connections
        start_nodes = self._find_start_nodes()

        if not start_nodes:
            # If every node has an incoming connection, start with the first one
            if self.model.nodes:
                start_nodes = [self.model.nodes[0].id]

        self._log_to_console("info", f"Starting flow execution ({len(start_nodes)} start nodes)...")

        try:
            for node_id in start_nodes:
                if self.cancelled:
                    break
                self._traverse(node_id)

            if self.cancelled:
                self._log_to_console("info", "Flow execution cancelled.")
            else:
                self._log_to_console("info", "Flow execution completed.")
        except Exception as e:
            self._log_to_console("error", f"Flow execution error: {e}")
        finally:
            # Notify completion on the UI thread
            if self.on_complete:
                self.canvas.after(0, self.on_complete)

    def _traverse(self, node_id):
        """Execute a single node and recursively follow its outgoing connections."""
        if node_id in self.visited or self.cancelled:
            return

        node_model = self.model.get_node(node_id)
        if node_model is None:
            return

        self.visited.add(node_id)

        node_cls = NODE_REGISTRY.get(node_model.node_type)
        if node_cls is None:
            self._log_to_console("error", f"Unknown node type: {node_model.node_type}")
            return

        node_instance = node_cls(node_model)

        # Highlight: running
        self.canvas.after(0, lambda: self.canvas.highlight_node(node_id, "running"))

        # Execute
        try:
            output = node_instance.execute(self.context, self._console_adapter())
            self.context[node_id] = output
        except Exception as e:
            self.context[node_id] = {"error": str(e)}
            self._log_to_console("error", f"{node_model.label}: {str(e)}")
            self.canvas.after(0, lambda: self.canvas.highlight_node(node_id, "error"))
            return  # Stop traversal from this node on error

        # Several node types report failure by *returning* {"error": ...} rather
        # than raising.  Treating that as success highlighted the node green and
        # kept following the happy path — for a Condition it silently took the
        # false branch.
        if isinstance(output, dict) and output.get("error"):
            self._log_to_console("error", f"{node_model.label}: {output['error']}")
            self.canvas.after(0, lambda: self.canvas.highlight_node(node_id, "error"))
            return

        self.canvas.after(0, lambda: self.canvas.highlight_node(node_id, "completed"))

        # Determine which output port(s) to follow
        if node_model.node_type == "condition" and "branch" in output:
            source_port = "true" if output["branch"] else "false"
        else:
            source_port = "output"

        # Follow outgoing connections
        for conn in self.model.get_outgoing_connections(node_id, source_port):
            if self.cancelled:
                break
            self._traverse(conn.target_node_id)

    def _find_start_nodes(self):
        """Find nodes with no incoming connections (start nodes)."""
        has_incoming = set()
        for conn in self.model.connections:
            has_incoming.add(conn.target_node_id)

        start_nodes = []
        for node in self.model.nodes:
            if node.id not in has_incoming:
                start_nodes.append(node.id)

        return start_nodes

    def _log_to_console(self, level, message):
        """Log a message to the editor console from any thread."""
        if level == "info":
            self.canvas.after(0, lambda: self.editor.info(message))
        elif level == "error":
            self.canvas.after(0, lambda: self.editor.error(message))
        else:
            self.canvas.after(0, lambda: self.editor.log(message))

    def _console_adapter(self):
        """Return a console-like object for node execution that logs through the editor."""
        engine = self

        class ConsoleAdapter:
            def log(self, *args):
                engine._log_to_console("log", " ".join(str(a) for a in args))

            def info(self, *args):
                engine._log_to_console("info", " ".join(str(a) for a in args))

            def error(self, *args):
                engine._log_to_console("error", " ".join(str(a) for a in args))

        return ConsoleAdapter()
