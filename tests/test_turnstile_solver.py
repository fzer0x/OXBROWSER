import io
import unittest
from PIL import Image
from engine.ai_captcha_solver import AICaptchaSolver

class TestTurnstileAndCropSolver(unittest.TestCase):
    def test_crop_challenge_region(self):
        # Create a test image 200x200
        img = Image.new("RGB", (200, 200), color=(255, 0, 0))
        buf = io.BytesIO()
        img.save(buf, format="JPEG")
        raw_bytes = buf.getvalue()

        # Crop box [50, 50, 60, 60] with padding 5 -> box [45, 45, 115, 115]
        cropped_b64 = AICaptchaSolver.crop_challenge_region(raw_bytes, (50, 50, 60, 60), padding=5)
        self.assertTrue(len(cropped_b64) > 0)
        self.assertIsInstance(cropped_b64, str)

    def test_audio_response_formatting(self):
        self.assertEqual(AICaptchaSolver._format_audio_response("The numbers are 4 8 2 1"), "4821")
        self.assertEqual(AICaptchaSolver._format_audio_response("four two nine"), "429")
        self.assertEqual(AICaptchaSolver._format_audio_response("vier sieben zwei"), "472")

if __name__ == "__main__":
    unittest.main()
