"""Flow Editor — visual canvas for building workflows.

Contains:
- FlowCanvas: tk.Canvas subclass for node rendering, dragging, connections, pan/zoom
- FlowEditor: container with toolbar, palette, canvas, inspector, console
"""

import json
import math
import tkinter as tk
from tkinter import  messagebox
import ttkbootstrap as ttk
from tkinter.scrolledtext import ScrolledText

from .model import FlowModel
from .nodes import NODE_REGISTRY, PALETTE_ENTRIES
from .palette import NodePalette
from .inspector import FlowInspector


# ---------------------------------------------------------------------------
# FlowCanvas — the visual graph editor
# ---------------------------------------------------------------------------

class FlowCanvas(tk.Canvas):
    """Interactive canvas for node-based workflow editing.

    Features:
    - Renders nodes as rounded rectangles with color coding and port circles
    - Drag nodes to reposition
    - Click-drag from output port to input port to draw connections
    - Pan via middle-mouse drag or Ctrl+left drag
    - Zoom via mouse wheel
    - Select/deselect nodes
    - Delete with Delete/BackSpace key
    """

    NODE_RADIUS = 8
    PORT_RADIUS = 6
    GRID_SPACING = 20
    GRID_COLOR = "#f0f0f0"
    BG_COLOR = "#fafafa"
    CONNECTION_COLOR = "#9ca3af"
    CONNECTION_ACTIVE_COLOR = "#10b981"
    CONNECTION_WIDTH = 2
    SELECTION_COLOR = "#3b82f6"
    HIGHLIGHT_RUNNING = "#fbbf24"
    HIGHLIGHT_COMPLETED = "#10b981"
    HIGHLIGHT_ERROR = "#ef4444"

    def __init__(self, master, model, on_selection_change=None, **kwargs):
        super().__init__(master, bg=self.BG_COLOR, borderwidth=0, highlightthickness=0, **kwargs)
        self.model = model                        # FlowModel
        self.on_selection_change = on_selection_change

        # Interaction state
        self.scale_factor = 1.0
        self.offset_x = 0.0
        self.offset_y = 0.0
        self.selected_node_id = None
        self._drag_state = None                   # 'move_node', 'draw_conn', 'pan'
        self._drag_node_id = None
        self._drag_start_x = 0
        self._drag_start_y = 0
        self._conn_source_node_id = None
        self._conn_source_port = None
        self._temp_conn_line = None
        self._pan_start_x = 0
        self._pan_start_y = 0
        self._pan_offset_x = 0
        self._pan_offset_y = 0
        self._node_highlight_states = {}          # node_id -> 'running'|'completed'|'error'

        # Bind events
        self.bind("<Button-1>", self._on_left_down)
        self.bind("<B1-Motion>", self._on_left_drag)
        self.bind("<ButtonRelease-1>", self._on_left_up)
        self.bind("<Button-2>", self._on_middle_down)
        self.bind("<B2-Motion>", self._on_middle_drag)
        self.bind("<ButtonRelease-2>", self._on_middle_up)
        self.bind("<Control-Button-1>", self._on_pan_down)
        self.bind("<Control-B1-Motion>", self._on_pan_drag)
        self.bind("<Control-ButtonRelease-1>", self._on_pan_up)

        # Zoom on all platforms
        if tk.TkVersion >= 8.5:
            self.bind("<MouseWheel>", self._on_zoom)
            self.bind("<Shift-MouseWheel>", self._on_zoom)
        self.bind("<Button-4>", self._on_zoom)
        self.bind("<Button-5>", self._on_zoom)

        self.bind("<Delete>", self._on_delete)
        self.bind("<BackSpace>", self._on_delete)

        # Right-click context menu
        self.bind("<Button-3>", self._on_right_click)
        self.bind("<Button-2>", self._on_right_click)

    # ------------------------------------------------------------------
    # Coordinate transforms
    # ------------------------------------------------------------------

    def _to_canvas(self, screen_x, screen_y):
        """Convert screen coordinates to canvas/logical coordinates."""
        cx = (screen_x - self.offset_x) / self.scale_factor
        cy = (screen_y - self.offset_y) / self.scale_factor
        return cx, cy

    def _to_screen(self, canvas_x, canvas_y):
        """Convert canvas/logical coordinates to screen coordinates."""
        sx = canvas_x * self.scale_factor + self.offset_x
        sy = canvas_y * self.scale_factor + self.offset_y
        return sx, sy

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def render(self):
        """Full redraw of the entire canvas."""
        self.delete("all")
        self._draw_grid()

        # Draw connections
        for conn in self.model.connections:
            self._draw_connection(conn)

        # Draw nodes
        for node in self.model.nodes:
            self._draw_node(node)

        # Draw temp connection line
        if self._temp_conn_line is not None:
            self._draw_temp_connection()

    def _draw_grid(self):
        """Draw a light dot grid."""
        w = max(self.winfo_width(), 1)
        h = max(self.winfo_height(), 1)
        spacing = self.GRID_SPACING * self.scale_factor
        ox = self.offset_x % spacing
        oy = self.offset_y % spacing
        for x in range(int(ox), w, int(max(spacing, 8))):
            self.create_line(x, 0, x, h, fill=self.GRID_COLOR, width=1)
        for y in range(int(oy), h, int(max(spacing, 8))):
            self.create_line(0, y, w, y, fill=self.GRID_COLOR, width=1)

    def _draw_node(self, node):
        """Draw a single node on the canvas."""
        sx1, sy1 = self._to_screen(node.x, node.y)
        sx2, sy2 = self._to_screen(node.x + node.width, node.y + node.height)

        node_cls = NODE_REGISTRY.get(node.node_type)
        color = node_cls.COLOR if node_cls else "#6b7280"
        display_name = node_cls.DISPLAY_NAME if node_cls else node.node_type

        is_selected = node.id == self.selected_node_id
        outline_color = self.SELECTION_COLOR if is_selected else "#d1d5db"
        outline_width = 2 if is_selected else 1

        # Highlight state (from execution)
        highlight = self._node_highlight_states.get(node.id)
        if highlight == "running":
            outline_color = self.HIGHLIGHT_RUNNING
            outline_width = 3
        elif highlight == "completed":
            outline_color = self.HIGHLIGHT_COMPLETED
            outline_width = 3
        elif highlight == "error":
            outline_color = self.HIGHLIGHT_ERROR
            outline_width = 3

        # Node body
        tag = f"node_{node.id}"
        self.create_rectangle(sx1, sy1, sx2, sy2,
                              fill="white", outline=outline_color,
                              width=outline_width, tags=(tag, "node"))

        # Color bar at top
        bar_height = 6 * self.scale_factor
        self.create_rectangle(sx1, sy1, sx2, sy1 + bar_height,
                              fill=color, outline="", tags=(tag, "node"))

        # Type label
        self.create_text(sx1 + 5 * self.scale_factor, sy1 + bar_height + 4 * self.scale_factor,
                         text=display_name, anchor="w",
                         fill=color, font=("TkDefaultFont", 8, "bold"),
                         tags=(tag, "node"))

        # Node label
        label = node.label or display_name
        label_cy = (sy1 + sy2) / 2
        self.create_text((sx1 + sx2) / 2, label_cy,
                         text=label, anchor="center",
                         fill="#1f2937", font=("TkDefaultFont", 9),
                         tags=(tag, "node"))

        # Input ports
        node_instance = node_cls(node) if node_cls else None
        if node_instance:
            for port in node_instance.INPUT_PORTS:
                px, py = node.get_port_position(port.port_id)
                spx, spy = self._to_screen(px, py)
                self.create_oval(spx - self.PORT_RADIUS, spy - self.PORT_RADIUS,
                                 spx + self.PORT_RADIUS, spy + self.PORT_RADIUS,
                                 fill=color, outline="white", width=1,
                                 tags=(tag, "port", f"port_in_{node.id}_{port.port_id}"))

            # Output ports
            for port in node_instance.OUTPUT_PORTS:
                px, py = node.get_port_position(port.port_id)
                spx, spy = self._to_screen(px, py)
                self.create_oval(spx - self.PORT_RADIUS, spy - self.PORT_RADIUS,
                                 spx + self.PORT_RADIUS, spy + self.PORT_RADIUS,
                                 fill=color, outline="white", width=1,
                                 tags=(tag, "port", f"port_out_{node.id}_{port.port_id}"))

    def _draw_connection(self, conn):
        """Draw a connection line between two ports."""
        source_node = self.model.get_node(conn.source_node_id)
        target_node = self.model.get_node(conn.target_node_id)
        if source_node is None or target_node is None:
            return

        sx, sy = source_node.get_port_position(conn.source_port)
        tx, ty = target_node.get_port_position(conn.target_port)
        ssx, ssy = self._to_screen(sx, sy)
        tsx, tsy = self._to_screen(tx, ty)

        conn_tag = f"conn_{conn.id}"

        # Draw a bezier-like curve using control points
        dy = abs(tsy - ssy)
        control_offset = max(dy * 0.4, 40)
        cp1x, cp1y = ssx, ssy + control_offset
        cp2x, cp2y = tsx, tsy - control_offset

        # Create smooth curve
        points = []
        steps = 20
        for i in range(steps + 1):
            t = i / steps
            # Cubic Bezier
            x = (1 - t) ** 3 * ssx + 3 * (1 - t) ** 2 * t * cp1x + 3 * (1 - t) * t ** 2 * cp2x + t ** 3 * tsx
            y = (1 - t) ** 3 * ssy + 3 * (1 - t) ** 2 * t * cp1y + 3 * (1 - t) * t ** 2 * cp2y + t ** 3 * tsy
            points.extend([x, y])

        self.create_line(*points, fill=self.CONNECTION_COLOR, width=self.CONNECTION_WIDTH,
                         smooth=False, tags=(conn_tag, "connection"))

        # Arrow at target end
        arrow_size = 6
        self.create_polygon(
            tsx, tsy,
            tsx - arrow_size, tsy - arrow_size * 1.5,
            tsx + arrow_size, tsy - arrow_size * 1.5,
            fill=self.CONNECTION_COLOR, outline="",
            tags=(conn_tag, "connection"),
        )

    def _draw_temp_connection(self):
        """Draw a temporary rubber-band line while the user is drawing a connection."""
        if self._conn_source_node_id is None:
            return
        source_node = self.model.get_node(self._conn_source_node_id)
        if source_node is None:
            return
        sx, sy = source_node.get_port_position(self._conn_source_port)
        ssx, ssy = self._to_screen(sx, sy)

        # The cursor position is already in screen coords
        cursor_x = self.winfo_pointerx() - self.winfo_rootx()
        cursor_y = self.winfo_pointery() - self.winfo_rooty()

        self.create_line(ssx, ssy, cursor_x, cursor_y,
                         fill="#3b82f6", dash=(4, 4), width=2,
                         tags=("temp_connection",))

    # ------------------------------------------------------------------
    # Hit testing
    # ------------------------------------------------------------------

    def _hit_port(self, screen_x, screen_y):
        """Check if a screen coordinate hits a port. Returns (node_id, port_id, direction) or None."""
        margin = self.PORT_RADIUS + 4
        for node in self.model.nodes:
            node_cls = NODE_REGISTRY.get(node.node_type)
            if node_cls is None:
                continue
            node_instance = node_cls(node)
            for port in node_instance.INPUT_PORTS:
                px, py = node.get_port_position(port.port_id)
                spx, spy = self._to_screen(px, py)
                if abs(screen_x - spx) <= margin and abs(screen_y - spy) <= margin:
                    return (node.id, port.port_id, "in")
            for port in node_instance.OUTPUT_PORTS:
                px, py = node.get_port_position(port.port_id)
                spx, spy = self._to_screen(px, py)
                if abs(screen_x - spx) <= margin and abs(screen_y - spy) <= margin:
                    return (node.id, port.port_id, "out")
        return None

    def _hit_node(self, screen_x, screen_y):
        """Check if a screen coordinate hits a node. Returns node_id or None."""
        # Check in reverse order (top-most first)
        for node in reversed(self.model.nodes):
            cx, cy = self._to_canvas(screen_x, screen_y)
            if node.contains_point(cx, cy):
                return node.id
        return None

    def _hit_connection(self, screen_x, screen_y):
        """Check if a screen coordinate hits a connection. Returns conn_id or None."""
        margin = 6
        for conn in self.model.connections:
            source_node = self.model.get_node(conn.source_node_id)
            target_node = self.model.get_node(conn.target_node_id)
            if source_node is None or target_node is None:
                continue
            # Simple proximity check along the line
            sx, sy = source_node.get_port_position(conn.source_port)
            tx, ty = target_node.get_port_position(conn.target_port)
            ssx, ssy = self._to_screen(sx, sy)
            tsx, tsy = self._to_screen(tx, ty)
            dist = self._point_to_line_dist(screen_x, screen_y, ssx, ssy, tsx, tsy)
            if dist <= margin:
                return conn.id
        return None

    @staticmethod
    def _point_to_line_dist(px, py, x1, y1, x2, y2):
        """Distance from point (px, py) to line segment (x1,y1)-(x2,y2)."""
        dx = x2 - x1
        dy = y2 - y1
        if dx == 0 and dy == 0:
            return math.hypot(px - x1, py - y1)
        t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
        nx = x1 + t * dx
        ny = y1 + t * dy
        return math.hypot(px - nx, py - ny)

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def select_node(self, node_id):
        """Select a node and notify listener."""
        self.selected_node_id = node_id
        if self.on_selection_change:
            node = self.model.get_node(node_id) if node_id else None
            self.on_selection_change(node)
        self.render()

    def deselect_all(self):
        """Clear selection."""
        self.selected_node_id = None
        if self.on_selection_change:
            self.on_selection_change(None)
        self.render()

    # ------------------------------------------------------------------
    # Mouse event handlers
    # ------------------------------------------------------------------

    def _on_left_down(self, event):
        """Handle left mouse button press."""
        # Check ports first
        port_hit = self._hit_port(event.x, event.y)
        if port_hit is not None and port_hit[2] == "out":
            # Start drawing a connection from output port
            self._drag_state = "draw_conn"
            self._conn_source_node_id = port_hit[0]
            self._conn_source_port = port_hit[1]
            self._temp_conn_line = True
            self.render()
            return

        # Check nodes
        node_hit = self._hit_node(event.x, event.y)
        if node_hit is not None:
            self.select_node(node_hit)
            self._drag_state = "move_node"
            self._drag_node_id = node_hit
            self._drag_start_x = event.x
            self._drag_start_y = event.y
            return

        # Check connections
        conn_hit = self._hit_connection(event.x, event.y)
        if conn_hit is not None:
            # Select the connection (for potential delete)
            return

        # Click on empty area
        self.deselect_all()
        self._drag_state = None

    def _on_left_drag(self, event):
        """Handle left mouse drag."""
        if self._drag_state == "move_node" and self._drag_node_id is not None:
            node = self.model.get_node(self._drag_node_id)
            if node:
                dx = (event.x - self._drag_start_x) / self.scale_factor
                dy = (event.y - self._drag_start_y) / self.scale_factor
                node.x += dx
                node.y += dy
                self._drag_start_x = event.x
                self._drag_start_y = event.y
            self.render()
        elif self._drag_state == "draw_conn":
            self.render()

    def _on_left_up(self, event):
        """Handle left mouse button release."""
        if self._drag_state == "draw_conn":
            self._temp_conn_line = None
            # Check if released on an input port
            port_hit = self._hit_port(event.x, event.y)
            if port_hit is not None and port_hit[2] == "in":
                # Prevent duplicate connections between same source port and target
                existing = [c for c in self.model.connections
                            if c.source_node_id == self._conn_source_node_id
                            and c.source_port == self._conn_source_port
                            and c.target_node_id == port_hit[0]
                            and c.target_port == port_hit[1]]
                if not existing and port_hit[0] != self._conn_source_node_id:
                    self.model.add_connection(
                        self._conn_source_node_id, self._conn_source_port,
                        port_hit[0], port_hit[1],
                    )
            self._conn_source_node_id = None
            self._conn_source_port = None
            self.render()

        self._drag_state = None
        self._drag_node_id = None

    def _on_middle_down(self, event):
        """Middle mouse pan start."""
        self._drag_state = "pan"
        self._pan_start_x = event.x
        self._pan_start_y = event.y
        self._pan_offset_x = self.offset_x
        self._pan_offset_y = self.offset_y

    def _on_middle_drag(self, event):
        """Middle mouse pan drag."""
        if self._drag_state == "pan":
            self.offset_x = self._pan_offset_x + (event.x - self._pan_start_x)
            self.offset_y = self._pan_offset_y + (event.y - self._pan_start_y)
            self.render()

    def _on_middle_up(self, event):
        """Middle mouse pan end."""
        if self._drag_state == "pan":
            self._drag_state = None

    def _on_pan_down(self, event):
        """Ctrl+Left pan start."""
        self._drag_state = "pan"
        self._pan_start_x = event.x
        self._pan_start_y = event.y
        self._pan_offset_x = self.offset_x
        self._pan_offset_y = self.offset_y

    def _on_pan_drag(self, event):
        """Ctrl+Left pan drag."""
        if self._drag_state == "pan":
            self.offset_x = self._pan_offset_x + (event.x - self._pan_start_x)
            self.offset_y = self._pan_offset_y + (event.y - self._pan_start_y)
            self.render()

    def _on_pan_up(self, event):
        """Ctrl+Left pan end."""
        if self._drag_state == "pan":
            self._drag_state = None

    def _on_zoom(self, event):
        """Mouse wheel zoom."""
        # Determine zoom direction
        if event.num == 4 or (hasattr(event, 'delta') and event.delta > 0):
            factor = 1.1
        elif event.num == 5 or (hasattr(event, 'delta') and event.delta < 0):
            factor = 0.9
        else:
            return

        new_scale = self.scale_factor * factor
        if 0.2 <= new_scale <= 3.0:
            # Zoom toward cursor position
            cx = event.x
            cy = event.y
            self.offset_x = cx - (cx - self.offset_x) * factor
            self.offset_y = cy - (cy - self.offset_y) * factor
            self.scale_factor = new_scale
            self.render()

    # ------------------------------------------------------------------
    # Keyboard handlers
    # ------------------------------------------------------------------

    def _on_delete(self, event):
        """Delete selected node or connection."""
        if self.selected_node_id is not None:
            self.model.remove_node(self.selected_node_id)
            self.selected_node_id = None
            if self.on_selection_change:
                self.on_selection_change(None)
            self.render()

    # ------------------------------------------------------------------
    # Context menu
    # ------------------------------------------------------------------

    def _on_right_click(self, event):
        """Right-click context menu."""
        node_hit = self._hit_node(event.x, event.y)
        conn_hit = self._hit_connection(event.x, event.y)

        menu = tk.Menu(self, tearoff=False)

        if node_hit is not None:
            self.select_node(node_hit)
            node = self.model.get_node(node_hit)
            node_cls = NODE_REGISTRY.get(node.node_type) if node else None
            type_name = node_cls.DISPLAY_NAME if node_cls else "Node"
            menu.add_command(label=f"Delete {type_name}",
                             command=lambda: self._delete_node(node_hit))
        elif conn_hit is not None:
            menu.add_command(label="Delete Connection",
                             command=lambda: self._delete_connection(conn_hit))
        else:
            # Empty area: show add node submenu
            for entry in PALETTE_ENTRIES:
                menu.add_command(
                    label=f"Add {entry['name']}",
                    command=lambda e=entry: self._add_node_at_cursor(e["type_id"], event.x, event.y),
                )

        menu.post(event.x_root, event.y_root)

    def _delete_node(self, node_id):
        """Delete a node and its connections."""
        self.model.remove_node(node_id)
        if self.selected_node_id == node_id:
            self.selected_node_id = None
            if self.on_selection_change:
                self.on_selection_change(None)
        self.render()

    def _delete_connection(self, conn_id):
        """Delete a connection."""
        self.model.remove_connection(conn_id)
        self.render()

    def _add_node_at_cursor(self, type_id, screen_x, screen_y):
        """Add a new node at the given screen position."""
        cx, cy = self._to_canvas(screen_x, screen_y)
        label = ""
        for entry in PALETTE_ENTRIES:
            if entry["type_id"] == type_id:
                label = entry["name"]
                break
        node = self.model.add_node(node_type=type_id, label=label, x=cx - 80, y=cy - 40)
        self.select_node(node.id)
        self.render()

    # ------------------------------------------------------------------
    # Public API for execution highlighting
    # ------------------------------------------------------------------

    def highlight_node(self, node_id, state):
        """Set execution highlight state for a node.
        States: 'running', 'completed', 'error', None (clear)
        """
        if state is None:
            self._node_highlight_states.pop(node_id, None)
        else:
            self._node_highlight_states[node_id] = state
        self.render()
        self.update()

    def clear_highlights(self):
        """Clear all execution highlights."""
        self._node_highlight_states.clear()
        self.render()

    def place_node(self, type_id, screen_x, screen_y):
        """Called from palette stamp: place a node at cursor position."""
        self._add_node_at_cursor(type_id, screen_x, screen_y)


# ---------------------------------------------------------------------------
# FlowEditor — the full editor workspace
# ---------------------------------------------------------------------------

class FlowEditor:
    """The full flow editing workspace, opened as a tab in CanvasNotebook.

    Layout:
    ┌──────────────────────────────────────────────────┐
    │ Toolbar: [Run] [Stop] [Save] [-] [+] [Fit]      │
    ├────────┬───────────────────────────┬─────────────┤
    │Palette │     FlowCanvas            │  Inspector  │
    │        │                           │             │
    ├────────┴───────────────────────────┴─────────────┤
    │ Console (execution output)                       │
    └──────────────────────────────────────────────────┘
    """

    def __init__(self, master, flow_id=None, on_save=None):
        """
        Args:
            master: parent ttk.Frame (the tab frame)
            flow_id: database id of the flow, or None for a new flow
            on_save: callback when the flow is saved
        """
        self.root = master
        self.on_save_callback = on_save
        self.is_dirty = False
        self._title_callback = None
        self._is_running = False

        # Load or create flow model
        if flow_id is not None:
            self.model = FlowModel.load(flow_id)
            if self.model is None:
                self.model = FlowModel(name="New Flow")
        else:
            self.model = FlowModel(name="New Flow")

        # Toolbar
        self._create_toolbar()

        # Main content area
        content = ttk.Frame(master)
        content.pack(fill=tk.BOTH, expand=True)

        # Palette (left)
        self.palette = NodePalette(content, on_select_type=self._on_palette_select)
        self.palette.pack(side=tk.LEFT, fill=tk.Y)

        ttk.Separator(content, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y)

        # Right side: inspector + console
        right_frame = ttk.Frame(content)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y)

        self.inspector = FlowInspector(right_frame, on_node_change=self._on_inspector_change)
        self.inspector.pack(fill=tk.BOTH, expand=True)

        ttk.Separator(right_frame, orient=tk.HORIZONTAL).pack(fill=tk.X)

        # Console (bottom-right)
        console_frame = ttk.Frame(right_frame, height=120)
        console_frame.pack(fill=tk.X, side=tk.BOTTOM)
        console_frame.pack_propagate(False)
        ttk.Label(console_frame, text="Console", font=("TkDefaultFont", 9, "bold")).pack(
            anchor="w", padx=4, pady=(2, 0))
        self.console_text = ScrolledText(console_frame, height=6)
        self.console_text.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        ttk.Separator(content, orient=tk.VERTICAL).pack(side=tk.RIGHT, fill=tk.Y)

        # Canvas (center)
        self.canvas = FlowCanvas(content, self.model, on_selection_change=self._on_canvas_selection)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Bind canvas click for palette stamp placement
        self.canvas.bind("<Button-1>", self._on_canvas_click_for_stamp, add="+")

        # Mark as clean after initial load
        self.is_dirty = (flow_id is None)

        # Store reference on root for close_tab lookup
        master.flow_editor = self

    def _create_toolbar(self):
        """Create the editor toolbar."""
        toolbar = ttk.Frame(self.root)
        toolbar.pack(fill=tk.X, padx=4, pady=2)

        self.run_btn = ttk.Button(toolbar, text="▶ Run", command=self.run_flow, bootstyle="success")
        self.run_btn.pack(side=tk.LEFT, padx=1)

        self.stop_btn = ttk.Button(toolbar, text="■ Stop", command=self.stop_flow, state=tk.DISABLED, bootstyle="danger")
        self.stop_btn.pack(side=tk.LEFT, padx=1)

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=4)

        save_btn = ttk.Button(toolbar, text="Save", command=self.save, bootstyle="primary")
        save_btn.pack(side=tk.LEFT, padx=1)

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=4)

        zoom_out_btn = ttk.Button(toolbar, text="−", width=3,
                                  command=lambda: self._zoom(0.9))
        zoom_out_btn.pack(side=tk.LEFT, padx=1)

        zoom_in_btn = ttk.Button(toolbar, text="+", width=3,
                                 command=lambda: self._zoom(1.1))
        zoom_in_btn.pack(side=tk.LEFT, padx=1)

        fit_btn = ttk.Button(toolbar, text="Fit", command=self.fit_to_window)
        fit_btn.pack(side=tk.LEFT, padx=1)

    # ------------------------------------------------------------------
    # Palette stamp integration
    # ------------------------------------------------------------------

    def _on_palette_select(self, type_id):
        """Called when user clicks a block type in the palette."""
        self.canvas.configure(cursor="crosshair")

    def _on_canvas_click_for_stamp(self, event):
        """Intercept canvas clicks for palette stamp placement."""
        selected = self.palette.get_selected_type()
        if selected is not None and self.canvas._hit_node(event.x, event.y) is None:
            # Only place if not clicking on an existing node
            if self.canvas._hit_port(event.x, event.y) is None:
                self.canvas.place_node(selected, event.x, event.y)
                self.canvas.configure(cursor="")
                self.palette.clear_selection()
                self.is_dirty = True
                self._update_title()

    def _on_canvas_selection(self, node_model):
        """Called when a node is selected on the canvas."""
        self.inspector.set_node(node_model)

    def _on_inspector_change(self):
        """Called when the inspector modifies node properties."""
        self.is_dirty = True
        self._update_title()
        self.canvas.render()

    # ------------------------------------------------------------------
    # Zoom helpers
    # ------------------------------------------------------------------

    def _zoom(self, factor):
        """Zoom the canvas by a factor."""
        self.canvas.scale_factor = max(0.2, min(3.0, self.canvas.scale_factor * factor))
        self.canvas.render()

    def fit_to_window(self):
        """Auto-fit all nodes in the viewport."""
        if not self.model.nodes:
            return
        w = max(self.canvas.winfo_width(), 400)
        h = max(self.canvas.winfo_height(), 300)
        min_x = min(n.x for n in self.model.nodes)
        max_x = max(n.x + n.width for n in self.model.nodes)
        min_y = min(n.y for n in self.model.nodes)
        max_y = max(n.y + n.height for n in self.model.nodes)
        content_w = max(max_x - min_x, 200)
        content_h = max(max_y - min_y, 200)
        scale_x = (w - 80) / content_w
        scale_y = (h - 80) / content_h
        scale = min(scale_x, scale_y, 1.5)
        self.canvas.scale_factor = scale
        # Center
        self.canvas.offset_x = (w - content_w * scale) / 2 - min_x * scale
        self.canvas.offset_y = (h - content_h * scale) / 2 - min_y * scale
        self.canvas.render()

    # ------------------------------------------------------------------
    # Title management
    # ------------------------------------------------------------------

    def get_title(self):
        """Return the tab title."""
        title = self.model.name or "New Flow"
        if self.is_dirty:
            title = "*" + title
        return title

    def set_title_callback(self, callback):
        """Set callback for title changes (called by main.py)."""
        self._title_callback = callback

    def _update_title(self):
        """Notify the notebook of a title change."""
        if self._title_callback:
            self._title_callback(self.get_title())

    # ------------------------------------------------------------------
    # Save / Load
    # ------------------------------------------------------------------

    def save(self):
        """Save the flow to the database."""
        self.model.save()
        self.is_dirty = False
        self._update_title()
        if self.on_save_callback:
            self.on_save_callback()
        self._console_log("Flow saved.")

    # ------------------------------------------------------------------
    # Run / Stop
    # ------------------------------------------------------------------

    def run_flow(self):
        """Execute the workflow."""
        from .engine import FlowEngine

        if self._is_running:
            return
        if not self.model.nodes:
            messagebox.showinfo("Run Flow", "Add some blocks to the flow first.")
            return

        # Save before running
        if self.is_dirty:
            self.save()

        self._is_running = True
        self.run_btn.configure(state=tk.DISABLED)
        self.stop_btn.configure(state=tk.NORMAL)
        self.canvas.clear_highlights()
        self.console_text.delete("1.0", tk.END)

        engine = FlowEngine(self.model, self.canvas, self)
        engine.on_complete = self._on_flow_complete
        engine.run()

    def stop_flow(self):
        """Request workflow execution to stop."""
        # The engine checks this flag
        self._is_running = False
        self._console_log("⏹ Stopping flow...")

    def _on_flow_complete(self):
        """Called when execution finishes."""
        self._is_running = False
        self.run_btn.configure(state=tk.NORMAL)
        self.stop_btn.configure(state=tk.DISABLED)

    # ------------------------------------------------------------------
    # Console output (used by FlowEngine)
    # ------------------------------------------------------------------

    def _console_log(self, message):
        """Append a message to the console."""
        self.console_text.insert(tk.END, message + "\n")
        self.console_text.see(tk.END)

    def log(self, *args):
        """Public console.log() compatible interface."""
        self._console_log(" ".join(str(a) for a in args))

    def info(self, *args):
        """Public console.info() compatible interface."""
        msg = " ".join(str(a) for a in args)
        self._console_log(f"[INFO] {msg}")

    def error(self, *args):
        """Public console.error() compatible interface."""
        msg = " ".join(str(a) for a in args)
        self._console_log(f"[ERROR] {msg}")
