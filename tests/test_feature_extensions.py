import unittest
import asyncio
import os
import tempfile
import shutil
import json
from unittest.mock import MagicMock, AsyncMock

from engine.workflow_service import WorkflowExecutionService
from engine.fingerprint import FingerprintGenerator
from engine.lifecycle import GlobalLifecycleManager
from engine.geo_ip_aligner import GeoIPAligner, get_country_locale_config
from storage.cloud_sync_manager import EncryptedCloudSyncManager, SyncProviderType


class TestFeatureExtensions(unittest.IsolatedAsyncioTestCase):

    async def asyncTearDown(self):
        try:
            from engine.events import AsyncEventBus
            await AsyncEventBus.get_instance().shutdown()
        except Exception:
            pass

    def test_workflow_execution_service_catalog_and_dag_loading(self):
        """Verify WorkflowExecutionService lists and retrieves valid workflow DAG definitions."""
        service = WorkflowExecutionService.get_instance()
        workflows = service.list_workflows()
        self.assertIsInstance(workflows, list)
        self.assertGreater(len(workflows), 0)
        
        # Verify first workflow
        wf_meta = workflows[0]
        self.assertIn("id", wf_meta)
        self.assertIn("name", wf_meta)
        self.assertIn("nodes_count", wf_meta)

        # Retrieve full definition
        full_wf = service.get_workflow(wf_meta["id"])
        self.assertIsNotNone(full_wf)
        self.assertIn("nodes", full_wf)

    async def test_workflow_execution_lifecycle(self):
        """Verify starting, tracking, and stopping a workflow execution via WorkflowExecutionService."""
        service = WorkflowExecutionService.get_instance()
        workflows = service.list_workflows()
        self.assertGreater(len(workflows), 0)
        wf_id = workflows[0]["id"]

        mock_launcher = MagicMock()
        mock_launcher.running_processes = {}
        mock_launcher.launch_profile = AsyncMock(return_value=(False, "Mock test launcher", None))

        ok, msg, exec_id = await service.start_workflow(
            workflow_id_or_dict=wf_id,
            profile_ids=["test-profile-1"],
            launcher=mock_launcher,
            concurrency=2
        )
        self.assertTrue(ok)
        self.assertIsNotNone(exec_id)

        status_info = service.get_execution_status(exec_id)
        self.assertIsNotNone(status_info)
        self.assertEqual(status_info["execution_id"], exec_id)
        self.assertIn(status_info["status"], ["running", "completed", "stopping", "failed"])

        # Test stop
        service.stop_execution(exec_id)

    def test_deterministic_canvas_noise_script_generation(self):
        """Verify FingerprintGenerator produces complete content-keyed deterministic canvas script."""
        patch_js = FingerprintGenerator._generate_canvas_noise_patch(canvas_noise=True, noise_seed=0.00789)
        self.assertIn("Content-Keyed Deterministic Canvas", patch_js)
        self.assertIn("fnv1a", patch_js)
        self.assertIn("mulberry32", patch_js)
        self.assertIn("getImageData", patch_js)
        self.assertIn("toDataURL", patch_js)
        self.assertIn("toBlob", patch_js)

    def test_resource_governor_headroom_check(self):
        """Verify ResourceGovernor reports accurate headroom and rejects unrealistic memory demands."""
        # 1. Realistic check should pass
        has_headroom, msg, metrics = GlobalLifecycleManager.check_system_headroom(min_free_ram_mb=100)
        self.assertTrue(has_headroom)
        self.assertIn("available_ram_mb", metrics)
        self.assertGreater(metrics["available_ram_mb"], 0)

        # 2. Unrealistic memory demand should fail safely
        has_headroom_fake, msg_fake, metrics_fake = GlobalLifecycleManager.check_system_headroom(min_free_ram_mb=9999999)
        self.assertFalse(has_headroom_fake)
        self.assertIn("Insufficient RAM", msg_fake)

    def test_geoip_aligner_expanded_countries(self):
        """Verify GeoIPAligner accurately maps newly supported countries and handles unmapped ISO codes."""
        test_cases = [
            ("CH", "de-CH", "Europe/Zurich"),
            ("SE", "sv-SE", "Europe/Stockholm"),
            ("BR", "pt-BR", "America/Sao_Paulo"),
            ("JP", "ja-JP", "Asia/Tokyo"),
            ("IN", "en-IN", "Asia/Kolkata"),
            ("PL", "pl-PL", "Europe/Warsaw"),
            ("TR", "tr-TR", "Europe/Istanbul"),
            ("MX", "es-MX", "America/Mexico_City"),
        ]

        for code, expected_locale, expected_tz in test_cases:
            cfg = get_country_locale_config(code)
            self.assertEqual(cfg["locale"], expected_locale)
            self.assertEqual(cfg["default_timezone"], expected_tz)

        # Unmapped country fallback generator test (e.g., Iceland 'IS')
        is_cfg = get_country_locale_config("IS")
        self.assertEqual(is_cfg["locale"], "is-IS")
        self.assertTrue(any("is" in lang for lang in is_cfg["languages"]))
        self.assertIn("is-IS", is_cfg["accept_language"])

    async def test_bidirectional_cloud_sync_local_backup(self):
        """Verify LOCAL_BACKUP executes both encrypted export and restoration."""
        temp_dir = tempfile.mkdtemp()
        try:
            mock_profile_mgr = MagicMock()
            sample_profile = {
                "id": "backup-sync-prof-1",
                "name": "Sync Profile 1",
                "os": "windows",
                "engine": "camoufox",
                "updated_at": 1700000000.0
            }
            mock_profile_mgr.list_profiles.return_value = [sample_profile]
            mock_profile_mgr.get_profile.return_value = sample_profile

            sync_mgr = EncryptedCloudSyncManager(profile_mgr=mock_profile_mgr)

            # 1. Export / Upload
            report_up = await sync_mgr.execute_sync(
                provider_type=SyncProviderType.LOCAL_BACKUP,
                provider_config={"backup_dir": temp_dir},
                master_password="test_sync_password_secure",
                direction="upload"
            )
            self.assertTrue(report_up.success)
            self.assertEqual(report_up.uploaded_count, 1)

            # Check .soxvault file created on disk
            vault_files = [f for f in os.listdir(temp_dir) if f.endswith(".soxvault")]
            self.assertEqual(len(vault_files), 1)

            # 2. Import / Download Restore
            report_down = await sync_mgr.execute_sync(
                provider_type=SyncProviderType.LOCAL_BACKUP,
                provider_config={"backup_dir": temp_dir},
                master_password="test_sync_password_secure",
                direction="download"
            )
            self.assertTrue(report_down.success)
            self.assertEqual(report_down.downloaded_count, 1)
            mock_profile_mgr.save_profile.assert_called()
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    async def test_hcaptcha_solver_instant_token_pass(self):
        """Verify AICaptchaSolver.solve_hcaptcha detects passive token completion."""
        from engine.ai_captcha_solver import AICaptchaSolver
        mock_page = MagicMock()
        mock_page.frames = []
        mock_page.locator.return_value.count = AsyncMock(return_value=0)
        # Mock evaluate returning valid token
        mock_page.evaluate = AsyncMock(return_value="P0_eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...")

        solved, msg, details = await AICaptchaSolver.solve_hcaptcha(mock_page)
        self.assertTrue(solved)
        self.assertIn("hCaptcha Solved", msg)
        self.assertTrue(details["solved"])
        self.assertIn("token", details)

    async def test_funcaptcha_solver_token_pass(self):
        """Verify AICaptchaSolver.solve_funcaptcha detects Arkose challenge token."""
        from engine.ai_captcha_solver import AICaptchaSolver
        mock_page = MagicMock()
        mock_frame = MagicMock()
        mock_frame.url = "https://client-api.arkoselabs.com/fc/api/"
        mock_frame.child_frames = []
        mock_frame.locator.return_value.count = AsyncMock(return_value=0)
        mock_page.frames = [mock_frame]
        mock_page.locator.return_value.count = AsyncMock(return_value=0)
        mock_page.evaluate = AsyncMock(return_value="1234567890abcdef1234567890abcdef.token")

        solved, msg, details = await AICaptchaSolver.solve_funcaptcha(mock_page)
        self.assertTrue(solved)
        self.assertIn("FunCaptcha Solved", msg)
        self.assertTrue(details["solved"])


if __name__ == "__main__":
    unittest.main()
