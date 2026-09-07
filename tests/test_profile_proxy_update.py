import unittest
import sys
import os
import shutil
import tempfile
from unittest.mock import MagicMock

from PyQt6.QtWidgets import QApplication

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from storage.profile_manager import ProfileManager
from storage.proxy_manager import ProxyManager
from ui.views.profiles_view import ProfilesView
from ui.views.proxies_view import ProxiesView
from ui.views.profile_dialog import ProfileDialog

app = QApplication.instance() or QApplication(sys.argv)


class TestProfileProxyUpdate(unittest.TestCase):
    """Verifies that subsequent proxy connection to a profile immediately updates the profile list without restarting."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.profiles_dir = os.path.join(self.test_dir, "profiles")
        os.makedirs(self.profiles_dir, exist_ok=True)
        self.proxies_file = os.path.join(self.test_dir, "proxies.json")
        self.pm = ProfileManager(profiles_dir=self.profiles_dir)
        self.proxy_mgr = ProxyManager(storage_file=self.proxies_file)
        self.mock_launcher = MagicMock()
        self.mock_launcher.profile_manager = self.pm

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_inplace_proxy_update_in_profiles_view(self):
        # 1. Create a profile without proxy
        prof_data = self.pm.create_profile({"name": "Test Profile InPlace"})
        pid = prof_data["id"]

        view = ProfilesView(self.pm, self.mock_launcher, proxy_manager=self.proxy_mgr)
        view.reload_profiles(force=True)

        self.assertEqual(view.table.rowCount(), 1)
        # Column 6 is Proxy / Location
        item_before = view.table.item(0, 6)
        self.assertIsNotNone(item_before)
        assert item_before is not None
        col6_before = item_before.text()
        self.assertIn("Direct (No Proxy)", col6_before)

        # 2. Nachträglich / subsequently connect proxy to profile on disk
        updated_prof = self.pm.load_profile(pid)
        self.assertIsNotNone(updated_prof)
        assert updated_prof is not None
        updated_prof["proxy"] = {
            "enabled": True,
            "type": "http",
            "host": "198.51.100.55",
            "port": 8080,
            "username": "",
            "password": ""
        }
        updated_prof["proxy_info"] = {
            "ip": "198.51.100.55",
            "country_code": "DE",
            "country": "Germany",
            "city": "Frankfurt"
        }
        self.pm.save_profile(updated_prof)

        # 3. Reload profiles without restarting (as timer or event does)
        self.assertTrue(view._can_update_in_place(self.pm.list_profiles()))
        view.reload_profiles()

        item_after = view.table.item(0, 6)
        self.assertIsNotNone(item_after)
        assert item_after is not None
        col6_after = item_after.text()
        self.assertNotIn("Direct (No Proxy)", col6_after)
        self.assertIn("HTTP", col6_after)
        self.assertIn("198.51.100.55", col6_after)
        self.assertIn("[DE]", col6_after)
        self.assertIn("🟢", col6_after)

    def test_proxies_view_assign_to_profile(self):
        # Create a profile
        prof_data = self.pm.create_profile({"name": "Browser Profile 1"})
        pid = prof_data["id"]

        # Create a proxy in pool
        p_item = self.proxy_mgr.add_proxy({
            "host": "203.0.113.10",
            "port": 3128,
            "type": "socks5",
            "country": "US",
            "city": "New York"
        })

        profiles_view = ProfilesView(self.pm, self.mock_launcher, proxy_manager=self.proxy_mgr)
        proxies_view = ProxiesView(self.proxy_mgr, profile_manager=self.pm)

        # Connect signal
        proxies_view.proxy_assigned.connect(lambda: profiles_view.reload_profiles(force=True))

        # Check initial profile view
        profiles_view.reload_profiles(force=True)
        item_init = profiles_view.table.item(0, 6)
        self.assertIsNotNone(item_init)
        assert item_init is not None
        self.assertIn("Direct (No Proxy)", item_init.text())

        # Simulate assigning proxy directly
        pdata = self.pm.load_profile(pid)
        self.assertIsNotNone(pdata)
        assert pdata is not None
        raw_port = p_item.get("port")
        port_int = int(raw_port) if raw_port is not None else 8080
        pdata["proxy"] = {
            "enabled": True,
            "type": p_item.get("type", "socks5"),
            "host": p_item.get("host"),
            "port": port_int,
            "username": "",
            "password": ""
        }
        pdata["proxy_info"] = {
            "ip": p_item.get("host"),
            "country_code": p_item.get("country"),
            "city": p_item.get("city")
        }
        self.pm.save_profile(pdata)
        proxies_view.proxy_assigned.emit()

        # Check that profiles view updated immediately
        col6_item = profiles_view.table.item(0, 6)
        self.assertIsNotNone(col6_item)
        assert col6_item is not None
        col6_text = col6_item.text()
        self.assertIn("SOCKS5", col6_text)
        self.assertIn("203.0.113.10", col6_text)
        self.assertIn("[US]", col6_text)
        self.assertIn("🟢", col6_text)

    def test_profile_dialog_proxy_info_sync(self):
        prof_data = self.pm.create_profile({"name": "Dialog Profile"})
        dlg = ProfileDialog(self.pm, profile_data=prof_data, launcher=self.mock_launcher, proxy_manager=self.proxy_mgr)

        dlg.proxy_enable_cb.setChecked(True)
        dlg.proxy_host_input.setText("192.0.2.1")
        dlg.proxy_port_spin.setValue(9050)
        dlg.proxy_type_combo.setCurrentText("socks5")

        result = dlg.get_profile_data()
        self.assertTrue(result["proxy"]["enabled"])
        self.assertEqual(result["proxy"]["host"], "192.0.2.1")
        self.assertEqual(result["proxy_info"]["ip"], "192.0.2.1")

        # Now disable proxy
        dlg.proxy_enable_cb.setChecked(False)
        result_disabled = dlg.get_profile_data()
        self.assertFalse(result_disabled["proxy"]["enabled"])
        self.assertEqual(result_disabled["proxy_info"], {})


if __name__ == "__main__":
    unittest.main()
