import unittest
import asyncio
from engine.browser_copilot_bridge import BrowserCopilotBridge


class TestBrowserCopilotBridge(unittest.IsolatedAsyncioTestCase):

    async def test_browser_copilot_bridge_sandbox_success(self):
        bridge = BrowserCopilotBridge.get_instance()
        
        # Test valid Python calculation and print
        script = """
x = 10 + 20
print(f"Computed sum: {x}")
return x
"""
        res = await bridge.execute_in_sandbox(script, timeout_sec=5.0)
        self.assertTrue(res["success"])
        self.assertIn("Computed sum: 30", res["output"])
        self.assertEqual(res["result"], "30")

    async def test_browser_copilot_bridge_sandbox_error(self):
        bridge = BrowserCopilotBridge.get_instance()
        
        # Test syntax / runtime error handling
        script = """
raise ValueError("Test error handling in sandbox")
"""
        res = await bridge.execute_in_sandbox(script, timeout_sec=5.0)
        self.assertFalse(res["success"])
        self.assertIn("ValueError", res["error"])

    async def test_browser_copilot_bridge_js_sandbox(self):
        bridge = BrowserCopilotBridge.get_instance()
        
        # 1. Test JS script without active page (graceful message, not a Python SyntaxError crash)
        js_script = "const nativeGetContext = HTMLCanvasElement.prototype.getContext;\nconsole.log(nativeGetContext);"
        res = await bridge.execute_in_sandbox(js_script, timeout_sec=5.0)
        self.assertFalse(res["success"])
        self.assertIn("No active browser tab found", res["error"])

        # 2. Test JS script with mock page supporting evaluate
        class MockPage:
            async def evaluate(self, code):
                return "webgl2_mock_context"
        
        from unittest.mock import patch
        with patch.object(bridge, "get_active_page_for_profile", return_value=MockPage()):
            res_mock = await bridge.execute_in_sandbox(js_script, profile_id="test-p1", timeout_sec=5.0)
            self.assertTrue(res_mock["success"])
            self.assertEqual(res_mock["result"], "webgl2_mock_context")


if __name__ == "__main__":
    unittest.main()
