import unittest
from unittest.mock import MagicMock, AsyncMock, patch

from engine.warmup.orchestrator import WarmupConfig, CookieWarmupRobot


class TestWarmupNoGoogle(unittest.IsolatedAsyncioTestCase):

    def test_warmup_config_default_no_google(self):
        cfg = WarmupConfig()
        self.assertFalse(cfg.no_google)

        cfg_no_google = WarmupConfig(no_google=True)
        self.assertTrue(cfg_no_google.no_google)

    async def test_search_duckduckgo_and_extract_top_results(self):
        launcher = MagicMock()
        robot = CookieWarmupRobot(launcher)
        page = MagicMock()

        navigated_urls = []
        async def fake_navigate(p, url, timeout=20000):
            navigated_urls.append(url)
            return True

        async def fake_evaluate(p, script, *args):
            if "forbidden" in script and "data-testid='result-title-a'" in script:
                return [
                    {"href": "https://example.com/item1", "text": "Item 1"},
                    {"href": "https://duckduckgo.com/l/?uddg=https%3A%2F%2Fpython.org%2Fdocs", "text": "Python Docs"},
                    {"href": "https://wikipedia.org/wiki/DuckDuckGo", "text": "DDG Wiki"}
                ]
            return True

        robot._navigate = fake_navigate
        robot._evaluate = fake_evaluate
        robot.dismiss_cookie_banners = AsyncMock()
        robot.human_scroll = AsyncMock()
        robot.scan_and_guard_honeypots = AsyncMock(return_value=MagicMock(is_clean=True))

        results = await robot.search_duckduckgo_and_extract_top_results(page, "best keyboards")

        self.assertGreaterEqual(len(results), 1)
        # Ensure DuckDuckGo was navigated to
        self.assertTrue(any("duckduckgo.com" in u for u in navigated_urls))
        # Ensure Google was NEVER navigated to
        self.assertFalse(any("google." in u for u in navigated_urls))

    async def test_perform_search_navigation_routes_to_ddg_when_no_google(self):
        launcher = MagicMock()
        robot = CookieWarmupRobot(launcher)
        robot.config = WarmupConfig(no_google=True)
        page = MagicMock()

        robot.search_duckduckgo_and_extract_top_results = AsyncMock(return_value=[
            {"href": "https://tech-site.com/article", "text": "Tech Article"}
        ])
        robot.search_google_and_extract_top_results = AsyncMock()
        robot._navigate = AsyncMock(return_value=True)
        robot.dismiss_cookie_banners = AsyncMock()
        robot.human_scroll = AsyncMock()

        success = await robot.perform_search_navigation(page, "ai machine learning")

        self.assertTrue(success)
        robot.search_duckduckgo_and_extract_top_results.assert_called_once()
        robot.search_google_and_extract_top_results.assert_not_called()

    async def test_perform_search_navigation_routes_to_google_when_no_google_false(self):
        launcher = MagicMock()
        robot = CookieWarmupRobot(launcher)
        robot.config = WarmupConfig(no_google=False)
        page = MagicMock()

        robot.search_duckduckgo_and_extract_top_results = AsyncMock()
        robot.search_google_and_extract_top_results = AsyncMock(return_value=[
            {"href": "https://example.com/google-hit", "text": "Hit"}
        ])
        robot._navigate = AsyncMock(return_value=True)
        robot.dismiss_cookie_banners = AsyncMock()
        robot.human_scroll = AsyncMock()

        success = await robot.perform_search_navigation(page, "ai machine learning")

        self.assertTrue(success)
        robot.search_google_and_extract_top_results.assert_called_once()
        robot.search_duckduckgo_and_extract_top_results.assert_not_called()

    def test_warmup_dialog_no_google_checkbox(self):
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication([])

        from ui.views.warmup_dialog import WarmupDialog
        dialog = WarmupDialog(None, ["test_profile"], MagicMock())

        self.assertFalse(dialog.chk_no_google.isChecked())
        self.assertIn("Google", dialog.chk_organic_search.text())

        # Toggle to True
        dialog.chk_no_google.setChecked(True)
        self.assertTrue(dialog.chk_no_google.isChecked())
        self.assertIn("DuckDuckGo", dialog.chk_organic_search.text())
        self.assertNotIn("Google", dialog.chk_organic_search.text())


if __name__ == "__main__":
    unittest.main()
