import unittest
import os
import json
import shutil
import tempfile
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QMouseEvent

# Ensure QApplication exists for Qt widget tests
app = QApplication.instance()
if app is None:
    app = QApplication([])

from engine.ai_model_config import AIModelConfigManager, DEFAULT_MODEL_CONFIGS
from engine.ai_model_manager import AIModelManager
from ui.views.ai_model_config_dialog import AIModelConfigDialog
from ui.views.ai_operations_matrix_view import AIModelCardWidget, AIOperationsMatrixView


class TestAIModelConfig(unittest.TestCase):
    """Unit tests for AI Model Configuration Manager, Dialog and Matrix Card Integration."""

    def setUp(self):
        self.cfg_mgr = AIModelConfigManager.get_instance()
        self.cfg_mgr.load_configs()

    def test_default_configs_loaded_for_all_models(self):
        all_cfgs = self.cfg_mgr.get_all_configs()
        self.assertIn("qwen2.5:0.5b", all_cfgs)
        self.assertIn("qwen2.5:1.5b", all_cfgs)
        self.assertIn("deepseek-r1:1.5b", all_cfgs)
        self.assertIn("qwen2.5-coder:1.5b", all_cfgs)
        self.assertIn("qwen2.5:3b", all_cfgs)
        self.assertIn("qwen2.5:7b", all_cfgs)
        self.assertIn("hermes-3:3b", all_cfgs)
        self.assertIn("granite3-dense:2b", all_cfgs)
        self.assertIn("qwen2.5vl:3b", all_cfgs)
        self.assertIn("moondream:v2", all_cfgs)
        self.assertIn("llava:7b", all_cfgs)
        self.assertIn("florence-2-base", all_cfgs)
        self.assertIn("got-ocr2", all_cfgs)
        self.assertIn("faster-whisper", all_cfgs)
        self.assertIn("sensevoice-small", all_cfgs)
        self.assertIn("onnx-anomaly", all_cfgs)
        self.assertIn("mouse-trajectory-onnx", all_cfgs)
        self.assertIn("gemini-3.6-flash", all_cfgs)

    def test_get_and_save_model_config(self):
        original = self.cfg_mgr.get_model_config("qwen2.5:1.5b")
        test_update = {
            "temperature": 0.42,
            "top_p": 0.77,
            "num_ctx": 32768,
            "system_prompt": "Custom automated security test prompt."
        }
        self.cfg_mgr.save_model_config("qwen2.5:1.5b", test_update)
        
        updated = self.cfg_mgr.get_model_config("qwen2.5:1.5b")
        self.assertEqual(updated["temperature"], 0.42)
        self.assertEqual(updated["top_p"], 0.77)
        self.assertEqual(updated["num_ctx"], 32768)
        self.assertEqual(updated["system_prompt"], "Custom automated security test prompt.")

        # Reset back to original
        self.cfg_mgr.save_model_config("qwen2.5:1.5b", original)
        reset_cfg = self.cfg_mgr.get_model_config("qwen2.5:1.5b")
        self.assertEqual(reset_cfg["temperature"], original["temperature"])
        self.assertEqual(reset_cfg["num_ctx"], original["num_ctx"])

    def test_model_config_dialog_initialization(self):
        for test_model in ["qwen2.5:1.5b", "deepseek-r1:1.5b", "qwen2.5vl:3b", "faster-whisper", "onnx-anomaly"]:
            dialog = AIModelConfigDialog(test_model)
            self.assertIsNotNone(dialog)
            self.assertEqual(dialog.tabs.count(), 5)
            
            # Verify UI values loaded from config
            collected = dialog._collect_ui_to_dict()
            self.assertIn("temperature", collected)
            self.assertIn("top_p", collected)
            self.assertIn("num_ctx", collected)
            self.assertIn("system_prompt", collected)
            self.assertIn("swarm_priority", collected)
            dialog.close()

    def test_card_widget_click_and_config_signal(self):
        card = AIModelCardWidget("deepseek-r1:1.5b")
        signal_received = []

        card.config_requested.connect(lambda m: signal_received.append(m))
        
        # Test clicking the gear button
        card.btn_config.click()
        self.assertEqual(signal_received, ["deepseek-r1:1.5b"])

        # Test clicking the card frame
        card.resize(250, 150)
        from PyQt6.QtCore import QPointF
        center_pt = card.rect().center()
        dummy_event = QMouseEvent(
            QMouseEvent.Type.MouseButtonPress,
            QPointF(center_pt),
            Qt.MouseButton.LeftButton,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier
        )
        card.mousePressEvent(dummy_event)
        self.assertEqual(signal_received, ["deepseek-r1:1.5b", "deepseek-r1:1.5b"])

    def test_ai_operations_matrix_view_cards_count(self):
        matrix_view = AIOperationsMatrixView()
        self.assertGreaterEqual(len(matrix_view.model_cards), 18)
        self.assertIn("deepseek-r1:1.5b", matrix_view.model_cards)
        self.assertIn("onnx-anomaly", matrix_view.model_cards)
        self.assertIn("qwen2.5vl:3b", matrix_view.model_cards)
    def test_sanitize_search_query(self):
        """Verify that AIModelManager.sanitize_search_query properly cleans all LLM artifacts."""
        # 1. JSON object outputs
        self.assertEqual(
            AIModelManager.sanitize_search_query('{"query":"best browser scan tool"}'),
            "best browser scan tool"
        )
        self.assertEqual(
            AIModelManager.sanitize_search_query('{"search_query": "online privacy audit 2026"}'),
            "online privacy audit 2026"
        )
        # 2. Markdown code fences
        self.assertEqual(
            AIModelManager.sanitize_search_query('```json\n{"query": "fingerprint leak test"}\n```'),
            "fingerprint leak test"
        )
        # 3. Model prefixes and introductory phrasing
        self.assertEqual(
            AIModelManager.sanitize_search_query('Search query: quantum encryption benchmarks'),
            "quantum encryption benchmarks"
        )
        self.assertEqual(
            AIModelManager.sanitize_search_query('Here is the search query: "python async performance"'),
            "python async performance"
        )
        # 4. Quotes and punctuation
        self.assertEqual(
            AIModelManager.sanitize_search_query('"best mechanical keyboards".'),
            "best mechanical keyboards"
        )
        # 5. Think tags
        self.assertEqual(
            AIModelManager.sanitize_search_query('<think>thinking about query</think> {"query": "cybersecurity news"}'),
            "cybersecurity news"
        )


if __name__ == "__main__":
    unittest.main()

