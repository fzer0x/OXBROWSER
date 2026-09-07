import unittest
import config
from storage.profile_manager import ProfileManager


class TestNativeWebGL(unittest.TestCase):

    def test_detect_native_webgl_info(self):
        info = config.detect_native_webgl_info()
        self.assertIsInstance(info, dict)
        self.assertIn("vendor", info)
        self.assertIn("renderer", info)
        self.assertTrue(len(info["vendor"]) > 0)
        self.assertTrue(len(info["renderer"]) > 0)
        self.assertTrue(info.get("is_native"))

    def test_profile_creation_with_native_webgl(self):
        pm = ProfileManager()
        native_gpu = config.detect_native_webgl_info()
        pdata = pm.create_default_profile_data("Native WebGL Test Profile")
        pdata["stealth"]["webgl_vendor"] = native_gpu["vendor"]
        pdata["stealth"]["webgl_renderer"] = native_gpu["renderer"]
        
        prof = pm.create_profile(pdata)
        self.assertEqual(prof["stealth"]["webgl_vendor"], native_gpu["vendor"])
        self.assertEqual(prof["stealth"]["webgl_renderer"], native_gpu["renderer"])
        
        # Cleanup
        pm.delete_profile(prof["id"])


    def test_unspoofed_webgl_stealth_script(self):
        from engine.fingerprint import FingerprintGenerator
        pm = ProfileManager()
        pdata = pm.create_default_profile_data("Unspoofed WebGL Profile")
        pdata["stealth"]["webgl_spoofing"] = False
        pdata["stealth"]["webgl_mode"] = "real"
        
        script = FingerprintGenerator.generate_stealth_script(pdata, "UTC")
        self.assertIn("WebGL Spoofing Disabled (100% Real Native GPU Passthrough)", script)
        self.assertNotIn("WebGLRenderingContext.prototype.getParameter", script)


if __name__ == "__main__":
    unittest.main()
