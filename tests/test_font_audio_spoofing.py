import unittest
from engine.fingerprint import FingerprintGenerator


class TestFontAndAudioSpoofing(unittest.TestCase):
    def setUp(self):
        self.profile_win = {
            "id": "prof_alpha_12345",
            "os": "windows",
            "language": "en-US,en;q=0.9",
            "stealth": {
                "noise_seed": "seed_secure_001",
                "audio_noise": True,
                "font_fingerprint_noise": True,
                "canvas_noise": True,
            }
        }
        self.profile_mac_ja = {
            "id": "prof_beta_67890",
            "os": "macos",
            "language": "ja-JP,ja;q=0.9",
            "stealth": {
                "noise_seed": "seed_tokyo_002",
                "audio_noise": True,
                "font_fingerprint_noise": True,
                "canvas_noise": False,
            }
        }

    def test_deterministic_seeds_consistency(self):
        """Verify that repeat calls for the same profile return identical 32-bit C++ seeds."""
        seeds1 = FingerprintGenerator.derive_camoufox_seeds(self.profile_win, self.profile_win["id"])
        seeds2 = FingerprintGenerator.derive_camoufox_seeds(self.profile_win, self.profile_win["id"])

        self.assertEqual(seeds1, seeds2)
        self.assertIn("audio:seed", seeds1)
        self.assertIn("fonts:spacing_seed", seeds1)
        self.assertIn("canvas:seed", seeds1)

        # Ensure seeds are valid 32-bit positive integers (1 .. 2^32 - 1)
        for name, s_val in seeds1.items():
            self.assertIsInstance(s_val, int)
            self.assertGreaterEqual(s_val, 1)
            self.assertLessEqual(s_val, 4294967295)

    def test_distinct_seeds_across_different_profiles(self):
        """Verify that different profiles receive completely distinct seeds."""
        seeds_win = FingerprintGenerator.derive_camoufox_seeds(self.profile_win, self.profile_win["id"])
        seeds_mac = FingerprintGenerator.derive_camoufox_seeds(self.profile_mac_ja, self.profile_mac_ja["id"])

        self.assertNotEqual(seeds_win["audio:seed"], seeds_mac["audio:seed"])
        self.assertNotEqual(seeds_win["fonts:spacing_seed"], seeds_mac["fonts:spacing_seed"])

    def test_noise_toggle_respect(self):
        """Verify disabled noise toggles omit their respective C++ seed."""
        seeds = FingerprintGenerator.derive_camoufox_seeds(self.profile_mac_ja, self.profile_mac_ja["id"])
        self.assertIn("audio:seed", seeds)
        self.assertIn("fonts:spacing_seed", seeds)
        self.assertNotIn("canvas:seed", seeds)  # canvas_noise is False

    def test_windows_font_subset_and_markers(self):
        """Verify Windows font list contains essential Windows marker fonts."""
        fonts = FingerprintGenerator.get_deterministic_camoufox_fonts(
            target_os="windows",
            seed_str="seed_test_123",
            locale="en-US"
        )
        self.assertIsInstance(fonts, list)
        self.assertGreater(len(fonts), 10)

        # Essential & Marker Windows fonts must be present
        for expected in ["Segoe UI", "Calibri", "Arial", "Consolas"]:
            self.assertIn(expected, fonts)

    def test_regional_font_enrichment(self):
        """Verify Japanese and Chinese locales inject appropriate CJK fonts."""
        # Japanese
        fonts_ja = FingerprintGenerator.get_deterministic_camoufox_fonts(
            target_os="windows",
            seed_str="seed_japan",
            locale="ja-JP"
        )
        has_ja_font = any(f in fonts_ja for f in ["MS Gothic", "Yu Gothic", "Meiryo"])
        self.assertTrue(has_ja_font, "Japanese locale must include MS Gothic, Yu Gothic or Meiryo")

        # Chinese
        fonts_zh = FingerprintGenerator.get_deterministic_camoufox_fonts(
            target_os="windows",
            seed_str="seed_china",
            locale="zh-CN"
        )
        has_zh_font = any(f in fonts_zh for f in ["Microsoft YaHei", "SimSun", "PingFang SC"])
        self.assertTrue(has_zh_font, "Chinese locale must include Microsoft YaHei, SimSun or PingFang SC")

    def test_deterministic_voices_generation(self):
        """Verify TTS voices generation structure and deterministic properties."""
        voices = FingerprintGenerator.get_deterministic_camoufox_voices(
            target_os="windows",
            seed_str="seed_voices_test",
            locale="en-US"
        )
        self.assertIsInstance(voices, list)
        if voices:
            first = voices[0]
            self.assertIn("name", first)
            self.assertIn("lang", first)
            self.assertIn("voiceURI", first)
            self.assertTrue(first.get("default", False))


if __name__ == "__main__":
    unittest.main()
