"""Data model classes for the Flow feature.

FlowModel holds the in-memory representation of a workflow graph.
It acts as a bridge between the visual canvas and the database (via dao.crud).
"""

from ..dao.crud import (
    create_flow,
    update_flow,
    delete_flow,
    retrieve_flow,
    list_flow,
    create_flow_node,
    list_flow_node,
    delete_flow_node_by_flow,
    create_flow_connection,
    list_flow_connection,
    delete_flow_connection_by_flow,
)


class NodeModel:
    """Represents a single block/node in a flow."""

    def __init__(self, node_type="log", label="", x=100.0, y=100.0,
                 width=160.0, height=80.0, config=None, node_id=None):
        self.id = node_id  # database id, None for new nodes
        self.node_type = node_type
        self.label = label
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.config = config if config is not None else {}

    @classmethod
    def from_dict(cls, data):
        return cls(
            node_id=data.get("id"),
            node_type=data.get("node_type", "log"),
            label=data.get("label", ""),
            x=data.get("x", 100.0),
            y=data.get("y", 100.0),
            width=data.get("width", 160.0),
            height=data.get("height", 80.0),
            config=data.get("config", {}),
        )

    def to_dict(self):
        return {
            "id": self.id,
            "node_type": self.node_type,
            "label": self.label,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "config": self.config,
        }

    def contains_point(self, px, py):
        """Check if a point (in canvas coords) is inside this node."""
        return (self.x <= px <= self.x + self.width and
                self.y <= py <= self.y + self.height)

    def get_port_position(self, port_id):
        """Return (x, y) of a port in canvas coordinates."""
        cx = self.x + self.width / 2
        if port_id in ("true", "false"):
            # Condition node: two output ports side by side
            if port_id == "true":
                return (self.x + self.width * 0.3, self.y + self.height)
            else:
                return (self.x + self.width * 0.7, self.y + self.height)
        elif port_id == "output":
            return (cx, self.y + self.height)
        else:
            # input port
            return (cx, self.y)


class ConnectionModel:
    """Represents a connection between two ports on nodes."""

    def __init__(self, source_node_id=None, source_port="output",
                 target_node_id=None, target_port="input", conn_id=None):
        self.id = conn_id
        self.source_node_id = source_node_id
        self.source_port = source_port
        self.target_node_id = target_node_id
        self.target_port = target_port

    @classmethod
    def from_dict(cls, data):
        return cls(
            conn_id=data.get("id"),
            source_node_id=data.get("source_node_id"),
            source_port=data.get("source_port", "output"),
            target_node_id=data.get("target_node_id"),
            target_port=data.get("target_port", "input"),
        )

    def to_dict(self):
        return {
            "id": self.id,
            "source_node_id": self.source_node_id,
            "source_port": self.source_port,
            "target_node_id": self.target_node_id,
            "target_port": self.target_port,
        }


class FlowModel:
    """In-memory representation of a complete workflow."""

    def __init__(self, flow_id=None, name="New Flow", description=""):
        self.id = flow_id
        self.name = name
        self.description = description
        self.nodes = []          # list of NodeModel
        self.connections = []    # list of ConnectionModel
        self._next_id = 1        # temporary id counter for new nodes (negative)

    def add_node(self, node_type="log", label="", x=100.0, y=100.0,
                 width=160.0, height=80.0, config=None):
        """Add a node and return it. Assigns a temporary negative id."""
        node = NodeModel(
            node_id=self._next_id * -1,  # negative temp id
            node_type=node_type,
            label=label,
            x=x,
            y=y,
            width=width,
            height=height,
            config=config,
        )
        self._next_id += 1
        self.nodes.append(node)
        return node

    def remove_node(self, node_id):
        """Remove a node and all its connections."""
        self.nodes = [n for n in self.nodes if n.id != node_id]
        self.connections = [c for c in self.connections
                            if c.source_node_id != node_id and c.target_node_id != node_id]

    def get_node(self, node_id):
        """Find a node by id."""
        for node in self.nodes:
            if node.id == node_id:
                return node
        return None

    def add_connection(self, source_node_id, source_port, target_node_id, target_port="input"):
        """Add a connection. Returns the ConnectionModel."""
        conn = ConnectionModel(
            source_node_id=source_node_id,
            source_port=source_port,
            target_node_id=target_node_id,
            target_port=target_port,
        )
        self.connections.append(conn)
        return conn

    def remove_connection(self, conn_id):
        """Remove a connection by id."""
        self.connections = [c for c in self.connections if c.id != conn_id]

    def get_outgoing_connections(self, node_id, port=None):
        """Get all connections originating from a node/port."""
        result = []
        for conn in self.connections:
            if conn.source_node_id == node_id:
                if port is None or conn.source_port == port:
                    result.append(conn)
        return result

    def get_incoming_connections(self, node_id, port=None):
        """Get all connections targeting a node/port."""
        result = []
        for conn in self.connections:
            if conn.target_node_id == node_id:
                if port is None or conn.target_port == port:
                    result.append(conn)
        return result

    # ---- Persistence ----

    def save(self):
        """Persist the entire flow graph to the database."""
        if self.id is None or retrieve_flow(id=self.id) is None:
            # The row can be gone (deleted from the sidebar while this editor
            # was open).  Re-create it instead of writing nodes that point at a
            # flow_id which no longer exists.
            self.id = create_flow(name=self.name, description=self.description)
        else:
            update_flow(id=self.id, name=self.name, description=self.description)

        # Clear existing nodes and connections for this flow
        delete_flow_node_by_flow(flow_id=self.id)
        delete_flow_connection_by_flow(flow_id=self.id)

        # Persist nodes and build old-to-new id mapping
        id_map = {}
        for node in self.nodes:
            old_id = node.id
            new_id = create_flow_node(
                flow_id=self.id,
                node_type=node.node_type,
                label=node.label,
                x=node.x,
                y=node.y,
                width=node.width,
                height=node.height,
                config=node.config,
            )
            id_map[old_id] = new_id
            node.id = new_id

        # Persist connections with remapped node ids.  The in-memory endpoints
        # have to be remapped too: leaving them pointing at the pre-save ids
        # made every edge dangle after a save (the canvas stopped drawing them,
        # the engine stopped following them, and the next save raised KeyError).
        for conn in self.connections:
            source_id = id_map.get(conn.source_node_id, conn.source_node_id)
            target_id = id_map.get(conn.target_node_id, conn.target_node_id)
            conn.id = create_flow_connection(
                flow_id=self.id,
                source_node_id=source_id,
                source_port=conn.source_port,
                target_node_id=target_id,
                target_port=conn.target_port,
            )
            conn.source_node_id = source_id
            conn.target_node_id = target_id

    @classmethod
    def load(cls, flow_id):
        """Load a flow and all its nodes/connections from the database."""
        flow_data = retrieve_flow(id=flow_id)
        if flow_data is None:
            return None

        model = cls(
            flow_id=flow_data["id"],
            name=flow_data["name"],
            description=flow_data.get("description", ""),
        )

        # Load nodes
        node_records = list_flow_node(flow_id=flow_id)
        for record in node_records:
            model.nodes.append(NodeModel.from_dict(record))

        # Load connections
        conn_records = list_flow_connection(flow_id=flow_id)
        for record in conn_records:
            model.connections.append(ConnectionModel.from_dict(record))

        # Set _next_id past any negative temp ids
        model._next_id = 1
        return model

    @staticmethod
    def list_all():
        """List all saved flows."""
        return list_flow()

    @staticmethod
    def delete(flow_id):
        """Delete a flow and all related data."""
        delete_flow(id=flow_id)
