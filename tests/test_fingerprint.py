import unittest
from storage.profile_manager import ProfileManager
from engine.fingerprint import FingerprintGenerator

class TestFingerprintGenerator(unittest.TestCase):

    def setUp(self):
        self.pm = ProfileManager()

    def test_generate_stealth_script_default(self):
        profile = self.pm.create_default_profile_data("Test Profile")
        profile["stealth"]["webgl_mode"] = "spoof"
        script = FingerprintGenerator.generate_stealth_script(profile, "Europe/Berlin")
        self.assertIsInstance(script, str)
        self.assertTrue(len(script) > 5000)
        self.assertIn("nativeToStringMap", script)
        self.assertIn("UNMASKED_VENDOR_WEBGL", script)
        self.assertIn("Europe/Berlin", script)

    def test_mac_os_alignment(self):
        profile = self.pm.create_default_profile_data("Mac Test")
        profile["os"] = "mac"
        profile["stealth"]["webgl_mode"] = "spoof"
        profile["stealth"]["webgl_vendor"] = "Google Inc. (NVIDIA)"
        script = FingerprintGenerator.generate_stealth_script(profile, "UTC")
        self.assertIn("Google Inc. (Apple)", script)
        self.assertIn("ANGLE (Apple", script)

    def test_windows_os_alignment(self):
        profile = self.pm.create_default_profile_data("Win Test")
        profile["os"] = "windows"
        profile["stealth"]["webgl_mode"] = "spoof"
        profile["stealth"]["webgl_vendor"] = "Google Inc. (Intel)"
        profile["stealth"]["webgl_renderer"] = "Intel(R) Iris(R) Xe Graphics"
        script = FingerprintGenerator.generate_stealth_script(profile, "UTC")
        self.assertIn("Google Inc. (Intel)", script)
        self.assertIn("ANGLE (Intel", script)

    def test_permissions_battery_network_patches(self):
        profile = self.pm.create_default_profile_data("API Test")
        script = FingerprintGenerator.generate_stealth_script(profile, "UTC")
        self.assertIn("navigator.permissions.query", script)
        self.assertIn("getBattery", script)
        self.assertIn("effectiveType: '4g'", script)

    def test_webgpu_supported_patch(self):
        profile = self.pm.create_default_profile_data("WebGPU Test")
        profile["stealth"]["webgpu_supported"] = True
        script = FingerprintGenerator.generate_stealth_script(profile, "UTC")
        self.assertIn("requestAdapter", script)
        self.assertIn("bgra8unorm", script)

    def test_custom_patches_plugin(self):
        profile = self.pm.create_default_profile_data("Custom Plugin Test")
        profile["stealth"]["custom_patches"] = ["window.__soxbot_custom_flag = true;"]
        script = FingerprintGenerator.generate_stealth_script(profile, "UTC")
        self.assertIn("window.__soxbot_custom_flag = true;", script)

if __name__ == "__main__":
    unittest.main()
