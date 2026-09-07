import unittest
import asyncio
import os
import json
import tempfile
import shutil
from unittest.mock import MagicMock, AsyncMock, patch

from engine.sandbox.network_killswitch import NetworkKillSwitchManager
from engine.sandbox.container_sandbox import ContainerSandbox
from engine.warmup.human_motion import BiGramTypingEngine
from engine.trust_score_evaluator import ProfileTrustEvaluator
from storage.cloud_sync_manager import EncryptedCloudSyncManager, SyncProviderType


class TestCriticalFixes(unittest.IsolatedAsyncioTestCase):

    def test_network_killswitch_subnet_allocation_no_collision(self):
        """Verify dynamic subnet byte allocation produces unique bytes and releases properly."""
        allocated = []
        profile_ids = [f"prof-test-{i}" for i in range(25)]
        
        for pid in profile_ids:
            byte_val = NetworkKillSwitchManager._allocate_subnet_byte(pid)
            self.assertGreaterEqual(byte_val, 2)
            self.assertLess(byte_val, 255)
            self.assertNotIn(byte_val, allocated)
            allocated.append(byte_val)

        # Re-querying same profile ID returns same byte
        same_byte = NetworkKillSwitchManager._allocate_subnet_byte(profile_ids[0])
        self.assertEqual(same_byte, allocated[0])

        # Release first byte
        released = NetworkKillSwitchManager._release_subnet_byte(profile_ids[0])
        self.assertEqual(released, allocated[0])

        # Cleanup all
        for pid in profile_ids:
            NetworkKillSwitchManager._release_subnet_byte(pid)

    async def test_container_sandbox_passthrough_for_camoufox(self):
        """Verify ContainerSandbox does NOT spawn Chromium when engine is Camoufox."""
        profile_data = {
            "id": "camoufox-test-prof",
            "engine": "camoufox",
            "sandbox": {"mode": "container"}
        }
        sandbox = ContainerSandbox("camoufox-test-prof", profile_data, "/tmp/dummy_user_data", 59999)
        ok, msg, dport = await sandbox.start()
        self.assertTrue(ok)
        self.assertIn("Camoufox native process sandbox", msg)
        self.assertIsNone(sandbox.process)
        self.assertIsNone(sandbox.xvfb_process)

    async def test_container_sandbox_passthrough_when_sandbox_off(self):
        """Verify ContainerSandbox does NOT spawn Chromium when sandbox mode is 'off'."""
        profile_data = {
            "id": "off-test-prof",
            "engine": "chromium",
            "sandbox": {"mode": "off"}
        }
        sandbox = ContainerSandbox("off-test-prof", profile_data, "/tmp/dummy_user_data", 59999)
        ok, msg, dport = await sandbox.start()
        self.assertTrue(ok)
        self.assertIn("uncontainerized", msg)
        self.assertIsNone(sandbox.process)
        self.assertIsNone(sandbox.xvfb_process)

    async def test_type_humanoid_press_enter_parameter(self):
        """Verify type_humanoid respects press_enter flag."""
        mock_page = MagicMock()
        mock_page.keyboard = MagicMock()
        mock_page.keyboard.type = AsyncMock()
        mock_page.keyboard.press = AsyncMock()
        
        async def dummy_eval(script):
            return True

        # 1. press_enter=False -> Enter key not pressed
        with patch.object(BiGramTypingEngine, "_press_key", new_callable=AsyncMock) as mock_press_key:
            await BiGramTypingEngine.type_humanoid(
                mock_page, "input#test", "hello", dummy_eval, press_enter=False
            )
            for c in mock_press_key.call_args_list:
                self.assertNotEqual(c[0][2], "Enter")

        # 2. press_enter=True -> Enter key is pressed
        with patch.object(BiGramTypingEngine, "_press_key", new_callable=AsyncMock) as mock_press_key:
            await BiGramTypingEngine.type_humanoid(
                mock_page, "input#test", "hello", dummy_eval, press_enter=True
            )
            has_enter = any(c[0][2] == "Enter" for c in mock_press_key.call_args_list)
            self.assertTrue(has_enter)

    async def test_trust_score_evaluator_reads_cookies_file(self):
        """Verify ProfileTrustEvaluator loads cookies from cookies.json when profile_data['cookies'] is empty."""
        temp_dir = tempfile.mkdtemp()
        try:
            profile_id = "evaluator-test-uuid"
            prof_folder = os.path.join(temp_dir, profile_id)
            os.makedirs(prof_folder, exist_ok=True)
            cookie_file = os.path.join(prof_folder, "cookies.json")
            sample_cookies = [{"name": f"cookie_{i}", "value": "val", "domain": ".example.com"} for i in range(30)]
            with open(cookie_file, "w", encoding="utf-8") as f:
                json.dump(sample_cookies, f)

            with patch("config.PROFILES_DIR", temp_dir):
                profile_data = {
                    "id": profile_id,
                    "stealth": {"canvas_noise": True}
                }
                score, details = await ProfileTrustEvaluator.evaluate_profile_trust(profile_data)
                self.assertGreater(score, 0.0)
                self.assertEqual(details["breakdown"]["cookie_count"], 30)
                self.assertGreater(details["breakdown"]["cookie_score"], 10.0)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    async def test_cloud_sync_manager_s3_validation(self):
        """Verify S3 sync fails gracefully with clear error when required credentials are missing."""
        sync_mgr = EncryptedCloudSyncManager()
        report = await sync_mgr.execute_sync(
            provider_type=SyncProviderType.S3_COMPATIBLE,
            provider_config={},
            master_password="test_master_password_123"
        )
        self.assertFalse(report.success)
        self.assertTrue(any("Missing S3 configuration" in err for err in report.errors))

    async def test_cloud_sync_manager_webdav_validation(self):
        """Verify WebDAV sync fails gracefully with clear error when URL is missing."""
        sync_mgr = EncryptedCloudSyncManager()
        report = await sync_mgr.execute_sync(
            provider_type=SyncProviderType.WEBDAV,
            provider_config={},
            master_password="test_master_password_123"
        )
        self.assertFalse(report.success)
        self.assertTrue(any("Missing WebDAV configuration" in err for err in report.errors))


if __name__ == "__main__":
    unittest.main()
