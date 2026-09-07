import os
import sys
import time
import json
import uuid
import copy
import asyncio
from typing import Optional, Dict, Any, List, Tuple, Set

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFrame, QSplitter, QListWidget, QListWidgetItem, QLineEdit,
    QTextEdit, QComboBox, QDoubleSpinBox, QSpinBox, QCheckBox,
    QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsItem,
    QGraphicsPathItem, QMessageBox, QFileDialog, QGroupBox, QFormLayout,
    QStyleOptionGraphicsItem, QTableWidget, QTableWidgetItem, QHeaderView,
    QMenu, QGraphicsSceneContextMenuEvent, QInputDialog, QSizePolicy,
    QTabWidget, QToolButton, QDialog, QProgressBar
)
from PyQt6.QtGui import (
    QColor, QPen, QBrush, QFont, QPainter, QPainterPath,
    QWheelEvent, QMouseEvent, QContextMenuEvent, QAction, QKeyEvent, QKeySequence, QIcon, QDesktopServices, QPixmap
)
from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal, QUrl

from engine.workflow_engine import (
    WorkflowDAG, WorkflowNode, WorkflowEdge, NodeType,
    WorkflowDAGRunner, MultiWorkflowRunner, WorkflowExecutionState,
    NODE_METADATA, get_node_metadata, get_node_description
)
from storage.profile_manager import ProfileManager


WORKFLOWS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "storage", "workflows")


def safe_float(val: Any, default: float = 0.0) -> float:
    """Safely converts Any | None to float without raising TypeError or ValueError."""
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


# Color Palette constants for Nodes
NODE_COLORS = {
    NodeType.START: QColor("#3B82F6"),             # Blue
    NodeType.NAVIGATE: QColor("#2563EB"),          # Deep Blue
    NodeType.NEW_TAB: QColor("#0284C7"),           # Sky Blue
    NodeType.SWITCH_TAB: QColor("#0EA5E9"),        # Cyan
    NodeType.CLOSE_TAB: QColor("#64748B"),         # Slate
    NodeType.SCROLL: QColor("#0284C7"),            # Blue
    NodeType.REFRESH: QColor("#64748B"),           # Slate
    NodeType.GO_BACK: QColor("#64748B"),           # Slate
    NodeType.CLEAR_CACHE: QColor("#475569"),        # Steel
    NodeType.VLA_CLICK: QColor("#0D9488"),         # Teal
    NodeType.VLA_TYPE: QColor("#4F46E5"),          # Indigo
    NodeType.KEY_PRESS: QColor("#6366F1"),         # Violet
    NodeType.HOVER: QColor("#0D9488"),             # Teal
    NodeType.DRAG_DROP: QColor("#0D9488"),          # Teal
    NodeType.SOLVE_CAPTCHA: QColor("#7C3AED"),     # Purple
    NodeType.ROTATE_PROXY: QColor("#6D28D9"),      # Deep Purple
    NodeType.FINGERPRINT_MORPH: QColor("#7C3AED"), # Purple
    NodeType.ADVERSARIAL_AUDIT: QColor("#475569"), # Steel
    NodeType.PRE_ACTION_CHECK: QColor("#475569"),  # Steel
    NodeType.CONDITION: QColor("#D97706"),         # Amber
    NodeType.AI_DECISION: QColor("#9333EA"),       # Purple
    NodeType.AI_MODEL_TASK: QColor("#8B5CF6"),     # Violet / AI Task
    NodeType.LOOP: QColor("#EA580C"),              # Orange
    NodeType.WAIT: QColor("#D97706"),              # Amber
    NodeType.EXTRACT_DATA: QColor("#0D9488"),      # Teal
    NodeType.JAVASCRIPT_EVAL: QColor("#475569"),   # Slate
    NodeType.SCREENSHOT: QColor("#0284C7"),        # Sky Blue
    NodeType.DOWNLOAD_WAIT: QColor("#D97706"),     # Amber
    NodeType.TERMINATE: QColor("#475569"),         # Slate
    NodeType.CHESS_SOLVER: QColor("#0EA5E9"),      # Cyan
    NodeType.POKER_SOLVER: QColor("#10B981")       # Emerald / Green
}


class NodePortGraphicsItem(QGraphicsRectItem):
    """Visual interactive connector socket on a node."""
    def __init__(self, port_name: str, is_output: bool, parent_node_item: 'NodeGraphicsItem'):
        super().__init__(-5, -5, 10, 10, parent_node_item)
        self.port_name = port_name
        self.is_output = is_output
        self.parent_node_item = parent_node_item
        self.setAcceptHoverEvents(True)

        if not is_output:
            self.brush_color = QColor("#94A3B8")
        elif port_name in ["true", "call"]:
            self.brush_color = QColor("#10B981")
        elif port_name in ["false", "fold"]:
            self.brush_color = QColor("#EF4444")
        elif port_name in ["raise"]:
            self.brush_color = QColor("#8B5CF6")
        elif port_name in ["loop_body", "checkmate"]:
            self.brush_color = QColor("#F97316")
        elif port_name == "loop_exit":
            self.brush_color = QColor("#38BDF8")
        else:
            self.brush_color = QColor("#38BDF8")

        self.setBrush(QBrush(self.brush_color))
        self.setPen(QPen(QColor("#0F172A"), 1.5))

    def get_scene_pos(self) -> QPointF:
        return self.scenePos()


class EdgeGraphicsItem(QGraphicsPathItem):
    """Visual Bézier curve representing a directed workflow edge."""
    def __init__(self, edge: WorkflowEdge, source_item: 'NodeGraphicsItem', target_item: 'NodeGraphicsItem', parent=None):
        super().__init__(parent)
        self.edge = edge
        self.source_item = source_item
        self.target_item = target_item
        self.setZValue(-1)
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        
        pen_color = QColor("#64748B")
        if edge.source_port in ["true", "call"]:
            pen_color = QColor("#10B981")
        elif edge.source_port in ["false", "fold"]:
            pen_color = QColor("#EF4444")
        elif edge.source_port in ["raise"]:
            pen_color = QColor("#8B5CF6")
        elif edge.source_port in ["loop_body", "checkmate"]:
            pen_color = QColor("#F97316")
        elif edge.source_port == "loop_exit":
            pen_color = QColor("#38BDF8")

        self._pen = QPen(pen_color, 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        self.setPen(self._pen)
        self.update_path()

    def update_path(self):
        src_port = self.source_item.get_port_pos(self.edge.source_port)
        dst_port = self.target_item.get_port_pos("in")
        
        path = QPainterPath()
        path.moveTo(src_port)
        
        dx = dst_port.x() - src_port.x()
        ctrl_offset = max(45.0, abs(dx) * 0.5)
        
        ctrl1 = QPointF(src_port.x() + ctrl_offset, src_port.y())
        ctrl2 = QPointF(dst_port.x() - ctrl_offset, dst_port.y())
        
        path.cubicTo(ctrl1, ctrl2, dst_port)
        self.setPath(path)

    def contextMenuEvent(self, event: Optional[QGraphicsSceneContextMenuEvent]):
        if not event:
            return
        sc = self.scene()
        views = sc.views() if sc else []
        view = views[0] if views else None
        parent_builder = getattr(view, "builder_view", None) if view else None
        menu = QMenu()
        menu.setStyleSheet("QMenu { background-color: #1E293B; color: #F1F5F9; border: 1px solid #334155; padding: 4px; } QMenu::item:selected { background-color: #334155; }")
        act_del = menu.addAction("✂️ Delete Connection")
        res = menu.exec(event.screenPos())
        if res and res == act_del and parent_builder:
            parent_builder._delete_edge(self.edge.id)


class NodeGraphicsItem(QGraphicsRectItem):
    """Rich interactive node on the visual canvas."""
    def __init__(self, node: WorkflowNode, parent=None):
        super().__init__(-95, -45, 190, 90, parent)
        self.node = node
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable |
            QGraphicsItem.GraphicsItemFlag.ItemIsSelectable |
            QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setAcceptHoverEvents(True)
        self._status = "idle"
        self.live_badge_text = ""
        self.port_items: Dict[str, NodePortGraphicsItem] = {}
        self.base_color = NODE_COLORS.get(self.node.node_type, QColor("#3B82F6"))
        self.setBrush(QBrush(QColor("#1E293B")))
        self.setPen(QPen(QColor("#334155"), 1.5))
        
        meta = get_node_metadata(self.node.node_type)
        desc = meta.get("description", "")
        cat = meta.get("category", "")
        self.setToolTip(f"<b>{self.node.title}</b> ({meta.get('label', self.node.node_type.value)})<br>"
                        f"<span style='color: #94A3B8;'>{cat}</span><br><br>"
                        f"{desc}")
        self._create_ports()

    def _create_ports(self):
        if self.node.node_type != NodeType.START:
            in_port = NodePortGraphicsItem("in", is_output=False, parent_node_item=self)
            in_port.setPos(-95, 0)
            self.port_items["in"] = in_port

        out_ports = self.node.get_output_ports()
        if len(out_ports) == 1:
            out_port = NodePortGraphicsItem(out_ports[0], is_output=True, parent_node_item=self)
            out_port.setPos(95, 0)
            self.port_items[out_ports[0]] = out_port
        elif len(out_ports) == 2:
            p1 = NodePortGraphicsItem(out_ports[0], is_output=True, parent_node_item=self)
            p1.setPos(95, -18)
            self.port_items[out_ports[0]] = p1

            p2 = NodePortGraphicsItem(out_ports[1], is_output=True, parent_node_item=self)
            p2.setPos(95, 18)
            self.port_items[out_ports[1]] = p2
        elif len(out_ports) > 2:
            step = 60.0 / (len(out_ports) - 1)
            start_y = -30.0
            for idx, p_name in enumerate(out_ports):
                p = NodePortGraphicsItem(p_name, is_output=True, parent_node_item=self)
                p.setPos(95, start_y + idx * step)
                self.port_items[p_name] = p

    def get_port_pos(self, port_name: str) -> QPointF:
        if port_name in self.port_items:
            return self.port_items[port_name].scenePos()
        if port_name == "in":
            return self.mapToScene(QPointF(-95, 0))
        return self.mapToScene(QPointF(95, 0))

    def set_execution_status(self, status: str):
        self._status = status
        if status == "running":
            self.setPen(QPen(QColor("#38BDF8"), 2.5))
        elif status == "paused":
            self.setPen(QPen(QColor("#F59E0B"), 3.0)) # Amber highlight for Breakpoint & Stepping Pause
        elif status == "success":
            self.setPen(QPen(QColor("#10B981"), 2.5))
        elif status == "error":
            self.setPen(QPen(QColor("#EF4444"), 2.5))
        else:
            self.setPen(QPen(QColor("#334155"), 1.5))
        self.update()

    def set_live_badge(self, text: str):
        self.live_badge_text = text
        self.update()

    def paint(self, painter: Optional[QPainter], option: Optional[QStyleOptionGraphicsItem], widget: Optional[QWidget] = None):
        if not painter:
            return
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Main Body
        bg_rect = QRectF(-95, -45, 190, 90)
        painter.setBrush(QBrush(QColor("#1E293B")))
        border_pen = QPen(QColor("#475569") if self.isSelected() else QColor("#334155"), 2.0 if self.isSelected() else 1.0)
        if self._status == "paused":
            border_pen = QPen(QColor("#F59E0B"), 3.0)
        elif self._status == "running":
            border_pen = QPen(QColor("#38BDF8"), 2.5)
        painter.setPen(border_pen)
        painter.drawRoundedRect(bg_rect, 6, 6)

        # Header Pill
        header_rect = QRectF(-95, -45, 190, 24)
        painter.setBrush(QBrush(self.base_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(header_rect, 6, 6)
        painter.drawRect(QRectF(-95, -30, 190, 9))  # flatten bottom corners of header

        # Header Text
        painter.setPen(QPen(QColor("#FFFFFF")))
        painter.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        painter.drawText(header_rect, Qt.AlignmentFlag.AlignCenter, self.node.node_type.value.upper())

        # Breakpoint Indicator (Prominent Red Dot)
        if self.node.is_breakpoint:
            painter.setBrush(QBrush(QColor("#EF4444")))
            painter.setPen(QPen(QColor("#FFFFFF"), 1.5))
            painter.drawEllipse(QRectF(-88, -39, 12, 12))

        # Title
        painter.setPen(QPen(QColor("#F1F5F9")))
        painter.setFont(QFont("Segoe UI", 9))
        body_rect = QRectF(-88, -16, 176, 42)
        painter.drawText(body_rect, Qt.AlignmentFlag.AlignHCenter | Qt.TextFlag.TextWordWrap, self.node.title)

        # Live Result Badge (Sub-Pill)
        if getattr(self, "live_badge_text", ""):
            badge_rect = QRectF(-88, 26, 176, 15)
            painter.setBrush(QBrush(QColor("#1E1B4B")))
            painter.setPen(QPen(QColor("#6366F1"), 1.0))
            painter.drawRoundedRect(badge_rect, 3, 3)
            painter.setPen(QPen(QColor("#C7D2FE")))
            painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
            painter.drawText(badge_rect, Qt.AlignmentFlag.AlignCenter, self.live_badge_text)

        # Port Labels
        if self.node.node_type in [NodeType.CONDITION, NodeType.AI_DECISION]:
            painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
            painter.setPen(QPen(QColor("#10B981")))
            painter.drawText(QRectF(50, -25, 38, 14), Qt.AlignmentFlag.AlignRight, "TRUE")
            painter.setPen(QPen(QColor("#EF4444")))
            painter.drawText(QRectF(50, 10, 38, 14), Qt.AlignmentFlag.AlignRight, "FALSE")
        elif self.node.node_type == NodeType.LOOP:
            painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
            painter.setPen(QPen(QColor("#F97316")))
            painter.drawText(QRectF(45, -25, 43, 14), Qt.AlignmentFlag.AlignRight, "BODY")
            painter.setPen(QPen(QColor("#38BDF8")))
            painter.drawText(QRectF(45, 10, 43, 14), Qt.AlignmentFlag.AlignRight, "EXIT")
        elif self.node.node_type == NodeType.CHESS_SOLVER:
            painter.setFont(QFont("Segoe UI", 7, QFont.Weight.Bold))
            painter.setPen(QPen(QColor("#38BDF8")))
            painter.drawText(QRectF(45, -25, 43, 14), Qt.AlignmentFlag.AlignRight, "MOVE")
            painter.setPen(QPen(QColor("#F97316")))
            painter.drawText(QRectF(45, 10, 43, 14), Qt.AlignmentFlag.AlignRight, "MATE")
        elif self.node.node_type == NodeType.POKER_SOLVER:
            painter.setFont(QFont("Segoe UI", 6, QFont.Weight.Bold))
            painter.setPen(QPen(QColor("#38BDF8")))
            painter.drawText(QRectF(45, -34, 43, 12), Qt.AlignmentFlag.AlignRight, "OUT")
            painter.setPen(QPen(QColor("#EF4444")))
            painter.drawText(QRectF(45, -15, 43, 12), Qt.AlignmentFlag.AlignRight, "FOLD")
            painter.setPen(QPen(QColor("#10B981")))
            painter.drawText(QRectF(45, 4, 43, 12), Qt.AlignmentFlag.AlignRight, "CALL")
            painter.setPen(QPen(QColor("#8B5CF6")))
            painter.drawText(QRectF(45, 23, 43, 12), Qt.AlignmentFlag.AlignRight, "RAISE")

    def contextMenuEvent(self, event: Optional[QGraphicsSceneContextMenuEvent]):
        if not event:
            return
        sc = self.scene()
        views = sc.views() if sc else []
        view = views[0] if views else None
        parent_builder = getattr(view, "builder_view", None) if view else None
        
        menu = QMenu()
        menu.setStyleSheet("QMenu { background-color: #1E293B; color: #F1F5F9; border: 1px solid #334155; padding: 4px; } QMenu::item:selected { background-color: #334155; }")
        
        act_entry = menu.addAction("🚩 Set as Start / Entry Node")
        act_dup = menu.addAction("📋 Duplicate Node")
        act_bp = menu.addAction(f"🔴 {'Disable' if self.node.is_breakpoint else 'Enable'} Breakpoint")
        menu.addSeparator()
        act_del = menu.addAction("🗑️ Delete Node")
        
        res = menu.exec(event.screenPos())
        if not parent_builder or not res:
            return
            
        if res == act_entry:
            parent_builder._set_entry_node(self.node.id)
        elif res == act_dup:
            parent_builder._duplicate_node(self.node.id)
        elif res == act_bp:
            parent_builder._toggle_node_breakpoint(self.node.id)
        elif res == act_del:
            parent_builder._delete_node(self.node.id)

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value: Any) -> Any:
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange and isinstance(value, QPointF):
            self.node.position = {"x": value.x(), "y": value.y()}
            sc = self.scene()
            if isinstance(sc, WorkflowGraphicsScene):
                sc.update_connected_edges(self.node.id)
        return super().itemChange(change, value)


class WorkflowGraphicsScene(QGraphicsScene):
    """Canvas scene supporting blueprint grid and edge tracking."""
    def __init__(self, parent=None):
        super().__init__(-3000, -3000, 6000, 6000, parent)
        self.setBackgroundBrush(QBrush(QColor("#0B0F19")))
        self.edge_items: Dict[str, EdgeGraphicsItem] = {}

    def drawBackground(self, painter: Optional[QPainter], rect: QRectF):
        super().drawBackground(painter, rect)
        if not painter:
            return
        painter.setPen(QPen(QColor("#1E293B"), 1))
        grid_size = 25
        left = int(rect.left()) - (int(rect.left()) % grid_size)
        top = int(rect.top()) - (int(rect.top()) % grid_size)
        
        for x in range(left, int(rect.right()), grid_size):
            for y in range(top, int(rect.bottom()), grid_size):
                painter.drawPoint(x, y)

    def update_connected_edges(self, node_id: str):
        for eitem in self.edge_items.values():
            if eitem.edge.source_node_id == node_id or eitem.edge.target_node_id == node_id:
                eitem.update_path()


class ZoomableGraphicsView(QGraphicsView):
    """View with zooming, panning, and shortcuts."""
    def __init__(self, scene: QGraphicsScene, builder_view: Optional['WorkflowBuilderView'] = None, parent=None):
        super().__init__(scene, parent)
        self.builder_view = builder_view
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)

    def zoom_in(self):
        self.scale(1.2, 1.2)

    def zoom_out(self):
        self.scale(1.0 / 1.2, 1.0 / 1.2)

    def zoom_reset(self):
        self.resetTransform()

    def wheelEvent(self, event: Optional[QWheelEvent]):
        if not event:
            return
        zoom_in_factor = 1.15
        zoom_out_factor = 1.0 / zoom_in_factor
        if event.angleDelta().y() > 0:
            self.scale(zoom_in_factor, zoom_in_factor)
        else:
            self.scale(zoom_out_factor, zoom_out_factor)

    def keyPressEvent(self, event: Optional[QKeyEvent]):
        if not event or not self.builder_view:
            super().keyPressEvent(event)
            return

        if event.key() in [Qt.Key.Key_Delete, Qt.Key.Key_Backspace]:
            self.builder_view._delete_selected_items()
            event.accept()
        elif event.key() == Qt.Key.Key_F9:
            self.builder_view._toggle_selected_breakpoint()
            event.accept()
        elif event.key() == Qt.Key.Key_F10:
            self.builder_view._step_workflow()
            event.accept()
        elif event.key() == Qt.Key.Key_F5:
            self.builder_view._toggle_pause_resume()
            event.accept()
        elif event.matches(QKeySequence.StandardKey.Save):
            self.builder_view._save_project(save_as=False)
            event.accept()
        elif event.matches(QKeySequence.StandardKey.Undo):
            self.builder_view._undo()
            event.accept()
        elif event.matches(QKeySequence.StandardKey.Redo):
            self.builder_view._redo()
            event.accept()
        else:
            super().keyPressEvent(event)

    def contextMenuEvent(self, event: Optional[QContextMenuEvent]):
        if not event or not self.builder_view:
            return
        item = self.itemAt(event.pos())
        if item:
            super().contextMenuEvent(event)
            return

        menu = QMenu(self)
        menu.setStyleSheet("QMenu { background-color: #1E293B; color: #F1F5F9; border: 1px solid #334155; padding: 4px; } QMenu::item:selected { background-color: #334155; }")
        
        act_save = menu.addAction("💾 Save Workflow (Ctrl+S)")
        if act_save:
            act_save.triggered.connect(lambda: self.builder_view._save_project(save_as=False))

        act_layout = menu.addAction("📐 Auto-Layout Nodes")
        if act_layout:
            act_layout.triggered.connect(self.builder_view._auto_layout)

        act_fit = menu.addAction("🔍 Fit Graph to View")
        if act_fit:
            act_fit.triggered.connect(self.builder_view._fit_to_view)

        menu.addSeparator()
        act_undo = menu.addAction("↩️ Undo (Ctrl+Z)")
        if act_undo:
            act_undo.setEnabled(len(self.builder_view._undo_stack) > 0)
            act_undo.triggered.connect(self.builder_view._undo)

        act_redo = menu.addAction("↪️ Redo (Ctrl+Y)")
        if act_redo:
            act_redo.setEnabled(len(self.builder_view._redo_stack) > 0)
            act_redo.triggered.connect(self.builder_view._redo)

        menu.addSeparator()
        act_clear = menu.addAction("🗑️ Clear Canvas")
        if act_clear:
            act_clear.triggered.connect(self.builder_view._clear_canvas)

        menu.exec(event.globalPos())


class WorkflowMultiProfileDialog(QDialog):
    """
    Advanced Multi-Profile Selector for Concurrent Workflow Executions:
    - Search profiles by name, ID, or engine.
    - Filter by engine (All, Camoufox, Chromium) and running status.
    - Quick actions: Select All, Select Running, Invert, Clear.
    - Concurrency worker spinbox (1 to 20 parallel browser workers).
    - Selected profile list with checkboxes.
    """
    def __init__(self, profiles: List[Dict[str, Any]], running_ids: Set[str], initially_selected: Optional[List[str]] = None, current_concurrency: int = 3, parent=None):
        super().__init__(parent)
        self.setWindowTitle("👥 Multi-Browser Profile Selection & Concurrency")
        self.setMinimumSize(620, 540)
        self.setStyleSheet("""
            QDialog {
                background-color: #0B0F19;
                color: #F1F5F9;
                font-family: 'Segoe UI', Inter, sans-serif;
            }
            QLabel {
                color: #CBD5E1;
            }
            QLineEdit {
                background-color: #020617;
                color: #F8FAFC;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 6px 10px;
            }
            QTableWidget {
                background-color: #020617;
                color: #F1F5F9;
                border: 1px solid #1E293B;
                border-radius: 6px;
                gridline-color: #1E293B;
            }
            QHeaderView::section {
                background-color: #0F172A;
                color: #94A3B8;
                font-weight: 600;
                border: none;
                padding: 6px;
            }
            QPushButton {
                background-color: #1E293B;
                color: #F8FAFC;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #334155;
            }
            QSpinBox {
                background-color: #020617;
                color: #F8FAFC;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 4px 8px;
            }
            QCheckBox {
                color: #E2E8F0;
            }
        """)
        self.profiles = profiles
        self.running_ids = running_ids
        self.selected_ids: Set[str] = set(initially_selected) if initially_selected else set()
        self.concurrency = current_concurrency
        self._init_ui()
        self._populate_table()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Header
        header = QLabel("👥 Multi-Browser Execution Configuration")
        header.setStyleSheet("font-size: 15px; font-weight: bold; color: #38BDF8;")
        layout.addWidget(header)

        desc = QLabel("Select the browser profiles to run this visual workflow across concurrently, and specify max parallel workers.")
        desc.setStyleSheet("font-size: 11px; color: #94A3B8;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Search & Filter Row
        filter_row = QHBoxLayout()
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("🔍 Search profile name, ID, or engine...")
        self.txt_search.textChanged.connect(self._filter_table)
        filter_row.addWidget(self.txt_search)

        self.combo_engine_filter = QComboBox()
        self.combo_engine_filter.setStyleSheet("background-color: #020617; color: #F8FAFC; border: 1px solid #334155; border-radius: 6px; padding: 4px 8px;")
        self.combo_engine_filter.addItem("All Engines", "all")
        self.combo_engine_filter.addItem("Camoufox Only", "camoufox")
        self.combo_engine_filter.addItem("Chromium Only", "chromium")
        self.combo_engine_filter.currentIndexChanged.connect(self._filter_table)
        filter_row.addWidget(self.combo_engine_filter)
        layout.addLayout(filter_row)

        # Quick Action Buttons Row
        actions_row = QHBoxLayout()
        btn_all = QPushButton("Select All")
        btn_all.clicked.connect(self._select_all)
        actions_row.addWidget(btn_all)

        btn_running = QPushButton("Select Running Only")
        btn_running.clicked.connect(self._select_running)
        actions_row.addWidget(btn_running)

        btn_invert = QPushButton("Invert")
        btn_invert.clicked.connect(self._invert_selection)
        actions_row.addWidget(btn_invert)

        btn_clear = QPushButton("Clear Selection")
        btn_clear.clicked.connect(self._clear_selection)
        actions_row.addWidget(btn_clear)

        actions_row.addStretch()
        layout.addLayout(actions_row)

        # Table of Profiles
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Select", "Profile Name", "Engine", "Status"])
        hdr = self.table.horizontalHeader()
        if hdr:
            hdr.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            hdr.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
            hdr.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
            hdr.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.table)

        # Concurrency Control Section
        concurrency_box = QGroupBox("⚡ Concurrency & Worker Throttling")
        concurrency_box.setStyleSheet("QGroupBox { font-weight: bold; color: #38BDF8; border: 1px solid #1E293B; border-radius: 6px; margin-top: 6px; padding-top: 12px; }")
        conc_layout = QHBoxLayout(concurrency_box)
        
        lbl_conc = QLabel("Max Parallel Browsers:")
        lbl_conc.setStyleSheet("color: #E2E8F0; font-size: 11px;")
        conc_layout.addWidget(lbl_conc)

        self.spin_concurrency = QSpinBox()
        self.spin_concurrency.setRange(1, 20)
        self.spin_concurrency.setValue(self.concurrency)
        self.spin_concurrency.setFixedWidth(70)
        conc_layout.addWidget(self.spin_concurrency)

        lbl_conc_hint = QLabel("(Higher = faster parallel execution, but requires more RAM/CPU)")
        lbl_conc_hint.setStyleSheet("color: #64748B; font-size: 10px;")
        conc_layout.addWidget(lbl_conc_hint)
        conc_layout.addStretch()
        layout.addWidget(concurrency_box)

        # Bottom summary & buttons
        bottom_row = QHBoxLayout()
        self.lbl_selected_count = QLabel("Selected: 0 profiles")
        self.lbl_selected_count.setStyleSheet("font-weight: bold; color: #38BDF8; font-size: 12px;")
        bottom_row.addWidget(self.lbl_selected_count)
        bottom_row.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        bottom_row.addWidget(btn_cancel)

        btn_ok = QPushButton("Apply Multi-Selection")
        btn_ok.setStyleSheet("background-color: #0369A1; color: #FFFFFF; font-weight: bold; padding: 6px 16px; border: 1px solid #38BDF8;")
        btn_ok.clicked.connect(self._on_apply)
        bottom_row.addWidget(btn_ok)

        layout.addLayout(bottom_row)

    def _populate_table(self):
        self.table.setRowCount(len(self.profiles))
        for row, prof in enumerate(self.profiles):
            pid = prof.get("id", "")
            pname = prof.get("name", "Unnamed Profile")
            engine = prof.get("engine", "camoufox").capitalize()
            is_running = pid in self.running_ids

            chk = QCheckBox()
            chk.setChecked(pid in self.selected_ids)
            chk.setProperty("profile_id", pid)
            chk.stateChanged.connect(self._on_chk_state_changed)
            self.table.setCellWidget(row, 0, chk)

            item_name = QTableWidgetItem(f"{pname} ({pid[:8]})")
            item_name.setData(Qt.ItemDataRole.UserRole, pid)
            self.table.setItem(row, 1, item_name)

            item_engine = QTableWidgetItem(engine)
            self.table.setItem(row, 2, item_engine)

            status_str = "🟢 Running" if is_running else "⚪ Stopped"
            item_status = QTableWidgetItem(status_str)
            self.table.setItem(row, 3, item_status)

        self._update_selected_count()

    def _on_chk_state_changed(self):
        self.selected_ids.clear()
        for r in range(self.table.rowCount()):
            chk = self.table.cellWidget(r, 0)
            if chk and isinstance(chk, QCheckBox) and chk.isChecked():
                pid = chk.property("profile_id")
                if pid:
                    self.selected_ids.add(pid)
        self._update_selected_count()

    def _update_selected_count(self):
        self.lbl_selected_count.setText(f"Selected: {len(self.selected_ids)} of {len(self.profiles)} profiles")

    def _filter_table(self):
        query = self.txt_search.text().lower().strip()
        engine_filter = self.combo_engine_filter.currentData()

        for r in range(self.table.rowCount()):
            item_name = self.table.item(r, 1)
            item_engine = self.table.item(r, 2)
            if not item_name or not item_engine:
                continue

            name_match = query in item_name.text().lower() or (query in (item_name.data(Qt.ItemDataRole.UserRole) or "").lower())
            engine_match = True
            if engine_filter != "all":
                engine_match = engine_filter in item_engine.text().lower()

            self.table.setRowHidden(r, not (name_match and engine_match))

    def _select_all(self):
        for r in range(self.table.rowCount()):
            if not self.table.isRowHidden(r):
                chk = self.table.cellWidget(r, 0)
                if chk and isinstance(chk, QCheckBox):
                    chk.setChecked(True)

    def _select_running(self):
        for r in range(self.table.rowCount()):
            chk = self.table.cellWidget(r, 0)
            if chk and isinstance(chk, QCheckBox):
                pid = chk.property("profile_id")
                chk.setChecked(pid in self.running_ids)

    def _invert_selection(self):
        for r in range(self.table.rowCount()):
            if not self.table.isRowHidden(r):
                chk = self.table.cellWidget(r, 0)
                if chk and isinstance(chk, QCheckBox):
                    chk.setChecked(not chk.isChecked())

    def _clear_selection(self):
        for r in range(self.table.rowCount()):
            chk = self.table.cellWidget(r, 0)
            if chk and isinstance(chk, QCheckBox):
                chk.setChecked(False)

    def _on_apply(self):
        self.concurrency = self.spin_concurrency.value()
        self.accept()

    def get_selected_profiles(self) -> List[str]:
        return list(self.selected_ids)

    def get_concurrency(self) -> int:
        return self.concurrency


class WorkflowBuilderView(QWidget):
    """
    Next-Gen Visual Workflow Builder & Automation Studio:
    - Full-height categorized & searchable Operations Palette on the left.
    - Streamlined File / Folder Manager integration.
    - Multi-Browser Concurrent Workflow Runner with Concurrency control.
    - Large multi-tab telemetry console with Live Logs, Multi-Browser Matrix, Variables & Python Code.
    - Professional, cohesive dark design with clean typography and no rainbow buttons.
    """
    def __init__(self, profile_manager: Optional[ProfileManager] = None, launcher: Optional[Any] = None, parent=None):
        super().__init__(parent)
        self.profile_manager = profile_manager or ProfileManager()
        self.launcher = launcher
        self.dag = WorkflowDAG(name="E-Commerce Farming Campaign")
        self.runner: Optional[WorkflowDAGRunner] = None
        self.multi_runner: Optional[MultiWorkflowRunner] = None
        self.multi_profile_ids: List[str] = []
        self.multi_concurrency: int = 3
        self.is_multi_mode: bool = False
        self.node_items: Dict[str, NodeGraphicsItem] = {}
        self.selected_node: Optional[WorkflowNode] = None
        self.current_project_filepath: Optional[str] = None

        self._undo_stack: List[Dict[str, Any]] = []
        self._redo_stack: List[Dict[str, Any]] = []

        self.auto_connect_enabled: bool = True
        self._last_added_node_id: Optional[str] = None

        self._ensure_workflows_dir()
        self._init_ui()
        self.reload_profiles()
        self._load_starter_template(0)

    def _ensure_workflows_dir(self):
        os.makedirs(WORKFLOWS_DIR, exist_ok=True)

    def _push_undo_state(self):
        state = copy.deepcopy(self.dag.to_dict())
        self._undo_stack.append(state)
        if len(self._undo_stack) > 30:
            self._undo_stack.pop(0)
        self._redo_stack.clear()
        self._update_undo_redo_buttons()

    def _undo(self):
        if not self._undo_stack:
            return
        current_state = copy.deepcopy(self.dag.to_dict())
        self._redo_stack.append(current_state)
        prev_state = self._undo_stack.pop()
        self.dag = WorkflowDAG.from_dict(prev_state)
        self._render_dag_on_canvas()
        self._update_node_dropdowns()
        self._update_undo_redo_buttons()
        self._update_title_header()
        self._refresh_diagnostics()
        self.txt_logs.append("↩️ Action Undone.")

    def _redo(self):
        if not self._redo_stack:
            return
        current_state = copy.deepcopy(self.dag.to_dict())
        self._undo_stack.append(current_state)
        next_state = self._redo_stack.pop()
        self.dag = WorkflowDAG.from_dict(next_state)
        self._render_dag_on_canvas()
        self._update_node_dropdowns()
        self._update_undo_redo_buttons()
        self._update_title_header()
        self._refresh_diagnostics()
        self.txt_logs.append("↪️ Action Redone.")

    def _update_undo_redo_buttons(self):
        if hasattr(self, "btn_undo"):
            self.btn_undo.setEnabled(len(self._undo_stack) > 0)
        if hasattr(self, "btn_redo"):
            self.btn_redo.setEnabled(len(self._redo_stack) > 0)

    def _update_title_header(self):
        pass

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Global Splitter (Left: Full Palette | Center: Canvas & Bottom Logs | Right: Properties)
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(main_splitter)

        # -------------------------------------------------------------
        # 1. LEFT PANEL: Full-Height Searchable Operations Palette
        # -------------------------------------------------------------
        left_panel = QWidget()
        left_panel.setMinimumWidth(230)
        left_panel.setMaximumWidth(280)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        palette_group = QGroupBox("🧩 Operations Palette")
        palette_group.setStyleSheet("QGroupBox { font-weight: bold; color: #94A3B8; border: 1px solid #334155; border-radius: 6px; margin-top: 6px; padding-top: 10px; }")
        pal_vbox = QVBoxLayout(palette_group)
        pal_vbox.setSpacing(6)

        # Search Bar
        self.txt_search_nodes = QLineEdit()
        self.txt_search_nodes.setPlaceholderText("🔍 Filter operations...")
        self.txt_search_nodes.setStyleSheet("background-color: #0F172A; color: #F1F5F9; border: 1px solid #334155; border-radius: 4px; padding: 5px; font-size: 11px;")
        self.txt_search_nodes.textChanged.connect(self._filter_palette_items)
        pal_vbox.addWidget(self.txt_search_nodes)

        # Quick Templates Dropdown
        lbl_tmpl = QLabel("Quick Templates:")
        lbl_tmpl.setStyleSheet("color: #64748B; font-size: 10px; font-weight: bold;")
        pal_vbox.addWidget(lbl_tmpl)

        self.combo_templates = QComboBox()
        self.combo_templates.setStyleSheet("background-color: #0F172A; color: #F1F5F9; border: 1px solid #334155; border-radius: 4px; padding: 4px; font-size: 11px;")
        self.combo_templates.addItems([
            "🛒 1. E-Commerce Warmup & Search",
            "📱 2. Social Media Feed Scroll & Dwell",
            "🛡️ 3. Cloudflare Turnstile Bypass",
            "🔄 4. Multi-Page Data Scrape Loop",
            "♟️ 5. Autonomous Browser Chess Bot (Stockfish)",
            "🃏 6. Texas Hold'em Poker GTO Auto-Player"
        ])
        self.combo_templates.currentIndexChanged.connect(self._load_starter_template)
        pal_vbox.addWidget(self.combo_templates)

        # Operations List (Full Height)
        self.node_palette_list = QListWidget()
        self.node_palette_list.setStyleSheet("""
            QListWidget {
                background-color: #0F172A;
                border: 1px solid #334155;
                border-radius: 4px;
                color: #F1F5F9;
                font-size: 11px;
                padding: 2px;
            }
            QListWidget::item {
                padding: 6px 8px;
                border-bottom: 1px solid #1E293B;
                border-radius: 3px;
            }
            QListWidget::item:hover {
                background-color: #1E293B;
            }
            QListWidget::item:selected {
                background-color: #334155;
                color: #38BDF8;
                font-weight: bold;
            }
        """)
        self.node_palette_list.itemDoubleClicked.connect(self._on_palette_item_double_clicked)

        self._all_palette_items = []
        for ntype in NodeType:
            meta = get_node_metadata(ntype)
            label = meta.get("label", ntype.value)
            desc = f"<b>{label}</b><br><span style='color: #94A3B8;'>[{meta.get('category', 'Allgemein')}]</span><br><br>{meta.get('description', '')}"
            self._all_palette_items.append((label, ntype, desc))

        for label, ntype, desc in self._all_palette_items:
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, ntype)
            item.setToolTip(desc)
            self.node_palette_list.addItem(item)

        pal_vbox.addWidget(self.node_palette_list)

        self.chk_auto_connect_palette = QCheckBox("🔗 Auto-Connect sequential")
        self.chk_auto_connect_palette.setStyleSheet("color: #38BDF8; font-size: 11px; font-weight: 600; padding: 2px 0;")
        self.chk_auto_connect_palette.setToolTip("Neu hinzugefügte Nodes automatisch aufsteigend an den vorherigen/ausgewählten Node anschließen")
        self.chk_auto_connect_palette.setChecked(True)
        self.chk_auto_connect_palette.toggled.connect(self._on_auto_connect_toggled)
        pal_vbox.addWidget(self.chk_auto_connect_palette)

        btn_add_node = QPushButton("➕ Add Selected Node")
        btn_add_node.setStyleSheet("background-color: #1E293B; color: #F1F5F9; border: 1px solid #334155; border-radius: 4px; padding: 6px; font-weight: 500; font-size: 11px;")
        btn_add_node.clicked.connect(self._add_selected_palette_node)
        pal_vbox.addWidget(btn_add_node)

        left_layout.addWidget(palette_group)
        main_splitter.addWidget(left_panel)

        # -------------------------------------------------------------
        # 2. CENTER PANEL: Toolbar, Canvas & Large Multi-Tab Bottom Dock
        # -------------------------------------------------------------
        center_panel = QWidget()
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(6)

        # Multi-Tier Action Toolbar Container (Clean, Grouped & Responsive)
        toolbar_frame = QFrame()
        toolbar_frame.setStyleSheet("""
            QFrame#ToolbarContainer {
                background-color: #0F172A;
                border: 1px solid #1E293B;
                border-radius: 6px;
                padding: 4px;
            }
        """)
        toolbar_frame.setObjectName("ToolbarContainer")
        toolbar_container_layout = QVBoxLayout(toolbar_frame)
        toolbar_container_layout.setContentsMargins(6, 4, 6, 4)
        toolbar_container_layout.setSpacing(4)

        # Button Style Helper
        btn_style = "QPushButton { background-color: #1E293B; color: #E2E8F0; border: 1px solid #334155; border-radius: 4px; padding: 4px 8px; font-size: 11px; } QPushButton:hover { background-color: #334155; color: #FFFFFF; } QPushButton:disabled { color: #475569; border-color: #1E293B; }"
        btn_icon_style = "QPushButton { background-color: #1E293B; color: #E2E8F0; border: 1px solid #334155; border-radius: 4px; padding: 4px 6px; font-size: 11px; } QPushButton:hover { background-color: #334155; color: #FFFFFF; } QPushButton:disabled { color: #475569; border-color: #1E293B; }"

        def _make_sep():
            sep = QFrame()
            sep.setFrameShape(QFrame.Shape.VLine)
            sep.setFrameShadow(QFrame.Shadow.Sunken)
            sep.setStyleSheet("color: #334155; background-color: #334155; max-height: 18px;")
            return sep

        # -------------------------------------------------------------
        # Row 1: File / Project Management & Main Execution Controls
        # -------------------------------------------------------------
        row1_toolbar = QHBoxLayout()
        row1_toolbar.setSpacing(5)
        row1_toolbar.setContentsMargins(0, 0, 0, 0)

        # Project File Controls
        btn_new = QPushButton("➕ New")
        btn_new.setStyleSheet(btn_style)
        btn_new.setToolTip("Create a new workflow")
        btn_new.clicked.connect(self._new_project)
        row1_toolbar.addWidget(btn_new)

        btn_open = QPushButton("📂 Open...")
        btn_open.setStyleSheet(btn_style)
        btn_open.setToolTip("Open workflow file from storage/workflows/")
        btn_open.clicked.connect(self._open_project_dialog)
        row1_toolbar.addWidget(btn_open)

        btn_save = QPushButton("💾 Save")
        btn_save.setStyleSheet(btn_style)
        btn_save.setToolTip("Save Current Workflow (Ctrl+S)")
        btn_save.clicked.connect(lambda: self._save_project(save_as=False))
        row1_toolbar.addWidget(btn_save)

        btn_save_as = QPushButton("Save As...")
        btn_save_as.setStyleSheet(btn_style)
        btn_save_as.setToolTip("Save As New File (Ctrl+Shift+S)")
        btn_save_as.clicked.connect(lambda: self._save_project(save_as=True))
        row1_toolbar.addWidget(btn_save_as)

        row1_toolbar.addWidget(_make_sep())

        btn_open_folder = QPushButton("📁 Workflows Dir")
        btn_open_folder.setStyleSheet(btn_style)
        btn_open_folder.setToolTip("Open storage/workflows/ folder in system file manager")
        btn_open_folder.clicked.connect(self._open_workflows_folder)
        row1_toolbar.addWidget(btn_open_folder)

        btn_editor = QPushButton("📝 File Editor")
        btn_editor.setStyleSheet(btn_style)
        btn_editor.setToolTip("Open File & Content Editor tab")
        btn_editor.clicked.connect(lambda: self.bottom_tabs.setCurrentWidget(self.tab_editor_widget))
        row1_toolbar.addWidget(btn_editor)

        row1_toolbar.addStretch()

        # Profile Selector
        lbl_target = QLabel("Profile / Target:")
        lbl_target.setStyleSheet("font-size: 11px; color: #94A3B8; font-weight: 600;")
        row1_toolbar.addWidget(lbl_target)

        self.combo_target_profile = QComboBox()
        self.combo_target_profile.setStyleSheet("background-color: #020617; color: #F1F5F9; border: 1px solid #334155; border-radius: 4px; padding: 3px 6px; font-size: 11px;")
        self.combo_target_profile.setMinimumWidth(150)
        self.combo_target_profile.setMaximumWidth(220)
        self.combo_target_profile.currentIndexChanged.connect(self._on_profile_selection_changed)
        row1_toolbar.addWidget(self.combo_target_profile)

        btn_refresh_prof = QPushButton("🔄")
        btn_refresh_prof.setStyleSheet(btn_icon_style)
        btn_refresh_prof.setToolTip("Refresh Profiles List")
        btn_refresh_prof.setFixedWidth(26)
        btn_refresh_prof.clicked.connect(self.reload_profiles)
        row1_toolbar.addWidget(btn_refresh_prof)

        self.btn_multi_browser = QPushButton("👥 Multi-Browser")
        self.btn_multi_browser.setStyleSheet("QPushButton { background-color: #1E293B; color: #38BDF8; border: 1px solid #0284C7; border-radius: 4px; padding: 4px 8px; font-weight: 600; font-size: 11px; } QPushButton:hover { background-color: #0369A1; color: #FFFFFF; }")
        self.btn_multi_browser.setToolTip("Configure concurrent Multi-Browser execution across multiple profiles & worker limits")
        self.btn_multi_browser.clicked.connect(self._open_multi_profile_dialog)
        row1_toolbar.addWidget(self.btn_multi_browser)

        row1_toolbar.addWidget(_make_sep())

        # Main Launch & Terminate
        self.btn_run_profile = QPushButton("🚀 Run (F5)")
        self.btn_run_profile.setStyleSheet("QPushButton { background-color: #0369A1; color: #FFFFFF; border: 1px solid #38BDF8; border-radius: 4px; padding: 4px 10px; font-weight: bold; font-size: 11px; } QPushButton:hover { background-color: #0284C7; }")
        self.btn_run_profile.setToolTip("Auto-launches target browser profile(s) and executes workflow (F5)")
        self.btn_run_profile.clicked.connect(lambda: self._start_execution(in_browser=True))
        row1_toolbar.addWidget(self.btn_run_profile)

        self.btn_run_headless = QPushButton("▶️ Headless")
        self.btn_run_headless.setStyleSheet(btn_style)
        self.btn_run_headless.setToolTip("Testet Workflow im schnellen Headless-Modus")
        self.btn_run_headless.clicked.connect(lambda: self._start_execution(in_browser=False))
        row1_toolbar.addWidget(self.btn_run_headless)

        self.btn_stop = QPushButton("🛑 Stop")
        self.btn_stop.setStyleSheet("QPushButton { background-color: #7F1D1D; color: #FECACA; border: 1px solid #DC2626; border-radius: 4px; padding: 4px 9px; font-weight: bold; font-size: 11px; } QPushButton:hover { background-color: #991B1B; color: #FFFFFF; }")
        self.btn_stop.setToolTip("Bricht Workflow-Ausführung sofort ab")
        self.btn_stop.clicked.connect(self._stop_workflow)
        row1_toolbar.addWidget(self.btn_stop)

        toolbar_container_layout.addLayout(row1_toolbar)

        # -------------------------------------------------------------
        # Row 2: Canvas View Tools & Interactive Debugging Strip
        # -------------------------------------------------------------
        row2_toolbar = QHBoxLayout()
        row2_toolbar.setSpacing(5)
        row2_toolbar.setContentsMargins(0, 0, 0, 0)

        # Canvas Tools Group
        lbl_canvas = QLabel("Canvas:")
        lbl_canvas.setStyleSheet("font-size: 10px; color: #64748B; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;")
        row2_toolbar.addWidget(lbl_canvas)

        self.btn_undo = QPushButton("↩️")
        self.btn_undo.setStyleSheet(btn_icon_style)
        self.btn_undo.setToolTip("Undo (Ctrl+Z)")
        self.btn_undo.setFixedWidth(28)
        self.btn_undo.setEnabled(False)
        self.btn_undo.clicked.connect(self._undo)
        row2_toolbar.addWidget(self.btn_undo)

        self.btn_redo = QPushButton("↪️")
        self.btn_redo.setStyleSheet(btn_icon_style)
        self.btn_redo.setToolTip("Redo (Ctrl+Y)")
        self.btn_redo.setFixedWidth(28)
        self.btn_redo.setEnabled(False)
        self.btn_redo.clicked.connect(self._redo)
        row2_toolbar.addWidget(self.btn_redo)

        row2_toolbar.addWidget(_make_sep())

        btn_layout = QPushButton("📐 Auto-Layout")
        btn_layout.setStyleSheet(btn_style)
        btn_layout.setToolTip("Automatically arrange workflow nodes in clean columns")
        btn_layout.clicked.connect(self._auto_layout)
        row2_toolbar.addWidget(btn_layout)

        btn_fit = QPushButton("🔍 Fit View")
        btn_fit.setStyleSheet(btn_style)
        btn_fit.setToolTip("Fit all nodes in center of view")
        btn_fit.clicked.connect(self._fit_to_view)
        row2_toolbar.addWidget(btn_fit)

        btn_zoom_in = QPushButton("➕")
        btn_zoom_in.setStyleSheet(btn_icon_style)
        btn_zoom_in.setToolTip("Zoom In (Ctrl++)")
        btn_zoom_in.setFixedWidth(28)
        btn_zoom_in.clicked.connect(self._zoom_in)
        row2_toolbar.addWidget(btn_zoom_in)

        btn_zoom_out = QPushButton("➖")
        btn_zoom_out.setStyleSheet(btn_icon_style)
        btn_zoom_out.setToolTip("Zoom Out (Ctrl+-)")
        btn_zoom_out.setFixedWidth(28)
        btn_zoom_out.clicked.connect(self._zoom_out)
        row2_toolbar.addWidget(btn_zoom_out)

        row2_toolbar.addWidget(_make_sep())

        self.chk_auto_connect_toolbar = QCheckBox("🔗 Auto-Connect")
        self.chk_auto_connect_toolbar.setStyleSheet("color: #38BDF8; font-size: 11px; font-weight: 600;")
        self.chk_auto_connect_toolbar.setToolTip("Neu hinzugefügte Nodes automatisch aufsteigend an den vorherigen Node anschließen")
        self.chk_auto_connect_toolbar.setChecked(True)
        self.chk_auto_connect_toolbar.toggled.connect(self._on_auto_connect_toggled)
        row2_toolbar.addWidget(self.chk_auto_connect_toolbar)

        row2_toolbar.addStretch()

        # Debugger Group
        lbl_debug = QLabel("Debugger:")
        lbl_debug.setStyleSheet("font-size: 10px; color: #64748B; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;")
        row2_toolbar.addWidget(lbl_debug)

        self.btn_pause_resume = QPushButton("⏸️ Pause / Takeover")
        self.btn_pause_resume.setStyleSheet("QPushButton { background-color: #1E293B; color: #F59E0B; border: 1px solid #D97706; border-radius: 4px; padding: 4px 9px; font-weight: bold; font-size: 11px; } QPushButton:hover { background-color: #D97706; color: white; }")
        self.btn_pause_resume.setToolTip("Pausiert den Workflow für manuelle Browser-Interaktionen (Takeover) oder setzt ihn fort")
        self.btn_pause_resume.clicked.connect(self._toggle_pause_resume)
        row2_toolbar.addWidget(self.btn_pause_resume)

        self.btn_step = QPushButton("⏭️ Step (F10)")
        self.btn_step.setStyleSheet("QPushButton { background-color: #1E293B; color: #C084FC; border: 1px solid #9333EA; border-radius: 4px; padding: 4px 9px; font-weight: bold; font-size: 11px; } QPushButton:hover { background-color: #9333EA; color: white; }")
        self.btn_step.setToolTip("Führt genau einen einzelnen Node aus und pausiert sofort danach (F10)")
        self.btn_step.clicked.connect(self._step_workflow)
        row2_toolbar.addWidget(self.btn_step)

        self.btn_bp = QPushButton("🔴 BP (F9)")
        self.btn_bp.setStyleSheet("QPushButton { background-color: #1E293B; color: #F87171; border: 1px solid #DC2626; border-radius: 4px; padding: 4px 8px; font-weight: bold; font-size: 11px; } QPushButton:hover { background-color: #DC2626; color: white; }")
        self.btn_bp.setToolTip("Breakpoint auf ausgewähltem Node umschalten (F9)")
        self.btn_bp.clicked.connect(self._toggle_selected_breakpoint)
        row2_toolbar.addWidget(self.btn_bp)

        toolbar_container_layout.addLayout(row2_toolbar)

        center_layout.addWidget(toolbar_frame)

        # Vertical Splitter: Canvas on Top, Enlarged Multi-Tab Console on Bottom
        center_v_splitter = QSplitter(Qt.Orientation.Vertical)
        center_v_splitter.setChildrenCollapsible(False)

        # Canvas Graphics View
        self.scene = WorkflowGraphicsScene()
        self.scene.selectionChanged.connect(self._on_canvas_selection_changed)

        self.view = ZoomableGraphicsView(self.scene, builder_view=self)
        self.view.setStyleSheet("border: 1px solid #334155; border-radius: 6px; background-color: #0B0F19;")
        self.view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        center_v_splitter.addWidget(self.view)

        # Bottom Studio Console Tabs (Enlarged Logs, Variables, Python Code, Health Check)
        self.bottom_tabs = QTabWidget()
        self.bottom_tabs.setMinimumHeight(180)
        self.bottom_tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #334155;
                background-color: #0F172A;
                border-radius: 4px;
            }
            QTabBar::tab {
                background-color: #1E293B;
                color: #94A3B8;
                padding: 6px 12px;
                border: 1px solid #334155;
                border-bottom: none;
                margin-right: 2px;
                font-size: 11px;
                font-weight: 500;
            }
            QTabBar::tab:selected {
                background-color: #0F172A;
                color: #38BDF8;
                font-weight: bold;
                border-top: 2px solid #38BDF8;
            }
        """)

        # Tab 1: Live Execution Stream & Logs
        tab_logs = QWidget()
        tab_logs_layout = QVBoxLayout(tab_logs)
        tab_logs_layout.setContentsMargins(6, 6, 6, 6)
        tab_logs_layout.setSpacing(4)

        logs_toolbar = QHBoxLayout()
        logs_toolbar.setSpacing(6)
        self.txt_filter_logs = QLineEdit()
        self.txt_filter_logs.setPlaceholderText("Filter logs...")
        self.txt_filter_logs.setStyleSheet("background-color: #020617; color: #F1F5F9; border: 1px solid #334155; border-radius: 3px; padding: 3px 6px; font-size: 10px;")
        logs_toolbar.addWidget(self.txt_filter_logs)

        self.chk_autoscroll = QCheckBox("Auto-Scroll")
        self.chk_autoscroll.setChecked(True)
        self.chk_autoscroll.setStyleSheet("color: #94A3B8; font-size: 10px;")
        logs_toolbar.addWidget(self.chk_autoscroll)

        btn_clear_logs = QPushButton("Clear")
        btn_clear_logs.setStyleSheet(btn_style)
        btn_clear_logs.clicked.connect(lambda: self.txt_logs.clear())
        logs_toolbar.addWidget(btn_clear_logs)

        tab_logs_layout.addLayout(logs_toolbar)

        self.txt_logs = QTextEdit()
        self.txt_logs.setReadOnly(True)
        self.txt_logs.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.txt_logs.setStyleSheet("background-color: #020617; color: #E2E8F0; font-family: monospace; font-size: 11px; border: 1px solid #1E293B; border-radius: 4px; padding: 4px;")
        tab_logs_layout.addWidget(self.txt_logs)
        self.bottom_tabs.addTab(tab_logs, "📜 Live Execution Logs")

        # Tab: Multi-Browser Execution Matrix
        tab_multi = QWidget()
        tab_multi_layout = QVBoxLayout(tab_multi)
        tab_multi_layout.setContentsMargins(6, 6, 6, 6)
        tab_multi_layout.setSpacing(4)

        multi_header_row = QHBoxLayout()
        self.lbl_multi_summary = QLabel("Execution Matrix: Idle")
        self.lbl_multi_summary.setStyleSheet("color: #38BDF8; font-weight: bold; font-size: 11px;")
        multi_header_row.addWidget(self.lbl_multi_summary)

        self.multi_progress_bar = QProgressBar()
        self.multi_progress_bar.setRange(0, 100)
        self.multi_progress_bar.setValue(0)
        self.multi_progress_bar.setFixedHeight(14)
        self.multi_progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #020617;
                border: 1px solid #334155;
                border-radius: 4px;
                text-align: center;
                color: #FFFFFF;
                font-size: 9px;
            }
            QProgressBar::chunk {
                background-color: #0284C7;
                border-radius: 3px;
            }
        """)
        multi_header_row.addWidget(self.multi_progress_bar)

        btn_cfg_multi = QPushButton("⚙️ Configure Multi-Run")
        btn_cfg_multi.setStyleSheet(btn_style)
        btn_cfg_multi.setToolTip("Open Multi-Browser Profile selection dialog")
        btn_cfg_multi.clicked.connect(self._open_multi_profile_dialog)
        multi_header_row.addWidget(btn_cfg_multi)

        tab_multi_layout.addLayout(multi_header_row)

        self.table_multi_matrix = QTableWidget(0, 7)
        self.table_multi_matrix.setHorizontalHeaderLabels([
            "Profile", "Engine", "Status", "Current Node", "Progress", "Duration", "Result"
        ])
        hdr_m = self.table_multi_matrix.horizontalHeader()
        if hdr_m:
            hdr_m.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
            hdr_m.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
            hdr_m.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
            hdr_m.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
            hdr_m.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
            hdr_m.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
            hdr_m.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        self.table_multi_matrix.setStyleSheet("background-color: #020617; color: #F1F5F9; gridline-color: #1E293B; font-size: 11px;")
        tab_multi_layout.addWidget(self.table_multi_matrix)
        self.tab_multi_widget = tab_multi
        self.bottom_tabs.addTab(tab_multi, "👥 Multi-Browser Matrix")

        # Tab 2: Runtime Variables
        tab_vars = QWidget()
        tab_vars_layout = QVBoxLayout(tab_vars)
        tab_vars_layout.setContentsMargins(6, 6, 6, 6)
        tab_vars_layout.setSpacing(4)

        vars_toolbar = QHBoxLayout()
        btn_add_var = QPushButton("➕ Add Variable")
        btn_add_var.setStyleSheet(btn_style)
        btn_add_var.clicked.connect(self._add_runtime_variable)
        vars_toolbar.addWidget(btn_add_var)

        btn_view_var = QPushButton("👁️ Open in Editor")
        btn_view_var.setStyleSheet(btn_style)
        btn_view_var.setToolTip("Open selected variable content or filepath in the File & Content Editor")
        btn_view_var.clicked.connect(self._on_open_selected_var_in_editor)
        vars_toolbar.addWidget(btn_view_var)

        vars_toolbar.addStretch()
        tab_vars_layout.addLayout(vars_toolbar)

        self.table_vars = QTableWidget(0, 2)
        self.table_vars.setHorizontalHeaderLabels(["Variable Name", "Current Value"])
        hdr = self.table_vars.horizontalHeader()
        if hdr:
            hdr.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_vars.setStyleSheet("background-color: #020617; color: #F1F5F9; gridline-color: #1E293B; font-size: 11px;")
        self.table_vars.cellDoubleClicked.connect(self._on_var_cell_double_clicked)
        tab_vars_layout.addWidget(self.table_vars)
        self.bottom_tabs.addTab(tab_vars, "📊 Runtime Variables")

        # Tab 3: Generated Playwright Python Code
        tab_code = QWidget()
        tab_code_layout = QVBoxLayout(tab_code)
        tab_code_layout.setContentsMargins(6, 6, 6, 6)
        tab_code_layout.setSpacing(4)

        code_toolbar = QHBoxLayout()
        btn_gen_code = QPushButton("🔄 Refresh Code")
        btn_gen_code.setStyleSheet(btn_style)
        btn_gen_code.clicked.connect(self._generate_playwright_code)
        code_toolbar.addWidget(btn_gen_code)

        btn_copy_code = QPushButton("📋 Copy to Clipboard")
        btn_copy_code.setStyleSheet(btn_style)
        btn_copy_code.clicked.connect(self._copy_python_code)
        code_toolbar.addWidget(btn_copy_code)
        code_toolbar.addStretch()
        tab_code_layout.addLayout(code_toolbar)

        self.txt_generated_code = QTextEdit()
        self.txt_generated_code.setReadOnly(True)
        self.txt_generated_code.setStyleSheet("background-color: #020617; color: #38BDF8; font-family: monospace; font-size: 11px; border: 1px solid #1E293B; border-radius: 4px; padding: 4px;")
        tab_code_layout.addWidget(self.txt_generated_code)
        self.bottom_tabs.addTab(tab_code, "🐍 Playwright Python Export")

        # Tab 4: Graph Diagnostics & Linter
        tab_diag = QWidget()
        tab_diag_layout = QVBoxLayout(tab_diag)
        tab_diag_layout.setContentsMargins(6, 6, 6, 6)
        tab_diag_layout.setSpacing(4)

        diag_toolbar = QHBoxLayout()
        btn_scan_diag = QPushButton("🔄 Re-Scan Graph")
        btn_scan_diag.setStyleSheet(btn_style)
        btn_scan_diag.clicked.connect(self._refresh_diagnostics)
        diag_toolbar.addWidget(btn_scan_diag)
        diag_toolbar.addStretch()
        tab_diag_layout.addLayout(diag_toolbar)

        self.txt_diagnostics = QTextEdit()
        self.txt_diagnostics.setReadOnly(True)
        self.txt_diagnostics.setStyleSheet("background-color: #020617; color: #F1F5F9; font-family: monospace; font-size: 11px; border: 1px solid #1E293B; border-radius: 4px; padding: 4px;")
        tab_diag_layout.addWidget(self.txt_diagnostics)
        self.bottom_tabs.addTab(tab_diag, "🩺 Graph Diagnostics")

        # Tab 5: Integrated File & Content Editor
        tab_editor = QWidget()
        tab_editor_layout = QVBoxLayout(tab_editor)
        tab_editor_layout.setContentsMargins(6, 6, 6, 6)
        tab_editor_layout.setSpacing(4)

        editor_toolbar = QHBoxLayout()
        lbl_ed_title = QLabel("Source / File:")
        lbl_ed_title.setStyleSheet("color: #94A3B8; font-size: 11px; font-weight: bold;")
        editor_toolbar.addWidget(lbl_ed_title)

        self.edit_editor_path = QLineEdit()
        self.edit_editor_path.setPlaceholderText("Filepath (e.g. storage/screenshots/screenshot.png, output.json) or variable name")
        self.edit_editor_path.setStyleSheet("background-color: #0F172A; color: #F1F5F9; border: 1px solid #334155; border-radius: 3px; padding: 4px; font-size: 11px;")
        editor_toolbar.addWidget(self.edit_editor_path)

        btn_open_file = QPushButton("📂 Open File...")
        btn_open_file.setStyleSheet(btn_style)
        btn_open_file.setToolTip("Open file from disk")
        btn_open_file.clicked.connect(self._on_editor_browse_file)
        editor_toolbar.addWidget(btn_open_file)

        btn_save_file = QPushButton("💾 Save File")
        btn_save_file.setStyleSheet(btn_style)
        btn_save_file.setToolTip("Save changes to file on disk")
        btn_save_file.clicked.connect(self._on_editor_save_file)
        editor_toolbar.addWidget(btn_save_file)

        btn_reload_file = QPushButton("🔄 Reload")
        btn_reload_file.setStyleSheet(btn_style)
        btn_reload_file.setToolTip("Reload file from disk")
        btn_reload_file.clicked.connect(self._on_editor_reload_file)
        editor_toolbar.addWidget(btn_reload_file)

        btn_copy_file_content = QPushButton("📋 Copy All")
        btn_copy_file_content.setStyleSheet(btn_style)
        btn_copy_file_content.setToolTip("Copy editor content to clipboard")
        btn_copy_file_content.clicked.connect(self._on_editor_copy_content)
        editor_toolbar.addWidget(btn_copy_file_content)

        tab_editor_layout.addLayout(editor_toolbar)

        self.txt_file_editor = QTextEdit()
        self.txt_file_editor.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.txt_file_editor.setStyleSheet("background-color: #020617; color: #F1F5F9; font-family: monospace; font-size: 11px; border: 1px solid #1E293B; border-radius: 4px; padding: 6px;")
        tab_editor_layout.addWidget(self.txt_file_editor)

        self.lbl_image_preview = QLabel("Kein Bild geladen")
        self.lbl_image_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_image_preview.setStyleSheet("background-color: #020617; color: #64748B; font-size: 11px; border: 1px solid #1E293B; border-radius: 4px; padding: 6px;")
        self.lbl_image_preview.setVisible(False)
        tab_editor_layout.addWidget(self.lbl_image_preview)

        self.tab_editor_widget = tab_editor
        self.bottom_tabs.addTab(tab_editor, "📝 File & Content Editor")

        center_v_splitter.addWidget(self.bottom_tabs)
        center_v_splitter.setSizes([600, 220])
        center_layout.addWidget(center_v_splitter)
        main_splitter.addWidget(center_panel)

        # -------------------------------------------------------------
        # 3. RIGHT PANEL: Node Properties Inspector & Wire Linking
        # -------------------------------------------------------------
        right_panel = QWidget()
        right_panel.setMinimumWidth(340)
        right_panel.setMaximumWidth(480)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)

        # Quick Wire Box
        wire_group = QGroupBox("🔗 Link Nodes")
        wire_group.setStyleSheet("QGroupBox { font-weight: bold; color: #94A3B8; border: 1px solid #334155; border-radius: 6px; margin-top: 6px; padding-top: 10px; }")
        wire_layout = QFormLayout(wire_group)
        self.wire_src = QComboBox()
        self.wire_src.setStyleSheet("background-color: #0F172A; color: #F1F5F9; border: 1px solid #334155; border-radius: 3px; font-size: 11px;")
        self.wire_dst = QComboBox()
        self.wire_dst.setStyleSheet("background-color: #0F172A; color: #F1F5F9; border: 1px solid #334155; border-radius: 3px; font-size: 11px;")
        self.wire_port = QComboBox()
        self.wire_port.setStyleSheet("background-color: #0F172A; color: #F1F5F9; border: 1px solid #334155; border-radius: 3px; font-size: 11px;")
        self.wire_port.addItems(["out", "true", "false", "loop_body", "loop_exit"])
        
        btn_create_wire = QPushButton("Connect Nodes")
        btn_create_wire.setStyleSheet(btn_style)
        btn_create_wire.clicked.connect(self._manual_connect_nodes)
        
        wire_layout.addRow("From:", self.wire_src)
        wire_layout.addRow("Port:", self.wire_port)
        wire_layout.addRow("To:", self.wire_dst)
        wire_layout.addRow(btn_create_wire)
        right_layout.addWidget(wire_group)

        # Properties Form
        prop_group = QGroupBox("⚙️ Node Properties")
        prop_group.setStyleSheet("QGroupBox { font-weight: bold; color: #94A3B8; border: 1px solid #334155; border-radius: 6px; margin-top: 6px; padding-top: 10px; }")
        self.prop_layout = QFormLayout(prop_group)

        # Function Description & Info Card
        self.node_info_card = QFrame()
        self.node_info_card.setStyleSheet("""
            QFrame {
                background-color: #0B1120;
                border: 1px solid #1E293B;
                border-left: 3px solid #38BDF8;
                border-radius: 4px;
                padding: 6px;
                margin-bottom: 6px;
            }
        """)
        info_layout = QVBoxLayout(self.node_info_card)
        info_layout.setContentsMargins(6, 6, 6, 6)
        info_layout.setSpacing(3)

        self.lbl_node_info_title = QLabel("Funktion")
        self.lbl_node_info_title.setStyleSheet("color: #38BDF8; font-weight: bold; font-size: 11px;")
        info_layout.addWidget(self.lbl_node_info_title)

        self.lbl_node_category_badge = QLabel("Kategorie")
        self.lbl_node_category_badge.setStyleSheet("color: #94A3B8; font-size: 10px; font-style: italic;")
        info_layout.addWidget(self.lbl_node_category_badge)

        self.lbl_node_desc = QLabel("Wähle einen Node aus, um dessen Beschreibung und Parameter zu sehen.")
        self.lbl_node_desc.setWordWrap(True)
        self.lbl_node_desc.setStyleSheet("color: #E2E8F0; font-size: 11px; line-height: 1.3;")
        info_layout.addWidget(self.lbl_node_desc)

        self.lbl_node_params_help = QLabel("")
        self.lbl_node_params_help.setWordWrap(True)
        self.lbl_node_params_help.setStyleSheet("color: #94A3B8; font-size: 10px; margin-top: 4px;")
        info_layout.addWidget(self.lbl_node_params_help)

        self.prop_layout.addRow(self.node_info_card)
        
        self.prop_title = QLineEdit()
        self.prop_title.setStyleSheet("background-color: #0F172A; color: #F1F5F9; border: 1px solid #334155; border-radius: 3px; padding: 4px; font-size: 11px;")
        self.prop_title.textChanged.connect(self._on_prop_title_changed)
        self.prop_layout.addRow("Title:", self.prop_title)

        # AI Generation Toggle for VLA_TYPE
        self.prop_use_ai = QCheckBox("🤖 Text durch KI-Modell erstellen lassen (AI Generation)")
        self.prop_use_ai.setStyleSheet("color: #38BDF8; font-weight: bold; font-size: 11px; padding: 2px 0;")
        self.prop_use_ai.setToolTip("Generiert den einzugebenden Text dynamisch durch ein KI-Modell (z. B. Gemini, Qwen, DeepSeek).")
        self.prop_use_ai.setVisible(False)
        self.prop_use_ai.toggled.connect(self._on_prop_use_ai_toggled)
        self.prop_layout.addRow(self.prop_use_ai)

        # Dynamic Form Controls
        self.lbl_p1 = QLabel("Param 1:")
        self.prop_p1 = QLineEdit()
        self.prop_p1.setStyleSheet("background-color: #0F172A; color: #F1F5F9; border: 1px solid #334155; border-radius: 3px; padding: 4px; font-size: 11px;")
        self.prop_p1.textChanged.connect(self._on_prop_p1_changed)
        self.prop_layout.addRow(self.lbl_p1, self.prop_p1)

        self.lbl_combo1 = QLabel("Option 1:")
        self.combo_p1 = QComboBox()
        self.combo_p1.setStyleSheet("background-color: #0F172A; color: #F1F5F9; border: 1px solid #334155; border-radius: 3px; font-size: 11px;")
        self.combo_p1.currentTextChanged.connect(self._on_combo_p1_changed)
        self.prop_layout.addRow(self.lbl_combo1, self.combo_p1)

        self.lbl_p2 = QLabel("Param 2:")
        self.prop_p2 = QLineEdit()
        self.prop_p2.setStyleSheet("background-color: #0F172A; color: #F1F5F9; border: 1px solid #334155; border-radius: 3px; padding: 4px; font-size: 11px;")
        self.prop_p2.textChanged.connect(self._on_prop_p2_changed)
        self.prop_layout.addRow(self.lbl_p2, self.prop_p2)

        self.lbl_combo2 = QLabel("Option 2:")
        self.combo_p2 = QComboBox()
        self.combo_p2.setStyleSheet("background-color: #0F172A; color: #F1F5F9; border: 1px solid #334155; border-radius: 3px; font-size: 11px;")
        self.combo_p2.currentTextChanged.connect(self._on_combo_p2_changed)
        self.prop_layout.addRow(self.lbl_combo2, self.combo_p2)

        self.lbl_combo3 = QLabel("Option 3:")
        self.combo_p3 = QComboBox()
        self.combo_p3.setStyleSheet("background-color: #0F172A; color: #F1F5F9; border: 1px solid #334155; border-radius: 3px; font-size: 11px;")
        self.combo_p3.currentTextChanged.connect(self._on_combo_p3_changed)
        self.prop_layout.addRow(self.lbl_combo3, self.combo_p3)

        self.lbl_num = QLabel("Value:")
        self.prop_num = QDoubleSpinBox()
        self.prop_num.setStyleSheet("background-color: #0F172A; color: #F1F5F9; border: 1px solid #334155; border-radius: 3px; font-size: 11px;")
        self.prop_num.setRange(0.01, 99999.0)
        self.prop_num.setValue(2.0)
        self.prop_num.valueChanged.connect(self._on_prop_num_changed)
        self.prop_layout.addRow(self.lbl_num, self.prop_num)

        self.prop_press_enter = QCheckBox("Press Enter afterwards")
        self.prop_press_enter.setStyleSheet("color: #E2E8F0; font-size: 11px;")
        self.prop_press_enter.setChecked(True)
        self.prop_press_enter.toggled.connect(self._on_prop_press_enter_changed)
        self.prop_layout.addRow(self.prop_press_enter)

        self.prop_clear_first = QCheckBox("Clear field before typing")
        self.prop_clear_first.setStyleSheet("color: #E2E8F0; font-size: 11px;")
        self.prop_clear_first.setChecked(True)
        self.prop_clear_first.toggled.connect(self._on_prop_clear_first_changed)
        self.prop_layout.addRow(self.prop_clear_first)

        # --- Chess Anti-Detect extra controls (visible only for CHESS_SOLVER) ---
        self.lbl_chess_speed = QLabel("Speed Preset:")
        self.combo_chess_speed = QComboBox()
        self.combo_chess_speed.setStyleSheet("background-color: #0F172A; color: #F1F5F9; border: 1px solid #334155; border-radius: 3px; font-size: 11px;")
        self.combo_chess_speed.addItems(["blitz", "bullet", "fast", "rapid", "classical", "balanced"])
        self.combo_chess_speed.setToolTip("Geschwindigkeitsprofil für humanisierte Bedenkzeiten (Anti-Detection Timing Engine).")
        self.combo_chess_speed.currentTextChanged.connect(self._on_chess_speed_changed)
        self.prop_layout.addRow(self.lbl_chess_speed, self.combo_chess_speed)

        self.lbl_chess_diff_depth = QLabel("Difficulty Depth:")
        self.prop_chess_diff_depth = QSpinBox()
        self.prop_chess_diff_depth.setStyleSheet("background-color: #0F172A; color: #F1F5F9; border: 1px solid #334155; border-radius: 3px; font-size: 11px;")
        self.prop_chess_diff_depth.setRange(6, 20)
        self.prop_chess_diff_depth.setValue(12)
        self.prop_chess_diff_depth.setToolTip("Stockfish-Tiefe für die MultiPV Schwierigkeitsanalyse (PositionDifficultyAnalyzer). Mehr = genauer, aber langsamer.")
        self.prop_chess_diff_depth.valueChanged.connect(self._on_chess_diff_depth_changed)
        self.prop_layout.addRow(self.lbl_chess_diff_depth, self.prop_chess_diff_depth)

        self.prop_antidetect = QCheckBox("🛡️ Anti-Detection Mode (AntiDetectChessSession)")
        self.prop_antidetect.setStyleSheet("color: #38BDF8; font-weight: bold; font-size: 11px; padding: 2px 0;")
        self.prop_antidetect.setToolTip("Aktiviert vollständiges Anti-Detection-System: Difficulty-Score, PlayerBaseline, EloThrottleController, HumanizedTimingEngine.")
        self.prop_antidetect.setChecked(True)
        self.prop_antidetect.toggled.connect(self._on_chess_antidetect_changed)
        self.prop_layout.addRow(self.prop_antidetect)

        self.prop_chess_auto_move = QCheckBox("🖱️ Auto-Move on Board")
        self.prop_chess_auto_move.setStyleSheet("color: #E2E8F0; font-size: 11px;")
        self.prop_chess_auto_move.setToolTip("Klickt / Drag den berechneten Zug automatisch auf dem Schachbrett im Browser aus.")
        self.prop_chess_auto_move.setChecked(True)
        self.prop_chess_auto_move.toggled.connect(self._on_chess_auto_move_changed)
        self.prop_layout.addRow(self.prop_chess_auto_move)
        # --- end chess controls ---

        self.prop_stop_on_err = QCheckBox("Halt workflow on error")
        self.prop_stop_on_err.setStyleSheet("color: #E2E8F0; font-size: 11px;")
        self.prop_stop_on_err.setChecked(True)
        self.prop_stop_on_err.toggled.connect(self._on_prop_stop_err_changed)
        self.prop_layout.addRow(self.prop_stop_on_err)

        self.btn_prop_open_editor = QPushButton("👁️ View File / Script in Editor")
        self.btn_prop_open_editor.setStyleSheet("background-color: #0284C7; color: #FFFFFF; border: 1px solid #0369A1; border-radius: 4px; padding: 5px; font-weight: 500; font-size: 11px;")
        self.btn_prop_open_editor.setToolTip("Opens this node's file, screenshot, script, or variable output in the File & Content Editor")
        self.btn_prop_open_editor.clicked.connect(self._on_prop_open_in_editor)
        self.prop_layout.addRow(self.btn_prop_open_editor)

        btn_prop_del = QPushButton("🗑️ Delete Selected Node")
        btn_prop_del.setStyleSheet(btn_style)
        btn_prop_del.clicked.connect(self._delete_selected_node)
        self.prop_layout.addRow(btn_prop_del)

        right_layout.addWidget(prop_group)
        right_layout.addStretch()

        main_splitter.addWidget(right_panel)
        main_splitter.setSizes([240, 950, 380])

    # ---------------- Search & Palette ----------------

    def _filter_palette_items(self, query: str):
        """Filters the palette list by node title, category or description."""
        q = query.strip().lower()
        for i in range(self.node_palette_list.count()):
            item = self.node_palette_list.item(i)
            if item:
                text = item.text().lower()
                tooltip = (item.toolTip() or "").lower()
                item.setHidden(bool(q and (q not in text and q not in tooltip)))

    def _on_palette_item_double_clicked(self, item: QListWidgetItem):
        ntype = item.data(Qt.ItemDataRole.UserRole)
        vp = self.view.viewport()
        center_pos = self.view.mapToScene(vp.rect().center()) if vp else QPointF(0, 0)
        self._add_node_at(ntype, center_pos.x(), center_pos.y())

    def _add_selected_palette_node(self):
        curr = self.node_palette_list.currentItem()
        if not curr:
            return
        ntype = curr.data(Qt.ItemDataRole.UserRole)
        vp = self.view.viewport()
        center_pos = self.view.mapToScene(vp.rect().center()) if vp else QPointF(0, 0)
        self._add_node_at(ntype, center_pos.x(), center_pos.y())

    # ---------------- File & Project Management ----------------

    def _open_project_dialog(self):
        chosen, _ = QFileDialog.getOpenFileName(self, "Open Workflow Project", WORKFLOWS_DIR, "JSON Workflow Files (*.json)")
        if chosen and os.path.exists(chosen):
            self._load_project_file(chosen)

    def _open_workflows_folder(self):
        self._ensure_workflows_dir()
        QDesktopServices.openUrl(QUrl.fromLocalFile(WORKFLOWS_DIR))

    def _new_project(self):
        name, ok = QInputDialog.getText(self, "New Workflow Project", "Enter Project Name:", text="Untitled Workflow")
        if not ok or not name.strip():
            return

        self._push_undo_state()
        self.dag = WorkflowDAG(name=name.strip())
        start_node = WorkflowNode(id="start_1", node_type=NodeType.START, title="Initialize Session", position={"x": 0.0, "y": 0.0})
        self.dag.nodes[start_node.id] = start_node
        self.dag.entry_node_id = start_node.id
        self._last_added_node_id = start_node.id
        
        safe_fname = "".join(c if c.isalnum() or c in " _-" else "" for c in name.strip()).replace(" ", "_").lower() + ".json"
        self.current_project_filepath = os.path.join(WORKFLOWS_DIR, safe_fname)
        self._save_project(save_as=False)

        self._render_dag_on_canvas()
        self._update_node_dropdowns()
        self._update_title_header()
        self._refresh_diagnostics()
        self.txt_logs.append(f"✨ Created New Project: '{name}'")

    def _save_project(self, save_as: bool = False):
        target_path = self.current_project_filepath

        if save_as or not target_path:
            safe_name = "".join(c if c.isalnum() or c in " _-" else "" for c in self.dag.name).replace(" ", "_").lower() + ".json"
            initial_path = os.path.join(WORKFLOWS_DIR, safe_name)
            chosen, _ = QFileDialog.getSaveFileName(self, "Save Workflow Project", initial_path, "JSON Workflow Files (*.json)")
            if not chosen:
                return
            target_path = chosen

        try:
            self.dag.updated_at = time.time()
            with open(target_path, "w", encoding="utf-8") as f:
                json.dump(self.dag.to_dict(), f, indent=2)
            
            self.current_project_filepath = target_path
            self._update_title_header()
            self.txt_logs.append(f"💾 Saved: {os.path.basename(target_path)}")
        except Exception as e:
            self.txt_logs.append(f"❌ Failed to save: {e}")
            QMessageBox.critical(self, "Save Error", f"Could not save project:\n{e}")

    def _load_project_file(self, fpath: str):
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._push_undo_state()
            self.dag = WorkflowDAG.from_dict(data)
            self.current_project_filepath = fpath
            self._last_added_node_id = list(self.dag.nodes.keys())[-1] if self.dag.nodes else None
            self._render_dag_on_canvas()
            self._update_node_dropdowns()
            self._update_title_header()
            self._refresh_diagnostics()
            self.txt_logs.append(f"📂 Loaded: '{self.dag.name}' ({len(self.dag.nodes)} nodes)")
        except Exception as e:
            self.txt_logs.append(f"❌ Failed to open: {e}")
            QMessageBox.critical(self, "Open Error", f"Could not load project file:\n{e}")

    # ---------------- Layout & View Tools ----------------

    def _auto_layout(self):
        """Automatically aligns graph nodes in neat columns."""
        self._push_undo_state()
        self.dag.auto_layout_nodes()
        self._render_dag_on_canvas()
        self._fit_to_view()
        self.txt_logs.append("📐 Applied Auto-Layout to graph.")

    def _fit_to_view(self):
        """Fits all nodes inside the visible graphics viewport."""
        items_rect = self.scene.itemsBoundingRect()
        if not items_rect.isEmpty():
            self.view.fitInView(items_rect.adjusted(-60, -60, 60, 60), Qt.AspectRatioMode.KeepAspectRatio)

    def _zoom_in(self):
        """Zooms in the graphics view."""
        self.view.zoom_in()

    def _zoom_out(self):
        """Zooms out the graphics view."""
        self.view.zoom_out()

    # ---------------- Canvas & Nodes Rendering ----------------

    def _build_template_dag(self, index: int) -> WorkflowDAG:
        dag = WorkflowDAG(name=f"Template Campaign {index + 1}")
        if index == 0:
            n1 = WorkflowNode(id="n1", node_type=NodeType.START, title="Initialize Session", position={"x": -300, "y": 0})
            n2 = WorkflowNode(id="n2", node_type=NodeType.NAVIGATE, title="Open Google Search", params={"url": "https://www.google.com"}, position={"x": -20, "y": 0})
            n3 = WorkflowNode(id="n3", node_type=NodeType.VLA_TYPE, title="Type GPU Query", params={"text": "RTX 4090 GPU", "instruction": "Google search bar", "press_enter": True, "clear_first": True}, position={"x": 260, "y": 0})
            n4 = WorkflowNode(id="n4", node_type=NodeType.WAIT, title="Wait for Results", params={"duration": 2.5}, position={"x": 540, "y": 0})
            n5 = WorkflowNode(id="n5", node_type=NodeType.SCROLL, title="Scroll Results", params={"direction": "down", "pixels": 500}, position={"x": 820, "y": 0})
            n6 = WorkflowNode(id="n6", node_type=NodeType.TERMINATE, title="Finish Farming", params={"status": "success"}, position={"x": 1100, "y": 0})

            for n in [n1, n2, n3, n4, n5, n6]:
                dag.nodes[n.id] = n
            dag.entry_node_id = "n1"
            dag.add_edge("n1", "n2")
            dag.add_edge("n2", "n3")
            dag.add_edge("n3", "n4")
            dag.add_edge("n4", "n5")
            dag.add_edge("n5", "n6")

        elif index == 1:
            n1 = WorkflowNode(id="n1", node_type=NodeType.START, title="Start Feed Routine", position={"x": -200, "y": -50})
            n2 = WorkflowNode(id="n2", node_type=NodeType.NAVIGATE, title="Open Reddit", params={"url": "https://reddit.com/r/technology"}, position={"x": 60, "y": -50})
            n3 = WorkflowNode(id="n3", node_type=NodeType.LOOP, title="Scroll Loop (5x)", params={"iterations": 5}, position={"x": 320, "y": -50})
            n4 = WorkflowNode(id="n4", node_type=NodeType.SCROLL, title="Scroll Feed", params={"direction": "down", "pixels": 500}, position={"x": 600, "y": -120})
            n5 = WorkflowNode(id="n5", node_type=NodeType.WAIT, title="Read Post (Dwell)", params={"duration": 2.5}, position={"x": 600, "y": 40})
            n6 = WorkflowNode(id="n6", node_type=NodeType.TERMINATE, title="Finish", params={"status": "success"}, position={"x": 880, "y": -50})

            for n in [n1, n2, n3, n4, n5, n6]:
                dag.nodes[n.id] = n
            dag.entry_node_id = "n1"
            dag.add_edge("n1", "n2")
            dag.add_edge("n2", "n3")
            dag.add_edge("n3", "n4", source_port="loop_body")
            dag.add_edge("n4", "n5")
            dag.add_edge("n5", "n3")
            dag.add_edge("n3", "n6", source_port="loop_exit")

        elif index == 2:
            n1 = WorkflowNode(id="n1", node_type=NodeType.NAVIGATE, title="Target Protected Site", params={"url": "https://cloudflare.com"}, position={"x": -150, "y": 0})
            n2 = WorkflowNode(id="n2", node_type=NodeType.SOLVE_CAPTCHA, title="AI Auto-Solve Turnstile", params={}, position={"x": 120, "y": 0})
            n3 = WorkflowNode(id="n3", node_type=NodeType.WAIT, title="Wait Verification Token", params={"duration": 3.0}, position={"x": 390, "y": 0})
            n4 = WorkflowNode(id="n4", node_type=NodeType.TERMINATE, title="Finish", params={"status": "success"}, position={"x": 660, "y": 0})

            for n in [n1, n2, n3, n4]:
                dag.nodes[n.id] = n
            dag.entry_node_id = "n1"
            dag.add_edge("n1", "n2")
            dag.add_edge("n2", "n3")
            dag.add_edge("n3", "n4")

        elif index == 3:
            n1 = WorkflowNode(id="n1", node_type=NodeType.START, title="Start Scraper", position={"x": -200, "y": 0})
            n2 = WorkflowNode(id="n2", node_type=NodeType.NAVIGATE, title="Open Target Site", params={"url": "https://quotes.toscrape.com"}, position={"x": 70, "y": 0})
            n3 = WorkflowNode(id="n3", node_type=NodeType.EXTRACT_DATA, title="Scrape Quotes Text", params={"selector": ".quote .text", "attribute": "innerText", "var_name": "scraped_quotes"}, position={"x": 340, "y": 0})
            n4 = WorkflowNode(id="n4", node_type=NodeType.TERMINATE, title="Finish Scrape", params={"status": "success"}, position={"x": 610, "y": 0})

            for n in [n1, n2, n3, n4]:
                dag.nodes[n.id] = n
            dag.entry_node_id = "n1"
            dag.add_edge("n1", "n2")
            dag.add_edge("n2", "n3")
            dag.add_edge("n3", "n4")

        elif index == 4:
            # 5. Autonomous Browser Chess Bot (Stockfish)
            n1 = WorkflowNode(id="n1", node_type=NodeType.START, title="Initialize Chess Session", position={"x": -200, "y": 0})
            n2 = WorkflowNode(id="n2", node_type=NodeType.NAVIGATE, title="Open Chess Table", params={"url": "https://www.chess.com/play/computer"}, position={"x": 70, "y": 0})
            n3 = WorkflowNode(id="n3", node_type=NodeType.LOOP, title="Play Loop (40 Turns)", params={"iterations": 500}, position={"x": 340, "y": 0})
            n4 = WorkflowNode(id="n4", node_type=NodeType.CHESS_SOLVER, title="Stockfish Auto-Move", params={"platform": "auto", "engine_type": "super_grandmaster_godmode", "depth": 14, "auto_move": True}, position={"x": 610, "y": -80})
            n5 = WorkflowNode(id="n5", node_type=NodeType.WAIT, title="Opponent Turn Dwell", params={"duration": 2.0}, position={"x": 610, "y": 80})
            n6 = WorkflowNode(id="n6", node_type=NodeType.TERMINATE, title="Finish Match", params={"status": "success"}, position={"x": 880, "y": 0})

            for n in [n1, n2, n3, n4, n5, n6]:
                dag.nodes[n.id] = n
            dag.entry_node_id = "n1"
            dag.add_edge("n1", "n2")
            dag.add_edge("n2", "n3")
            dag.add_edge("n3", "n4", source_port="loop_body")
            dag.add_edge("n4", "n5", source_port="out")
            dag.add_edge("n5", "n3")
            dag.add_edge("n4", "n6", source_port="checkmate")
            dag.add_edge("n3", "n6", source_port="loop_exit")

        elif index == 5:
            # 6. Texas Hold'em Poker AI Omniscient Auto-Player
            n1 = WorkflowNode(id="n1", node_type=NodeType.START, title="Initialize Poker Session", position={"x": -200, "y": 0})
            n2 = WorkflowNode(id="n2", node_type=NodeType.NAVIGATE, title="Open Poker Client", params={"url": "https://www.replaypoker.com"}, position={"x": 70, "y": 0})
            n3 = WorkflowNode(id="n3", node_type=NodeType.LOOP, title="Hand Loop (50x)", params={"iterations": 50}, position={"x": 340, "y": 0})
            n4 = WorkflowNode(id="n4", node_type=NodeType.POKER_SOLVER, title="AI All-Models Poker Solver", params={"strategy": "ai_all_models_hybrid", "ai_model": "auto", "num_opponents": 2, "iterations": 3000, "auto_click_action": True}, position={"x": 610, "y": -60})
            n5 = WorkflowNode(id="n5", node_type=NodeType.WAIT, title="Street Dwell Delay", params={"duration": 2.0}, position={"x": 610, "y": 80})
            n6 = WorkflowNode(id="n6", node_type=NodeType.TERMINATE, title="Session Complete", params={"status": "success"}, position={"x": 880, "y": 0})

            for n in [n1, n2, n3, n4, n5, n6]:
                dag.nodes[n.id] = n
            dag.entry_node_id = "n1"
            dag.add_edge("n1", "n2")
            dag.add_edge("n2", "n3")
            dag.add_edge("n3", "n4", source_port="loop_body")
            dag.add_edge("n4", "n5", source_port="out")
            dag.add_edge("n5", "n3")
            dag.add_edge("n3", "n6", source_port="loop_exit")

        return dag

    def _load_starter_template(self, index: int):
        self._push_undo_state()
        self.dag = self._build_template_dag(index)
        self.current_project_filepath = None
        self._last_added_node_id = list(self.dag.nodes.keys())[-1] if self.dag.nodes else None
        self._update_title_header()
        self._render_dag_on_canvas()
        self._update_node_dropdowns()
        self._refresh_diagnostics()

    def _render_dag_on_canvas(self):
        self.scene.clear()
        self.node_items.clear()
        self.scene.edge_items.clear()

        for nid, node in self.dag.nodes.items():
            item = NodeGraphicsItem(node)
            item.setPos(node.position.get("x", 0.0), node.position.get("y", 0.0))
            self.scene.addItem(item)
            self.node_items[nid] = item

        for edge in self.dag.edges:
            src_item = self.node_items.get(edge.source_node_id)
            dst_item = self.node_items.get(edge.target_node_id)
            if src_item and dst_item:
                eitem = EdgeGraphicsItem(edge, src_item, dst_item)
                self.scene.addItem(eitem)
                self.scene.edge_items[edge.id] = eitem

    def _update_node_dropdowns(self):
        self.wire_src.clear()
        self.wire_dst.clear()
        for nid, node in self.dag.nodes.items():
            self.wire_src.addItem(f"{node.title} ({nid[:4]})", nid)
            self.wire_dst.addItem(f"{node.title} ({nid[:4]})", nid)

    def _on_auto_connect_toggled(self, checked: bool):
        self.auto_connect_enabled = checked
        if hasattr(self, "chk_auto_connect_palette") and self.chk_auto_connect_palette.isChecked() != checked:
            self.chk_auto_connect_palette.blockSignals(True)
            self.chk_auto_connect_palette.setChecked(checked)
            self.chk_auto_connect_palette.blockSignals(False)
        if hasattr(self, "chk_auto_connect_toolbar") and self.chk_auto_connect_toolbar.isChecked() != checked:
            self.chk_auto_connect_toolbar.blockSignals(True)
            self.chk_auto_connect_toolbar.setChecked(checked)
            self.chk_auto_connect_toolbar.blockSignals(False)

    def _get_source_node_for_auto_connect(self) -> Optional[WorkflowNode]:
        """
        Finds the best predecessor node to connect from:
        1. Currently selected node on canvas (if any and has output ports).
        2. Most recently added node.
        3. The rightmost / terminal node in the graph.
        """
        if not self.dag or not self.dag.nodes:
            return None

        # 1. Check selected node on canvas
        try:
            selected_items = self.scene.selectedItems() if hasattr(self, "scene") and self.scene else []
            for item in selected_items:
                if isinstance(item, NodeGraphicsItem) and item.node.id in self.dag.nodes:
                    if item.node.get_output_ports():
                        return item.node
        except Exception:
            pass

        # 2. Check last added node
        if self._last_added_node_id and self._last_added_node_id in self.dag.nodes:
            last_node = self.dag.nodes[self._last_added_node_id]
            if last_node.get_output_ports():
                return last_node

        # 3. Check rightmost node (max X position)
        valid_nodes = [n for n in self.dag.nodes.values() if n.get_output_ports()]
        if valid_nodes:
            best_node = max(valid_nodes, key=lambda n: n.position.get("x", 0.0))
            return best_node

        return None

    def _determine_source_port(self, source_node: WorkflowNode) -> Optional[str]:
        """Selects the best available output port on source_node."""
        out_ports = source_node.get_output_ports()
        if not out_ports:
            return None

        if len(out_ports) == 1:
            return out_ports[0]

        if source_node.node_type in [NodeType.CONDITION, NodeType.AI_DECISION]:
            existing_ports = {e.source_port for e in self.dag.edges if e.source_node_id == source_node.id}
            if "true" not in existing_ports:
                return "true"
            elif "false" not in existing_ports:
                return "false"
            return "true"

        if source_node.node_type == NodeType.LOOP:
            existing_ports = {e.source_port for e in self.dag.edges if e.source_node_id == source_node.id}
            if "loop_body" not in existing_ports:
                return "loop_body"
            elif "loop_exit" not in existing_ports:
                return "loop_exit"
            return "loop_body"

        existing_ports = {e.source_port for e in self.dag.edges if e.source_node_id == source_node.id}
        for p in out_ports:
            if p not in existing_ports:
                return p
        return out_ports[0]

    def _add_node_at(self, ntype: NodeType, x: float, y: float):
        self._push_undo_state()
        new_id = f"n_{uuid.uuid4().hex[:6]}"

        source_node = None
        source_port = None
        if self.auto_connect_enabled and ntype != NodeType.START:
            source_node = self._get_source_node_for_auto_connect()
            if source_node:
                source_port = self._determine_source_port(source_node)

        # Smart coordinate calculation if auto-connecting from a predecessor
        node_x = x
        node_y = y
        if source_node and source_port:
            src_x = source_node.position.get("x", 0.0)
            src_y = source_node.position.get("y", 0.0)
            node_x = src_x + 270.0
            if source_port in ["false", "loop_exit"]:
                node_y = src_y + 110.0
            else:
                node_y = src_y

        node = WorkflowNode(
            id=new_id,
            node_type=ntype,
            title=f"{ntype.value.replace('_', ' ').title()}",
            position={"x": node_x, "y": node_y}
        )
        self.dag.nodes[new_id] = node

        if not self.dag.entry_node_id:
            self.dag.entry_node_id = new_id

        # Update visual canvas items & selection
        self.scene.clearSelection()
        item = NodeGraphicsItem(node)
        item.setPos(node_x, node_y)
        self.scene.addItem(item)
        self.node_items[new_id] = item
        item.setSelected(True)
        self._last_added_node_id = new_id

        # Automatically wire the connection if auto-connect is active
        if source_node and source_port:
            edge = self.dag.add_edge(source_node.id, new_id, source_port=source_port, target_port="in")
            src_item = self.node_items.get(source_node.id)
            if src_item and edge.id not in self.scene.edge_items:
                eitem = EdgeGraphicsItem(edge, src_item, item)
                self.scene.addItem(eitem)
                self.scene.edge_items[edge.id] = eitem
            self.txt_logs.append(f"🔗 Auto-connected [{source_node.title}] ➔ [{node.title}] ({source_port})")

        self._update_node_dropdowns()
        self._refresh_diagnostics()
        self.txt_logs.append(f"Added [{ntype.value.upper()}] Node '{node.title}'")

    def _manual_connect_nodes(self):
        src_id = self.wire_src.currentData()
        dst_id = self.wire_dst.currentData()
        port = self.wire_port.currentText()
        if src_id and dst_id and src_id != dst_id:
            self._push_undo_state()
            self.dag.add_edge(src_id, dst_id, source_port=port)
            self._render_dag_on_canvas()
            self._refresh_diagnostics()
            self.txt_logs.append(f"Connected [{src_id}] -> [{dst_id}] ({port})")

    def _set_entry_node(self, node_id: str):
        if node_id in self.dag.nodes:
            self._push_undo_state()
            self.dag.entry_node_id = node_id
            self.txt_logs.append(f"🚩 Node '{self.dag.nodes[node_id].title}' set as Entry.")
            self._refresh_diagnostics()

    def _duplicate_node(self, node_id: str):
        orig = self.dag.nodes.get(node_id)
        if not orig:
            return
        self._push_undo_state()
        new_id = f"n_{uuid.uuid4().hex[:6]}"
        dup_node = WorkflowNode(
            id=new_id,
            node_type=orig.node_type,
            title=f"{orig.title} (Copy)",
            params=copy.deepcopy(orig.params),
            position={"x": orig.position.get("x", 0.0) + 40.0, "y": orig.position.get("y", 0.0) + 40.0},
            is_breakpoint=orig.is_breakpoint
        )
        self.dag.nodes[new_id] = dup_node
        self._render_dag_on_canvas()
        self._update_node_dropdowns()
        self._refresh_diagnostics()
        self.txt_logs.append(f"📋 Duplicated Node '{orig.title}'")

    def _toggle_node_breakpoint(self, node_id: str):
        node = self.dag.nodes.get(node_id)
        if node:
            node.is_breakpoint = not node.is_breakpoint
            if node_id in self.node_items:
                self.node_items[node_id].update()
            self.txt_logs.append(f"Breakpoint {'SET 🔴' if node.is_breakpoint else 'REMOVED ⚪'} on '{node.title}'")

    def _delete_node(self, node_id: str):
        if node_id not in self.dag.nodes:
            return
        self._push_undo_state()
        node_title = self.dag.nodes[node_id].title
        self.dag.edges = [e for e in self.dag.edges if e.source_node_id != node_id and e.target_node_id != node_id]
        del self.dag.nodes[node_id]
        if self.dag.entry_node_id == node_id:
            self.dag.entry_node_id = None
        if self._last_added_node_id == node_id:
            self._last_added_node_id = list(self.dag.nodes.keys())[-1] if self.dag.nodes else None
        
        self.selected_node = None
        self._render_dag_on_canvas()
        self._update_node_dropdowns()
        self._refresh_diagnostics()
        self.txt_logs.append(f"🗑️ Deleted Node '{node_title}'")

    def _delete_edge(self, edge_id: str):
        self._push_undo_state()
        self.dag.remove_edge(edge_id)
        self._render_dag_on_canvas()
        self._refresh_diagnostics()
        self.txt_logs.append(f"✂️ Deleted Connection ({edge_id[:6]})")

    def _delete_selected_items(self):
        selected = self.scene.selectedItems()
        if not selected:
            return

        self._push_undo_state()
        nodes_to_del = []
        edges_to_del = []

        for item in selected:
            if isinstance(item, NodeGraphicsItem):
                nodes_to_del.append(item.node.id)
            elif isinstance(item, EdgeGraphicsItem):
                edges_to_del.append(item.edge.id)

        for nid in nodes_to_del:
            self.dag.edges = [e for e in self.dag.edges if e.source_node_id != nid and e.target_node_id != nid]
            self.dag.nodes.pop(nid, None)
            if self.dag.entry_node_id == nid:
                self.dag.entry_node_id = None

        for eid in edges_to_del:
            self.dag.remove_edge(eid)

        self.selected_node = None
        self._render_dag_on_canvas()
        self._update_node_dropdowns()
        self._refresh_diagnostics()
        self.txt_logs.append(f"🗑️ Deleted {len(nodes_to_del)} node(s) and {len(edges_to_del)} wire(s).")

    def _on_canvas_selection_changed(self):
        try:
            if not hasattr(self, "scene") or not self.scene:
                return
            selected = self.scene.selectedItems()
            if selected and isinstance(selected[0], NodeGraphicsItem):
                self.selected_node = selected[0].node
                self._populate_properties(self.selected_node)
            else:
                self.selected_node = None
                if hasattr(self, "lbl_node_info_title") and self.lbl_node_info_title:
                    self.lbl_node_info_title.setText("Kein Node ausgewählt")
                    self.lbl_node_category_badge.setText("Klicke auf einen Node im Canvas oder wähle einen aus der Palette.")
                    self.lbl_node_desc.setText("Jeder Node im Workflow führt eine spezialisierte Browser-, Anti-Detect-, KI- oder Kontrollfluss-Funktion aus.")
                    self.lbl_node_params_help.setVisible(False)
        except (RuntimeError, AttributeError):
            return
        except Exception:
            pass

    def _get_available_vision_models(self) -> List[str]:
        """Returns all detected local and cloud Vision AI models."""
        models = [
            "50/50_smart_hybrid",
            "gemini-3.6-flash",
            "gemini-flash-lite-latest",
            "gemini-1.5-flash",
            "gemini-1.5-pro",
            "llava:7b",
            "moondream:latest",
            "moondream:v2",
            "qwen2.5vl:3b",
            "got-ocr2",
            "florence-2-base",
            "auto"
        ]
        try:
            from engine.ai_model_manager import AIModelManager
            mgr = AIModelManager.get_instance()
            installed = mgr.get_installed_model_ids_sync()
            vision_keywords = ["vision", "vl", "llava", "moondream", "florence", "ocr", "gemini", "qwen2.5vl"]
            for m in installed:
                if any(k in m.lower() for k in vision_keywords) and m not in models:
                    models.append(m)
        except Exception:
            pass
        return models

    def _get_available_hybrid_swarms(self) -> List[str]:
        """Returns all built-in and user-created custom AI Hybrid Groups and Swarms."""
        swarms = [
            "swarm_full_master",
            "hybrid_stealth_vla",
            "hybrid_eco_vision",
            "50/50_smart_hybrid"
        ]
        try:
            from engine.ai_hybrid_groups_manager import AIHybridGroupsManager
            hg_mgr = AIHybridGroupsManager.get_instance()
            for g in hg_mgr.get_all_groups():
                gid = g.get("id")
                if gid and gid not in swarms:
                    swarms.append(gid)
        except Exception:
            pass
        return swarms

    def _get_available_poker_models(self) -> List[str]:
        """Returns all AI models, Hybrid Swarms, and Custom Hybrid Groups for Poker Decision Making."""
        items = [
            "auto",
            "50/50_smart_hybrid"
        ]

        # 1. Custom Hybrid Groups and Swarms
        for swarm_id in self._get_available_hybrid_swarms():
            if swarm_id not in items:
                items.append(swarm_id)

        # 2. Priority Reasoning & Multimodal Models
        priority_models = [
            "deepseek-r1:1.5b",
            "deepseek-r1:7b",
            "qwen2.5:7b",
            "qwen2.5:3b",
            "qwen2.5:1.5b",
            "qwen2.5vl:3b",
            "gemini-2.0-flash",
            "gemini-1.5-flash",
            "gemini-1.5-pro",
            "gemini-3.6-flash",
            "moondream:v2",
            "florence-2-base",
            "got-ocr2",
            "llava:7b",
            "granite3-dense:2b",
            "hermes3:3b"
        ]
        for m in priority_models:
            if m not in items:
                items.append(m)

        # 3. Installed local Ollama / ONNX models
        try:
            from engine.ai_model_manager import AIModelManager
            mgr = AIModelManager.get_instance()
            installed = mgr.get_installed_model_ids_sync()
            for m in installed:
                if m not in items:
                    items.append(m)
        except Exception:
            pass

        return items

    def _get_available_text_models(self) -> List[str]:
        """Returns all detected local and cloud Text/LLM models and Hybrid Swarms."""
        models = [
            "auto",
            "gemini-3.6-flash",
            "gemini-flash-lite-latest",
            "gemini-1.5-flash",
            "gemini-1.5-pro",
            "qwen2.5:1.5b",
            "qwen2.5:3b",
            "qwen2.5:7b",
            "deepseek-r1:1.5b",
            "deepseek-r1:7b",
            "llama3.2:3b",
            "smolvlm:1.7b",
            "50/50_smart_hybrid"
        ]
        # Add custom hybrid swarms
        for s in self._get_available_hybrid_swarms():
            if s not in models:
                models.append(s)

        try:
            from engine.ai_model_manager import AIModelManager
            mgr = AIModelManager.get_instance()
            installed = mgr.get_installed_model_ids_sync()
            for m in installed:
                if m not in models:
                    models.append(m)
        except Exception:
            pass
        return models

    def _get_available_all_models(self) -> List[str]:
        """Returns all detected local and cloud AI models (multimodal, vision, text, STT, and custom hybrid swarms)."""
        installed = []
        try:
            from engine.ai_model_manager import AIModelManager
            mgr = AIModelManager.get_instance()
            installed = mgr.get_installed_model_ids_sync()
        except Exception:
            pass

        base_models = [
            "auto",
            "50/50_smart_hybrid",
            "gemini-2.0-flash",
            "gemini-1.5-flash",
            "gemini-1.5-pro",
            "deepseek-r1:1.5b",
            "qwen2.5:7b",
            "qwen2.5:1.5b",
            "qwen2.5:3b",
            "qwen2.5:0.5b",
            "qwen2.5vl:3b",
            "moondream:v2",
            "got-ocr2",
            "florence-2-base",
            "llava:7b",
            "granite3-dense:2b",
            "hermes3:3b",
            "whisper-base"
        ]

        combined = []
        for m in ["auto", "50/50_smart_hybrid"] + self._get_available_hybrid_swarms() + installed:
            if m not in combined:
                combined.append(m)
        for m in base_models:
            if m not in combined:
                combined.append(m)
        return combined

    def _populate_properties(self, node: WorkflowNode):
        self.prop_title.blockSignals(True)
        self.prop_use_ai.blockSignals(True)
        self.prop_p1.blockSignals(True)
        self.combo_p1.blockSignals(True)
        self.prop_p2.blockSignals(True)
        self.combo_p2.blockSignals(True)
        self.combo_p3.blockSignals(True)
        self.prop_num.blockSignals(True)
        self.prop_press_enter.blockSignals(True)
        self.prop_clear_first.blockSignals(True)
        self.prop_stop_on_err.blockSignals(True)
        self.combo_chess_speed.blockSignals(True)
        self.prop_chess_diff_depth.blockSignals(True)
        self.prop_antidetect.blockSignals(True)
        self.prop_chess_auto_move.blockSignals(True)

        try:
            self.prop_title.setText(node.title)
            ntype = node.node_type
            meta = get_node_metadata(ntype)

            # Update info card with function description & parameter documentation
            self.lbl_node_info_title.setText(f"{meta.get('label', ntype.value)}")
            self.lbl_node_category_badge.setText(f"📁 {meta.get('category', 'Allgemein')}")
            self.lbl_node_desc.setText(meta.get("description", ""))

            params_doc = meta.get("params_doc", {})
            if params_doc:
                help_lines = ["<span style='color:#38BDF8;'><b>Parameter:</b></span>"]
                for p_name, p_desc in params_doc.items():
                    help_lines.append(f"• <b>{p_name}</b>: {p_desc}")
                self.lbl_node_params_help.setText("<br>".join(help_lines))
                self.lbl_node_params_help.setVisible(True)
            else:
                self.lbl_node_params_help.setVisible(False)

            # Reset dynamic controls
            self.prop_use_ai.setVisible(False)
            self.lbl_p1.setVisible(False)
            self.prop_p1.setVisible(False)
            self.lbl_combo1.setVisible(False)
            self.combo_p1.setVisible(False)
            self.lbl_p2.setVisible(False)
            self.prop_p2.setVisible(False)
            self.lbl_combo2.setVisible(False)
            self.combo_p2.setVisible(False)
            self.lbl_combo3.setVisible(False)
            self.combo_p3.setVisible(False)
            self.lbl_num.setVisible(False)
            self.prop_num.setVisible(False)
            self.prop_press_enter.setVisible(False)
            self.prop_clear_first.setVisible(False)
            # Chess extra controls
            self.lbl_chess_speed.setVisible(False)
            self.combo_chess_speed.setVisible(False)
            self.lbl_chess_diff_depth.setVisible(False)
            self.prop_chess_diff_depth.setVisible(False)
            self.prop_antidetect.setVisible(False)
            self.prop_chess_auto_move.setVisible(False)

            self.combo_p1.clear()
            self.combo_p2.clear()
            self.combo_p3.clear()

            if ntype == NodeType.NAVIGATE:
                self.lbl_p1.setText("Target URL:")
                self.lbl_p1.setVisible(True)
                self.prop_p1.setVisible(True)
                self.prop_p1.setText(str(node.params.get("url") or node.params.get("param1") or "https://google.com"))
                self.prop_p1.setPlaceholderText("https://... or {target_url}")
                self.prop_p1.setToolTip("Ziel-Webadresse eingeben. Unterstützt Variablen wie {target_url}.")

                self.lbl_combo2.setText("Wait Until:")
                self.lbl_combo2.setVisible(True)
                self.combo_p2.setVisible(True)
                self.combo_p2.addItems(["domcontentloaded", "load", "networkidle", "commit"])
                self.combo_p2.setCurrentText(str(node.params.get("wait_until") or "domcontentloaded"))
                self.combo_p2.setToolTip("Ladebedingung: domcontentloaded (DOM bereit), load (vollständig geladen), networkidle (kein Netzwerkverkehr).")

                self.lbl_num.setText("Timeout (ms):")
                self.lbl_num.setVisible(True)
                self.prop_num.setVisible(True)
                self.prop_num.setValue(safe_float(node.params.get("timeout_ms"), 30000.0))
                self.prop_num.setToolTip("Maximales Zeitlimit für den Seitenaufruf in Millisekunden.")

            elif ntype == NodeType.NEW_TAB:
                self.lbl_p1.setText("New Tab URL:")
                self.lbl_p1.setVisible(True)
                self.prop_p1.setVisible(True)
                self.prop_p1.setText(str(node.params.get("url") or node.params.get("param1") or "about:blank"))
                self.prop_p1.setPlaceholderText("https://... or about:blank")
                self.prop_p1.setToolTip("Start-URL für den neuen Browser-Tab.")

            elif ntype == NodeType.SWITCH_TAB:
                self.lbl_num.setText("Tab Index (0-based):")
                self.lbl_num.setVisible(True)
                self.prop_num.setVisible(True)
                self.prop_num.setValue(safe_float(node.params.get("tab_index") or node.params.get("num_val"), 0.0))
                self.prop_num.setToolTip("0-basierter Index des Ziel-Tabs (0 = erster Tab, 1 = zweiter Tab).")

            elif ntype == NodeType.CLOSE_TAB:
                self.lbl_num.setText("Tab Index (-1 for active):")
                self.lbl_num.setVisible(True)
                self.prop_num.setVisible(True)
                self.prop_num.setValue(safe_float(node.params.get("tab_index") or node.params.get("num_val"), -1.0))
                self.prop_num.setToolTip("Index des zu schließenden Tabs (-1 = aktiver Tab).")

            elif ntype == NodeType.VLA_TYPE:
                self.prop_use_ai.setVisible(True)
                use_ai = bool(node.params.get("use_ai_generation", False))
                self.prop_use_ai.setChecked(use_ai)

                if use_ai:
                    self.lbl_p1.setText("AI Prompt:")
                    self.lbl_p1.setVisible(True)
                    self.prop_p1.setVisible(True)
                    self.prop_p1.setText(str(node.params.get("ai_prompt") or node.params.get("prompt") or node.params.get("text") or "Generate a natural search query for {query}"))
                    self.prop_p1.setPlaceholderText("Prompt for AI model or template with {variables}")
                    self.prop_p1.setToolTip("Prompt-Anweisung an das KI-Modell zur dynamischen Text-Erstellung.")

                    self.lbl_combo1.setText("AI Model:")
                    self.lbl_combo1.setVisible(True)
                    self.combo_p1.setVisible(True)
                    self.combo_p1.setEditable(True)
                    text_models = self._get_available_text_models()
                    self.combo_p1.addItems(text_models)
                    cur_model = str(node.params.get("ai_model") or "auto")
                    if cur_model not in text_models:
                        self.combo_p1.addItem(cur_model)
                    self.combo_p1.setCurrentText(cur_model)
                    self.combo_p1.setToolTip("Ausgewähltes KI-Modell zur Texterstellung (z. B. auto, gemini-3.6-flash, qwen2.5:1.5b, deepseek-r1).")

                    self.lbl_combo2.setText("Save to Var:")
                    self.lbl_combo2.setVisible(True)
                    self.combo_p2.setVisible(True)
                    self.combo_p2.setEditable(True)
                    self.combo_p2.addItems(["", "generated_text", "ai_query", "ai_comment", "typed_text"])
                    self.combo_p2.setCurrentText(str(node.params.get("save_to_var") or ""))
                    self.combo_p2.setToolTip("Optionale Workflow-Variable zur Speicherung des generierten Textes.")
                else:
                    self.lbl_p1.setText("Text to Type:")
                    self.lbl_p1.setVisible(True)
                    self.prop_p1.setVisible(True)
                    self.prop_p1.setText(str(node.params.get("text") or node.params.get("param1") or ""))
                    self.prop_p1.setPlaceholderText("Text or {var_name}")
                    self.prop_p1.setToolTip("Einzugebender Text. Variablen wie {query} werden dynamisch ersetzt.")

                self.lbl_p2.setText("Target Field / Selector:")
                self.lbl_p2.setVisible(True)
                self.prop_p2.setVisible(True)
                self.prop_p2.setText(str(node.params.get("instruction") or node.params.get("param2") or "Google search bar"))
                self.prop_p2.setToolTip("Selektor oder semantische Beschreibung des Ziel-Eingabefelds.")

                self.lbl_num.setText("Keystroke Speed (ms):")
                self.lbl_num.setVisible(True)
                self.prop_num.setVisible(True)
                self.prop_num.setValue(safe_float(node.params.get("delay_ms") or node.params.get("num_val"), 60.0))
                self.prop_num.setToolTip("Durchschnittliche Tastenanschlags-Verzögerung pro Zeichen in Millisekunden.")

                self.prop_press_enter.setVisible(True)
                self.prop_press_enter.setChecked(bool(node.params.get("press_enter", True)))
                self.prop_press_enter.setToolTip("Drückt nach Abschluss des Tippens automatisch Enter.")

                self.prop_clear_first.setVisible(True)
                self.prop_clear_first.setChecked(bool(node.params.get("clear_first", True)))
                self.prop_clear_first.setToolTip("Leert das Feld vor der Texteingabe vollständig.")

            elif ntype in [NodeType.VLA_CLICK, NodeType.HOVER]:
                self.lbl_combo1.setText("Mode:")
                self.lbl_combo1.setVisible(True)
                self.combo_p1.setVisible(True)
                self.combo_p1.addItems(["auto", "xpath", "selector", "coordinates", "vla_vision"])
                self.combo_p1.setCurrentText(str(node.params.get("click_mode") or "auto"))
                self.combo_p1.setToolTip("Interaktionsmodus: auto, vla_vision (KI-Vision), selector, xpath oder coordinates.")

                self.lbl_p1.setText("Target / XPath / Coords:")
                self.lbl_p1.setVisible(True)
                self.prop_p1.setVisible(True)
                self.prop_p1.setText(str(node.params.get("instruction") or node.params.get("param1") or "Click target"))
                self.prop_p1.setToolTip("Ziel-Element, semantische KI-Beschreibung oder XPath/CSS-Selektor.")

                self.lbl_num.setText("Jitter (px):")
                self.lbl_num.setVisible(True)
                self.prop_num.setVisible(True)
                self.prop_num.setValue(safe_float(node.params.get("jitter_px") or node.params.get("num_val"), 2.0))
                self.prop_num.setToolTip("Zufälliger Pixel-Offset zur Bot-Vermeidung.")

            elif ntype == NodeType.DRAG_DROP:
                self.lbl_p1.setText("Target Coordinates / Element:")
                self.lbl_p1.setVisible(True)
                self.prop_p1.setVisible(True)
                self.prop_p1.setText(str(node.params.get("instruction") or node.params.get("param1") or "Drag target"))
                self.prop_p1.setToolTip("Ziel-Element oder Koordinaten-Paar für die Drag & Drop Bewegung.")

            elif ntype == NodeType.KEY_PRESS:
                self.lbl_combo1.setText("Key to Press:")
                self.lbl_combo1.setVisible(True)
                self.combo_p1.setVisible(True)
                self.combo_p1.setEditable(True)
                self.combo_p1.addItems(["Enter", "Escape", "Tab", "Space", "Backspace", "ArrowDown", "ArrowUp", "Control+A", "Control+C", "Control+V"])
                self.combo_p1.setCurrentText(str(node.params.get("key") or node.params.get("param1") or "Enter"))
                self.combo_p1.setToolTip("Zu sendende Taste oder Tastenkombination (Enter, Escape, Tab, Hotkeys).")

            elif ntype == NodeType.SCROLL:
                self.lbl_combo1.setText("Direction:")
                self.lbl_combo1.setVisible(True)
                self.combo_p1.setVisible(True)
                self.combo_p1.addItems(["down", "up", "bottom", "top"])
                self.combo_p1.setCurrentText(str(node.params.get("direction") or node.params.get("param1") or "down"))
                self.combo_p1.setToolTip("Scroll-Richtung: down (nach unten), up (nach oben), bottom (Seitenende), top (Seitenanfang).")

                self.lbl_num.setText("Distance (px):")
                self.lbl_num.setVisible(True)
                self.prop_num.setVisible(True)
                self.prop_num.setValue(safe_float(node.params.get("pixels") or node.params.get("num_val"), 500.0))
                self.prop_num.setToolTip("Scroll-Distanz in Pixeln.")

            elif ntype == NodeType.WAIT:
                self.lbl_p1.setText("Step Notes:")
                self.lbl_p1.setVisible(True)
                self.prop_p1.setVisible(True)
                self.prop_p1.setText(str(node.params.get("notes") or node.params.get("param1") or ""))
                self.prop_p1.setToolTip("Optionale Notiz oder Beschreibung für diesen Warte-Schritt.")

                self.lbl_num.setText("Duration (s):")
                self.lbl_num.setVisible(True)
                self.prop_num.setVisible(True)
                self.prop_num.setValue(safe_float(node.params.get("duration") or node.params.get("num_val"), 2.0))
                self.prop_num.setToolTip("Wartezeit in Sekunden (wird mit natürlichem humanen Jitter ausgeführt).")

            elif ntype == NodeType.SOLVE_CAPTCHA:
                self.lbl_p1.setText("Target Barrier:")
                self.lbl_p1.setVisible(True)
                self.prop_p1.setVisible(True)
                self.prop_p1.setText(str(node.params.get("captcha_type") or "auto"))
                self.prop_p1.setToolTip("Target Barrier: 'auto' (Smart Detection), 'normal' (Normal Captcha / Image-to-Text), 'turnstile', 'recaptcha', 'hcaptcha', 'funcaptcha'.")

                self.lbl_combo1.setText("Strategy:")
                self.lbl_combo1.setVisible(True)
                self.combo_p1.setVisible(True)
                self.combo_p1.addItems(["auto", "normal_first", "vision_first", "audio_first", "50/50_smart_hybrid", "audio_only", "vision_only"])
                self.combo_p1.setCurrentText(str(node.params.get("strategy") or node.params.get("param1") or "auto"))
                self.combo_p1.setToolTip("Lösungs-Strategie: auto, normal_first, vision_first, audio_first, 50/50_smart_hybrid.")

                self.lbl_combo2.setText("Audio STT Model:")
                self.lbl_combo2.setVisible(True)
                self.combo_p2.setVisible(True)
                self.combo_p2.setEditable(True)
                self.combo_p2.addItems(["base", "tiny", "small", "medium", "large-v3-turbo", "gemini-audio"])
                self.combo_p2.setCurrentText(str(node.params.get("whisper_model") or "base"))
                self.combo_p2.setToolTip("Whisper Speech-to-Text Modell für Audio-Captchas.")

                self.lbl_combo3.setText("Vision Model:")
                self.lbl_combo3.setVisible(True)
                self.combo_p3.setVisible(True)
                self.combo_p3.setEditable(True)
                vision_models = self._get_available_vision_models()
                self.combo_p3.addItems(vision_models)
                cur_vision = str(node.params.get("vision_model") or node.params.get("param2") or "50/50_smart_hybrid")
                if cur_vision not in vision_models:
                    self.combo_p3.addItem(cur_vision)
                self.combo_p3.setCurrentText(cur_vision)
                self.combo_p3.setToolTip("Vision-KI Modell für visuelle Captcha-Challenges.")

                self.lbl_num.setText("Timeout (s):")
                self.lbl_num.setVisible(True)
                self.prop_num.setVisible(True)
                self.prop_num.setValue(safe_float(node.params.get("timeout_sec") or node.params.get("num_val"), 45.0))
                self.prop_num.setToolTip("Maximales Zeitlimit für die Captcha-Lösung in Sekunden.")

            elif ntype == NodeType.CONDITION:
                self.lbl_combo1.setText("Condition Type:")
                self.lbl_combo1.setVisible(True)
                self.combo_p1.setVisible(True)
                self.combo_p1.addItems(["url_contains", "text_exists", "element_exists", "var_equals"])
                self.combo_p1.setCurrentText(str(node.params.get("condition_type") or node.params.get("param1") or "url_contains"))
                self.combo_p1.setToolTip("Bedingungs-Typ: url_contains, text_exists, element_exists, var_equals.")

                self.lbl_p2.setText("Expected Match:")
                self.lbl_p2.setVisible(True)
                self.prop_p2.setVisible(True)
                self.prop_p2.setText(str(node.params.get("expected") or node.params.get("param2") or ""))
                self.prop_p2.setToolTip("Erwarteter Suchwert, Text oder Variablenwert zum Abgleich.")

            elif ntype == NodeType.AI_DECISION:
                self.lbl_p1.setText("Decision Prompt:")
                self.lbl_p1.setVisible(True)
                self.prop_p1.setVisible(True)
                self.prop_p1.setText(str(node.params.get("prompt") or node.params.get("param1") or "Is the target in stock?"))
                self.prop_p1.setToolTip("Entscheidungs-Frage an die KI (z. B. 'Ist der Artikel auf Lager?'). Ja führt zu True-Port, Nein zu False-Port.")

            elif ntype == NodeType.AI_MODEL_TASK:
                task_types = [
                    "analyze_screenshot",
                    "extract_text_ocr",
                    "transcribe_audio",
                    "security_pentest",
                    "summarize_page",
                    "custom_prompt"
                ]
                self.lbl_combo1.setText("Task Type:")
                self.lbl_combo1.setVisible(True)
                self.combo_p1.setVisible(True)
                self.combo_p1.addItems(task_types)
                cur_task = str(node.params.get("task_type") or "analyze_screenshot")
                if cur_task not in task_types:
                    self.combo_p1.addItem(cur_task)
                self.combo_p1.setCurrentText(cur_task)
                self.combo_p1.setToolTip("Wähle die modellspezifische Aufgabe: Screenshot-Analyse, OCR-Textextraktion, Audio-Transkription (Whisper), Pentest-Sicherheitscheck, Zusammenfassung.")

                self.lbl_combo2.setText("AI Model:")
                self.lbl_combo2.setVisible(True)
                self.combo_p2.setVisible(True)
                self.combo_p2.setEditable(True)
                all_models = self._get_available_all_models()
                self.combo_p2.addItems(all_models)
                cur_model = str(node.params.get("model_name") or "auto")
                if cur_model not in all_models:
                    self.combo_p2.addItem(cur_model)
                self.combo_p2.setCurrentText(cur_model)
                self.combo_p2.setToolTip("Ausgewähltes Modell für diese Aufgabe (z. B. Gemini, Qwen-VL, GOT-OCR2, Whisper, DeepSeek).")

                self.lbl_p1.setText("Prompt / Task Instruction:")
                self.lbl_p1.setVisible(True)
                self.prop_p1.setVisible(True)
                self.prop_p1.setText(str(node.params.get("prompt") or node.params.get("param1") or ""))
                self.prop_p1.setPlaceholderText("Prompt or instruction for the AI model (supports {variables})")
                self.prop_p1.setToolTip("Spezifische Anweisung oder Prompt an das Modell.")

                self.lbl_p2.setText("Save result into Variable:")
                self.lbl_p2.setVisible(True)
                self.prop_p2.setVisible(True)
                self.prop_p2.setText(str(node.params.get("save_to_var") or node.params.get("param2") or "ai_result"))
                self.prop_p2.setPlaceholderText("Variable name (e.g. ocr_text, audit_report)")
                self.prop_p2.setToolTip("Workflow-Variable, in der das Analyse-/Extraktions-Ergebnis abgelegt wird.")

                self.lbl_combo3.setText("Optional Selector / Scope:")
                self.lbl_combo3.setVisible(True)
                self.combo_p3.setVisible(True)
                self.combo_p3.setEditable(True)
                self.combo_p3.addItems(["", "body", "audio", "video", "main", "form", "article"])
                self.combo_p3.setCurrentText(str(node.params.get("selector") or ""))
                self.combo_p3.setToolTip("Optionaler CSS/XPath-Selektor zur Eingrenzung (z. B. für Element-Screenshot oder Audio-Tag).")

            elif ntype == NodeType.LOOP:
                self.lbl_p1.setText("Counter Variable:")
                self.lbl_p1.setVisible(True)
                self.prop_p1.setVisible(True)
                self.prop_p1.setText(str(node.params.get("counter_var") or node.params.get("param1") or "loop_index"))
                self.prop_p1.setToolTip("Name der Schleifenindex-Variable (Standard: loop_index).")

                self.lbl_num.setText("Iterations:")
                self.lbl_num.setVisible(True)
                self.prop_num.setVisible(True)
                self.prop_num.setRange(1, 999999)
                self.prop_num.setValue(safe_float(node.params.get("iterations") or node.params.get("num_val"), 5.0))
                self.prop_num.setToolTip("Anzahl der Schleifendurchläufe.")

            elif ntype == NodeType.EXTRACT_DATA:
                self.lbl_p1.setText("Selector:")
                self.lbl_p1.setVisible(True)
                self.prop_p1.setVisible(True)
                self.prop_p1.setText(str(node.params.get("selector") or node.params.get("param1") or "body"))
                self.prop_p1.setToolTip("CSS- oder XPath-Selektor des Quell-Elements.")

                self.lbl_p2.setText("Save into Variable:")
                self.lbl_p2.setVisible(True)
                self.prop_p2.setVisible(True)
                self.prop_p2.setText(str(node.params.get("var_name") or node.params.get("param2") or "extracted_data"))
                self.prop_p2.setToolTip("Name der Ziel-Variable zur Speicherung des extrahierten Werts.")

                self.lbl_combo2.setText("Attribute:")
                self.lbl_combo2.setVisible(True)
                self.combo_p2.setVisible(True)
                self.combo_p2.setEditable(True)
                self.combo_p2.addItems(["innerText", "innerHTML", "value", "href", "src"])
                self.combo_p2.setCurrentText(str(node.params.get("attribute") or "innerText"))
                self.combo_p2.setToolTip("Zu extrahierendes Attribut: innerText, innerHTML, value, href, src.")

            elif ntype == NodeType.SCREENSHOT:
                self.lbl_p1.setText("Save Path:")
                self.lbl_p1.setVisible(True)
                self.prop_p1.setVisible(True)
                self.prop_p1.setText(str(node.params.get("path") or node.params.get("param1") or "storage/screenshots/screenshot.png"))
                self.prop_p1.setToolTip("Dateipfad zum Speichern der Screenshot-Bilddatei.")

            elif ntype == NodeType.DOWNLOAD_WAIT:
                self.lbl_p1.setText("File Pattern / Name:")
                self.lbl_p1.setVisible(True)
                self.prop_p1.setVisible(True)
                self.prop_p1.setText(str(node.params.get("filename_pattern") or node.params.get("param1") or ""))
                self.prop_p1.setToolTip("Dateimuster oder Dateiname des Downloads (z. B. *.pdf oder report.csv).")

                self.lbl_num.setText("Timeout (s):")
                self.lbl_num.setVisible(True)
                self.prop_num.setVisible(True)
                self.prop_num.setValue(safe_float(node.params.get("timeout_sec") or node.params.get("num_val"), 30.0))
                self.prop_num.setToolTip("Maximales Warte-Timeout für den Download in Sekunden.")

            elif ntype == NodeType.FINGERPRINT_MORPH:
                self.lbl_combo1.setText("Intensity:")
                self.lbl_combo1.setVisible(True)
                self.combo_p1.setVisible(True)
                self.combo_p1.addItems(["mild", "moderate", "aggressive"])
                self.combo_p1.setCurrentText(str(node.params.get("intensity") or node.params.get("param1") or "mild"))
                self.combo_p1.setToolTip("Morphing-Intensität: mild, moderate oder aggressive.")

            elif ntype == NodeType.ROTATE_PROXY:
                self.lbl_combo1.setText("Rotation Mode:")
                self.lbl_combo1.setVisible(True)
                self.combo_p1.setVisible(True)
                self.combo_p1.addItems(["auto_fallback", "force_pool", "url_only"])
                self.combo_p1.setCurrentText(str(node.params.get("rotation_mode") or node.params.get("param1") or "auto_fallback"))
                self.combo_p1.setToolTip("auto_fallback: Versucht Change-IP-URL, fällt bei Fehlen/Fehler auf neuen unbenutzten Proxy_Pool Proxy zurück. force_pool: Wählt immer direkt einen unbenutzten Pool-Proxy.")

                self.lbl_combo2.setText("Proxy Pool Group:")
                self.lbl_combo2.setVisible(True)
                self.combo_p2.setVisible(True)
                self.combo_p2.setEditable(True)
                pool_groups = ["All", "Default", "Imported"]
                try:
                    from storage.proxy_manager import ProxyManager
                    for p in ProxyManager().list_proxies(sort_speed=False):
                        grp = p.get("group")
                        if grp and grp not in pool_groups:
                            pool_groups.append(grp)
                except Exception:
                    pass
                self.combo_p2.addItems(pool_groups)
                cur_grp = str(node.params.get("proxy_group") or node.params.get("param2") or "All")
                if cur_grp not in pool_groups:
                    self.combo_p2.addItem(cur_grp)
                self.combo_p2.setCurrentText(cur_grp)
                self.combo_p2.setToolTip("Filtert Fallback-Proxies nach Gruppe (z. B. 'Default', 'Imported' oder 'All' für alle Gruppen).")

                self.lbl_p1.setText("Custom Change-IP URL (Optional):")
                self.lbl_p1.setVisible(True)
                self.prop_p1.setVisible(True)
                self.prop_p1.setText(str(node.params.get("change_ip_url") or ""))
                self.prop_p1.setPlaceholderText("https://api.proxyprovider.com/rotate?key=... (leer lassen für Profil-Standard)")
                self.prop_p1.setToolTip("Optionale spezifische Rotations-URL. Wenn leer, wird die URL des aktiven Profils genutzt.")

            elif ntype == NodeType.ADVERSARIAL_AUDIT:
                self.lbl_combo1.setText("Audit Focus:")
                self.lbl_combo1.setVisible(True)
                self.combo_p1.setVisible(True)
                self.combo_p1.addItems(["turnstile_focus", "full", "quick"])
                self.combo_p1.setCurrentText(str(node.params.get("audit_mode") or node.params.get("param1") or "turnstile_focus"))
                self.combo_p1.setToolTip("Audit-Fokus: turnstile_focus (Turnstile/Cloudflare), full, quick.")

            elif ntype == NodeType.PRE_ACTION_CHECK:
                self.lbl_p1.setText("Target / Action Check:")
                self.lbl_p1.setVisible(True)
                self.prop_p1.setVisible(True)
                self.prop_p1.setText(str(node.params.get("selector") or node.params.get("param1") or "body"))
                self.prop_p1.setToolTip("Selektor des Ziel-Elements zur Vorab-Verifikation.")

            elif ntype == NodeType.JAVASCRIPT_EVAL:
                self.lbl_p1.setText("JS Script:")
                self.lbl_p1.setVisible(True)
                self.prop_p1.setVisible(True)
                self.prop_p1.setText(str(node.params.get("script") or node.params.get("param1") or "return document.title;"))
                self.prop_p1.setToolTip("JavaScript-Code, der im Seitenkontext ausgeführt werden soll.")

                self.lbl_p2.setText("Save result to Var:")
                self.lbl_p2.setVisible(True)
                self.prop_p2.setVisible(True)
                self.prop_p2.setText(str(node.params.get("save_to_var") or node.params.get("param2") or "js_result"))
                self.prop_p2.setToolTip("Variable zur Speicherung des Rückgabewerts.")

            elif ntype == NodeType.CHESS_SOLVER:
                # --- Row 1: Platform ---
                self.lbl_combo1.setText("Platform:")
                self.lbl_combo1.setVisible(True)
                self.combo_p1.setVisible(True)
                self.combo_p1.addItems(["auto", "chess_com", "lichess", "generic"])
                self.combo_p1.setCurrentText(str(node.params.get("platform") or "auto"))
                self.combo_p1.setToolTip("Ziel-Plattform zur automatischen Board-Erkennung.")

                # --- Row 2: Engine Mode ---
                self.lbl_combo2.setText("Engine Mode:")
                self.lbl_combo2.setVisible(True)
                self.combo_p2.setVisible(True)
                self.combo_p2.addItems([
                    "super_grandmaster_godmode",
                    "ai_hybrid_ensemble",
                    "ai_deepseek_reasoning",
                    "ai_qwen_tactics",
                    "ai_vision_vlm",
                    "stockfish",
                    "builtin"
                ])
                self.combo_p2.setCurrentText(str(node.params.get("engine_type") or "super_grandmaster_godmode"))
                self.combo_p2.setToolTip("Modus: 👑 Super Grandmaster Godmode (3500+ ELO Stockfish 18 NNUE + Theory Book + DeepSeek-R1 CoT), AI Hybrid Ensemble, DeepSeek-R1 Reasoning, Qwen 2.5 Tactics, Vision VLM, Stockfish oder Builtin Minimax.")

                # --- Row 3: AI Model ---
                self.lbl_combo3.setText("AI Model / Swarm:")
                self.lbl_combo3.setVisible(True)
                self.combo_p3.setVisible(True)
                self.combo_p3.addItems([
                    "auto",
                    "deepseek-r1:1.5b",
                    "qwen2.5:7b",
                    "qwen2.5:1.5b",
                    "qwen2.5vl:3b",
                    "moondream:v2",
                    "gemini-1.5-flash",
                    "gemini-1.5-pro",
                    "gemini-2.0-flash"
                ])
                cur_m = str(node.params.get("ai_model") or node.params.get("model_name") or "auto")
                self.combo_p3.setCurrentText(cur_m)
                self.combo_p3.setToolTip("Spezifisches lokales Modell für die Zug- und Strategieberechnung.")

                # --- Row 4: Target Elo ---
                self.lbl_p1.setText("Target Elo:")
                self.lbl_p1.setVisible(True)
                self.prop_p1.setVisible(True)
                self.prop_p1.setText(str(node.params.get("target_elo") or "1500"))
                self.prop_p1.setToolTip("Ziel-Elo für EloThrottleController & HumanizedTimingEngine (z. B. 1200, 1500, 1800, 2400).")

                # --- Row 5: Stockfish Depth ---
                self.lbl_num.setText("Stockfish Depth:")
                self.lbl_num.setVisible(True)
                self.prop_num.setVisible(True)
                self.prop_num.setRange(1, 50)
                self.prop_num.setValue(safe_float(node.params.get("depth"), 18.0))
                self.prop_num.setToolTip("Suchtiefe für Stockfish (1 bis 50 Plies). Höher = besser, aber langsamer.")

                # --- Row 6: Speed Preset (chess-specific) ---
                self.lbl_chess_speed.setVisible(True)
                self.combo_chess_speed.setVisible(True)
                self.combo_chess_speed.setCurrentText(str(node.params.get("speed_preset") or "blitz"))

                # --- Row 7: Difficulty Depth (chess-specific) ---
                self.lbl_chess_diff_depth.setVisible(True)
                self.prop_chess_diff_depth.setVisible(True)
                self.prop_chess_diff_depth.setValue(int(safe_float(node.params.get("difficulty_depth"), 12.0)))

                # --- Row 8: Anti-Detect toggle ---
                self.prop_antidetect.setVisible(True)
                self.prop_antidetect.setChecked(bool(node.params.get("anti_detect", True)))

                # --- Row 9: Auto-Move toggle ---
                self.prop_chess_auto_move.setVisible(True)
                self.prop_chess_auto_move.setChecked(bool(node.params.get("auto_move", True)))

                # --- Row 10: Save to Var ---
                self.lbl_p2.setText("Save Move to Var:")
                self.lbl_p2.setVisible(True)
                self.prop_p2.setVisible(True)
                self.prop_p2.setText(str(node.params.get("save_to_var") or "chess_move"))

            elif ntype == NodeType.POKER_SOLVER:
                self.lbl_combo1.setText("Strategy Profile:")
                self.lbl_combo1.setVisible(True)
                self.combo_p1.setVisible(True)
                self.combo_p1.addItems([
                    "ai_all_models_hybrid",
                    "ai_deepseek_reasoning",
                    "ai_vision_vlm",
                    "ai_adaptive",
                    "gto_balanced",
                    "tight_aggressive",
                    "loose_aggressive"
                ])
                self.combo_p1.setCurrentText(str(node.params.get("strategy") or "ai_all_models_hybrid"))
                self.combo_p1.setToolTip("Spielstrategie: ai_all_models_hybrid (Vision + DeepSeek-R1 + Monte Carlo), AI DeepSeek Reasoning, GTO Balanced, Tight-Aggressive, Loose-Aggressive.")

                self.lbl_combo2.setText("AI Model / Hybrid Swarm:")
                self.lbl_combo2.setVisible(True)
                self.combo_p2.setVisible(True)
                self.combo_p2.setEditable(True)
                poker_models = self._get_available_poker_models()
                self.combo_p2.addItems(poker_models)
                cur_m = str(node.params.get("ai_model") or node.params.get("model_name") or "auto")
                if cur_m not in poker_models:
                    self.combo_p2.addItem(cur_m)
                self.combo_p2.setCurrentText(cur_m)
                self.combo_p2.setToolTip("Ausgewähltes KI-Modell oder Custom AI Hybrid Swarm für Grandmaster Chain-of-Thought Reasoning (z. B. swarm_full_master, hybrid_stealth_vla, custom_hybrid, deepseek-r1, qwen2.5, gemini).")

                self.lbl_num.setText("Opponents:")
                self.lbl_num.setVisible(True)
                self.prop_num.setVisible(True)
                self.prop_num.setRange(1, 9)
                self.prop_num.setValue(safe_float(node.params.get("num_opponents"), 1.0))
                self.prop_num.setToolTip("Anzahl aktiver Gegenspieler in der Hand.")

                self.lbl_p2.setText("Save Action to Var:")
                self.lbl_p2.setVisible(True)
                self.prop_p2.setVisible(True)
                self.prop_p2.setText(str(node.params.get("save_to_var") or "poker_action"))

            elif ntype == NodeType.TERMINATE:
                self.lbl_combo1.setText("Status:")
                self.lbl_combo1.setVisible(True)
                self.combo_p1.setVisible(True)
                self.combo_p1.addItems(["success", "failed", "aborted"])
                self.combo_p1.setCurrentText(str(node.params.get("status") or node.params.get("param1") or "success"))
                self.combo_p1.setToolTip("Workflow-Endstatus: success (Erfolg), failed (Fehler), aborted (Abgebrochen).")

            else:
                self.lbl_p1.setText("Param 1:")
                self.lbl_p1.setVisible(True)
                self.prop_p1.setVisible(True)
                self.prop_p1.setText(str(node.params.get("param1", "")))
                self.prop_p1.setToolTip("Zusätzlicher Parameterwert für diesen Node-Typ.")

            self.prop_stop_on_err.setChecked(bool(node.params.get("stop_on_error", True)))
            self.prop_stop_on_err.setToolTip("Stoppt die gesamte Workflow-Ausführung sofort, wenn dieser Node fehlschlägt.")
        finally:
            self.prop_title.blockSignals(False)
            self.prop_use_ai.blockSignals(False)
            self.prop_p1.blockSignals(False)
            self.combo_p1.blockSignals(False)
            self.prop_p2.blockSignals(False)
            self.combo_p2.blockSignals(False)
            self.combo_p3.blockSignals(False)
            self.prop_num.blockSignals(False)
            self.prop_press_enter.blockSignals(False)
            self.prop_clear_first.blockSignals(False)
            self.prop_stop_on_err.blockSignals(False)
            self.combo_chess_speed.blockSignals(False)
            self.prop_chess_diff_depth.blockSignals(False)
            self.prop_antidetect.blockSignals(False)
            self.prop_chess_auto_move.blockSignals(False)

    def _on_prop_use_ai_toggled(self, checked: bool):
        if not self.selected_node or self.selected_node.node_type != NodeType.VLA_TYPE:
            return
        self._push_undo_state()
        self.selected_node.params["use_ai_generation"] = checked
        if checked and not self.selected_node.params.get("ai_prompt"):
            self.selected_node.params["ai_prompt"] = self.selected_node.params.get("text") or "Generate a natural search query for {query}"
        self.dag.updated_at = time.time()
        self._populate_properties(self.selected_node)

    def _on_prop_title_changed(self, text: str):
        if self.selected_node:
            self.selected_node.title = text
            self.dag.updated_at = time.time()
            if self.selected_node.id in self.node_items:
                self.node_items[self.selected_node.id].update()

    def _on_prop_p1_changed(self, text: str):
        if not self.selected_node:
            return
        nt = self.selected_node.node_type
        if nt in [NodeType.NAVIGATE, NodeType.NEW_TAB]:
            self.selected_node.params["url"] = text
        elif nt == NodeType.VLA_TYPE:
            if self.selected_node.params.get("use_ai_generation", False):
                self.selected_node.params["ai_prompt"] = text
            else:
                self.selected_node.params["text"] = text
        elif nt in [NodeType.VLA_CLICK, NodeType.HOVER]:
            self.selected_node.params["instruction"] = text
        elif nt == NodeType.LOOP:
            self.selected_node.params["counter_var"] = text
        elif nt in [NodeType.EXTRACT_DATA, NodeType.PRE_ACTION_CHECK]:
            self.selected_node.params["selector"] = text
        elif nt == NodeType.JAVASCRIPT_EVAL:
            self.selected_node.params["script"] = text
        elif nt == NodeType.DOWNLOAD_WAIT:
            self.selected_node.params["filename_pattern"] = text
        elif nt == NodeType.ROTATE_PROXY:
            self.selected_node.params["change_ip_url"] = text
        elif nt == NodeType.WAIT:
            self.selected_node.params["notes"] = text
        elif nt in [NodeType.AI_DECISION, NodeType.AI_MODEL_TASK]:
            self.selected_node.params["prompt"] = text
        elif nt == NodeType.SCREENSHOT:
            self.selected_node.params["path"] = text
        elif nt == NodeType.CHESS_SOLVER:
            self.selected_node.params["target_elo"] = text
        elif nt == NodeType.SOLVE_CAPTCHA:
            self.selected_node.params["captcha_type"] = text.strip()
        else:
            self.selected_node.params["param1"] = text
        self.selected_node.params["param1"] = text
        self.dag.updated_at = time.time()

    def _on_prop_p2_changed(self, text: str):
        if not self.selected_node:
            return
        nt = self.selected_node.node_type
        if nt == NodeType.VLA_TYPE:
            self.selected_node.params["instruction"] = text
        elif nt == NodeType.AI_MODEL_TASK:
            self.selected_node.params["save_to_var"] = text
        elif nt == NodeType.CONDITION:
            self.selected_node.params["expected"] = text
        elif nt == NodeType.EXTRACT_DATA:
            self.selected_node.params["var_name"] = text
        elif nt == NodeType.JAVASCRIPT_EVAL:
            self.selected_node.params["save_to_var"] = text
        elif nt in [NodeType.CHESS_SOLVER, NodeType.POKER_SOLVER]:
            self.selected_node.params["save_to_var"] = text
        else:
            self.selected_node.params["param2"] = text
        self.selected_node.params["param2"] = text
        self.dag.updated_at = time.time()

    def _on_combo_p1_changed(self, text: str):
        if not self.selected_node or not text.strip():
            return
        val = text.strip()
        nt = self.selected_node.node_type
        if nt in [NodeType.VLA_CLICK, NodeType.HOVER]:
            self.selected_node.params["click_mode"] = val
        elif nt == NodeType.VLA_TYPE:
            self.selected_node.params["ai_model"] = val
        elif nt == NodeType.AI_MODEL_TASK:
            self.selected_node.params["task_type"] = val
            cur_m = str(self.selected_node.params.get("model_name", "auto"))
            if val in ["security_pentest", "summarize_page", "custom_prompt"] and cur_m in ["got-ocr2", "whisper", "faster-whisper", "sensevoice-small"]:
                self.selected_node.params["model_name"] = "auto"
                self.combo_p2.setCurrentText("auto")
            elif val == "extract_text_ocr" and cur_m == "auto":
                self.selected_node.params["model_name"] = "got-ocr2"
                self.combo_p2.setCurrentText("got-ocr2")
            elif val == "transcribe_audio" and cur_m == "auto":
                self.selected_node.params["model_name"] = "whisper-base"
                self.combo_p2.setCurrentText("whisper-base")
        elif nt == NodeType.KEY_PRESS:
            self.selected_node.params["key"] = val
        elif nt == NodeType.SCROLL:
            self.selected_node.params["direction"] = val
        elif nt == NodeType.SOLVE_CAPTCHA:
            self.selected_node.params["strategy"] = val
        elif nt == NodeType.CONDITION:
            self.selected_node.params["condition_type"] = val
        elif nt == NodeType.FINGERPRINT_MORPH:
            self.selected_node.params["intensity"] = val
        elif nt == NodeType.ROTATE_PROXY:
            self.selected_node.params["rotation_mode"] = val
        elif nt == NodeType.ADVERSARIAL_AUDIT:
            self.selected_node.params["audit_mode"] = val
        elif nt == NodeType.CHESS_SOLVER:
            self.selected_node.params["platform"] = val
        elif nt == NodeType.POKER_SOLVER:
            self.selected_node.params["strategy"] = val
        elif nt == NodeType.TERMINATE:
            self.selected_node.params["status"] = val
        self.selected_node.params["param1"] = val
        self.dag.updated_at = time.time()

    def _on_combo_p2_changed(self, text: str):
        if not self.selected_node or not text.strip():
            return
        val = text.strip()
        nt = self.selected_node.node_type
        if nt == NodeType.NAVIGATE:
            self.selected_node.params["wait_until"] = val
        elif nt == NodeType.VLA_TYPE:
            self.selected_node.params["save_to_var"] = val
        elif nt == NodeType.AI_MODEL_TASK:
            self.selected_node.params["model_name"] = val
        elif nt == NodeType.SOLVE_CAPTCHA:
            self.selected_node.params["whisper_model"] = val
        elif nt == NodeType.EXTRACT_DATA:
            self.selected_node.params["attribute"] = val
        elif nt == NodeType.ROTATE_PROXY:
            self.selected_node.params["proxy_group"] = val
        elif nt == NodeType.CHESS_SOLVER:
            self.selected_node.params["engine_type"] = val
        elif nt == NodeType.POKER_SOLVER:
            self.selected_node.params["ai_model"] = val
            self.selected_node.params["model_name"] = val
        self.dag.updated_at = time.time()

    def _on_combo_p3_changed(self, text: str):
        if not self.selected_node or not text.strip():
            return
        val = text.strip()
        nt = self.selected_node.node_type
        if nt == NodeType.SOLVE_CAPTCHA:
            self.selected_node.params["vision_model"] = val
            self.selected_node.params["param2"] = val
        elif nt == NodeType.AI_MODEL_TASK:
            self.selected_node.params["selector"] = val
        elif nt == NodeType.CHESS_SOLVER:
            self.selected_node.params["ai_model"] = val
            self.selected_node.params["model_name"] = val
        self.dag.updated_at = time.time()

    def _on_prop_press_enter_changed(self, checked: bool):
        if self.selected_node and self.selected_node.node_type == NodeType.VLA_TYPE:
            self.selected_node.params["press_enter"] = checked
            self.dag.updated_at = time.time()

    def _on_prop_clear_first_changed(self, checked: bool):
        if self.selected_node and self.selected_node.node_type == NodeType.VLA_TYPE:
            self.selected_node.params["clear_first"] = checked
            self.dag.updated_at = time.time()

    # ---- Chess Anti-Detect extra signal handlers ----

    def _on_chess_speed_changed(self, text: str):
        if self.selected_node and self.selected_node.node_type == NodeType.CHESS_SOLVER:
            self.selected_node.params["speed_preset"] = text.strip()
            self.dag.updated_at = time.time()

    def _on_chess_diff_depth_changed(self, val: int):
        if self.selected_node and self.selected_node.node_type == NodeType.CHESS_SOLVER:
            self.selected_node.params["difficulty_depth"] = val
            self.dag.updated_at = time.time()

    def _on_chess_antidetect_changed(self, checked: bool):
        if self.selected_node and self.selected_node.node_type == NodeType.CHESS_SOLVER:
            self.selected_node.params["anti_detect"] = checked
            self.dag.updated_at = time.time()

    def _on_chess_auto_move_changed(self, checked: bool):
        if self.selected_node and self.selected_node.node_type == NodeType.CHESS_SOLVER:
            self.selected_node.params["auto_move"] = checked
            self.dag.updated_at = time.time()

    def _on_prop_num_changed(self, val: float):
        if not self.selected_node:
            return
        nt = self.selected_node.node_type
        if nt == NodeType.WAIT:
            self.selected_node.params["duration"] = val
        elif nt == NodeType.SCROLL:
            self.selected_node.params["pixels"] = int(val)
        elif nt == NodeType.LOOP:
            self.selected_node.params["iterations"] = int(val)
        elif nt in [NodeType.SWITCH_TAB, NodeType.CLOSE_TAB]:
            self.selected_node.params["tab_index"] = int(val)
        elif nt == NodeType.NAVIGATE:
            self.selected_node.params["timeout_ms"] = val
        elif nt in [NodeType.SOLVE_CAPTCHA, NodeType.DOWNLOAD_WAIT]:
            self.selected_node.params["timeout_sec"] = val
        elif nt in [NodeType.VLA_CLICK, NodeType.HOVER]:
            self.selected_node.params["jitter_px"] = val
        elif nt == NodeType.CHESS_SOLVER:
            self.selected_node.params["depth"] = int(val)
        elif nt == NodeType.POKER_SOLVER:
            self.selected_node.params["num_opponents"] = int(val)
        else:
            self.selected_node.params["num_val"] = val
        self.selected_node.params["num_val"] = val
        self.dag.updated_at = time.time()

    def _on_prop_stop_err_changed(self, checked: bool):
        if self.selected_node:
            self.selected_node.params["stop_on_error"] = checked
            self.dag.updated_at = time.time()

    def _clear_canvas(self):
        self._push_undo_state()
        self.dag.nodes.clear()
        self.dag.edges.clear()
        self.dag.entry_node_id = None
        self._last_added_node_id = None
        self.current_project_filepath = None
        self._render_dag_on_canvas()
        self._update_node_dropdowns()
        self._update_title_header()
        self._refresh_diagnostics()
        self.txt_logs.append("Canvas cleared.")

    # ---------------- Bottom Tabs Helpers ----------------

    def _add_runtime_variable(self):
        key, ok1 = QInputDialog.getText(self, "Add Variable", "Variable Key:")
        if not ok1 or not key.strip():
            return
        val, ok2 = QInputDialog.getText(self, "Add Variable", "Variable Value:")
        if ok2:
            self.dag.variables[key.strip()] = val.strip()
            self._on_variables_updated(self.dag.variables)

    def _generate_playwright_code(self):
        code = self.dag.export_to_playwright_python()
        self.txt_generated_code.setText(code)

    def _copy_python_code(self):
        code = self.dag.export_to_playwright_python()
        from PyQt6.QtWidgets import QApplication
        cb = QApplication.clipboard()
        if cb:
            cb.setText(code)
            self.txt_logs.append("📋 Generated Playwright Python code copied to clipboard.")

    def _refresh_diagnostics(self):
        diags = self.dag.validate_dag()
        lines = []
        for d in diags:
            lvl = d.get("level", "info").upper()
            msg = d.get("message", "")
            icon = "✅" if lvl == "SUCCESS" else ("⚠️" if lvl == "WARNING" else "ℹ️")
            lines.append(f"{icon} [{lvl}] {msg}")
        self.txt_diagnostics.setText("\n".join(lines))
        self._generate_playwright_code()

    # ---------------- Profiles & Execution ----------------

    def reload_profiles(self):
        if not hasattr(self, "combo_target_profile"):
            return
        
        current_selection = self.combo_target_profile.currentData()
        self.combo_target_profile.blockSignals(True)
        self.combo_target_profile.clear()
        
        profiles = self.profile_manager.list_profiles() if hasattr(self.profile_manager, "list_profiles") else []
        if not profiles and hasattr(self.profile_manager, "get_profiles"):
            profiles = self.profile_manager.get_profiles()

        running_ids = set()
        if self.launcher and hasattr(self.launcher, "running_processes"):
            running_ids = set(self.launcher.running_processes.keys())

        if not profiles:
            self.combo_target_profile.addItem("No Profiles Available", None)
            self.combo_target_profile.blockSignals(False)
            return

        # 1. Single Profiles
        for prof in profiles:
            pid = prof.get("id", "")
            pname = prof.get("name", "Unnamed Profile")
            is_running = pid in running_ids
            icon = "🟢" if is_running else "⚪"
            engine_str = prof.get("engine", "camoufox").capitalize()
            label = f"{icon} {pname} ({engine_str})"
            self.combo_target_profile.addItem(label, pid)

        # 2. Multi-Profile Bulk Targets
        self.combo_target_profile.insertSeparator(self.combo_target_profile.count())
        self.combo_target_profile.addItem(f"🌐 All Saved Profiles ({len(profiles)})", "__ALL_SAVED__")
        if running_ids:
            self.combo_target_profile.addItem(f"🟢 All Running Profiles ({len(running_ids)})", "__ALL_RUNNING__")
        self.combo_target_profile.addItem("👥 Custom Multi-Selection...", "__CUSTOM_MULTI__")

        if current_selection:
            for idx in range(self.combo_target_profile.count()):
                if self.combo_target_profile.itemData(idx) == current_selection:
                    self.combo_target_profile.setCurrentIndex(idx)
                    break

        self.combo_target_profile.blockSignals(False)
        self._update_run_buttons_state()

    def _on_profile_selection_changed(self):
        target_val = self.combo_target_profile.currentData()
        if target_val == "__CUSTOM_MULTI__":
            self._open_multi_profile_dialog()
        else:
            self._update_run_buttons_state()

    def _open_multi_profile_dialog(self):
        profiles = self.profile_manager.list_profiles() if hasattr(self.profile_manager, "list_profiles") else []
        if not profiles and hasattr(self.profile_manager, "get_profiles"):
            profiles = self.profile_manager.get_profiles()

        running_ids = set()
        if self.launcher and hasattr(self.launcher, "running_processes"):
            running_ids = set(self.launcher.running_processes.keys())

        # If currently in custom selection, keep selected IDs; otherwise pre-select all or running
        init_sel = self.multi_profile_ids if self.multi_profile_ids else [p.get("id") for p in profiles if p.get("id")]
        dialog = WorkflowMultiProfileDialog(
            profiles=profiles,
            running_ids=running_ids,
            initially_selected=init_sel,
            current_concurrency=self.multi_concurrency,
            parent=self
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.multi_profile_ids = dialog.get_selected_profiles()
            self.multi_concurrency = dialog.get_concurrency()
            self.is_multi_mode = True
            
            # Select "__CUSTOM_MULTI__" in dropdown if not already selected
            self.combo_target_profile.blockSignals(True)
            for idx in range(self.combo_target_profile.count()):
                if self.combo_target_profile.itemData(idx) == "__CUSTOM_MULTI__":
                    self.combo_target_profile.setItemText(idx, f"👥 Custom Multi ({len(self.multi_profile_ids)} profiles)")
                    self.combo_target_profile.setCurrentIndex(idx)
                    break
            self.combo_target_profile.blockSignals(False)
            self._update_run_buttons_state()

    def _update_run_buttons_state(self):
        target_val = self.combo_target_profile.currentData()
        if target_val in ["__ALL_SAVED__", "__ALL_RUNNING__", "__CUSTOM_MULTI__"] or (self.is_multi_mode and len(self.multi_profile_ids) > 1):
            self.is_multi_mode = True
            count = len(self.multi_profile_ids) if target_val == "__CUSTOM_MULTI__" else ("All" if target_val == "__ALL_SAVED__" else "Running")
            self.btn_run_profile.setText(f"🚀 Run Multi ({count}) (F5)")
            self.btn_run_profile.setToolTip(f"Executes workflow across {count} browser profiles concurrently (Workers: {self.multi_concurrency})")
            self.btn_run_headless.setText("▶️ Multi Headless")
        else:
            self.is_multi_mode = False
            self.btn_run_profile.setText("🚀 Run (F5)")
            self.btn_run_profile.setToolTip("Auto-launches target browser profile and executes workflow (F5)")
            self.btn_run_headless.setText("▶️ Headless")

    def _start_execution(self, in_browser: bool = True):
        target_val = self.combo_target_profile.currentData() if hasattr(self, "combo_target_profile") else None

        if target_val in ["__ALL_SAVED__", "__ALL_RUNNING__", "__CUSTOM_MULTI__"]:
            profiles = self.profile_manager.list_profiles() if hasattr(self.profile_manager, "list_profiles") else []
            if not profiles and hasattr(self.profile_manager, "get_profiles"):
                profiles = self.profile_manager.get_profiles()

            if target_val == "__ALL_SAVED__":
                target_pids = [p.get("id") for p in profiles if p.get("id")]
            elif target_val == "__ALL_RUNNING__":
                running_ids = set(self.launcher.running_processes.keys()) if self.launcher and hasattr(self.launcher, "running_processes") else set()
                target_pids = [p.get("id") for p in profiles if p.get("id") in running_ids]
            else:  # __CUSTOM_MULTI__
                target_pids = list(self.multi_profile_ids)

            if not target_pids:
                self.txt_logs.append("⚠️ No target profiles found or selected for Multi-Browser run.")
                return

            if hasattr(self, "tab_multi_widget"):
                self.bottom_tabs.setCurrentWidget(self.tab_multi_widget)
            asyncio.create_task(self._async_run_multi_workflow(target_pids, in_browser=in_browser))
        else:
            self.bottom_tabs.setCurrentIndex(0)
            asyncio.create_task(self._async_run_workflow(in_browser=in_browser))

    async def _async_run_workflow(self, in_browser: bool = True):
        target_pid = self.combo_target_profile.currentData() if hasattr(self, "combo_target_profile") else None
        page = None

        if in_browser and target_pid and self.launcher:
            self.txt_logs.append(f"🔍 Preparing browser profile '{target_pid}' for workflow...")
            running_procs = getattr(self.launcher, "running_processes", {})
            
            if target_pid not in running_procs:
                self.txt_logs.append(f"🚀 Launching browser profile '{target_pid}'...")
                try:
                    success, msg, _ = await self.launcher.launch_profile(target_pid)
                    if not success:
                        self.txt_logs.append(f"❌ Failed to launch browser profile: {msg}")
                        return
                    self.txt_logs.append(f"✅ Browser profile started successfully: {msg}")
                    await asyncio.sleep(1.2)
                except Exception as l_err:
                    self.txt_logs.append(f"❌ Browser launch exception: {l_err}")
                    return

            try:
                page = self.launcher.get_active_page(target_pid)
                if page:
                    self.txt_logs.append(f"🌐 Attached to active browser page for profile '{target_pid}'.")
                else:
                    self.txt_logs.append(f"⚠️ Warning: Could not retrieve active page object, executing in decoupled mode.")
            except Exception as p_err:
                self.txt_logs.append(f"⚠️ Warning on page attachment: {p_err}")

        self.txt_logs.append(f"⚡ Starting DAG Runner: '{self.dag.name}' (in_browser={in_browser and page is not None})...")
        self.runner = WorkflowDAGRunner(self.dag)
        await self.runner.execute(
            page=page,
            log_cb=self._append_log_message,
            node_status_cb=self._on_node_status_changed,
            var_update_cb=self._on_variables_updated,
            badge_update_cb=self._on_node_badge_updated,
            profile_id=target_pid,
            launcher=self.launcher
        )

    async def _async_run_multi_workflow(self, profile_ids: List[str], in_browser: bool = True):
        """Runs the workflow DAG across multiple profiles concurrently using MultiWorkflowRunner."""
        profiles = self.profile_manager.list_profiles() if hasattr(self.profile_manager, "list_profiles") else []
        if not profiles and hasattr(self.profile_manager, "get_profiles"):
            profiles = self.profile_manager.get_profiles()

        prof_map = {p.get("id"): p for p in profiles if p.get("id")}
        p_names = {pid: prof_map.get(pid, {}).get("name", pid[:8]) for pid in profile_ids}

        # Initialize Multi Matrix Table
        total_profs = len(profile_ids)
        self.lbl_multi_summary.setText(f"👥 Multi-Browser Execution: Running {total_profs} profile(s) (Concurrency: {self.multi_concurrency})")
        self.multi_progress_bar.setValue(0)
        self.table_multi_matrix.setRowCount(total_profs)

        row_map: Dict[str, int] = {}
        for row, pid in enumerate(profile_ids):
            row_map[pid] = row
            prof = prof_map.get(pid, {})
            pname = prof.get("name", pid[:8])
            engine = prof.get("engine", "camoufox").capitalize()

            item_prof = QTableWidgetItem(f"{pname} ({pid[:8]})")
            item_prof.setData(Qt.ItemDataRole.UserRole, pid)
            self.table_multi_matrix.setItem(row, 0, item_prof)

            self.table_multi_matrix.setItem(row, 1, QTableWidgetItem(engine))
            self.table_multi_matrix.setItem(row, 2, QTableWidgetItem("🕒 Queued"))
            self.table_multi_matrix.setItem(row, 3, QTableWidgetItem("—"))
            self.table_multi_matrix.setItem(row, 4, QTableWidgetItem("0%"))
            self.table_multi_matrix.setItem(row, 5, QTableWidgetItem("0.0s"))
            self.table_multi_matrix.setItem(row, 6, QTableWidgetItem("Pending"))

        start_time = time.time()

        def _on_p_status(pid: str, st: str, current_node: Optional[str], prog: float):
            row = row_map.get(pid)
            if row is not None:
                st_icons = {
                    "queued": "🕒 Queued",
                    "launching": "🚀 Launching",
                    "running": "🟢 Running",
                    "completed": "✅ Success",
                    "failed": "❌ Failed",
                    "error": "❌ Error",
                    "stopped": "🛑 Stopped",
                    "paused": "⏸️ Paused"
                }
                status_display = st_icons.get(st.lower(), st.capitalize())
                self.table_multi_matrix.setItem(row, 2, QTableWidgetItem(status_display))
                if current_node:
                    self.table_multi_matrix.setItem(row, 3, QTableWidgetItem(current_node))
                self.table_multi_matrix.setItem(row, 4, QTableWidgetItem(f"{int(prog * 100)}%"))
                elapsed = time.time() - start_time
                self.table_multi_matrix.setItem(row, 5, QTableWidgetItem(f"{elapsed:.1f}s"))

        def _on_p_node_status(pid: str, nid: str, st: str):
            # Update canvas if active selected profile matches or general execution
            self._on_node_status_changed(nid, st)

        self.multi_runner = MultiWorkflowRunner(self.dag, profile_ids, max_concurrency=self.multi_concurrency)
        results = await self.multi_runner.execute(
            launcher=self.launcher,
            in_browser=in_browser,
            log_cb=self._append_log_message,
            profile_status_cb=_on_p_status,
            node_status_cb=_on_p_node_status,
            profile_names=p_names
        )

        total_elapsed = time.time() - start_time
        succ_count = sum(1 for r in results.values() if r.get("success"))
        self.lbl_multi_summary.setText(f"🎉 Multi-Browser Finished: {succ_count}/{total_profs} succeeded in {total_elapsed:.1f}s.")
        self.multi_progress_bar.setValue(100)

        for pid, res in results.items():
            row = row_map.get(pid)
            if row is not None:
                succ = res.get("success", False)
                res_str = "✅ SUCCESS" if succ else f"❌ {res.get('error', 'Failed')}"
                self.table_multi_matrix.setItem(row, 6, QTableWidgetItem(res_str))
                dur = res.get("duration", 0.0)
                self.table_multi_matrix.setItem(row, 5, QTableWidgetItem(f"{dur:.1f}s"))

    def _append_log_message(self, msg: str):
        self.txt_logs.append(msg)
        if hasattr(self, "chk_autoscroll") and self.chk_autoscroll.isChecked():
            sb = self.txt_logs.verticalScrollBar()
            if sb:
                sb.setValue(sb.maximum())

    def _toggle_selected_breakpoint(self):
        if self.selected_node:
            self._toggle_node_breakpoint(self.selected_node.id)
        else:
            self.txt_logs.append("ℹ️ Select a node on the canvas to toggle its breakpoint (F9).")

    def _toggle_node_breakpoint(self, node_id: str):
        if node_id in self.dag.nodes:
            n = self.dag.nodes[node_id]
            n.is_breakpoint = not n.is_breakpoint
            if node_id in self.node_items:
                self.node_items[node_id].update()
            state_str = "ENABLED (🔴)" if n.is_breakpoint else "DISABLED"
            self.txt_logs.append(f"🔴 Breakpoint {state_str} for Node '{n.title}'")

    def _toggle_pause_resume(self):
        active_runner = self.multi_runner if (self.is_multi_mode and self.multi_runner) else self.runner
        if not active_runner or active_runner.state in [WorkflowExecutionState.IDLE, WorkflowExecutionState.COMPLETED, WorkflowExecutionState.FAILED, WorkflowExecutionState.STOPPED]:
            self._start_execution(in_browser=True)
            return

        if active_runner.state == WorkflowExecutionState.RUNNING:
            active_runner.pause()
            if hasattr(self, "btn_pause_resume"):
                self.btn_pause_resume.setText("▶️ Resume (F5)")
            self.txt_logs.append("⏸️ Workflow PAUSED. Browser Takeover enabled — you can now interact manually with the page. Click 'Resume' or press F5 when ready.")
        elif active_runner.state in [WorkflowExecutionState.PAUSED, WorkflowExecutionState.STEPPING]:
            active_runner.resume()
            if hasattr(self, "btn_pause_resume"):
                self.btn_pause_resume.setText("⏸️ Pause / Takeover")
            self.txt_logs.append("▶️ Workflow RESUMED.")

    def _step_workflow(self):
        if self.is_multi_mode and self.multi_runner:
            self.multi_runner.step()
            self.txt_logs.append("⏭️ Stepping multi-browser runners...")
            return

        if not self.runner or self.runner.state in [WorkflowExecutionState.IDLE, WorkflowExecutionState.COMPLETED, WorkflowExecutionState.FAILED, WorkflowExecutionState.STOPPED]:
            self.dag.entry_node_id = self.selected_node.id if self.selected_node else self.dag.entry_node_id
            self.runner = WorkflowDAGRunner(self.dag)
            self.runner.state = WorkflowExecutionState.STEPPING
            self.bottom_tabs.setCurrentIndex(0)
            asyncio.create_task(self._async_run_workflow(in_browser=True))
        else:
            self.runner.step()
            self.txt_logs.append("⏭️ Stepping to next node...")

    def _stop_workflow(self):
        if self.multi_runner:
            self.multi_runner.stop()
        if self.runner:
            self.runner.stop()
        if hasattr(self, "btn_pause_resume"):
            self.btn_pause_resume.setText("⏸️ Pause / Takeover")
        self.txt_logs.append("🛑 Stopped DAG execution.")

    def _on_node_status_changed(self, node_id: str, status: str):
        if node_id in self.node_items:
            self.node_items[node_id].set_execution_status(status)

    def _on_node_badge_updated(self, node_id: str, badge_text: str):
        if node_id in self.node_items:
            self.node_items[node_id].set_live_badge(badge_text)

    def _on_variables_updated(self, vars_dict: Dict[str, Any]):
        self.table_vars.setRowCount(len(vars_dict))
        for r, (k, v) in enumerate(vars_dict.items()):
            self.table_vars.setItem(r, 0, QTableWidgetItem(k))
            self.table_vars.setItem(r, 1, QTableWidgetItem(str(v)))

    # ---------------- Integrated File & Content Editor ----------------

    def open_file_in_editor(self, filepath: str):
        """Loads any local text/code/data file or image screenshot into the integrated Editor."""
        if not filepath:
            return

        # Resolve relative path to project root
        if not os.path.isabs(filepath):
            proj_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            cand = os.path.join(proj_root, filepath)
            if os.path.exists(cand):
                filepath = cand

        self.edit_editor_path.setText(filepath)
        ext = os.path.splitext(filepath)[1].lower()

        if ext in [".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"]:
            if os.path.exists(filepath):
                pixmap = QPixmap(filepath)
                if not pixmap.isNull():
                    scaled = pixmap.scaled(720, 360, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    self.lbl_image_preview.setPixmap(scaled)
                    self.lbl_image_preview.setVisible(True)
                    self.txt_file_editor.setVisible(False)
                else:
                    self.lbl_image_preview.setText(f"⚠️ Could not decode image: {filepath}")
                    self.lbl_image_preview.setVisible(True)
                    self.txt_file_editor.setVisible(False)
            else:
                self.lbl_image_preview.setText(f"⚠️ Image file does not exist yet: {filepath}")
                self.lbl_image_preview.setVisible(True)
                self.txt_file_editor.setVisible(False)
        else:
            self.lbl_image_preview.setVisible(False)
            self.txt_file_editor.setVisible(True)
            if os.path.exists(filepath):
                try:
                    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()
                    self.txt_file_editor.setPlainText(content)
                except Exception as ex:
                    self.txt_file_editor.setPlainText(f"Error reading file '{filepath}': {ex}")
            else:
                self.txt_file_editor.setPlainText(f"# File '{filepath}' does not exist on disk yet.\n# You can write content here and click 'Save File' to create it.")

        self.bottom_tabs.setCurrentWidget(self.tab_editor_widget)

    def open_content_in_editor(self, title: str, content: str):
        """Displays arbitrary memory text, JSON, or logs in the Editor."""
        self.edit_editor_path.setText(title)
        self.lbl_image_preview.setVisible(False)
        self.txt_file_editor.setVisible(True)
        self.txt_file_editor.setPlainText(content)
        self.bottom_tabs.setCurrentWidget(self.tab_editor_widget)

    def _on_editor_browse_file(self):
        proj_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open File in Editor",
            proj_root,
            "All Supported Files (*.json *.txt *.csv *.py *.html *.log *.md *.png *.jpg *.webp);;Text Files (*.txt *.log *.md);;JSON Files (*.json);;Python Files (*.py);;Images (*.png *.jpg *.webp);;All Files (*)"
        )
        if path:
            self.open_file_in_editor(path)

    def _on_editor_save_file(self):
        filepath = self.edit_editor_path.text().strip()
        if not filepath or filepath.startswith("Memory:") or filepath.startswith("Variable:") or filepath.startswith("JS Script:") or filepath.startswith("AI Task Result") or filepath.startswith("Node Content:"):
            path, _ = QFileDialog.getSaveFileName(self, "Save File As", "", "All Files (*)")
            if not path:
                return
            filepath = path
            self.edit_editor_path.setText(filepath)

        try:
            os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(self.txt_file_editor.toPlainText())
            self.txt_logs.append(f"💾 File saved successfully: {filepath}")
            QMessageBox.information(self, "File Saved", f"Successfully saved file:\n{filepath}")
        except Exception as ex:
            QMessageBox.critical(self, "Save Error", f"Failed to save file:\n{ex}")

    def _on_editor_reload_file(self):
        filepath = self.edit_editor_path.text().strip()
        if filepath and os.path.exists(filepath):
            self.open_file_in_editor(filepath)

    def _on_editor_copy_content(self):
        content = self.txt_file_editor.toPlainText()
        if content:
            from PyQt6.QtWidgets import QApplication
            clipboard = QApplication.clipboard()
            if clipboard:
                clipboard.setText(content)
                self.txt_logs.append("📋 Copied editor content to clipboard.")

    def _on_var_cell_double_clicked(self, row: int, col: int):
        var_name_item = self.table_vars.item(row, 0)
        var_val_item = self.table_vars.item(row, 1)
        if not var_name_item or not var_val_item:
            return
        var_name = var_name_item.text()
        var_val = var_val_item.text()

        proj_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        cand_path = os.path.join(proj_root, var_val) if not os.path.isabs(var_val) else var_val

        if os.path.exists(cand_path) or var_val.startswith("storage/") or var_val.endswith((".png", ".jpg", ".jpeg", ".webp", ".json", ".txt", ".csv", ".py", ".html", ".log")):
            self.open_file_in_editor(var_val)
        else:
            self.open_content_in_editor(f"Variable: {var_name}", var_val)

    def _on_open_selected_var_in_editor(self):
        cur_row = self.table_vars.currentRow()
        if cur_row >= 0:
            self._on_var_cell_double_clicked(cur_row, 0)
        else:
            QMessageBox.information(self, "Select Variable", "Please select a variable in the table first.")

    def _on_prop_open_in_editor(self):
        if not self.selected_node:
            return
        nt = self.selected_node.node_type
        if nt == NodeType.SCREENSHOT:
            path = self.selected_node.params.get("path") or "storage/screenshots/screenshot.png"
            self.open_file_in_editor(path)
        elif nt == NodeType.DOWNLOAD_WAIT:
            pattern = self.selected_node.params.get("filename_pattern") or ""
            downloads_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "storage", "downloads")
            cand = os.path.join(downloads_dir, pattern) if pattern else downloads_dir
            self.open_file_in_editor(cand)
        elif nt == NodeType.JAVASCRIPT_EVAL:
            script = self.selected_node.params.get("script") or "return document.title;"
            self.open_content_in_editor(f"JS Script: {self.selected_node.title}", script)
        elif nt == NodeType.AI_MODEL_TASK:
            save_var = str(self.selected_node.params.get("save_to_var") or "ai_result")
            val = self.dag.variables.get(save_var, "")
            self.open_content_in_editor(f"AI Task Result (${save_var})", str(val))
        else:
            p1 = str(self.selected_node.params.get("param1") or self.selected_node.params.get("text") or "")
            if os.path.exists(p1):
                self.open_file_in_editor(p1)
            else:
                self.open_content_in_editor(f"Node Content: {self.selected_node.title}", p1)

    def _delete_selected_node(self):
        if self.selected_node:
            self._delete_node(self.selected_node.id)
