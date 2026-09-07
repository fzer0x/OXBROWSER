import unittest
import os
import sys
import tempfile
import shutil
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication
from storage.profile_manager import ProfileManager
from storage.proxy_manager import ProxyManager
from ui.views.profile_dialog import ProfileDialog

app = QApplication.instance() or QApplication(sys.argv)


class TestProfileDialogProxyPool(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="ox_test_profiles_")
        self.profiles_dir = os.path.join(self.test_dir, "profiles")
        self.proxies_file = os.path.join(self.test_dir, "proxies.json")
        os.makedirs(self.profiles_dir, exist_ok=True)

        # Create dummy proxies in proxy manager
        self.dummy_proxies = [
            {
                "id": "proxy-1",
                "name": "Proxy 1.1.1.1",
                "type": "http",
                "host": "1.1.1.1",
                "port": 8080,
                "username": "user1",
                "password": "pass1",
                "status": "✓ Active",
                "latency_ms": 120.0,
                "country": "Germany"
            },
            {
                "id": "proxy-2",
                "name": "Proxy 2.2.2.2",
                "type": "socks5",
                "host": "2.2.2.2",
                "port": 1080,
                "username": "user2",
                "password": "pass2",
                "status": "✓ Active",
                "latency_ms": 150.0,
                "country": "France"
            },
            {
                "id": "proxy-3",
                "name": "Proxy 3.3.3.3",
                "type": "http",
                "host": "3.3.3.3",
                "port": 3128,
                "username": "",
                "password": "",
                "status": "Untested",
                "latency_ms": -1,
                "country": "USA"
            }
        ]
        with open(self.proxies_file, "w", encoding="utf-8") as f:
            json.dump(self.dummy_proxies, f)

        self.pm = ProfileManager(profiles_dir=self.profiles_dir)
        self.proxy_mgr = ProxyManager(storage_file=self.proxies_file)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_new_profile_auto_assigns_unused_proxy(self):
        """When creating a new profile, an unused proxy from Proxy Pool is auto-assigned by default."""
        dialog = ProfileDialog(self.pm, proxy_manager=self.proxy_mgr)
        
        # Proxy connection should be checked by default
        self.assertTrue(dialog.proxy_enable_cb.isChecked())

        # Combo should select index 0 (Auto item)
        self.assertEqual(dialog.proxy_pool_combo.currentIndex(), 0)
        auto_data = dialog.proxy_pool_combo.currentData()
        self.assertIsNotNone(auto_data)
        self.assertEqual(auto_data["mode"], "auto_unused")
        self.assertEqual(auto_data["proxy"]["id"], "proxy-1")

        # Inputs should match proxy-1
        self.assertEqual(dialog.proxy_host_input.text(), "1.1.1.1")
        self.assertEqual(dialog.proxy_port_spin.value(), 8080)
        self.assertEqual(dialog.proxy_type_combo.currentText(), "http")
        self.assertEqual(dialog.proxy_user_input.text(), "user1")
        self.assertEqual(dialog.proxy_pass_input.text(), "pass1")
        self.assertEqual(dialog._selected_proxy_id, "proxy-1")

        # Proxy config from UI should include proxy_id
        cfg = dialog._get_proxy_config_from_ui()
        self.assertTrue(cfg["enabled"])
        self.assertEqual(cfg["host"], "1.1.1.1")
        self.assertEqual(cfg["proxy_id"], "proxy-1")

    def test_used_proxy_detection_and_next_assignment(self):
        """Proxies used by other profiles are marked as used and auto-assign chooses next unused."""
        # Create an existing profile that uses proxy-1
        p1 = self.pm.create_default_profile_data(name="Profile One")
        p1["proxy"] = {
            "enabled": True,
            "type": "http",
            "host": "1.1.1.1",
            "port": 8080,
            "username": "user1",
            "password": "pass1",
            "proxy_id": "proxy-1"
        }
        self.pm.create_profile(p1)

        # Now create a new profile dialog
        dialog = ProfileDialog(self.pm, proxy_manager=self.proxy_mgr)

        # proxy-1 is used, so auto-assignment should pick proxy-2
        self.assertTrue(dialog.proxy_enable_cb.isChecked())
        self.assertEqual(dialog.proxy_host_input.text(), "2.2.2.2")
        self.assertEqual(dialog.proxy_port_spin.value(), 1080)
        self.assertEqual(dialog.proxy_type_combo.currentText(), "socks5")
        self.assertEqual(dialog._selected_proxy_id, "proxy-2")

        # Check dropdown items: proxy-1 item should be marked "In Use: Profile One"
        found_used = False
        found_avail = False
        for i in range(dialog.proxy_pool_combo.count()):
            txt = dialog.proxy_pool_combo.itemText(i)
            if "1.1.1.1" in txt and "In Use: Profile One" in txt:
                found_used = True
            if "2.2.2.2" in txt and "Available" in txt:
                found_avail = True
        self.assertTrue(found_used)
        self.assertTrue(found_avail)

    def test_manual_dropdown_selection(self):
        """User can select any specific proxy from the dropdown and inputs update."""
        dialog = ProfileDialog(self.pm, proxy_manager=self.proxy_mgr)
        
        # Switch dropdown to proxy-3
        target_idx = -1
        for i in range(dialog.proxy_pool_combo.count()):
            d = dialog.proxy_pool_combo.itemData(i)
            if d and d.get("mode") == "specific" and d.get("proxy", {}).get("id") == "proxy-3":
                target_idx = i
                break

        self.assertGreater(target_idx, 0)
        dialog.proxy_pool_combo.setCurrentIndex(target_idx)

        self.assertEqual(dialog.proxy_host_input.text(), "3.3.3.3")
        self.assertEqual(dialog.proxy_port_spin.value(), 3128)
        self.assertEqual(dialog._selected_proxy_id, "proxy-3")

    def test_manual_input_edits_switch_combo_to_manual(self):
        """Editing host/port text fields switches dropdown to Custom/Manual."""
        dialog = ProfileDialog(self.pm, proxy_manager=self.proxy_mgr)
        self.assertEqual(dialog.proxy_pool_combo.currentIndex(), 0)

        # Manually change host
        dialog.proxy_host_input.setText("99.99.99.99")

        cur_data = dialog.proxy_pool_combo.currentData()
        self.assertEqual(cur_data.get("mode"), "manual")
        self.assertIsNone(dialog._selected_proxy_id)

    def test_no_proxy_selection(self):
        """Selecting 'No Proxy' unchecks proxy_enable_cb."""
        dialog = ProfileDialog(self.pm, proxy_manager=self.proxy_mgr)
        self.assertTrue(dialog.proxy_enable_cb.isChecked())

        # Select 'none' mode
        for i in range(dialog.proxy_pool_combo.count()):
            d = dialog.proxy_pool_combo.itemData(i)
            if d and d.get("mode") == "none":
                dialog.proxy_pool_combo.setCurrentIndex(i)
                break

        self.assertFalse(dialog.proxy_enable_cb.isChecked())


if __name__ == "__main__":
    unittest.main()
