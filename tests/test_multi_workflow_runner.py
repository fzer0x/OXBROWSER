import os
import unittest
import asyncio
from typing import Dict, Any

from engine.workflow_engine import (
    WorkflowDAG, WorkflowNode, WorkflowEdge, NodeType,
    WorkflowDAGRunner, MultiWorkflowRunner, WorkflowExecutionState
)


class TestMultiWorkflowRunner(unittest.IsolatedAsyncioTestCase):

    def _create_sample_dag(self) -> WorkflowDAG:
        dag = WorkflowDAG(name="Multi Profile Test DAG")
        n1 = WorkflowNode(id="start", node_type=NodeType.START, title="Start")
        n2 = WorkflowNode(id="wait", node_type=NodeType.WAIT, title="Simulate Work", params={"duration": 0.05})
        n3 = WorkflowNode(id="term", node_type=NodeType.TERMINATE, title="Finish", params={"status": "success"})

        dag.nodes = {"start": n1, "wait": n2, "term": n3}
        dag.entry_node_id = "start"
        dag.add_edge("start", "wait")
        dag.add_edge("wait", "term")
        dag.variables = {"run_mode": "multi"}
        return dag

    async def test_multi_profile_execution_isolation(self):
        dag = self._create_sample_dag()
        profile_ids = ["prof_alpha", "prof_beta", "prof_gamma"]
        profile_names = {
            "prof_alpha": "Alpha Profile (Camoufox)",
            "prof_beta": "Beta Profile (Chromium)",
            "prof_gamma": "Gamma Profile (Camoufox)"
        }

        logs = []
        statuses = {}
        node_updates = []

        def log_cb(msg: str):
            logs.append(msg)

        def profile_status_cb(pid: str, st: str, node: str, prog: float):
            statuses[pid] = st

        def node_status_cb(pid: str, nid: str, st: str):
            node_updates.append((pid, nid, st))

        multi_runner = MultiWorkflowRunner(dag, profile_ids, max_concurrency=2)
        results = await multi_runner.execute(
            launcher=None,
            in_browser=False,
            log_cb=log_cb,
            profile_status_cb=profile_status_cb,
            node_status_cb=node_status_cb,
            profile_names=profile_names
        )

        self.assertEqual(len(results), 3)
        for pid in profile_ids:
            self.assertIn(pid, results)
            self.assertTrue(results[pid]["success"])
            self.assertEqual(statuses[pid], "completed")

        self.assertEqual(multi_runner.state, WorkflowExecutionState.COMPLETED)
        self.assertTrue(any("Multi-Browser Run Completed: 3 Succeeded" in l for l in logs))

    async def test_multi_profile_stop_coordination(self):
        dag = WorkflowDAG(name="Long Multi Workflow")
        n1 = WorkflowNode(id="start", node_type=NodeType.START, title="Start")
        n2 = WorkflowNode(id="wait", node_type=NodeType.WAIT, title="Long Wait", params={"duration": 2.0})
        n3 = WorkflowNode(id="term", node_type=NodeType.TERMINATE, title="Finish")
        dag.nodes = {"start": n1, "wait": n2, "term": n3}
        dag.entry_node_id = "start"
        dag.add_edge("start", "wait")
        dag.add_edge("wait", "term")

        profile_ids = ["prof_1", "prof_2", "prof_3"]
        multi_runner = MultiWorkflowRunner(dag, profile_ids, max_concurrency=3)

        async def _stop_soon():
            await asyncio.sleep(0.1)
            multi_runner.stop()

        asyncio.create_task(_stop_soon())
        results = await multi_runner.execute(launcher=None, in_browser=False)

        self.assertEqual(multi_runner.state, WorkflowExecutionState.STOPPED)

    async def test_multi_profile_pause_and_resume(self):
        dag = WorkflowDAG(name="Pause Resume Multi Workflow")
        n1 = WorkflowNode(id="start", node_type=NodeType.START, title="Start")
        n2 = WorkflowNode(id="wait1", node_type=NodeType.WAIT, title="Wait 1", params={"duration": 0.05})
        n3 = WorkflowNode(id="wait2", node_type=NodeType.WAIT, title="Wait 2", params={"duration": 0.05})
        n4 = WorkflowNode(id="term", node_type=NodeType.TERMINATE, title="Finish")
        dag.nodes = {"start": n1, "wait1": n2, "wait2": n3, "term": n4}
        dag.entry_node_id = "start"
        dag.add_edge("start", "wait1")
        dag.add_edge("wait1", "wait2")
        dag.add_edge("wait2", "term")

        multi_runner = MultiWorkflowRunner(dag, ["p1", "p2"], max_concurrency=2)

        async def _pause_then_resume():
            await asyncio.sleep(0.02)
            multi_runner.pause()
            self.assertEqual(multi_runner.state, WorkflowExecutionState.PAUSED)
            await asyncio.sleep(0.05)
            multi_runner.resume()
            self.assertEqual(multi_runner.state, WorkflowExecutionState.RUNNING)

        asyncio.create_task(_pause_then_resume())
        results = await multi_runner.execute(launcher=None, in_browser=False)
        self.assertEqual(len(results), 2)
        self.assertTrue(results["p1"]["success"])
        self.assertTrue(results["p2"]["success"])

    async def test_multi_profile_concurrency_throttling(self):
        dag = self._create_sample_dag()
        profile_ids = [f"prof_{i}" for i in range(6)]
        multi_runner = MultiWorkflowRunner(dag, profile_ids, max_concurrency=2)
        
        results = await multi_runner.execute(launcher=None, in_browser=False)
        self.assertEqual(len(results), 6)
        for pid in profile_ids:
            self.assertTrue(results[pid]["success"])


if __name__ == "__main__":
    unittest.main()
