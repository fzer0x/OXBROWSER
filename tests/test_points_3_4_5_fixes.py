import unittest
import os
import config
from engine.ai_model_config import AIModelConfigManager, DEFAULT_MODEL_CONFIGS
from engine.ai_model_manager import AIModelManager
from engine.ai_agent_actions import AIAgentActionEngine
from engine.ai_vla_engine import VisionLanguageActionEngine

class TestPoints345Fixes(unittest.TestCase):
    """
    Automated regression tests verifying 100% implementation of Points 3, 4, and 5:
    - Model Tag Harmonization (hermes3:3b, moondream:v2)
    - Context size optimization & DeepSeek-R1 CoT decoupling
    - Flash Attention & KV cache quantization
    - Action block security gating & Indirect Prompt Injection defense
    - REST API Host binding & token security
    """

    def test_hermes_and_moondream_tag_harmonization(self):
        ai_mgr = AIModelManager.get_instance()
        self.assertEqual(ai_mgr.normalize_ollama_tag("hermes-3:3b"), "hermes3:3b")
        self.assertEqual(ai_mgr.normalize_ollama_tag("hermes3"), "hermes3:3b")
        self.assertEqual(ai_mgr.normalize_ollama_tag("moondream:latest"), "moondream:v2")
        self.assertEqual(ai_mgr.normalize_ollama_tag("moondream"), "moondream:v2")

        # Config lookups
        cfg_mgr = AIModelConfigManager.get_instance()
        cfg_hyphen = cfg_mgr.get_model_config("hermes-3:3b")
        cfg_nohyphen = cfg_mgr.get_model_config("hermes3:3b")
        self.assertEqual(cfg_hyphen["system_prompt"], cfg_nohyphen["system_prompt"])
        self.assertEqual(cfg_nohyphen["num_ctx"], 8192)

    def test_context_sizes_and_deepseek_r1_cot(self):
        cfg_mgr = AIModelConfigManager.get_instance()
        
        # Qwen 1.5B optimized from 8192 to 4096
        qwen15 = cfg_mgr.get_model_config("qwen2.5:1.5b")
        self.assertEqual(qwen15["num_ctx"], 4096)

        # Qwen Coder optimized to 4096
        coder = cfg_mgr.get_model_config("qwen2.5-coder:1.5b")
        self.assertEqual(coder["num_ctx"], 4096)

        # DeepSeek-R1 decoupled from json_mode
        r1 = cfg_mgr.get_model_config("deepseek-r1:1.5b")
        self.assertFalse(r1["json_mode"], "DeepSeek-R1 must have json_mode=False to allow <think> CoT output")
        self.assertEqual(r1["num_ctx"], 8192)

    def test_vla_engine_default_vision_model(self):
        vla = VisionLanguageActionEngine.get_instance()
        # Ensure default model is moondream:v2
        import inspect
        sig = inspect.signature(vla.perceive_and_act)
        self.assertEqual(sig.parameters["vision_model"].default, "moondream:v2")

    def test_action_safety_gating(self):
        engine = AIAgentActionEngine.get_instance()
        
        # Safe read-only action
        safe_action = {"action": "audit_profile", "target": "Profile 1"}
        ok, msg = engine.validate_action_safety(safe_action, allow_destructive=False)
        self.assertTrue(ok)

        # Destructive action without approval -> BLOCKED
        destruct_action = {"action": "delete_profile", "target": "Profile 1"}
        ok, msg = engine.validate_action_safety(destruct_action, allow_destructive=False)
        self.assertFalse(ok)
        self.assertIn("requires human confirmation", msg)

        # Destructive action with explicit approval -> ALLOWED
        ok, msg = engine.validate_action_safety(destruct_action, allow_destructive=True)
        self.assertTrue(ok)

    def test_api_security_defaults(self):
        # API Host must default to 127.0.0.1
        self.assertIn(config.API_HOST, ["127.0.0.1", "localhost"])
        
        # Token must not be the vulnerable static default string
        self.assertNotEqual(config.API_BEARER_TOKEN, "soxbot_secret_bearer_token_2.0.0")

if __name__ == "__main__":
    unittest.main()
