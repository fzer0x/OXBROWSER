import unittest
import asyncio
import time
from typing import Dict, Any

from engine.ai_action_council import AIActionCouncil, ActionCouncilVerdict
from engine.geo_ip_aligner import GeoIPAligner, GeoIPProfileAlignment
from storage.cloud_sync_manager import EncryptedCloudSyncManager, SyncProviderType
from engine.session_pool_manager import SessionPoolManager
from engine.workflow_engine import WorkflowDAG, WorkflowNode, NodeType, WorkflowDAGRunner
from engine.fingerprint import FingerprintGenerator


class TestRoadmapFeatures(unittest.IsolatedAsyncioTestCase):

    def test_geoip_aligner(self):
        # Test German Proxy
        proxy_de = {
            "ip": "185.220.101.5",
            "country": "Germany",
            "country_code": "DE",
            "city": "Berlin",
            "lat": 52.52,
            "lon": 13.405,
            "timezone": "Europe/Berlin"
        }
        alignment = GeoIPAligner.align_from_proxy_info(proxy_de)
        self.assertEqual(alignment.country_code, "DE")
        self.assertEqual(alignment.locale, "de-DE")
        self.assertIn("de-DE", alignment.languages)
        self.assertIn("de-DE", alignment.accept_language)
        self.assertEqual(alignment.timezone_id, "Europe/Berlin")
        self.assertEqual(alignment.latitude, 52.52)

        # Context Kwargs injection test
        ctx_opts: Dict[str, Any] = {}
        injected = GeoIPAligner.apply_to_playwright_context_options(ctx_opts, alignment)
        self.assertEqual(injected["locale"], "de-DE")
        self.assertEqual(injected["timezone_id"], "Europe/Berlin")
        self.assertEqual(injected["geolocation"]["latitude"], 52.52)
        self.assertIn("Accept-Language", injected["extra_http_headers"])

    def test_encrypted_cloud_sync_zero_knowledge(self):
        sync_mgr = EncryptedCloudSyncManager.get_instance()
        dummy_profile = {
            "id": "prof-sync-test-99",
            "name": "Secret Enterprise Profile",
            "cookies": [{"name": "session_id", "value": "secret_token_12345"}]
        }
        master_pass = "UltraSecretVaultPassphrase2026!"
        
        # Encrypt
        enc_blob, sha = sync_mgr.create_encrypted_package(dummy_profile, master_pass)
        self.assertIsInstance(enc_blob, bytes)
        self.assertGreater(len(enc_blob), 0)
        self.assertEqual(len(sha), 64)
        self.assertNotIn(b"secret_token_12345", enc_blob)  # Ciphertext must not leak plaintext

        # Decrypt
        decrypted = sync_mgr.unpack_encrypted_package(enc_blob, master_pass)
        self.assertEqual(decrypted["id"], "prof-sync-test-99")
        self.assertEqual(decrypted["name"], "Secret Enterprise Profile")
        self.assertEqual(decrypted["cookies"][0]["value"], "secret_token_12345")

    async def test_session_pool_manager(self):
        pool = SessionPoolManager(max_concurrent_sessions=5, max_ram_per_session_mb=500.0)
        
        # Acquire 3 slots
        ok1 = await pool.acquire_session_slot("session-1")
        ok2 = await pool.acquire_session_slot("session-2")
        ok3 = await pool.acquire_session_slot("session-3")
        self.assertTrue(ok1 and ok2 and ok3)
        
        status = pool.get_pool_status()
        self.assertEqual(status["active_sessions_count"], 3)
        self.assertEqual(status["max_concurrent_sessions"], 5)

        # Release slots
        pool.release_session_slot("session-1")
        pool.release_session_slot("session-2")
        pool.release_session_slot("session-3")

        status_after = pool.get_pool_status()
        self.assertEqual(status_after["active_sessions_count"], 0)

    def test_workflow_dag_serialization(self):
        dag = WorkflowDAG(name="E-Commerce Farming DAG")
        n1 = WorkflowNode(id="node-1", node_type=NodeType.NAVIGATE, title="Open Amazon", params={"url": "https://amazon.com"})
        n2 = WorkflowNode(id="node-2", node_type=NodeType.WAIT, title="Dwell 5s", params={"duration": 5.0})
        n3 = WorkflowNode(id="node-3", node_type=NodeType.VLA_CLICK, title="Click Cart", params={"instruction": "Click cart icon"})
        
        n1.next_node_ids = [n2.id]
        n2.next_node_ids = [n3.id]
        dag.entry_node_id = n1.id
        dag.nodes = {n1.id: n1, n2.id: n2, n3.id: n3}

        serialized = dag.to_dict()
        self.assertEqual(serialized["name"], "E-Commerce Farming DAG")
        self.assertEqual(len(serialized["nodes"]), 3)

        restored = WorkflowDAG.from_dict(serialized)
        self.assertEqual(restored.entry_node_id, "node-1")
        self.assertEqual(restored.nodes["node-1"].params["url"], "https://amazon.com")
        self.assertEqual(restored.nodes["node-3"].node_type, NodeType.VLA_CLICK)

    def test_webgl_shader_jitter_in_fingerprint(self):
        # Verify WebGL injection contains GPU Shader Jitter and readPixels micro-noise
        webgl_patch = FingerprintGenerator._generate_webgl_patch("Google Inc. (NVIDIA)", "ANGLE (NVIDIA, RTX 3060)")
        self.assertIn("readPixels", webgl_patch)
        self.assertIn("noiseFactor", webgl_patch)
        self.assertIn("getShaderPrecisionFormat", webgl_patch)

    async def test_ai_action_council_verdict(self):
        council = AIActionCouncil.get_instance()
        verdict = await council.evaluate_action_safety(
            page=None,
            action_type="click",
            target_point=(450, 320),
            target_text="Accept Cookies",
            context_intent="Dismissing consent modal"
        )
        self.assertIsInstance(verdict, ActionCouncilVerdict)
        self.assertTrue(verdict.is_approved)
        self.assertLess(verdict.risk_score, 0.5)
        self.assertIsNotNone(verdict.adjusted_point)


if __name__ == "__main__":
    unittest.main()
