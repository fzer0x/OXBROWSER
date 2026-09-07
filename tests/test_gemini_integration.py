import unittest
import asyncio
import io
import json
from unittest.mock import AsyncMock, patch, MagicMock
from PIL import Image

import config
from engine.ai_gemini_client import GeminiApiClient
from engine.ai_model_manager import AIModelManager

class TestGeminiIntegration(unittest.TestCase):
    """Unit tests for Google Gemini API Client, Grid Solver, and AIModelManager Hybrid Routing."""

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.client = GeminiApiClient("test_gemini_api_key_123456789")

    def tearDown(self):
        self.loop.close()

    def test_client_configuration(self):
        self.assertTrue(self.client.is_configured())
        self.assertEqual(self.client.get_api_key(), "test_gemini_api_key_123456789")

        empty_client = GeminiApiClient("")
        empty_client.set_api_key("")
        self.assertFalse(empty_client.is_configured())

    def test_image_base64_encoding(self):
        # 1. Test raw bytes
        test_bytes = b"fake_jpeg_image_data"
        b64 = GeminiApiClient._encode_image_to_base64(test_bytes)
        self.assertTrue(len(b64) > 0)

        # 2. Test PIL Image
        img = Image.new("RGB", (64, 64), color="blue")
        b64_pil = GeminiApiClient._encode_image_to_base64(img)
        self.assertTrue(len(b64_pil) > 0)

        # 3. Test data URI
        data_uri = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        b64_uri = GeminiApiClient._encode_image_to_base64(data_uri)
        self.assertEqual(b64_uri, "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==")

    def test_extract_text_from_response(self):
        sample_resp = {
            "candidates": [{
                "content": {
                    "parts": [{"text": "Hello, Gemini!"}]
                }
            }]
        }
        text = GeminiApiClient._extract_text_from_response(sample_resp)
        self.assertEqual(text, "Hello, Gemini!")

    def test_solve_captcha_grid_parsing(self):
        async def _test():
            # Mock generate_vision to return a JSON grid response
            with patch.object(self.client, "generate_vision", new_callable=AsyncMock) as mock_vision:
                mock_vision.return_value = json.dumps({
                    "matching_tiles": [0, 3, 5],
                    "confidence": 0.98
                })

                tiles = await self.client.solve_captcha_grid(
                    image_data=b"fake_image_bytes",
                    target_instruction="Select all images with a bus",
                    grid_size=(3, 3)
                )
                self.assertEqual(tiles, [0, 3, 5])

                # Out of bounds indices should be filtered out
                mock_vision.return_value = json.dumps({
                    "matching_tiles": [1, 7, 99, -5, "invalid"]
                })
                tiles_bounded = await self.client.solve_captcha_grid(
                    image_data=b"fake_image_bytes",
                    target_instruction="Select all bicycles",
                    grid_size=(3, 3)
                )
                self.assertEqual(tiles_bounded, [1, 7])

        self.loop.run_until_complete(_test())

    def test_hybrid_roles_gemini(self):
        mgr = AIModelManager.get_instance()
        
        # Test direct gemini-3.6-flash role
        roles_flash = mgr.get_hybrid_roles("gemini-3.6-flash")
        self.assertEqual(roles_flash["text_model"], "gemini-3.6-flash")
        self.assertEqual(roles_flash["vision_model"], "gemini-3.6-flash")

        # Test hybrid_gemini_vision role
        roles_hybrid = mgr.get_hybrid_roles("hybrid_gemini_vision")
        self.assertEqual(roles_hybrid["text_model"], "qwen2.5:1.5b")
        self.assertEqual(roles_hybrid["vision_model"], "gemini-3.6-flash")

    def test_model_normalization(self):
        self.assertEqual(GeminiApiClient.normalize_model_name("gemini-2.0-flash"), "gemini-flash-lite-latest")
        self.assertEqual(GeminiApiClient.normalize_model_name("models/gemini-flash-lite-latest"), "gemini-flash-lite-latest")


    def test_ensure_model_pulled_skips_cloud_gemini(self):
        async def _test():
            mgr = AIModelManager.get_instance()
            # Gemini models should immediately return True without running ollama pull
            ready = await mgr.ensure_model_pulled("gemini-3.6-flash")
            self.assertTrue(ready)
            ready_pro = await mgr.ensure_model_pulled("gemini-1.5-pro")
            self.assertTrue(ready_pro)

        self.loop.run_until_complete(_test())


if __name__ == "__main__":
    unittest.main()

