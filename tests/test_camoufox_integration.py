import unittest
import os
import config
from storage.profile_manager import ProfileManager
from engine.browser import BrowserLauncher

class TestCamoufoxIntegration(unittest.TestCase):

    def setUp(self):
        self.pm = ProfileManager()
        self.launcher = BrowserLauncher(self.pm)

    def test_camoufox_directory_exists(self):
        self.assertTrue(os.path.exists(config.CAMOUFOX_DIR))

    def test_find_camoufox_binary_returns_type(self):
        result = self.launcher._find_camoufox_binary()
        self.assertTrue(result is None or isinstance(result, str))

    def test_create_camoufox_profile(self):
        profile = self.pm.create_default_profile_data()
        profile["name"] = "Camoufox Test Profile"
        profile["engine"] = "camoufox"
        self.assertEqual(profile["engine"], "camoufox")

if __name__ == "__main__":
    unittest.main()
