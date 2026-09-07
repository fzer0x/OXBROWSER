import os
import sys
import json
import unittest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.ai_chat_engine import (
    AIChatEngine, ChatMessage, SwarmAgentResponse,
    SYSTEM_PERSONAS, SWARM_MODES
)


class TestAIChatEngine(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = AIChatEngine.get_instance()
        self.engine.clear_history()

    def test_chat_message_dataclass_and_serialization(self):
        """Verify ChatMessage initialization and dictionary export."""
        msg = ChatMessage(
            role="user",
            content="How does Canvas noise evasion work?",
            model="qwen2.5:1.5b",
            image_b64=None,
            metadata={"tokens": 12}
        )
        self.assertEqual(msg.role, "user")
        self.assertEqual(msg.content, "How does Canvas noise evasion work?")
        self.assertEqual(msg.model, "qwen2.5:1.5b")
        self.assertEqual(msg.metadata["tokens"], 12)

        d = msg.to_dict()
        self.assertEqual(d["role"], "user")
        self.assertEqual(d["content"], "How does Canvas noise evasion work?")
        self.assertIn("timestamp", d)

    def test_history_management_and_export(self):
        """Verify adding messages, clearing history, and exporting markdown/json."""
        self.assertEqual(len(self.engine.get_history()), 0)

        self.engine.add_message(ChatMessage(role="user", content="Hello AI"))
        self.engine.add_message(ChatMessage(
            role="assistant",
            content="Hello Human! Here is code: ```python\nprint('stealth')\n```",
            model="qwen2.5:1.5b",
            swarm_breakdown=[{
                "agent_id": "tactician",
                "role_name": "Tactical Scout",
                "model_name": "qwen2.5:1.5b",
                "thought_process": "Analyzed greeting",
                "response_text": "Hello Human!",
                "latency_ms": 42.0
            }]
        ))

        history = self.engine.get_history()
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0].role, "user")
        self.assertEqual(history[1].role, "assistant")

        # Test Markdown export
        md = self.engine.export_to_markdown()
        self.assertIn("# OXBROWSER AI Chat Session Export", md)
        self.assertIn("Hello AI", md)
        self.assertIn("Hello Human!", md)
        self.assertIn("Tactical Scout", md)

        # Test JSON export
        js = self.engine.export_to_json()
        data = json.loads(js)
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["content"], "Hello AI")

        # Test clear
        self.engine.clear_history()
        self.assertEqual(len(self.engine.get_history()), 0)

    def test_personas_and_custom_prompt(self):
        """Verify system personas and custom system prompt handling."""
        self.engine.set_system_persona("stealth_copilot")
        prompt = self.engine.get_effective_system_prompt()
        self.assertIn("OXBROWSER AI Stealth & Anti-Detect Copilot", prompt)

        self.engine.set_system_persona("security_pentester")
        prompt_pentest = self.engine.get_effective_system_prompt()
        self.assertIn("Web Security Pentester", prompt_pentest)
        self.assertIn("OWASP", prompt_pentest)

        self.engine.set_system_persona("evasion_redteam")
        prompt_evasion = self.engine.get_effective_system_prompt()
        self.assertIn("Red Team Operator", prompt_evasion)
        self.assertIn("WAF", prompt_evasion)

        self.engine.set_system_persona("poweruser_engineer")
        prompt_power = self.engine.get_effective_system_prompt()
        self.assertIn("Reverse Engineer", prompt_power)
        self.assertIn("PCAP", prompt_power)

        self.engine.set_system_persona("automation_architect")
        prompt_auto = self.engine.get_effective_system_prompt()
        self.assertIn("Playwright", prompt_auto)

        self.engine.set_system_persona("custom", "You are a custom AI pentester.")
        self.assertIn("You are a custom AI pentester.", self.engine.get_effective_system_prompt())

    def test_preferred_response_languages(self):
        """Verify response language selection and directive injection."""
        self.engine.set_preferred_language("de")
        self.assertEqual(self.engine.get_preferred_language(), "de")
        prompt_de = self.engine.get_effective_system_prompt()
        self.assertIn("German (Deutsch)", prompt_de)

        self.engine.set_preferred_language("en")
        prompt_en = self.engine.get_effective_system_prompt()
        self.assertIn("English", prompt_en)

        self.engine.set_preferred_language("auto")
        prompt_auto = self.engine.get_effective_system_prompt()
        self.assertNotIn("CRITICAL LANGUAGE REQUIREMENT", prompt_auto)

    def test_profile_context_injection(self):
        """Verify anti-detect browser profile context string formatting."""
        self.assertEqual(self.engine.format_profile_context(None), "")

        profile = {
            "id": "prof_12345",
            "name": "E-Commerce Stealth Profile",
            "os": "Windows",
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Camoufox/135.0",
            "status": "Running",
            "hardware_concurrency": 16,
            "device_memory": 32,
            "screen_width": 2560,
            "screen_height": 1440,
            "proxy": {"enabled": True, "host": "192.168.1.100", "port": 8080, "type": "socks5"},
            "stealth": {
                "canvas_noise": True,
                "webgl_vendor": "Google Inc.",
                "webgl_renderer": "ANGLE",
                "audio_noise": True,
                "webrtc_mode": "altered"
            }
        }

        ctx = self.engine.format_profile_context(profile)
        self.assertIn("[CURRENT ACTIVE BROWSER PROFILE CONTEXT]", ctx)
        self.assertIn("E-Commerce Stealth Profile", ctx)
        self.assertIn("SOCKS5://192.168.1.100:8080", ctx)
        self.assertIn("Canvas Noise=True", ctx)
        self.assertIn("WebRTC Policy: altered", ctx)
        self.assertIn("ONNX ML Authenticity Score:", ctx)
        self.assertIn("LIVE ONNX MATHEMATICAL & STEALTH SECURITY AUDIT", ctx)

    def test_resolve_profile_from_prompt(self):
        sample_prof = {"id": "p_linux_01", "name": "LINUX_01", "os": "linux"}
        with patch("storage.profile_manager.ProfileManager.list_profiles", return_value=[sample_prof]):
            # Test quoted matching
            resolved = self.engine.resolve_profile_from_prompt("Audit the stealth configuration of profile 'LINUX_01'")
            self.assertIsNotNone(resolved)
            self.assertEqual(resolved["name"], "LINUX_01")

            # Test unquoted matching
            resolved2 = self.engine.resolve_profile_from_prompt("Check LINUX_01 for leaks")
            self.assertIsNotNone(resolved2)
            self.assertEqual(resolved2["name"], "LINUX_01")

            # Test fallback when not mentioned
            fallback = {"id": "fallback_id", "name": "Fallback"}
            resolved3 = self.engine.resolve_profile_from_prompt("General question without profile", fallback_profile=fallback)
            self.assertEqual(resolved3, fallback)

    async def test_swarm_consensus_routing_and_execution(self):
        """Verify Swarm Consensus mode dispatches sub-agents and synthesizes response."""
        mock_ai_mgr = self.engine.ai_mgr
        mock_gemini = self.engine.gemini_client

        with patch.object(mock_ai_mgr, "generate_response", new=AsyncMock(return_value="Tactical perspective on fingerprint evasion.")), \
             patch.object(mock_gemini, "is_configured", return_value=False), \
             patch.object(self.engine, "_stream_ollama", new=AsyncMock(return_value=ChatMessage(role="assistant", content="Synthesized consensus response.", model="qwen2.5:1.5b"))):

            chunks = []
            swarm_steps = []
            statuses = []

            result = await self.engine.stream_chat(
                prompt="How do I evade Canvas font detection?",
                model_or_swarm="swarm_consensus",
                on_chunk=lambda c: chunks.append(c),
                on_swarm_step=lambda s: swarm_steps.append(s),
                on_status=lambda st: statuses.append(st)
            )

            self.assertEqual(result.role, "assistant")
            self.assertGreaterEqual(len(swarm_steps), 1)
            self.assertIn("Swarm Consensus Council", result.model)

    async def test_swarm_specialist_routing(self):
        """Verify Swarm Specialist routes fingerprint queries and automation queries."""
        mock_gemini = self.engine.gemini_client
        with patch.object(mock_gemini, "is_configured", return_value=False), \
             patch.object(self.engine, "_stream_ollama", new=AsyncMock(return_value=ChatMessage(role="assistant", content="Specialist script generated.", model="qwen2.5:3b"))), \
             patch.object(self.engine, "_stream_gemini", new=AsyncMock(return_value=ChatMessage(role="assistant", content="Specialist script generated.", model="gemini-3.6-flash"))):
            steps = []
            res = await self.engine.stream_chat(
                prompt="Write a Playwright python script to click the login button",
                model_or_swarm="swarm_specialist",
                on_swarm_step=lambda s: steps.append(s)
            )

            self.assertEqual(len(steps), 1)
            self.assertIn("DOM & Automation Script Architect", steps[0].role_name)
            self.assertIn("Swarm Specialist", res.model)


if __name__ == "__main__":
    unittest.main()
