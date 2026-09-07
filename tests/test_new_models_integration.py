import unittest
import asyncio
from unittest.mock import AsyncMock, patch
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication

app = QApplication.instance()
if app is None:
    app = QApplication([])

from engine.ai_model_manager import AIModelManager
from engine.ai_telemetry import AITelemetryBus
from engine.google_proxy_checker import GoogleProxyChecker
from ui.views.model_manager_dialog import ModelManagerDialog
import config


class TestNewModelsIntegration(unittest.TestCase):
    """Unit tests for newly added AI models: DeepSeek R1 (1.5B), Qwen 2.5 Coder (1.5B), Qwen 2.5 VL (3B), and Faster-Whisper Base."""

    def setUp(self):
        self.ai_mgr = AIModelManager.get_instance()
        self.bus = AITelemetryBus.get_instance()

    def test_strip_think_tags(self):
        raw_output = "<think>\nThinking through the optimal evasive query...\nConsidering entropy.\n</think>\nlatest quantum computing breakthroughs 2026"
        cleaned = AIModelManager.strip_think_tags(raw_output)
        self.assertEqual(cleaned, "latest quantum computing breakthroughs 2026")

        no_think = "simple clean query without tags"
        self.assertEqual(AIModelManager.strip_think_tags(no_think), no_think)

    def test_role_assignments(self):
        # 1. DeepSeek R1
        roles_ds = self.ai_mgr.get_hybrid_roles("deepseek-r1:1.5b")
        self.assertEqual(roles_ds["text_model"], "deepseek-r1:1.5b")
        self.assertEqual(roles_ds["reasoning_model"], "deepseek-r1:1.5b")
        self.assertEqual(roles_ds["vision_model"], "qwen2.5vl:3b")

        # 2. Qwen Coder
        roles_coder = self.ai_mgr.get_hybrid_roles("qwen2.5-coder:1.5b")
        self.assertEqual(roles_coder["text_model"], "qwen2.5-coder:1.5b")
        self.assertEqual(roles_coder["coder_model"], "qwen2.5-coder:1.5b")

        # 3. Qwen 2.5 VL
        roles_vl = self.ai_mgr.get_hybrid_roles("qwen2.5vl:3b")
        self.assertEqual(roles_vl["vision_model"], "qwen2.5vl:3b")
        self.assertEqual(roles_vl["heavy_vision_model"], "qwen2.5vl:3b")

    def test_download_manager_model_config(self):
        model_ids = [m["id"] for m in ModelManagerDialog.MODELS_CONFIG]
        self.assertIn("deepseek-r1:1.5b", model_ids)
        self.assertIn("qwen2.5-coder:1.5b", model_ids)
        self.assertIn("qwen2.5vl:3b", model_ids)
        self.assertIn("qwen2.5:1.5b", model_ids)
        self.assertIn("qwen2.5:3b", model_ids)
        self.assertIn("qwen2.5:0.5b", model_ids)
        self.assertIn("llava:7b", model_ids)
        self.assertIn("moondream:v2", model_ids)

    def test_google_check_query_generation_with_think_tags(self):
        async def _test():
            with patch.object(self.ai_mgr, "is_engine_ready", new=AsyncMock(return_value=True)), \
                 patch.object(self.ai_mgr, "generate_response", new=AsyncMock(return_value="<think>\nEvaluating topic...\n</think>\nhow to configure residential proxies")):
                query = await GoogleProxyChecker.generate_test_query(model_name="deepseek-r1:1.5b")
                self.assertEqual(query, "how to configure residential proxies")
        asyncio.run(_test())

    def test_config_ai_model_options(self):
        keys = [opt[0] for opt in config.AI_MODEL_OPTIONS]
        self.assertIn("deepseek-r1:1.5b", keys)
        self.assertIn("qwen2.5-coder:1.5b", keys)
        self.assertIn("qwen2.5vl:3b", keys)
        self.assertIn("qwen2.5:7b", keys)
        self.assertIn("hermes-3:3b", keys)
        self.assertIn("granite3-dense:2b", keys)
        self.assertIn("hybrid_deepseek_vision", keys)
        self.assertIn("hybrid_coder_tactician", keys)

    def test_download_manager_models_config(self):
        from ui.views.model_manager_dialog import ModelManagerDialog
        dm_ids = [m["id"] for m in ModelManagerDialog.MODELS_CONFIG]
        self.assertIn("qwen2.5:7b", dm_ids)
        self.assertIn("hermes-3:3b", dm_ids)
        self.assertIn("granite3-dense:2b", dm_ids)
        self.assertIn("faster-whisper", dm_ids)
        self.assertIn("onnx-anomaly", dm_ids)

    def test_modality_fallback_routing_and_recommendations(self):
        # 1. When model is installed (e.g. onnx-anomaly)
        sel, rec = self.ai_mgr.get_best_available_model("fingerprint_sentinel")
        self.assertEqual(sel, "onnx-anomaly")
        self.assertIsNone(rec)

        # 2. When modality has no local model installed, it returns the top candidate and a clear recommendation
        with patch.object(self.ai_mgr, "is_model_installed", return_value=False):
            sel_ocr, rec_ocr = self.ai_mgr.get_best_available_model("dense_ocr")
            self.assertEqual(sel_ocr, "got-ocr2")
            self.assertIsNotNone(rec_ocr)
    def test_download_manager_all_18_models_present(self):
        from ui.views.model_manager_dialog import ModelManagerDialog
        dm_ids = [m["id"] for m in ModelManagerDialog.MODELS_CONFIG]
        expected = [
            "qwen2.5:0.5b", "qwen2.5:1.5b", "qwen2.5:3b", "qwen2.5:7b",
            "deepseek-r1:1.5b", "qwen2.5-coder:1.5b", "qwen2.5vl:3b",
            "hermes-3:3b", "granite3-dense:2b", "llava:7b", "moondream:v2",
            "florence-2-base", "got-ocr2", "faster-whisper", "sensevoice-small",
            "onnx-anomaly", "mouse-trajectory-onnx", "gemini-3.6-flash"
        ]
        for exp_id in expected:
            self.assertIn(exp_id, dm_ids, f"Missing model '{exp_id}' in Download Manager MODELS_CONFIG!")

    def test_download_routing_dialog(self):
        from ui.views.model_manager_dialog import ModelDownloadRoutingDialog
        info = {
            "id": "qwen2.5:1.5b",
            "name": "Qwen 2.5 (1.5B)",
            "desc": "Fast Text Reasoning",
            "size": "~980 MB"
        }
        dlg = ModelDownloadRoutingDialog(info, "/tmp/models")
        self.assertIn("ollama.com", dlg.external_url)
        self.assertIn("ollama_models", dlg.target_dir)
        dlg._select_internal()
        self.assertEqual(dlg.choice, ModelDownloadRoutingDialog.ROUTE_INTERNAL)
        dlg._select_external()
        self.assertEqual(dlg.choice, ModelDownloadRoutingDialog.ROUTE_EXTERNAL)

        # Test Specialized models routing
        dlg_florence = ModelDownloadRoutingDialog({"id": "florence-2-base", "name": "Florence 2"}, "/tmp/models")
        self.assertIn("florence", dlg_florence.target_dir)
        self.assertIn("huggingface.co", dlg_florence.external_url)

        dlg_sense = ModelDownloadRoutingDialog({"id": "sensevoice-small", "name": "SenseVoice"}, "/tmp/models")
        self.assertIn("sensevoice", dlg_sense.target_dir)
        self.assertIn("huggingface.co", dlg_sense.external_url)

        dlg_got = ModelDownloadRoutingDialog({"id": "got-ocr2", "name": "GOT-OCR 2.0"}, "/tmp/models")
        self.assertIn("got_ocr", dlg_got.target_dir)
        self.assertIn("huggingface.co", dlg_got.external_url)

        dlg_traj = ModelDownloadRoutingDialog({"id": "mouse-trajectory-onnx", "name": "Mouse Trajectory"}, "/tmp/models")
        self.assertIn("/tmp/models", dlg_traj.target_dir)
        self.assertIn("github.com/microsoft/onnxruntime", dlg_traj.external_url)

    def test_delete_specialized_models(self):
        async def _test():
            # Test delete for got-ocr2, florence, sensevoice
            res_ocr = await self.ai_mgr.delete_model("got-ocr2")
            self.assertTrue(res_ocr)
            res_flor = await self.ai_mgr.delete_model("florence-2-base")
            self.assertTrue(res_flor)
            res_sense = await self.ai_mgr.delete_model("sensevoice-small")
            self.assertTrue(res_sense)
        asyncio.run(_test())


if __name__ == "__main__":
    unittest.main()
