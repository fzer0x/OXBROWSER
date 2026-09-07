import os
import sys
import unittest
import tempfile
import json
import shutil
import asyncio

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from storage.profile_manager import ProfileManager
from storage.proxy_manager import ProxyManager
from engine.ai_agent_actions import AIAgentActionEngine
from engine.environment_tester import (
    EnvironmentAuditEngine,
    AutoPatchEngine,
    EnvironmentBenchmarkTarget,
    BENCHMARK_URLS
)
from engine.browser import BrowserLauncher


class TestSeniorAgentFullSuite(unittest.TestCase):
    """
    Comprehensive Test Suite for 100% AI Agent Mode Control,
    Senior Environment Tests, and 1-Click Autonomous Patching.
    """

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.profile_mgr = ProfileManager(profiles_dir=self.test_dir)
        self.proxy_mgr = ProxyManager(storage_file=os.path.join(self.test_dir, "proxies.json"))
        self.agent_engine = AIAgentActionEngine(
            profile_manager=self.profile_mgr,
            proxy_manager=self.proxy_mgr
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    # -------------------------------------------------------------------------
    # 1. Profile Generation & Harmonization
    # -------------------------------------------------------------------------
    def test_generate_harmonized_profiles_across_operating_systems(self):
        for os_name in ["windows", "mac", "linux"]:
            p = self.agent_engine.generate_harmonized_profile(
                name=f"Test_{os_name.capitalize()}",
                os_type=os_name,
                country="DE"
            )
            self.assertEqual(p["os"], os_name)
            self.assertTrue(p["stealth"]["canvas_noise"])
            self.assertTrue(p["stealth"]["audio_noise"])
            self.assertIn("webgl_vendor", p["stealth"])
            self.assertIn("webgl_renderer", p["stealth"])

            # Verify audit score on freshly synthesized profile
            audit = EnvironmentAuditEngine.audit_profile_configuration(p)
            self.assertGreaterEqual(audit["health_score"], 90.0)

    # -------------------------------------------------------------------------
    # 2. Batch Profile Creation
    # -------------------------------------------------------------------------
    def test_batch_profile_creation(self):
        profiles = [
            self.agent_engine.generate_harmonized_profile(name=f"Batch_Prof_{i}", os_type="windows")
            for i in range(5)
        ]
        success, ids, msg = self.agent_engine.create_batch_profiles(profiles)
        self.assertTrue(success)
        self.assertEqual(len(ids), 5)
        self.assertEqual(len(self.profile_mgr.list_profiles()), 5)

    # -------------------------------------------------------------------------
    # 3. Profile Lifecycle & Identification Resolution
    # -------------------------------------------------------------------------
    def test_profile_resolution_by_name_index_and_id(self):
        p1 = self.agent_engine.generate_harmonized_profile(name="Alpha_Stealth", os_type="windows")
        p2 = self.agent_engine.generate_harmonized_profile(name="Beta_Stealth", os_type="mac")
        self.agent_engine.create_profile(p1)
        self.agent_engine.create_profile(p2)

        # By exact ID
        self.assertEqual(self.agent_engine.resolve_profile_id(p1["id"]), p1["id"])
        # By Name
        self.assertEqual(self.agent_engine.resolve_profile_id("Alpha_Stealth"), p1["id"])
        # By Index / Ordinal (e.g. 'Profil 1' or 'Profile 2')
        self.assertEqual(self.agent_engine.resolve_profile_id("Profil 1"), p1["id"])
        self.assertEqual(self.agent_engine.resolve_profile_id("Profile 2"), p2["id"])

    # -------------------------------------------------------------------------
    # 4. Senior Audit & Anomaly Detection (Intentionally Corrupted Tensors)
    # -------------------------------------------------------------------------
    def test_audit_detects_mismatches(self):
        corrupted_profile = {
            "id": "corrupted_001",
            "name": "Corrupted_Profile",
            "os": "windows",
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "hardware_concurrency": 16,
            "device_memory": 2,  # Anomalous RAM for 16 cores
            "screen_resolution": "640x480",  # Anomalous screen
            "engine": "camoufox",
            "stealth": {
                "webgl_vendor": "Apple",  # Critical Mismatch: Apple GPU on Windows
                "webgl_renderer": "Apple M2 Max",
                "canvas_noise": False,  # Noise disabled
                "audio_noise": False,
                "webrtc_mode": "disabled"
            }
        }
        self.profile_mgr.save_profile(corrupted_profile)

        success, audit, msg = self.agent_engine.audit_profile("corrupted_001")
        self.assertTrue(success)
        self.assertFalse(audit["is_clean"])
        self.assertLess(audit["health_score"], 80.0)
        self.assertGreater(audit["anomaly_count"], 0)

        # Check detected anomaly categories
        categories = [an["category"] for an in audit["anomalies"]]
        self.assertIn("WebGL", categories)
        self.assertIn("Noise", categories)
        self.assertIn("Hardware", categories)

    # -------------------------------------------------------------------------
    # 5. 1-Click Auto-Patching & Remediation
    # -------------------------------------------------------------------------
    def test_one_click_auto_patch_remediation(self):
        corrupted_profile = {
            "id": "patch_test_001",
            "name": "To_Be_Patched",
            "os": "windows",
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "hardware_concurrency": 16,
            "device_memory": 2,
            "screen_resolution": "800x600",
            "engine": "camoufox",
            "stealth": {
                "webgl_vendor": "Apple",
                "webgl_renderer": "Apple M1",
                "canvas_noise": False,
                "audio_noise": False,
                "webrtc_mode": "altered"
            }
        }
        self.profile_mgr.save_profile(corrupted_profile)

        # Execute 1-Click Auto Patch
        success, msg, changes = self.agent_engine.apply_audit_patches("patch_test_001")
        self.assertTrue(success)
        self.assertGreater(len(changes), 0)

        # Verify profile is now 100% harmonized
        patched_prof = self.profile_mgr.load_profile("patch_test_001")
        self.assertTrue(patched_prof["stealth"]["canvas_noise"])
        self.assertTrue(patched_prof["stealth"]["audio_noise"])
        self.assertNotIn("Apple", patched_prof["stealth"]["webgl_vendor"])

        re_audit = EnvironmentAuditEngine.audit_profile_configuration(patched_prof)
        self.assertTrue(re_audit["is_clean"])
        self.assertGreaterEqual(re_audit["health_score"], 90.0)

    # -------------------------------------------------------------------------
    # 6. Action Block Parser Coverage (All A-Z Action Types)
    # -------------------------------------------------------------------------
    def test_extract_action_blocks_full_grammar(self):
        sample_ai_text = """
        Hier ist die Analyse und die Aktionen zur Steuerung:
        
        ```action:create_profile
        {
            "name": "Stealth_Win_01",
            "os": "windows",
            "country": "DE"
        }
        ```
        
        Und hier der Lifecycle-Befehl:
        ```action:launch_profile
        {"target": "Profil 1"}
        ```
        
        Und der Audit-Befehl:
        ```action:audit_profile
        {"target": "Profil 1"}
        ```
        """
        actions = AIAgentActionEngine.extract_action_blocks(sample_ai_text)
        self.assertEqual(len(actions), 3)
        self.assertEqual(actions[0]["action"], "create_profile")
        self.assertEqual(actions[1]["action"], "launch_profile")
        self.assertEqual(actions[2]["action"], "audit_profile")

    # -------------------------------------------------------------------------
    # 7. Benchmark Targets
    # -------------------------------------------------------------------------
    def test_benchmark_targets(self):
        url = self.agent_engine.get_benchmark_url(EnvironmentBenchmarkTarget.CREEPJS)
        self.assertIn("creepjs", url)
        b_url = self.agent_engine.get_benchmark_url("browserleaks")
        self.assertIn("browserleaks", b_url)


if __name__ == "__main__":
    unittest.main()
