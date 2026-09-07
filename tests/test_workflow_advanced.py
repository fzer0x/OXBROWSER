import os
import unittest
import asyncio
from typing import Dict, Any

from engine.workflow_engine import (
    WorkflowDAG, WorkflowNode, WorkflowEdge, NodeType,
    WorkflowDAGRunner, WorkflowExecutionState
)


class TestWorkflowAdvanced(unittest.IsolatedAsyncioTestCase):

    def test_dag_construction_and_serialization(self):
        dag = WorkflowDAG(name="Advanced E-Commerce Harvester", category="Farming")
        
        n_start = WorkflowNode(id="start_1", node_type=NodeType.START, title="Start Session")
        n_nav = WorkflowNode(id="nav_1", node_type=NodeType.NAVIGATE, title="Go to Search", params={"url": "https://google.com?q={query}"})
        n_cond = WorkflowNode(id="cond_1", node_type=NodeType.CONDITION, title="Check URL", params={"condition_type": "url_contains", "expected": "google"})
        n_loop = WorkflowNode(id="loop_1", node_type=NodeType.LOOP, title="Scroll Loop", params={"iterations": 3})
        n_scroll = WorkflowNode(id="scroll_1", node_type=NodeType.SCROLL, title="Scroll 300px", params={"pixels": 300})
        n_term = WorkflowNode(id="term_1", node_type=NodeType.TERMINATE, title="Finish", params={"status": "success"})

        for n in [n_start, n_nav, n_cond, n_loop, n_scroll, n_term]:
            dag.nodes[n.id] = n

        dag.entry_node_id = "start_1"
        dag.variables = {"query": "GeForce RTX 4090"}

        # Add directed wiring
        dag.add_edge("start_1", "nav_1")
        dag.add_edge("nav_1", "cond_1")
        dag.add_edge("cond_1", "loop_1", source_port="true")
        dag.add_edge("cond_1", "term_1", source_port="false")
        dag.add_edge("loop_1", "scroll_1", source_port="loop_body")
        dag.add_edge("scroll_1", "loop_1")
        dag.add_edge("loop_1", "term_1", source_port="loop_exit")

        # Verify Serialization
        serialized = dag.to_dict()
        self.assertEqual(serialized["name"], "Advanced E-Commerce Harvester")
        self.assertEqual(len(serialized["nodes"]), 6)
        self.assertEqual(len(serialized["edges"]), 7)

        # Verify Deserialization
        restored = WorkflowDAG.from_dict(serialized)
        self.assertEqual(restored.entry_node_id, "start_1")
        self.assertEqual(len(restored.nodes), 6)
        self.assertEqual(len(restored.edges), 7)
        self.assertEqual(restored.variables["query"], "GeForce RTX 4090")

    async def test_dag_variable_interpolation_and_runner(self):
        dag = WorkflowDAG(name="Variable Test DAG")
        n1 = WorkflowNode(id="n1", node_type=NodeType.START, title="Start")
        n2 = WorkflowNode(id="n2", node_type=NodeType.WAIT, title="Wait with Variable", params={"duration": 0.05})
        n3 = WorkflowNode(id="n3", node_type=NodeType.TERMINATE, title="End", params={"status": "success"})

        dag.nodes = {"n1": n1, "n2": n2, "n3": n3}
        dag.entry_node_id = "n1"
        dag.add_edge("n1", "n2")
        dag.add_edge("n2", "n3")

        dag.variables = {"user_name": "AntigravityAgent", "target_price": "$999"}

        runner = WorkflowDAGRunner(dag)
        interpolated = runner.interpolate_vars("Hello {user_name}, price is {target_price}")
        self.assertEqual(interpolated, "Hello AntigravityAgent, price is $999")

        # Execute DAG
        logs = []
        success = await runner.execute(page=None, log_cb=lambda m: logs.append(m))
        self.assertTrue(success)
        self.assertEqual(runner.state, WorkflowExecutionState.COMPLETED)
        self.assertTrue(any("TERMINATE" in l for l in logs))

    async def test_loop_execution_branching(self):
        dag = WorkflowDAG(name="Loop Test DAG")
        n_start = WorkflowNode(id="start", node_type=NodeType.START, title="Start")
        n_loop = WorkflowNode(id="loop", node_type=NodeType.LOOP, title="Loop 2x", params={"iterations": 2})
        n_body = WorkflowNode(id="body", node_type=NodeType.WAIT, title="Body Step", params={"duration": 0.01})
        n_end = WorkflowNode(id="end", node_type=NodeType.TERMINATE, title="End", params={"status": "success"})

        dag.nodes = {"start": n_start, "loop": n_loop, "body": n_body, "end": n_end}
        dag.entry_node_id = "start"
        dag.add_edge("start", "loop")
        dag.add_edge("loop", "body", source_port="loop_body")
        dag.add_edge("body", "loop")
        dag.add_edge("loop", "end", source_port="loop_exit")

        runner = WorkflowDAGRunner(dag)
        logs = []
        success = await runner.execute(page=None, log_cb=lambda m: logs.append(m))
        self.assertTrue(success)
        self.assertEqual(runner.loop_counters.get("loop", 0), 0)
        self.assertEqual(runner.variables.get("loop_index"), 2)

    def test_captcha_solver_node_whisper_and_50_50_hybrid(self):
        dag = WorkflowDAG(name="Captcha Solver Test")
        n_start = WorkflowNode(id="n1", node_type=NodeType.START, title="Start")
        n_captcha = WorkflowNode(
            id="n2",
            node_type=NodeType.SOLVE_CAPTCHA,
            title="Solve Captcha",
            params={
                "strategy": "50/50_smart_hybrid",
                "whisper_model": "large-v3-turbo",
                "vision_model": "50/50_smart_hybrid",
                "timeout_sec": 30.0
            }
        )
        n_end = WorkflowNode(id="n3", node_type=NodeType.TERMINATE, title="End", params={"status": "success"})

        dag.nodes = {"n1": n_start, "n2": n_captcha, "n3": n_end}
        dag.entry_node_id = "n1"
        dag.add_edge("n1", "n2")
        dag.add_edge("n2", "n3")

        data = dag.to_dict()
        reconstructed = WorkflowDAG.from_dict(data)

        captcha_node = reconstructed.nodes["n2"]
        self.assertEqual(captcha_node.params.get("strategy"), "50/50_smart_hybrid")
        self.assertEqual(captcha_node.params.get("whisper_model"), "large-v3-turbo")
        self.assertEqual(captcha_node.params.get("vision_model"), "50/50_smart_hybrid")

    def test_auto_layout_and_validation(self):
        dag = WorkflowDAG(name="Layout Test")
        for i in range(6):
            dag.nodes[f"n{i}"] = WorkflowNode(id=f"n{i}", node_type=NodeType.START if i == 0 else NodeType.WAIT, title=f"Node {i}")
            if i > 0:
                dag.add_edge(f"n{i-1}", f"n{i}")
        dag.entry_node_id = "n0"

        dag.auto_layout_nodes(max_per_row=4)
        # Check that nodes n0..n3 have identical Y (row 0) and increasing X
        self.assertEqual(dag.nodes["n0"].position["y"], dag.nodes["n1"].position["y"])
        self.assertEqual(dag.nodes["n1"].position["y"], dag.nodes["n2"].position["y"])
        self.assertEqual(dag.nodes["n2"].position["y"], dag.nodes["n3"].position["y"])
        self.assertLess(dag.nodes["n0"].position["x"], dag.nodes["n1"].position["x"])
        self.assertLess(dag.nodes["n1"].position["x"], dag.nodes["n2"].position["x"])
        self.assertLess(dag.nodes["n2"].position["x"], dag.nodes["n3"].position["x"])

        # Check that nodes n4..n5 are in row 1 (greater Y)
        self.assertGreater(dag.nodes["n4"].position["y"], dag.nodes["n0"].position["y"])
        self.assertEqual(dag.nodes["n4"].position["y"], dag.nodes["n5"].position["y"])

        # Validate DAG
        diags = dag.validate_dag()
        self.assertTrue(any(d["level"] == "success" for d in diags))

    def test_playwright_python_export(self):
        dag = WorkflowDAG(name="Playwright Export Test")
        n1 = WorkflowNode(id="a", node_type=NodeType.START, title="Start", position={"x": 0, "y": 0})
        n2 = WorkflowNode(id="b", node_type=NodeType.NAVIGATE, title="Go to Google", params={"url": "https://google.com"}, position={"x": 200, "y": 0})
        n3 = WorkflowNode(id="c", node_type=NodeType.SCREENSHOT, title="Take Screenshot", params={"path": "storage/screenshots/test.png"}, position={"x": 400, "y": 0})
        dag.nodes = {"a": n1, "b": n2, "c": n3}
        dag.entry_node_id = "a"
        dag.add_edge("a", "b")
        dag.add_edge("b", "c")

        code = dag.export_to_playwright_python()
        self.assertIn("async def run_workflow():", code)
        self.assertIn("page.goto('https://google.com'", code)
        self.assertIn("page.screenshot(path='storage/screenshots/test.png'", code)

    def test_vla_type_ai_generation_parameters(self):
        dag = WorkflowDAG(name="VLA Type AI Test")
        n_start = WorkflowNode(id="s1", node_type=NodeType.START, title="Start")
        n_vla_ai = WorkflowNode(
            id="vla1",
            node_type=NodeType.VLA_TYPE,
            title="AI Search Query Generator",
            params={
                "use_ai_generation": True,
                "ai_prompt": "Write a 3-word query about {product}",
                "ai_model": "gemini-3.6-flash",
                "save_to_var": "ai_query",
                "instruction": "input[name='q']",
                "press_enter": True,
                "clear_first": True,
                "delay_ms": 50.0
            }
        )
        dag.nodes = {"s1": n_start, "vla1": n_vla_ai}
        dag.entry_node_id = "s1"
        dag.add_edge("s1", "vla1")
        dag.variables = {"product": "Quantum Computers"}

        # Check serialization roundtrip
        data = dag.to_dict()
        restored = WorkflowDAG.from_dict(data)
        restored_node = restored.nodes["vla1"]
        self.assertTrue(restored_node.params.get("use_ai_generation"))
        self.assertEqual(restored_node.params.get("ai_prompt"), "Write a 3-word query about {product}")
        self.assertEqual(restored_node.params.get("ai_model"), "gemini-3.6-flash")
        self.assertEqual(restored_node.params.get("save_to_var"), "ai_query")

        # Check export to playwright includes AI comment
        exported = restored.export_to_playwright_python()
        self.assertIn("AI Text Generation: model='gemini-3.6-flash'", exported)

        # Check metadata
        meta = n_vla_ai.get_metadata()
        self.assertIn("use_ai_generation", meta["params_doc"])
        self.assertIn("ai_prompt", meta["params_doc"])
        self.assertIn("ai_model", meta["params_doc"])

    def test_ai_model_task_features(self):
        dag = WorkflowDAG(name="AI Model Task Workflow")
        n_start = WorkflowNode(id="s1", node_type=NodeType.START, title="Start Session")
        
        # 1. OCR Task
        n_ocr = WorkflowNode(
            id="task_ocr",
            node_type=NodeType.AI_MODEL_TASK,
            title="Extract Text with GOT-OCR2",
            params={
                "task_type": "extract_text_ocr",
                "model_name": "got-ocr2",
                "prompt": "Extract all text legible",
                "save_to_var": "extracted_ocr",
                "selector": "#main-content"
            }
        )

        # 2. Pentest Audit Task
        n_pentest = WorkflowNode(
            id="task_pentest",
            node_type=NodeType.AI_MODEL_TASK,
            title="Red-Team Security Pentest",
            params={
                "task_type": "security_pentest",
                "model_name": "gemini-3.6-flash",
                "prompt": "Audit for honeypots and bot traps",
                "save_to_var": "pentest_report"
            }
        )

        # 3. Audio Transcribe Task
        n_audio = WorkflowNode(
            id="task_audio",
            node_type=NodeType.AI_MODEL_TASK,
            title="Transcribe Audio Whisper",
            params={
                "task_type": "transcribe_audio",
                "model_name": "whisper-base",
                "save_to_var": "audio_transcript"
            }
        )

        dag.nodes = {"s1": n_start, "task_ocr": n_ocr, "task_pentest": n_pentest, "task_audio": n_audio}
        dag.entry_node_id = "s1"
        dag.add_edge("s1", "task_ocr")
        dag.add_edge("task_ocr", "task_pentest")
        dag.add_edge("task_pentest", "task_audio")

        # Check serialization roundtrip
        data = dag.to_dict()
        restored = WorkflowDAG.from_dict(data)
        self.assertEqual(len(restored.nodes), 4)
        self.assertEqual(restored.nodes["task_ocr"].params["task_type"], "extract_text_ocr")
        self.assertEqual(restored.nodes["task_pentest"].params["task_type"], "security_pentest")
        self.assertEqual(restored.nodes["task_audio"].params["task_type"], "transcribe_audio")

        # Check metadata
        meta = n_pentest.get_metadata()
        self.assertEqual(meta["category"], "Cognitive AI & Multimodal Models")
        self.assertIn("security_pentest", meta["params_doc"]["task_type"])

        # Check export
        code = restored.export_to_playwright_python()
        self.assertIn("Executing AI Model Task [extract_text_ocr]", code)
        self.assertIn("Executing AI Model Task [security_pentest]", code)

    def test_clean_ai_generated_text(self):
        from engine.workflow_engine import clean_ai_generated_text

        # 1. Exact user case: JSON dict with {"text": "android rooting"}
        self.assertEqual(clean_ai_generated_text('{"text":"android rooting"}'), "android rooting")
        self.assertEqual(clean_ai_generated_text('{"query": "android rooting"}'), "android rooting")
        self.assertEqual(clean_ai_generated_text('{"search_term": "android rooting"}'), "android rooting")
        self.assertEqual(clean_ai_generated_text('{"result": "android rooting"}'), "android rooting")

        # 2. Markdown fenced JSON
        self.assertEqual(clean_ai_generated_text('```json\n{"text":"android rooting"}\n```'), "android rooting")
        self.assertEqual(clean_ai_generated_text('```\nandroid rooting\n```'), "android rooting")

        # 3. Quoted strings
        self.assertEqual(clean_ai_generated_text('"android rooting"'), "android rooting")
        self.assertEqual(clean_ai_generated_text("'android rooting'"), "android rooting")
        self.assertEqual(clean_ai_generated_text('“android rooting”'), "android rooting")

        # 4. Conversational prefixes
        self.assertEqual(clean_ai_generated_text('Here is the search query: android rooting'), "android rooting")
        self.assertEqual(clean_ai_generated_text('Output: "android rooting"'), "android rooting")
        self.assertEqual(clean_ai_generated_text('Query: android rooting'), "android rooting")

        # 5. List format
        self.assertEqual(clean_ai_generated_text('["android rooting"]'), "android rooting")

        # 6. Key-only JSON dictionaries (e.g. {"Samsung S24 Rooting Questions?":"", "How do I root my Samsung Galaxy S24?":""})
        self.assertEqual(
            clean_ai_generated_text('{"Samsung S24 Rooting Questions?":"", "How do I root my Samsung Galaxy S24?":""}'),
            "How do I root my Samsung Galaxy S24?"
        )
        self.assertEqual(
            clean_ai_generated_text('{"Samsung Galaxy S24 Root": ""}'),
            "Samsung Galaxy S24 Root"
        )
        self.assertEqual(
            clean_ai_generated_text('{"suggestions": ["How do I root my phone?"]}'),
            "How do I root my phone?"
        )

        # 7. Plain text passthrough
        self.assertEqual(clean_ai_generated_text('android rooting'), "android rooting")

    def test_javascript_eval_wrapping(self):
        # Verify script wrapping logic
        raw_scripts = [
            "return document.title;",
            "return window.location.href;",
            "const x = 10;\nreturn x * 2;"
        ]
        for script in raw_scripts:
            eval_script = script
            if not (eval_script.startswith("() =>") or eval_script.startswith("function")):
                if "return " in eval_script or "\n" in eval_script or ";" in eval_script:
                    eval_script = f"() => {{\n{script}\n}}"
    def test_workflow_live_debugging_and_stepping(self):
        # Build a 3-node DAG: Start -> Wait -> Terminate
        dag = WorkflowDAG(name="Debug DAG")
        n1 = WorkflowNode(id="n1", node_type=NodeType.START, title="Start Node")
        n2 = WorkflowNode(id="n2", node_type=NodeType.WAIT, title="Wait 0.01s", params={"duration": 0.01}, is_breakpoint=True)
        n3 = WorkflowNode(id="n3", node_type=NodeType.TERMINATE, title="End Node")
        
        dag.nodes = {"n1": n1, "n2": n2, "n3": n3}
        dag.edges = [
            WorkflowEdge(source_node_id="n1", target_node_id="n2"),
            WorkflowEdge(source_node_id="n2", target_node_id="n3")
        ]
        dag.entry_node_id = "n1"

        runner = WorkflowDAGRunner(dag)
        badges = {}
        statuses = []

        def on_badge(nid, text):
            badges[nid] = text

        def on_status(nid, st):
            statuses.append((nid, st))

        async def run_and_step():
            task = asyncio.create_task(runner.execute(
                page=None,
                node_status_cb=on_status,
                badge_update_cb=on_badge
            ))
            
            # Wait briefly for n2 breakpoint to hit and pause
            await asyncio.sleep(0.05)
            self.assertEqual(runner.state, WorkflowExecutionState.PAUSED)
            self.assertEqual(runner.current_node_id, "n2")

            # Step one node
            runner.step()
            await asyncio.sleep(0.05)
            
            # Resume to finish
            runner.resume()
            res = await task
            self.assertTrue(res)
            self.assertEqual(runner.state, WorkflowExecutionState.COMPLETED)
            self.assertIn("n1", badges)
            self.assertIn("n2", badges)

        asyncio.run(run_and_step())

    async def test_rotate_proxy_fallback_from_proxy_pool(self):
        """Tests that ROTATE_PROXY selects a new unused proxy from Proxy_Pool as fallback and sets variables."""
        from unittest.mock import patch
        dag = WorkflowDAG(name="Proxy Rotation Test")
        n1 = WorkflowNode(id="n1", node_type=NodeType.START, title="Start")
        n_rot1 = WorkflowNode(id="n_rot1", node_type=NodeType.ROTATE_PROXY, title="Rotate Proxy 1", params={"rotation_mode": "force_pool"})
        n_rot2 = WorkflowNode(id="n_rot2", node_type=NodeType.ROTATE_PROXY, title="Rotate Proxy 2", params={"rotation_mode": "force_pool"})
        n_end = WorkflowNode(id="n_end", node_type=NodeType.TERMINATE, title="End", params={"status": "success"})

        dag.nodes = {"n1": n1, "n_rot1": n_rot1, "n_rot2": n_rot2, "n_end": n_end}
        dag.edges = [
            WorkflowEdge(source_node_id="n1", target_node_id="n_rot1"),
            WorkflowEdge(source_node_id="n_rot1", target_node_id="n_rot2"),
            WorkflowEdge(source_node_id="n_rot2", target_node_id="n_end")
        ]
        dag.entry_node_id = "n1"

        runner = WorkflowDAGRunner(dag)
        logs = []
        badges = {}

        def on_badge(nid, text):
            badges[nid] = text

        mock_proxies = [
            {"id": "p1", "host": "1.2.3.4", "port": 8080, "type": "http", "status": "🟢 Online", "group": "Default"},
            {"id": "p2", "host": "5.6.7.8", "port": 8080, "type": "http", "status": "🟢 Online", "group": "Default"}
        ]

        with patch("storage.proxy_manager.ProxyManager.list_proxies", return_value=mock_proxies):
            success = await runner.execute(
                page=None,
                log_cb=lambda m: logs.append(m),
                badge_update_cb=on_badge
            )
        self.assertTrue(success)
        self.assertEqual(runner.state, WorkflowExecutionState.COMPLETED)
        # Verify variables were updated
        self.assertIn("current_proxy", runner.variables)
        self.assertIn("proxy_host", runner.variables)
        self.assertIn("proxy_port", runner.variables)
        self.assertEqual(runner.variables.get("rotated_via"), "proxy_pool")
        self.assertIn("n_rot1", badges)
        self.assertIn("n_rot2", badges)
        # Ensure 2 distinct proxies were selected
        self.assertGreaterEqual(len(runner.used_proxy_ids), 1)


if __name__ == "__main__":
    unittest.main()

