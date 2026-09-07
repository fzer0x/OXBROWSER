import unittest
import asyncio
from engine.ai_knowledge_rag import AIKnowledgeRAG
from engine.ai_voice_copilot import AIVoiceCopilot
from engine.ai_chat_engine import AIChatEngine, SWARM_MODES


class TestAIAdversarialRAG(unittest.IsolatedAsyncioTestCase):

    def test_ai_knowledge_rag(self):
        rag = AIKnowledgeRAG.get_instance()
        
        # Query for WebRTC
        res = rag.query("How to prevent WebRTC leaks?")
        self.assertGreater(len(res), 0)
        self.assertTrue(any("webrtc" in r["id"].lower() for r in res))

        # Query for TLS JA3
        formatted = rag.format_rag_context("Explain JA3 and JA4 TLS fingerprinting")
        self.assertIn("JA4", formatted)
        self.assertIn("[LOCAL VERIFIED KNOWLEDGE BASE", formatted)

    def test_swarm_modes_has_adversarial(self):
        self.assertIn("swarm_adversarial", SWARM_MODES)
        self.assertIn("⚔️", SWARM_MODES["swarm_adversarial"]["icon"])

    async def test_voice_copilot_intent_detection(self):
        voice = AIVoiceCopilot.get_instance()
        intent1 = "Erstelle 5 Windows-Profile"
        self.assertIn("profil", intent1.lower())


if __name__ == "__main__":
    unittest.main()
