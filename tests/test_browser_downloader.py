"""
Unit and integration tests for BrowserDownloader and BrowserDownloadDialog.
"""

import sys
import unittest
from PyQt6.QtWidgets import QApplication

from engine.browser_downloader import BrowserDownloader, CancellationToken


class TestBrowserDownloader(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def test_cancellation_token(self):
        token = CancellationToken()
        self.assertFalse(token.is_cancelled)
        token.cancel()
        self.assertTrue(token.is_cancelled)

    def test_is_engine_installed_camoufox(self):
        is_ready, msg = BrowserDownloader.is_engine_installed("camoufox")
        self.assertIsInstance(is_ready, bool)
        self.assertIsInstance(msg, str)
        self.assertTrue(len(msg) > 0)

    def test_is_engine_installed_playwright(self):
        is_ready, msg = BrowserDownloader.is_engine_installed("playwright")
        self.assertIsInstance(is_ready, bool)
        self.assertIsInstance(msg, str)

    def test_is_engine_installed_other(self):
        is_ready, msg = BrowserDownloader.is_engine_installed("unknown_engine")
        self.assertTrue(is_ready)

    def test_dialog_instantiation(self):
        from ui.views.browser_download_dialog import BrowserDownloadDialog
        dlg = BrowserDownloadDialog(engine_type="camoufox")
        self.assertEqual(dlg.engine_type, "camoufox")
        self.assertIsNotNone(dlg.progress_bar)
        self.assertIsNotNone(dlg.lbl_size)
        self.assertIsNotNone(dlg.lbl_speed)
        self.assertIsNotNone(dlg.lbl_status)
        # Clean up worker thread
        if dlg.worker and dlg.worker.isRunning():
            dlg.cancel_token.cancel()
            dlg.worker.wait(1000)
        dlg.close()


if __name__ == "__main__":
    unittest.main()
