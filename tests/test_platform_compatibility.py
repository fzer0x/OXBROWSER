"""
test_platform_compatibility.py - Comprehensive Unit & Regression Tests for Windows & Cross-Platform Compatibility.
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

import config
from engine.platform_helper import PlatformHelper, CREATE_NO_WINDOW
from storage.profile_manager import ProfileManager
from engine.sandbox.ephemeral_storage import EphemeralStorageManager
from engine.cdp_patcher import ChromiumBinaryPatcher


class TestPlatformCompatibility(unittest.TestCase):

    def test_platform_helper_detection(self):
        """Tests that PlatformHelper accurately identifies the active host OS."""
        plat = PlatformHelper.get_current_platform()
        self.assertIn(plat, ["windows", "linux", "mac"])
        
        display_name = PlatformHelper.get_platform_display_name()
        self.assertIsInstance(display_name, str)
        self.assertTrue(len(display_name) > 0)

        if sys.platform == "win32":
            self.assertTrue(PlatformHelper.is_windows())
            self.assertFalse(PlatformHelper.is_linux())
            self.assertFalse(PlatformHelper.is_mac())
            self.assertEqual(PlatformHelper.get_subprocess_creation_flags(), 0x08000000)
        else:
            self.assertEqual(PlatformHelper.get_subprocess_creation_flags(), 0)

    def test_timezone_resolution(self):
        """Tests cross-platform timezone resolution."""
        tz = PlatformHelper.get_system_timezone()
        self.assertIsInstance(tz, str)
        self.assertTrue(len(tz) > 0)

        # Test Windows mapping specifically
        mapped = PlatformHelper._map_windows_tz_to_iana("W. Europe Standard Time")
        self.assertEqual(mapped, "Europe/Berlin")

        mapped_us = PlatformHelper._map_windows_tz_to_iana("Eastern Standard Time")
        self.assertEqual(mapped_us, "America/New_York")

    @patch("sys.platform", "win32")
    def test_windows_simulation_binary_paths(self):
        """Tests Windows binary discovery and resolution logic when running under Windows simulation."""
        self.assertTrue(PlatformHelper.is_windows())
        self.assertEqual(PlatformHelper.get_subprocess_creation_flags(), 0x08000000)

        # Test Stockfish search on Windows returns valid fallback or None
        sf = PlatformHelper.find_stockfish_binary(config.BASE_DIR)
        # Should not raise exception
        self.assertTrue(sf is None or isinstance(sf, str))

        # Test Ollama search on Windows
        ollama_bin = PlatformHelper.find_ollama_binary(os.path.join(config.BASE_DIR, "models"))
        self.assertTrue(isinstance(ollama_bin, str))
        self.assertTrue(ollama_bin.endswith("ollama.exe") or "ollama" in ollama_bin)

    def test_ephemeral_storage_cross_platform(self):
        """Tests ephemeral storage mounting and teardown across platforms."""
        self.assertTrue(EphemeralStorageManager.is_tmpfs_supported())
        
        profile_id = "test-ephemeral-compat-uuid"
        shm_path = EphemeralStorageManager.get_shm_path(profile_id)
        self.assertIsInstance(shm_path, str)

        # Mount test
        test_dir = os.path.join(config.BASE_DIR, "scratch", "test_ephemeral")
        ok, msg = EphemeralStorageManager.mount_ramdisk(profile_id, test_dir, size_mb=64)
        self.assertTrue(ok)
        self.assertTrue(os.path.exists(test_dir))

        # Teardown test
        cleaned = EphemeralStorageManager.wipe_and_unmount(profile_id, test_dir)
        self.assertTrue(cleaned)
        self.assertFalse(os.path.exists(test_dir))

    def test_config_host_metadata(self):
        """Verifies that config module exports platform metadata."""
        self.assertIn(config.HOST_OS, ["windows", "linux", "mac"])
        self.assertIsInstance(config.IS_WINDOWS, bool)
        self.assertIsInstance(config.IS_LINUX, bool)
        self.assertIsInstance(config.IS_MAC, bool)
        self.assertIsInstance(config.HOST_OS_NAME, str)

    def test_default_profile_creation_matching_os(self):
        """Verifies that ProfileManager creates profiles cleanly for target OS."""
        pm = ProfileManager()
        win_prof = pm.create_default_profile_data("Win Test", os_type="windows")
        self.assertEqual(win_prof["os"], "windows")
        self.assertIn("Windows NT 10.0", win_prof["user_agent"])

        lin_prof = pm.create_default_profile_data("Lin Test", os_type="linux")
        self.assertEqual(lin_prof["os"], "linux")
        self.assertIn("Linux", lin_prof["user_agent"])

    def test_native_webgl_detection(self):
        """Tests that native WebGL info returns valid vendor and renderer on all OSes."""
        info = config.detect_native_webgl_info()
        self.assertIn("vendor", info)
        self.assertIn("renderer", info)
        self.assertTrue(len(info["vendor"]) > 0)
        self.assertTrue(len(info["renderer"]) > 0)

    def test_open_folder_and_url_helpers(self):
        """Tests that cross-platform file and url opening methods execute without errors."""
        scratch_dir = os.path.join(config.BASE_DIR, "scratch")
        with patch("subprocess.Popen") as mock_popen, patch("webbrowser.open", return_value=True):
            res_folder = PlatformHelper.open_folder_or_file(scratch_dir)
            self.assertIsInstance(res_folder, bool)

            res_url = PlatformHelper.open_url("https://example.com")
            self.assertIsInstance(res_url, bool)

    def test_camoufox_and_chromium_discovery_on_windows_mock(self):
        """Tests Camoufox and Chromium resolution with Windows simulation."""
        with patch.object(PlatformHelper, "is_windows", return_value=True):
            camoufox_bin = PlatformHelper.find_camoufox_binary(config.BASE_DIR)
            self.assertTrue(camoufox_bin is None or isinstance(camoufox_bin, str))

            chrome_bin = PlatformHelper.find_chromium_binary(config.BASE_DIR)
            self.assertTrue(chrome_bin is None or isinstance(chrome_bin, str))

    def test_cdp_patcher_windows_exe_matching(self):
        """Tests that CDP patcher scans and matches .exe binaries on Windows."""
        scratch_dir = os.path.join(config.BASE_DIR, "scratch", "test_cdp_patch")
        os.makedirs(scratch_dir, exist_ok=True)
        fake_exe = os.path.join(scratch_dir, "chromedriver.exe")
        with open(fake_exe, "wb") as f:
            f.write(b"MZ\x90\x00" + b"cdc_adoQpoasnfa76pfcZLmcfl_Array" + b"\x00" * 10)
        
        try:
            results = ChromiumBinaryPatcher.scan_and_patch_workspace(scratch_dir)
            self.assertTrue(len(results) > 0)
            self.assertEqual(results[0][0], fake_exe)
            self.assertGreater(results[0][1], 0)
        finally:
            import shutil
            shutil.rmtree(scratch_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
