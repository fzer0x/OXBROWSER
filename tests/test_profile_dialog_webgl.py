import unittest
from PyQt6.QtWidgets import QApplication
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from storage.profile_manager import ProfileManager
from ui.views.profile_dialog import ProfileDialog
import config

app = QApplication.instance() or QApplication(sys.argv)


class TestProfileDialogWebGL(unittest.TestCase):
    """Verifies that WebGL presets in ProfileDialog are preserved and correctly saved/loaded."""

    def setUp(self):
        self.pm = ProfileManager()
        self.dialog = ProfileDialog(self.pm)

    def test_default_webgl_preset_selection(self):
        # On new profile creation, webgl_combo should select a harmonized preset (index 2), not "nicht spoofen" (index 0)
        self.dialog._populate_webgl_presets("windows", select_default=True)
        self.assertEqual(self.dialog.webgl_combo.currentIndex(), 2)
        data = self.dialog.webgl_combo.currentData()
        self.assertIsNotNone(data)
        self.assertFalse(data.get("is_unspoofed", False))

    def test_sync_webgl_combo_selection(self):
        # Test syncing known preset
        self.dialog._populate_webgl_presets("windows")
        presets = config.get_webgl_presets_for_os("windows")
        if presets:
            target_preset = presets[0]
            self.dialog._sync_webgl_combo_selection(target_preset["vendor"], target_preset["renderer"], spoof_enabled=True)
            self.assertGreater(self.dialog.webgl_combo.currentIndex(), 0)
            cur_data = self.dialog.webgl_combo.currentData()
            self.assertEqual(cur_data["vendor"], target_preset["vendor"])

    def test_load_and_save_profile_preserves_webgl(self):
        test_prof = {
            "name": "Test WebGL Profile",
            "os": "windows",
            "stealth": {
                "webgl_spoofing": True,
                "webgl_mode": "spoof",
                "webgl_vendor": "Google Inc. (NVIDIA)",
                "webgl_renderer": "ANGLE (NVIDIA, GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)",
                "canvas_noise": True,
                "audio_noise": True,
                "webrtc_mode": "altered"
            }
        }
        self.dialog.profile_data = test_prof
        self.dialog._load_data()
        self.assertTrue(self.dialog.webgl_spoof_cb.isChecked())
        self.assertEqual(self.dialog.webgl_vendor_input.text(), "Google Inc. (NVIDIA)")
        self.assertIn("GeForce RTX 3060", self.dialog.webgl_renderer_input.text())
        # Ensure combo is NOT at index 0 ("nicht spoofen")
        self.assertNotEqual(self.dialog.webgl_combo.currentIndex(), 0)

        # Get saved data
        saved = self.dialog.get_profile_data()
        self.assertTrue(saved["stealth"]["webgl_spoofing"])
        self.assertEqual(saved["stealth"]["webgl_mode"], "spoof")
        self.assertEqual(saved["stealth"]["webgl_vendor"], "Google Inc. (NVIDIA)")
        self.assertIn("GeForce RTX 3060", saved["stealth"]["webgl_renderer"])

    def test_toggle_webgl_spoofing_persistence(self):
        """Verifies that activating or deactivating WebGL spoofing persists across save and load cycles."""
        test_prof = {
            "name": "Toggle Profile",
            "os": "windows",
            "stealth": {
                "webgl_spoofing": False,
                "webgl_mode": "real"
            }
        }
        self.dialog.profile_data = test_prof
        self.dialog._load_data()
        self.assertFalse(self.dialog.webgl_spoof_cb.isChecked())

        # Turn ON
        self.dialog.webgl_spoof_cb.setChecked(True)
        saved_on = self.dialog.get_profile_data()
        self.assertTrue(saved_on["stealth"]["webgl_spoofing"])
        self.assertEqual(saved_on["stealth"]["webgl_mode"], "spoof")

        # Reload the saved profile data
        self.dialog.profile_data = saved_on
        self.dialog._load_data()
        self.assertTrue(self.dialog.webgl_spoof_cb.isChecked())
        self.assertNotEqual(self.dialog.webgl_combo.currentIndex(), 0)


if __name__ == "__main__":
    unittest.main()
