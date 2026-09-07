import unittest
import asyncio
from engine.ai_telemetry import AITelemetryBus
from engine.ai_model_manager import AIModelManager

class TestAISwarmMatrix(unittest.TestCase):
    """Unit tests for AI Telemetry Bus, multi-model state tracking and telemetry reporting."""

    def setUp(self):
        self.bus = AITelemetryBus.get_instance()
        self.bus.clear_history()

    def test_all_eight_models_registered(self):
        stats = self.bus.get_all_models_stats()
        self.assertIn("onnx-anomaly", stats)
        self.assertIn("qwen2.5:0.5b", stats)
        self.assertIn("qwen2.5:1.5b", stats)
        self.assertIn("qwen2.5:3b", stats)
        self.assertIn("qwen2.5:7b", stats)
        self.assertIn("deepseek-r1:1.5b", stats)
        self.assertIn("qwen2.5-coder:1.5b", stats)
        self.assertIn("qwen2.5vl:3b", stats)
        self.assertIn("hermes-3:3b", stats)
        self.assertIn("granite3-dense:2b", stats)
        self.assertIn("got-ocr2", stats)
        self.assertIn("florence-2-base", stats)
        self.assertIn("sensevoice-small", stats)
        self.assertIn("mouse-trajectory-onnx", stats)
        self.assertIn("gemini-3.6-flash", stats)
        self.assertIn("moondream:v2", stats)
        self.assertIn("llava:7b", stats)
        self.assertIn("faster-whisper", stats)
        self.assertEqual(len(stats), 18)

    def test_record_start_and_finish_lifecycle(self):
        # 1. Start operation on Qwen 1.5B (DOM Consent)
        self.bus.record_start(
            model_id="qwen2.5:1.5b",
            operation="⚇ GDPR Cookie Banner Resolution",
            prompt_summary="Analyze button tags for consent",
            target_info="https://browserscan.net"
        )
        
        stat = self.bus.get_model_stats("qwen2.5:1.5b")
        self.assertTrue(stat["is_active"])
        self.assertEqual(stat["status"], "ACTIVE")
        self.assertEqual(stat["current_task"], "⚇ GDPR Cookie Banner Resolution")
        self.assertEqual(stat["current_target"], "https://browserscan.net")

        # 2. Finish operation
        self.bus.record_finish(
            model_id="qwen2.5:1.5b",
            operation="⚇ GDPR Cookie Banner Resolution",
            duration_ms=115.4,
            status="SUCCESS",
            result_summary="AI selected candidate [0]: 'Alle akzeptieren'"
        )

        stat_after = self.bus.get_model_stats("qwen2.5:1.5b")
        self.assertFalse(stat_after["is_active"])
        self.assertEqual(stat_after["status"], "IDLE")
        self.assertEqual(stat_after["total_calls"], 1)
        self.assertAlmostEqual(stat_after["last_duration_ms"], 115.4, delta=0.1)

        # 3. History verification
        history = self.bus.get_history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["model_id"], "qwen2.5:1.5b")
        self.assertEqual(history[0]["operation"], "⚇ GDPR Cookie Banner Resolution")
        self.assertEqual(history[0]["status"], "SUCCESS")

    def test_model_id_normalization(self):
        self.assertEqual(self.bus._normalize_model_id("onnx"), "onnx-anomaly")
        self.assertEqual(self.bus._normalize_model_id("QWEN2.5:0.5B"), "qwen2.5:0.5b")
        self.assertEqual(self.bus._normalize_model_id("qwen2.5:3b"), "qwen2.5:3b")
        self.assertEqual(self.bus._normalize_model_id("deepseek-r1:1.5b"), "deepseek-r1:1.5b")
        self.assertEqual(self.bus._normalize_model_id("qwen2.5-coder:1.5b"), "qwen2.5-coder:1.5b")
        self.assertEqual(self.bus._normalize_model_id("qwen2.5vl:3b"), "qwen2.5vl:3b")
        self.assertEqual(self.bus._normalize_model_id("llava:7b"), "llava:7b")
        self.assertEqual(self.bus._normalize_model_id("smolvlm"), "moondream:v2")
        self.assertEqual(self.bus._normalize_model_id("whisper-tiny"), "faster-whisper")
        self.assertEqual(self.bus._normalize_model_id("gemini-3.6-flash"), "gemini-3.6-flash")
        self.assertEqual(self.bus._normalize_model_id("gemini-2.0-flash"), "gemini-3.6-flash")
        self.assertEqual(self.bus._normalize_model_id("gemini-1.5-pro"), "gemini-3.6-flash")

    def test_dynamic_model_routing_and_active_switching(self):
        ai_mgr = AIModelManager.get_instance()
        
        # Test swarm_auto_full mapping
        ai_mgr.set_active_model("swarm_auto_full")
        self.assertEqual(ai_mgr.get_active_model(), "swarm_auto_full")
        roles_swarm = ai_mgr.get_hybrid_roles()
        self.assertEqual(roles_swarm["text_model"], "qwen2.5:1.5b")
        self.assertEqual(roles_swarm["reasoning_model"], "deepseek-r1:1.5b")
        self.assertEqual(roles_swarm["coder_model"], "qwen2.5-coder:1.5b")
        self.assertEqual(roles_swarm["vision_model"], "gemini-3.6-flash")
        self.assertEqual(roles_swarm["heavy_vision_model"], "gemini-3.6-flash")
        self.assertEqual(roles_swarm["local_vision_fallback"], "moondream:v2")
        self.assertEqual(roles_swarm["local_heavy_vision_fallback"], "llava:7b")
        self.assertEqual(roles_swarm["strategy_model"], "qwen2.5:3b")
        self.assertEqual(roles_swarm["micro_model"], "qwen2.5:0.5b")
        self.assertEqual(roles_swarm["audio_model"], "faster-whisper")
        self.assertEqual(roles_swarm["sentinel_model"], "onnx-anomaly")

        # Test next-gen hybrid modes
        roles_ds = ai_mgr.get_hybrid_roles("hybrid_deepseek_vision")
        self.assertEqual(roles_ds["text_model"], "deepseek-r1:1.5b")
        self.assertEqual(roles_ds["vision_model"], "qwen2.5vl:3b")

        roles_coder = ai_mgr.get_hybrid_roles("hybrid_coder_tactician")
        self.assertEqual(roles_coder["text_model"], "qwen2.5-coder:1.5b")
        self.assertEqual(roles_coder["coder_model"], "qwen2.5-coder:1.5b")

        # Test default and active switching
        ai_mgr.set_active_model("hybrid_high_perf")
        self.assertEqual(ai_mgr.get_active_model(), "hybrid_high_perf")
        roles = ai_mgr.get_hybrid_roles()
        self.assertEqual(roles["text_model"], "qwen2.5:3b")
        self.assertEqual(roles["vision_model"], "llava:7b")

        ai_mgr.set_active_model("hybrid_eco")
        roles_eco = ai_mgr.get_hybrid_roles()
        self.assertEqual(roles_eco["text_model"], "qwen2.5:0.5b")
        self.assertEqual(roles_eco["vision_model"], "moondream:v2")

    def test_ai_swarm_orchestrator_initialization(self):
        from engine.ai_swarm_orchestrator import AISwarmOrchestrator
        swarm = AISwarmOrchestrator.get_instance()
        self.assertIsNotNone(swarm)
        self.assertFalse(swarm.is_auto_full_mode_active())
        swarm.set_auto_full_mode(True)
        self.assertTrue(swarm.is_auto_full_mode_active())
        swarm.set_auto_full_mode(False)


if __name__ == "__main__":
    unittest.main()
