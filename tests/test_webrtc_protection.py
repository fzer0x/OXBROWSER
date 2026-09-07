import unittest
from storage.profile_manager import ProfileManager
from engine.fingerprint import FingerprintGenerator
from engine.browser import BrowserLauncher


class TestWebRTCProtection(unittest.TestCase):

    def setUp(self):
        self.pm = ProfileManager()
        self.launcher = BrowserLauncher(self.pm)

    def test_default_webrtc_mode_is_altered(self):
        profile = self.pm.create_default_profile_data("WebRTC Test")
        self.assertEqual(profile.get("stealth", {}).get("webrtc_mode"), "altered")

    def test_legacy_webrtc_normalization(self):
        # Legacy: top-level webrtc boolean True
        p1 = {"name": "Test1", "webrtc": True, "stealth": {}}
        self.pm._normalize_stealth_config(p1)
        self.assertEqual(p1["stealth"]["webrtc_mode"], "altered")
        self.assertNotIn("webrtc", p1)

        # Legacy: top-level webrtc boolean False
        p2 = {"name": "Test2", "webrtc": False, "stealth": {}}
        self.pm._normalize_stealth_config(p2)
        self.assertEqual(p2["stealth"]["webrtc_mode"], "disabled")

        # Legacy: stealth webrtc_mode "spoofed" or "proxy"
        p3 = {"name": "Test3", "stealth": {"webrtc_mode": "spoofed"}}
        self.pm._normalize_stealth_config(p3)
        self.assertEqual(p3["stealth"]["webrtc_mode"], "altered")

        p4 = {"name": "Test4", "stealth": {"webrtc_mode": "proxy"}}
        self.pm._normalize_stealth_config(p4)
        self.assertEqual(p4["stealth"]["webrtc_mode"], "altered")

        # Legacy: stealth webrtc_mode "raw" or "leak"
        p5 = {"name": "Test5", "stealth": {"webrtc_mode": "raw"}}
        self.pm._normalize_stealth_config(p5)
        self.assertEqual(p5["stealth"]["webrtc_mode"], "real")

        # Legacy: stealth webrtc_mode "block" or "off"
        p6 = {"name": "Test6", "stealth": {"webrtc_mode": "block"}}
        self.pm._normalize_stealth_config(p6)
        self.assertEqual(p6["stealth"]["webrtc_mode"], "disabled")

    def test_harmonize_invalid_webrtc_mode(self):
        p = self.pm.create_default_profile_data("Harmonize Test")
        p["stealth"]["webrtc_mode"] = "invalid_mode_xyz"
        p_harm, fixes = self.pm.harmonize_profile_tensor(p)
        self.assertEqual(p_harm["stealth"]["webrtc_mode"], "altered")
        self.assertTrue(any("WebRTC" in f for f in fixes))

    def test_stealth_js_webrtc_altered_patch(self):
        profile = self.pm.create_default_profile_data("JS Altered Test")
        profile["stealth"]["webrtc_mode"] = "altered"
        profile["proxy"] = {"enabled": True, "host": "198.51.100.25", "port": 8080}
        profile["proxy_info"] = {"ip": "198.51.100.25"}
        script = FingerprintGenerator.generate_stealth_script(profile, "UTC")
        self.assertIn("sanitizeSDP", script)
        self.assertIn("iceTransportPolicy = 'relay'", script)
        self.assertIn("onicecandidate", script)
        self.assertIn("createAnswer", script)
        self.assertIn("addEventListener", script)
        self.assertIn("getStats", script)
        self.assertIn("198.51.100.25", script)

    def test_stealth_js_webrtc_disabled_patch(self):
        profile = self.pm.create_default_profile_data("JS Disabled Test")
        profile["stealth"]["webrtc_mode"] = "disabled"
        script = FingerprintGenerator.generate_stealth_script(profile, "UTC")
        self.assertIn("delete win.RTCPeerConnection", script)
        self.assertIn("getUserMedia", script)

    def test_ensure_chromium_webrtc_preferences(self):
        import tempfile
        import json
        import os
        with tempfile.TemporaryDirectory() as tmpdir:
            BrowserLauncher._ensure_chromium_webrtc_preferences(tmpdir, "altered")
            pref_file = os.path.join(tmpdir, "Default", "Preferences")
            self.assertTrue(os.path.exists(pref_file))
            with open(pref_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data.get("webrtc", {}).get("ip_handling_policy"), "disable_non_proxied_udp")
            self.assertFalse(data.get("webrtc", {}).get("multiple_routes_enabled"))


if __name__ == "__main__":
    unittest.main()
