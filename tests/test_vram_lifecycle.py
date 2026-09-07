import unittest
import asyncio
from engine.ai_model_manager import AIModelManager

class TestVRAMLifecycle(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.mgr = AIModelManager.get_instance()

    async def test_hybrid_roles_mapping(self):
        roles_auto = self.mgr.get_hybrid_roles("hybrid_auto")
        self.assertIn("text_model", roles_auto)
        self.assertIn("vision_model", roles_auto)
        self.assertEqual(roles_auto["text_model"], "qwen2.5:1.5b")
        self.assertEqual(roles_auto["vision_model"], "llava:7b")

        roles_eco = self.mgr.get_hybrid_roles("hybrid_eco")
        self.assertEqual(roles_eco["text_model"], "qwen2.5:0.5b")
        self.assertEqual(roles_eco["vision_model"], "moondream:v2")

        roles_perf = self.mgr.get_hybrid_roles("hybrid_high_perf")
        self.assertEqual(roles_perf["text_model"], "qwen2.5:3b")
        self.assertEqual(roles_perf["vision_model"], "llava:7b")

    async def test_unload_model_safe_execution(self):
        # Should execute safely without raising exception even if ollama not connected
        res = await self.mgr.unload_model("non_existent_test_model")
        self.assertIsInstance(res, bool)

        res_vision = await self.mgr.unload_vision_models()
        self.assertTrue(res_vision)

if __name__ == "__main__":
    unittest.main()
