import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import io
from PIL import Image
from engine.ai_captcha_solver import AICaptchaSolver


class TestNormalCaptchaSolver(unittest.IsolatedAsyncioTestCase):
    """
    Comprehensive Unit Tests for Normal Captcha (Image-to-Text) solving and routing.
    """

    async def test_ddddocr_instant_classification(self):
        """Validates that ddddocr engine classifications operate reliably."""
        try:
            import ddddocr
            ocr = ddddocr.DdddOcr(show_ad=False)
            
            # Create a valid test image with PIL
            img = Image.new('RGB', (80, 30), color='white')
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            raw_png = buf.getvalue()
            
            res = ocr.classification(raw_png)
            self.assertIsInstance(res, str)
        except Exception as e:
            self.fail(f"ddddocr failed to run classification: {e}")

    async def test_detect_normal_captcha_returns_bool(self):
        """Verifies _detect_normal_captcha evaluates page and returns boolean."""
        mock_page = AsyncMock()
        mock_page.evaluate.return_value = True
        
        detected = await AICaptchaSolver._detect_normal_captcha(mock_page)
        self.assertTrue(detected)
        self.assertTrue(mock_page.evaluate.called)

    async def test_solve_normal_captcha_flow(self):
        """Validates autonomous solve_normal_captcha workflow execution."""
        mock_page = MagicMock()
        mock_page.evaluate = AsyncMock(return_value=True)

        # Mock image locator
        mock_img = MagicMock()
        mock_img.count = AsyncMock(return_value=1)
        mock_img.is_visible = AsyncMock(return_value=True)
        mock_img.screenshot = AsyncMock(return_value=b"FAKE_IMG_BYTES")
        mock_img.first = mock_img

        # Mock input locator
        mock_input = MagicMock()
        mock_input.count = AsyncMock(return_value=1)
        mock_input.is_visible = AsyncMock(return_value=True)
        mock_input.click = AsyncMock()
        mock_input.fill = AsyncMock()
        mock_input.press_sequentially = AsyncMock()
        mock_input.first = mock_input
        
        mock_ancestor = MagicMock()
        mock_ancestor.count = AsyncMock(return_value=0)
        mock_input.locator.return_value = mock_ancestor

        # Mock submit button
        mock_btn = MagicMock()
        mock_btn.count = AsyncMock(return_value=1)
        mock_btn.first = mock_btn

        def locator_dispatch(sel):
            if "img" in sel or "captcha" in sel.lower():
                return mock_img
            elif "input" in sel or "field" in sel:
                return mock_input
            else:
                return mock_btn

        mock_page.locator.side_effect = locator_dispatch

        # Mock ddddocr classification to return 'test12'
        mock_ocr = MagicMock()
        mock_ocr.classification.return_value = "test12"

        with patch("ddddocr.DdddOcr", return_value=mock_ocr), \
             patch.object(AICaptchaSolver, "_human_click", new_callable=AsyncMock):
            
            # Reset cached instance
            AICaptchaSolver._ddddocr_instance = mock_ocr
            
            ok, msg, details = await AICaptchaSolver.solve_normal_captcha(
                page=mock_page,
                image_selector="img#captcha",
                input_selector="input#code",
                submit_selector="button#submit"
            )

            self.assertTrue(ok)
            self.assertEqual(details.get("text"), "test12")
            self.assertTrue(details.get("solved"))

    async def test_solve_captcha_on_page_explicit_normal_routing(self):
        """Validates solve_captcha_on_page routes to solve_normal_captcha when requested."""
        mock_page = AsyncMock()
        
        with patch.object(AICaptchaSolver, "solve_normal_captcha", new_callable=AsyncMock) as mock_solve:
            mock_solve.return_value = (True, "Normal Captcha Solved", {"solved": True, "text": "abc1"})
            
            ok, msg, details = await AICaptchaSolver.solve_captcha_on_page(
                page=mock_page,
                captcha_type="normal"
            )

            self.assertTrue(ok)
            self.assertTrue(mock_solve.called)


if __name__ == "__main__":
    unittest.main()
