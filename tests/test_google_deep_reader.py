import os
import sys
import unittest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

if "playwright" not in sys.modules:
    mock_pw = MagicMock()
    mock_pw_async = MagicMock()
    mock_pw.async_api = mock_pw_async
    sys.modules["playwright"] = mock_pw
    sys.modules["playwright.async_api"] = mock_pw_async

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.warmup.trajectory_planner import PERSONA_PROFILES
from engine.warmup.orchestrator import WarmupConfig, CookieWarmupRobot


class TestGoogleDeepReader(unittest.IsolatedAsyncioTestCase):

    def test_persona_profiles_contains_google_search(self):
        """Verify that google_search persona is registered in PERSONA_PROFILES."""
        self.assertIn("google_search", PERSONA_PROFILES)
        p = PERSONA_PROFILES["google_search"]
        self.assertEqual(p["name"], "Google Search & Top-5 Deep Reader")
        self.assertGreater(len(p["queries"]), 0)
        self.assertGreater(p["wpm_target"], 150)

    async def test_search_google_strictly_uses_google_and_no_duckduckgo(self):
        """Verify search_google_and_extract_top_results exclusively opens google.com."""
        launcher = MagicMock()
        robot = CookieWarmupRobot(launcher)
        robot.swarm = None
        robot.ai_manager = None
        page = MagicMock()
        page.url = "https://www.google.com"

        navigated_urls = []

        async def fake_navigate(p, url, timeout=20000):
            navigated_urls.append(url)
            return True

        async def fake_evaluate(p, script, *args):
            if "forbidden" in script:
                return [
                    {"href": "https://example.com/article1", "text": "Article 1"},
                    {"href": "https://example.org/article2", "text": "Article 2"},
                    {"href": "https://example.net/article3", "text": "Article 3"},
                    {"href": "https://tech-site.io/article4", "text": "Article 4"},
                    {"href": "https://news-portal.com/article5", "text": "Article 5"},
                ]
            if "querySelector" in script:
                return True
            return {}

        robot._navigate = fake_navigate
        robot._evaluate = fake_evaluate
        robot.dismiss_cookie_banners = AsyncMock()
        robot.human_scroll = AsyncMock()
        robot.scan_and_guard_honeypots = AsyncMock(return_value=MagicMock(is_clean=True))

        with patch("asyncio.sleep", AsyncMock()):
            results = await robot.search_google_and_extract_top_results(page, "quantum computing 2026", max_results=5)

        self.assertEqual(len(results), 5)
        self.assertEqual(results[0]["href"], "https://example.com/article1")

        # Verify ONLY google was navigated, NO duckduckgo or bing
        for url in navigated_urls:
            self.assertTrue("google.com" in url or "google.de" in url)
            self.assertNotIn("duckduckgo", url)
            self.assertNotIn("bing.com", url)

    async def test_google_search_only_pipeline_execution(self):
        """Verify run_warmup routes to Google Deep Reader pipeline when mode is google_search_only."""
        launcher = MagicMock()
        launcher.profile_manager = MagicMock()
        launcher.profile_manager.load_profile.return_value = {"id": "p1", "name": "Prof 1"}
        launcher.profile_manager.get_profile_path.return_value = "/tmp/fake_profile"
        launcher.launch_profile = AsyncMock(return_value=(True, "OK", MagicMock()))
        launcher.stop_profile = AsyncMock()

        robot = CookieWarmupRobot(launcher)
        robot.swarm = None
        robot.ai_manager = None
        cfg = WarmupConfig(
            persona="google_search",
            mode="google_search_only",
            max_pages=3,
            dwell_time=0.1
        )

        deep_read_visited = []

        async def mock_extract(p, q, max_results=5, notify_progress=None):
            return [
                {"href": "https://target-one.org/page", "text": "Target One"},
                {"href": "https://target-two.org/page", "text": "Target Two"},
                {"href": "https://target-three.org/page", "text": "Target Three"},
            ]

        async def mock_nav(p, url, timeout=20000):
            deep_read_visited.append(url)
            return True

        robot.search_google_and_extract_top_results = mock_extract
        robot._navigate = mock_nav
        robot._evaluate = AsyncMock(return_value={})
        robot.dismiss_cookie_banners = AsyncMock()
        robot.human_scroll = AsyncMock()
        robot.scan_and_guard_honeypots = AsyncMock(return_value=MagicMock(is_clean=True))

        with patch("asyncio.sleep", AsyncMock()):
            with patch("engine.warmup.trajectory_planner.SitePortalEngine.handle_portal_navigation", AsyncMock(return_value=True)):
                with patch("engine.cookie_manager.CookieManager.get_profile_metrics", return_value={"cookies": 10, "storage_items": 5}):
                    with patch("engine.trust_score_evaluator.ProfileTrustEvaluator.evaluate_profile_trust", return_value=(95.0, {})):
                        success = await robot.run_warmup("p1", config=cfg)

        self.assertTrue(success)
        self.assertIn("https://target-one.org/page", deep_read_visited)
        self.assertIn("https://target-two.org/page", deep_read_visited)
        self.assertIn("https://target-three.org/page", deep_read_visited)

    async def test_parallel_warmup_generates_distinct_queries_for_all_browsers(self):
        """Verify that 5 concurrent browser profile warmups generate 5 completely distinct search queries."""
        launcher = MagicMock()
        launcher.profile_manager = MagicMock()
        launcher.profile_manager.load_profile.side_effect = lambda pid: {"id": pid, "name": f"Profile_{pid}"}
        launcher.profile_manager.get_profile_path.return_value = "/tmp/fake_profile"
        launcher.launch_profile = AsyncMock(return_value=(True, "OK", MagicMock()))
        launcher.stop_profile = AsyncMock()

        robot = CookieWarmupRobot(launcher)
        robot.swarm = None
        robot.ai_manager = None
        cfg = WarmupConfig(
            persona="google_search",
            mode="google_search_only",
            max_pages=1,
            concurrency=5
        )

        performed_queries = []

        async def mock_extract(p, q, max_results=5, notify_progress=None):
            performed_queries.append(q)
            return [{"href": f"https://example.com/{q.replace(' ', '-')}", "text": q}]

        robot.search_google_and_extract_top_results = mock_extract
        robot._navigate = AsyncMock(return_value=True)
        robot._evaluate = AsyncMock(return_value={})
        robot.dismiss_cookie_banners = AsyncMock()
        robot.human_scroll = AsyncMock()
        robot.scan_and_guard_honeypots = AsyncMock(return_value=MagicMock(is_clean=True))

        pids = [f"prof_{i}" for i in range(5)]

        with patch("asyncio.sleep", AsyncMock()):
            with patch("engine.warmup.trajectory_planner.SitePortalEngine.handle_portal_navigation", AsyncMock(return_value=True)):
                with patch("engine.cookie_manager.CookieManager.get_profile_metrics", return_value={"cookies": 10, "storage_items": 5}):
                    with patch("engine.trust_score_evaluator.ProfileTrustEvaluator.evaluate_profile_trust", return_value=(95.0, {})):
                        res = await robot.run_warmup_batch(pids, config=cfg)

        self.assertEqual(len(performed_queries), 5)
        # Verify all 5 queries are completely distinct (no duplicates!)
        unique_queries = set(performed_queries)
        self.assertEqual(len(unique_queries), 5, f"Expected 5 distinct queries, got duplicates: {performed_queries}")


if __name__ == "__main__":
    unittest.main()

