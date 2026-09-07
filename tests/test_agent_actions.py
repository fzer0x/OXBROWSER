import os
import shutil
import tempfile
import unittest
from storage.profile_manager import ProfileManager
from storage.warmup_campaign_manager import WarmupCampaignManager
from engine.ai_agent_actions import AIAgentActionEngine


class TestAgentActions(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.profiles_dir = os.path.join(self.test_dir, "profiles")
        self.campaigns_dir = os.path.join(self.test_dir, "warmup_campaigns")
        
        self.profile_mgr = ProfileManager(profiles_dir=self.profiles_dir)
        self.campaign_mgr = WarmupCampaignManager(campaigns_dir=self.campaigns_dir)
        self.agent_engine = AIAgentActionEngine(
            profile_manager=self.profile_mgr,
            campaign_manager=self.campaign_mgr
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_default_campaigns_initialization(self):
        campaigns = self.campaign_mgr.list_campaigns()
        self.assertGreaterEqual(len(campaigns), 4)
        
        ecom = self.campaign_mgr.get_campaign("ecommerce_trust_builder")
        self.assertIsNotNone(ecom)
        self.assertEqual(ecom["category"], "ecommerce")
        self.assertIn("urls", ecom)
        self.assertGreater(len(ecom["urls"]), 0)

    def test_save_and_load_custom_campaign(self):
        custom_data = {
            "name": "DeFi Alpha Seeker",
            "category": "tech",
            "persona": "crypto_trader",
            "max_pages": 4,
            "dwell_time": 12.0,
            "urls": ["https://app.uniswap.org", "https://defillama.com"],
            "search_queries": ["defi lending pools 2026"],
            "custom_keywords": ["liquidity", "yield", "staking"]
        }
        self.campaign_mgr.save_campaign("defi_alpha_seeker", custom_data)
        
        loaded = self.campaign_mgr.get_campaign("defi_alpha_seeker")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["name"], "DeFi Alpha Seeker")
        self.assertEqual(loaded["dwell_time"], 12.0)

        # Convert to WarmupConfig
        cfg = self.campaign_mgr.to_warmup_config(loaded)
        self.assertEqual(cfg.max_pages, 4)
        self.assertEqual(cfg.category, "tech")

    def test_generate_harmonized_profile(self):
        # Windows Profile
        p_win = self.agent_engine.generate_harmonized_profile(
            name="Win_Trader", os_type="windows", engine="camoufox", country="DE"
        )
        self.assertEqual(p_win["os"], "windows")
        self.assertIn(p_win["hardware_concurrency"], [8, 12, 16])
        self.assertIn(p_win["device_memory"], [8, 16, 32])
        self.assertTrue(p_win["stealth"]["canvas_noise"])
        self.assertTrue(p_win["stealth"]["noise_seed"].startswith("seed_"))

        # Linux Profile (Memory <= 16 GB for Linux desktop harmony)
        p_linux = self.agent_engine.generate_harmonized_profile(
            name="Linux_Dev", os_type="linux", engine="camoufox", country="GB"
        )
        self.assertEqual(p_linux["os"], "linux")
        self.assertIn(p_linux["device_memory"], [8, 16])

    def test_create_profile_execution(self):
        p_data = self.agent_engine.generate_harmonized_profile(
            name="Auto_Agent_Profile", os_type="windows"
        )
        success, pid, msg = self.agent_engine.create_profile(p_data)
        self.assertTrue(success)
        self.assertNotEqual(pid, "")

        loaded = self.profile_mgr.load_profile(pid)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["name"], "Auto_Agent_Profile")

    def test_extract_action_blocks_parsing(self):
        sample_ai_text = """
        Hier ist Ihr harmonisiertes Profil für den deutschen Markt:

        ```action:create_profile
        {
            "name": "Amazon_Shopper_DE",
            "os": "windows",
            "engine": "camoufox",
            "country": "DE",
            "hardware_concurrency": 12,
            "device_memory": 16
        }
        ```

        Und hier ist die passende Warmup-Kampagne:

        ```action:save_campaign
        {
            "name": "ECommerce_Warmup_DE",
            "category": "ecommerce",
            "max_pages": 5,
            "dwell_time": 9.0
        }
        ```
        """
        actions = AIAgentActionEngine.extract_action_blocks(sample_ai_text)
        self.assertEqual(len(actions), 2)
        self.assertEqual(actions[0]["action"], "create_profile")
        self.assertEqual(actions[0]["data"]["name"], "Amazon_Shopper_DE")
        self.assertEqual(actions[1]["action"], "save_campaign")
        self.assertEqual(actions[1]["data"]["name"], "ECommerce_Warmup_DE")

    def test_create_batch_profiles_execution(self):
        batch = [
            self.agent_engine.generate_harmonized_profile(name=f"Batch_Prof_{i}", os_type="windows" if i % 2 == 0 else "mac")
            for i in range(10)
        ]
        success, ids, msg = self.agent_engine.create_batch_profiles(batch)
        self.assertTrue(success)
        self.assertEqual(len(ids), 10)

        for pid in ids:
            p = self.profile_mgr.load_profile(pid)
            self.assertIsNotNone(p)
            self.assertTrue(p["name"].startswith("Batch_Prof_"))

    def test_extract_batch_action_blocks(self):
        sample_batch_text = """
        Hier sind alle 10 generierten Profile:

        ```action:create_batch_profiles
        [
            {"name": "Prof_1", "os": "windows", "engine": "camoufox"},
            {"name": "Prof_2", "os": "mac", "engine": "camoufox"}
        ]
        ```
        """
        actions = AIAgentActionEngine.extract_action_blocks(sample_batch_text)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["action"], "create_batch_profiles")
        self.assertIsInstance(actions[0]["data"], list)
        self.assertEqual(len(actions[0]["data"]), 2)


if __name__ == "__main__":
    unittest.main()
