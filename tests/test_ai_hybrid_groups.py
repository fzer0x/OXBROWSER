import os
import json
import unittest
from PyQt6.QtWidgets import QApplication

# Ensure single headless QApplication instance
app = QApplication.instance()
if app is None:
    app = QApplication([])

import config
from engine.ai_hybrid_groups_manager import (
    AIHybridGroupsManager, BUILTIN_HYBRID_GROUPS, SWARM_ROLE_DEFINITIONS
)
from engine.ai_model_manager import AIModelManager
from ui.views.ai_hybrid_groups_tab import AIHybridGroupsTab, AIHybridGroupCardWidget
from ui.views.ai_operations_matrix_view import AIOperationsMatrixView


class TestAIHybridGroups(unittest.TestCase):

    def setUp(self):
        self.mgr = AIHybridGroupsManager.get_instance()
        self.ai_mgr = AIModelManager.get_instance()

    def test_builtin_groups_initialization(self):
        groups = self.mgr.get_all_groups()
        self.assertGreaterEqual(len(groups), 5)
        
        group_ids = [g["id"] for g in groups]
        self.assertIn("swarm_auto_full", group_ids)
        self.assertIn("swarm_poker_grandmaster", group_ids)
        self.assertIn("hybrid_deepseek_vision", group_ids)
        self.assertIn("hybrid_coder_tactician", group_ids)
        self.assertIn("hybrid_eco", group_ids)
        self.assertIn("hybrid_high_perf", group_ids)

    def test_create_and_update_custom_hybrid_group(self):
        custom_roles = {
            "text_model": "qwen2.5:3b",
            "reasoning_model": "deepseek-r1:1.5b",
            "coder_model": "granite3-dense:2b",
            "vision_model": "florence-2-base",
            "heavy_vision_model": "llava:7b",
            "strategy_model": "qwen2.5:7b",
            "micro_model": "qwen2.5:0.5b",
            "audio_model": "sensevoice-small",
            "sentinel_model": "onnx-anomaly",
            "cloud_model": "gemini-3.6-flash"
        }
        
        new_g = self.mgr.create_group(
            name="Test Cyber Squad",
            description="Testing custom hybrid group creation",
            icon="🎯",
            accent_color="#f59e0b",
            roles=custom_roles,
            custom_id="test_custom_squad_001"
        )
        self.assertEqual(new_g["id"], "test_custom_squad_001")
        self.assertEqual(new_g["name"], "Test Cyber Squad")
        self.assertEqual(new_g["roles"]["coder_model"], "granite3-dense:2b")
        self.assertEqual(new_g["roles"]["vision_model"], "florence-2-base")

        # Verify update
        updated = self.mgr.update_group("test_custom_squad_001", {
            "name": "Updated Cyber Squad",
            "roles": {"vision_model": "got-ocr2"}
        })
        self.assertIsNotNone(updated)
        self.assertEqual(updated["name"], "Updated Cyber Squad")
        self.assertEqual(updated["roles"]["vision_model"], "got-ocr2")

    def test_vram_and_latency_calculation(self):
        roles_eco = {
            "text_model": "qwen2.5:0.5b",
            "reasoning_model": "qwen2.5:0.5b",
            "coder_model": "qwen2.5:0.5b",
            "vision_model": "florence-2-base",
            "heavy_vision_model": "florence-2-base",
            "strategy_model": "qwen2.5:0.5b",
            "micro_model": "qwen2.5:0.5b",
            "audio_model": "faster-whisper",
            "sentinel_model": "onnx-anomaly",
            "cloud_model": "none"
        }
        metrics_eco = AIHybridGroupsManager.calculate_group_metrics(roles_eco, {"vram_strategy": "ultra_eco"})
        self.assertLessEqual(metrics_eco["estimated_peak_vram_gb"], 1.5)
        self.assertIn("Eco", metrics_eco["classification"])

        roles_heavy = {
            "text_model": "qwen2.5:7b",
            "reasoning_model": "qwen2.5:7b",
            "coder_model": "qwen2.5-coder:1.5b",
            "vision_model": "qwen2.5vl:3b",
            "heavy_vision_model": "llava:7b",
            "strategy_model": "qwen2.5:7b",
            "micro_model": "qwen2.5:1.5b",
            "audio_model": "faster-whisper",
            "sentinel_model": "mouse-trajectory-onnx",
            "cloud_model": "gemini-3.6-flash"
        }
        metrics_heavy = AIHybridGroupsManager.calculate_group_metrics(roles_heavy, {"vram_strategy": "resident_pinned"})
        self.assertGreater(metrics_heavy["estimated_peak_vram_gb"], 5.0)

    def test_export_and_import_json(self):
        exported_json = self.mgr.export_group_json("swarm_auto_full")
        self.assertIsInstance(exported_json, str)
        data = json.loads(exported_json)
        self.assertEqual(data["id"], "swarm_auto_full")

        imported = self.mgr.import_group_json(exported_json)
        self.assertIsNotNone(imported)
        self.assertTrue(imported["id"].startswith("custom_hybrid_"))
        self.assertIn("Imported", imported["name"])

        # Clean up
        self.mgr.delete_group(imported["id"])

    def test_duplicate_and_delete_group(self):
        dup = self.mgr.duplicate_group("hybrid_deepseek_vision", "Cloned DeepSeek Squad")
        self.assertIsNotNone(dup)
        self.assertEqual(dup["name"], "Cloned DeepSeek Squad")
        self.assertFalse(dup["is_builtin"])

        # Built-in deletion must fail
        can_delete_builtin = self.mgr.delete_group("swarm_auto_full")
        self.assertFalse(can_delete_builtin)

        # Custom deletion must succeed
        can_delete_custom = self.mgr.delete_group(dup["id"])
        self.assertTrue(can_delete_custom)
        self.assertIsNone(self.mgr.get_group(dup["id"]))

    def test_role_resolution_in_ai_model_manager(self):
        # Create a specific custom group and verify get_hybrid_roles resolves it
        custom_id = "custom_hybrid_test_routing"
        self.mgr.create_group(
            name="Routing Test Group",
            roles={
                "text_model": "qwen2.5:3b",
                "reasoning_model": "deepseek-r1:1.5b",
                "coder_model": "qwen2.5-coder:1.5b",
                "vision_model": "moondream:v2",
                "heavy_vision_model": "llava:7b",
                "strategy_model": "qwen2.5:7b",
                "micro_model": "qwen2.5:0.5b",
                "audio_model": "faster-whisper",
                "sentinel_model": "onnx-anomaly",
                "cloud_model": "gemini-3.6-flash"
            },
            custom_id=custom_id
        )

        resolved_roles = self.ai_mgr.get_hybrid_roles(custom_id)
        self.assertEqual(resolved_roles["text_model"], "qwen2.5:3b")
        self.assertEqual(resolved_roles["reasoning_model"], "deepseek-r1:1.5b")
        self.assertEqual(resolved_roles["strategy_model"], "qwen2.5:7b")

        # Clean up
        self.mgr.delete_group(custom_id)

    def test_config_dynamic_model_options(self):
        # Verify custom options get merged
        self.mgr.create_group(
            name="Dynamic Option Test",
            custom_id="custom_hybrid_opt_test"
        )
        options = config.get_all_ai_model_options()
        opt_ids = [opt[0] for opt in options]
        self.assertIn("custom_hybrid_opt_test", opt_ids)

        # Clean up
        self.mgr.delete_group("custom_hybrid_opt_test")

    def test_ui_tab_and_operations_matrix_integration(self):
        tab = AIHybridGroupsTab()
        self.assertIsNotNone(tab)
        self.assertGreater(len(tab.role_combos), 0)
        self.assertEqual(len(tab.role_combos), 10)

        # Test Operations Matrix View containing Tab 3
        matrix_view = AIOperationsMatrixView()
        self.assertIsNotNone(matrix_view)
        self.assertEqual(matrix_view.tabs.count(), 3)
        self.assertEqual(matrix_view.tabs.tabText(2), "⚔ KI-Hybrid Gruppen")

    def test_ensure_model_pulled_with_custom_group(self):
        import asyncio
        custom_id = "test_custom_squad_pull"
        self.mgr.create_group(
            name="Pull Test Squad",
            roles={
                "text_model": "gemini-3.6-flash",
                "vision_model": "gemini-3.6-flash",
                "audio_model": "faster-whisper",
                "sentinel_model": "onnx-anomaly"
            },
            custom_id=custom_id
        )

        async def run_check():
            return await self.ai_mgr.ensure_model_pulled(custom_id)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        ready = loop.run_until_complete(run_check())
        loop.close()
        self.assertTrue(ready)

        self.mgr.delete_group(custom_id)

    def test_push_group_config_and_tasks(self):
        json_payload = json.dumps({
            "id": "custom_poker_swarm_99",
            "name": "🃏 Poker Pro Multi-Task Swarm",
            "description": "Swarm designed for browser poker with multi-purpose tasks",
            "icon": "🃏",
            "accent_color": "#f59e0b",
            "roles": {
                "text_model": "qwen2.5:1.5b",
                "reasoning_model": "deepseek-r1:1.5b",
                "coder_model": "qwen2.5-coder:1.5b",
                "vision_model": "qwen2.5vl:3b",
                "heavy_vision_model": "qwen2.5vl:3b",
                "strategy_model": "deepseek-r1:1.5b",
                "micro_model": "qwen2.5:0.5b",
                "audio_model": "faster-whisper",
                "sentinel_model": "onnx-anomaly",
                "cloud_model": "none"
            },
            "orchestration": {
                "vram_strategy": "dynamic_tier",
                "temperature": 0.2
            },
            "tasks": {
                "poker": {
                    "vision_ocr_role": "vision_model",
                    "reasoning_role": "reasoning_model",
                    "equity_eval_iterations": 2500,
                    "custom_gto_prompt": "Special GTO reasoning prompt for browser poker"
                }
            }
        })

        # Test pushing config
        grp = self.mgr.push_group_config(json_payload)
        self.assertEqual(grp["id"], "custom_poker_swarm_99")
        self.assertEqual(grp["name"], "🃏 Poker Pro Multi-Task Swarm")
        self.assertIn("tasks", grp)
        self.assertIn("poker", grp["tasks"])

        # Test get_group_task_config
        poker_cfg = self.mgr.get_group_task_config("custom_poker_swarm_99", "poker")
        self.assertEqual(poker_cfg.get("vision_ocr_role"), "vision_model")
        self.assertEqual(poker_cfg.get("equity_eval_iterations"), 2500)
        self.assertEqual(poker_cfg.get("custom_gto_prompt"), "Special GTO reasoning prompt for browser poker")

        # Clean up
        self.mgr.delete_group("custom_poker_swarm_99")

    def test_get_preset_config_templates(self):
        poker_tpl = self.mgr.get_preset_config_template("poker")
        self.assertIn("roles", poker_tpl)
        self.assertIn("tasks", poker_tpl)
        self.assertIn("poker", poker_tpl["tasks"])

        chess_tpl = self.mgr.get_preset_config_template("chess")
        self.assertIn("chess", chess_tpl["tasks"])


if __name__ == "__main__":
    unittest.main()
