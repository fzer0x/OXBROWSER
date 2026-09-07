import unittest
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QPointF

from engine.workflow_engine import NodeType, WorkflowDAG, WorkflowNode
from ui.views.workflow_builder_view import WorkflowBuilderView

# Ensure single QApplication instance for Qt tests
app = QApplication.instance() or QApplication([])

class TestWorkflowAutoConnect(unittest.TestCase):

    def setUp(self):
        self.view = WorkflowBuilderView()
        self.view._clear_canvas()

    def test_auto_connect_sequential_chain(self):
        self.view.auto_connect_enabled = True
        
        # 1. Add Start node
        self.view._add_node_at(NodeType.START, 0.0, 0.0)
        self.assertEqual(len(self.view.dag.nodes), 1)
        self.assertEqual(len(self.view.dag.edges), 0)
        
        # 2. Add Navigate node -> should automatically connect START -> NAVIGATE
        self.view._add_node_at(NodeType.NAVIGATE, 0.0, 0.0)
        self.assertEqual(len(self.view.dag.nodes), 2)
        self.assertEqual(len(self.view.dag.edges), 1)
        
        # Verify edge
        edge1 = self.view.dag.edges[0]
        start_id = [nid for nid, n in self.view.dag.nodes.items() if n.node_type == NodeType.START][0]
        nav_id = [nid for nid, n in self.view.dag.nodes.items() if n.node_type == NodeType.NAVIGATE][0]
        self.assertEqual(edge1.source_node_id, start_id)
        self.assertEqual(edge1.target_node_id, nav_id)
        self.assertEqual(edge1.source_port, "out")
        self.assertEqual(edge1.target_port, "in")

        # 3. Add Wait node -> should automatically connect NAVIGATE -> WAIT
        self.view._add_node_at(NodeType.WAIT, 0.0, 0.0)
        self.assertEqual(len(self.view.dag.nodes), 3)
        self.assertEqual(len(self.view.dag.edges), 2)
        
        wait_id = [nid for nid, n in self.view.dag.nodes.items() if n.node_type == NodeType.WAIT][0]
        edge2 = self.view.dag.edges[1]
        self.assertEqual(edge2.source_node_id, nav_id)
        self.assertEqual(edge2.target_node_id, wait_id)

    def test_auto_connect_disabled_toggle(self):
        self.view._on_auto_connect_toggled(False)
        self.assertFalse(self.view.auto_connect_enabled)
        self.assertFalse(self.view.chk_auto_connect_palette.isChecked())
        self.assertFalse(self.view.chk_auto_connect_toolbar.isChecked())

        self.view._add_node_at(NodeType.START, 0.0, 0.0)
        self.view._add_node_at(NodeType.NAVIGATE, 100.0, 100.0)
        
        # When disabled, no edges should be created automatically
        self.assertEqual(len(self.view.dag.nodes), 2)
        self.assertEqual(len(self.view.dag.edges), 0)

    def test_auto_connect_condition_branching(self):
        self.view.auto_connect_enabled = True
        
        # Add Condition node
        self.view._add_node_at(NodeType.CONDITION, 0.0, 0.0)
        cond_id = list(self.view.dag.nodes.keys())[0]

        # Add First target node -> should connect to "true"
        self.view._add_node_at(NodeType.VLA_CLICK, 0.0, 0.0)
        self.assertEqual(len(self.view.dag.edges), 1)
        self.assertEqual(self.view.dag.edges[0].source_port, "true")

        # Select condition node again and add another node -> should connect to "false"
        self.view.scene.clearSelection()
        self.view.node_items[cond_id].setSelected(True)
        self.view._add_node_at(NodeType.SCROLL, 0.0, 0.0)
        self.assertEqual(len(self.view.dag.edges), 2)
        self.assertEqual(self.view.dag.edges[1].source_port, "false")


if __name__ == "__main__":
    unittest.main()
