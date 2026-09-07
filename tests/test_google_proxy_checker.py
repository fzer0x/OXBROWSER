import unittest
import asyncio
import os
from engine.google_proxy_checker import GoogleProxyChecker
from storage.proxy_manager import ProxyManager

class TestGoogleProxyChecker(unittest.TestCase):

    def test_generate_test_query(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        query = loop.run_until_complete(GoogleProxyChecker.generate_test_query())
        loop.close()
        self.assertIsInstance(query, str)
        self.assertGreater(len(query), 5)

    def test_build_camoufox_proxy_config(self):
        p_cfg = {
            "enabled": True,
            "type": "socks5",
            "host": "1.2.3.4",
            "port": 1080,
            "username": "user",
            "password": "pwd"
        }
        cfg = GoogleProxyChecker._build_camoufox_proxy_config(p_cfg)
        self.assertIsNotNone(cfg)
        self.assertEqual(cfg["server"], "socks5://1.2.3.4:1080")
        self.assertEqual(cfg["username"], "user")
        self.assertEqual(cfg["password"], "pwd")

    def test_proxy_manager_tagging(self):
        test_file = "/tmp/test_soxbot_proxies_unittest.json"
        if os.path.exists(test_file):
            os.remove(test_file)
        
        pm = ProxyManager(storage_file=test_file)
        proxy = pm.add_proxy({"host": "127.0.0.1", "port": 8080, "type": "http"})
        pid = proxy["id"]
        
        pm.add_tag_to_proxy(pid, "Google Proxy")
        updated = [p for p in pm.list_proxies() if p["id"] == pid][0]
        self.assertIn("Google Proxy", updated.get("tags", []))
        
        if os.path.exists(test_file):
            os.remove(test_file)

    def test_humanoid_session_profile(self):
        from engine.google_proxy_checker import HumanoidSessionProfile
        profile = HumanoidSessionProfile()
        self.assertIn(profile.profile_type, ["fast", "moderate", "deliberate"])
        delay = profile.get_char_delay('a', 's')
        self.assertGreater(delay, 0.0)
        self.assertLess(delay, 1.0)

if __name__ == "__main__":
    unittest.main()
