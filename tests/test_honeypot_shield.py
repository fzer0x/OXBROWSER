import asyncio
import unittest
from engine.honeypot_detector import HoneypotDetector, HoneypotScanResult
from engine.warmup.orchestrator import WarmupConfig, CookieWarmupRobot
from engine.google_proxy_checker import GoogleProxyChecker
from engine.ai_model_manager import AIModelManager


class TestHoneypotShield(unittest.TestCase):
    """Unit and integration test suite for AI Honeypot & Click-Trap Shield."""

    def test_honeypot_scan_result_filtering(self):
        result = HoneypotScanResult(
            is_clean=False,
            total_scanned=20,
            traps_count=2,
            blacklisted_hrefs={"https://example.com/hidden-trap", "https://example.com/honeypot"},
            blacklisted_selectors=["#trap-btn", ".invisible-link"],
            blacklisted_rects=[{"x": 100.0, "y": 200.0, "width": 50.0, "height": 30.0}]
        )

        self.assertFalse(result.is_safe_url("https://example.com/hidden-trap"))
        self.assertFalse(result.is_safe_url("https://example.com/honeypot"))
        self.assertTrue(result.is_safe_url("https://example.com/legitimate-article"))

        # Test safe element checks
        self.assertFalse(result.is_safe_element(selector="#trap-btn"))
        self.assertFalse(result.is_safe_element(element_rect={"x": 110.0, "y": 210.0}))
        self.assertTrue(result.is_safe_element(selector="#safe-btn", element_rect={"x": 500.0, "y": 500.0}))

        # Test link filtering
        raw_candidates = [
            {"href": "https://example.com/hidden-trap", "text": "Trap 1"},
            {"href": "https://example.com/legitimate-news", "text": "Real News", "selector": ".news-link"},
            {"href": "https://example.com/honeypot", "text": "Trap 2"},
            {"href": "https://example.com/blog-post", "text": "Real Blog", "rect": {"x": 500, "y": 500, "width": 100, "height": 20}}
        ]

        safe_links = result.filter_safe_links(raw_candidates)
        self.assertEqual(len(safe_links), 2)
        self.assertEqual(safe_links[0]["href"], "https://example.com/legitimate-news")
        self.assertEqual(safe_links[1]["href"], "https://example.com/blog-post")

    def test_warmup_config_defaults(self):
        cfg = WarmupConfig()
        self.assertTrue(hasattr(cfg, "enable_honeypot_shield"))
        self.assertTrue(cfg.enable_honeypot_shield)
        self.assertEqual(cfg.honeypot_model, "auto")

    def test_ai_model_manager_honeypot_eval(self):
        async def _test():
            ai_mgr = AIModelManager.get_instance()
            self.assertTrue(hasattr(ai_mgr, "evaluate_honeypot_elements"))
            
            # Pass sample candidate with mock
            elements = [
                {"tag": "a", "href": "https://example.com/trap", "text": "", "id": "honey_link", "rect": {"x": -9999, "y": 0, "width": 0, "height": 0}}
            ]
            # Since live LLM might not be running in headless test, test method handles gracefully
            res = await ai_mgr.evaluate_honeypot_elements(elements, "https://example.com", "Test Page")
            self.assertIsInstance(res, list)

        asyncio.run(_test())

    def test_google_proxy_checker_signature(self):
        import inspect
        sig = inspect.signature(GoogleProxyChecker.check_proxy_with_google)
        self.assertIn("enable_honeypot_shield", sig.parameters)
        self.assertTrue(sig.parameters["enable_honeypot_shield"].default)

        batch_sig = inspect.signature(GoogleProxyChecker.check_proxies_batch)
        self.assertIn("enable_honeypot_shield", batch_sig.parameters)
        self.assertTrue(batch_sig.parameters["enable_honeypot_shield"].default)


if __name__ == "__main__":
    unittest.main()
