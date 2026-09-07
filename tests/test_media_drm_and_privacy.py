import unittest
import os
import shutil
import tempfile
from storage.profile_manager import ProfileManager
from engine.fingerprint import FingerprintGenerator
from engine.spotify_bridge import SpotifyBridge

class TestMediaDrmAndPrivacy(unittest.TestCase):

    def test_eme_stealth_script_privacy_and_rejection(self):
        """Verify that when DRM is disabled, EME script provides standard W3C rejection layer for TikTok."""
        profile_privacy = {
            "id": "test_privacy_profile",
            "engine": "camoufox",
            "os": "windows",
            "behavior": {
                "drm_widevine": False
            },
            "stealth": {
                "canvas_noise": True
            }
        }
        
        script_privacy = FingerprintGenerator.generate_stealth_script(profile_privacy)
        self.assertIn("W3C Standard EME Privacy-First Rejection Layer", script_privacy)
        self.assertIn("Key system not supported", script_privacy)
        self.assertIn("NotSupportedError", script_privacy)

    def test_eme_stealth_script_drm_enabled(self):
        """Verify that when DRM is enabled, EME script provides full CDM & ClearKey compatibility layer for Spotify."""
        profile_drm = {
            "id": "test_drm_profile",
            "engine": "camoufox",
            "os": "windows",
            "behavior": {
                "drm_widevine": True
            },
            "stealth": {
                "canvas_noise": True
            }
        }
        
        script_drm = FingerprintGenerator.generate_stealth_script(profile_drm)
        self.assertTrue("Virtual CDM System" in script_drm or "ClearKey" in script_drm)
        self.assertIn("requestMediaKeySystemAccess", script_drm)

    def test_profile_manager_clear_drm_cache(self):
        """Verify ProfileManager properly wipes Widevine CDM files and EME database caches."""
        tmp_dir = tempfile.mkdtemp(prefix="sox_test_pm_")
        try:
            pm = ProfileManager(profiles_dir=tmp_dir)
            p_data = pm.create_default_profile_data(name="DRM Test Profile")
            p_id = p_data["id"]
            pm.create_profile(p_data)
            
            user_data = pm.get_user_data_dir(p_id)
            gmp_dir = os.path.join(user_data, "gmp-widevinecdm")
            spotify_storage = os.path.join(user_data, "storage", "default", "https+++open.spotify.com")
            
            os.makedirs(gmp_dir, exist_ok=True)
            os.makedirs(spotify_storage, exist_ok=True)
            
            with open(os.path.join(gmp_dir, "widevine.sig"), "w") as f:
                f.write("mock_sig")
            with open(os.path.join(spotify_storage, "data.sqlite"), "w") as f:
                f.write("mock_db")
                
            self.assertTrue(os.path.exists(gmp_dir))
            self.assertTrue(os.path.exists(spotify_storage))
            
            ok = pm.clear_profile_drm_cache(p_id)
            self.assertTrue(ok)
            self.assertFalse(os.path.exists(gmp_dir))
            self.assertFalse(os.path.exists(spotify_storage))
        finally:
            if os.path.exists(tmp_dir):
                shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_spotify_bridge_session_extraction(self):
        """Verify SpotifyBridge extracts sp_dc and session credentials accurately."""
        bridge = SpotifyBridge(profile_id="test_bridge_profile")
        
        mock_profile = {
            "cookies": [
                {"domain": ".spotify.com", "name": "sp_dc", "value": "AQD_TEST_TOKEN_12345"},
                {"domain": ".spotify.com", "name": "sp_key", "value": "KEY_UUID_67890"},
                {"domain": ".google.com", "name": "SID", "value": "GOOGLE_SID"}
            ]
        }
        
        loaded = bridge.load_cookies_from_profile(mock_profile)
        self.assertTrue(loaded)
        self.assertEqual(bridge.session_cookies.get("sp_dc"), "AQD_TEST_TOKEN_12345")
        self.assertEqual(bridge.session_cookies.get("sp_key"), "KEY_UUID_67890")
        self.assertNotIn("SID", bridge.session_cookies)

if __name__ == "__main__":
    unittest.main()
