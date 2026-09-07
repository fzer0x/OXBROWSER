import unittest
from storage.profile_manager import ProfileManager
from engine.sandbox.gpu_profiles import GPUProfileManager

class TestGPUProfileManager(unittest.TestCase):

    def setUp(self):
        self.pm = ProfileManager()

    def test_nvidia_detection(self):
        profile = {
            "os": "windows",
            "screen_resolution": "1920x1080",
            "stealth": {
                "webgl_vendor": "Google Inc. (NVIDIA)",
                "webgl_renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)"
            }
        }
        gpu_type = GPUProfileManager._detect_gpu_type(
            profile["stealth"]["webgl_vendor"],
            profile["stealth"]["webgl_renderer"]
        )
        self.assertEqual(gpu_type, "nvidia_ampere")

        env = GPUProfileManager.build_mesa_env(profile)
        self.assertIn("GALLIUM_DRIVER", env)

    def test_amd_detection(self):
        profile = {
            "os": "windows",
            "screen_resolution": "1920x1080",
            "stealth": {
                "webgl_vendor": "Google Inc. (AMD)",
                "webgl_renderer": "AMD Radeon RX 6700 XT"
            }
        }
        gpu_type = GPUProfileManager._detect_gpu_type(
            profile["stealth"]["webgl_vendor"],
            profile["stealth"]["webgl_renderer"]
        )
        self.assertEqual(gpu_type, "amd_rdna2")

    def test_intel_detection(self):
        profile = {
            "os": "windows",
            "screen_resolution": "1920x1080",
            "stealth": {
                "webgl_vendor": "Google Inc. (Intel)",
                "webgl_renderer": "Intel(R) Iris(R) Xe Graphics"
            }
        }
        gpu_type = GPUProfileManager._detect_gpu_type(
            profile["stealth"]["webgl_vendor"],
            profile["stealth"]["webgl_renderer"]
        )
        self.assertEqual(gpu_type, "intel_iris")

    def test_invalid_profile_fallback(self):
        invalid_profile = {}
        env = GPUProfileManager.build_mesa_env(invalid_profile)
        self.assertEqual(env.get("GALLIUM_DRIVER"), "llvmpipe")

    def test_chromium_flags_4k(self):
        profile = {
            "os": "windows",
            "screen_resolution": "3840x2160",
            "stealth": {
                "webgl_vendor": "Google Inc. (NVIDIA)",
                "webgl_renderer": "NVIDIA GeForce RTX 4090"
            }
        }
        flags = GPUProfileManager.get_chromium_gpu_flags(profile)
        self.assertIn("--force-device-scale-factor=2", flags)
        self.assertIn("--gl-vendor=Google Inc. (NVIDIA)", flags)

    def test_linux_nvidia_rtx3060_flags(self):
        profile = {
            "os": "linux",
            "screen_resolution": "1920x1080",
            "hardware_concurrency": 12,
            "device_memory": 32,
            "stealth": {
                "webgl_vendor": "NVIDIA Corporation",
                "webgl_renderer": "NVIDIA GeForce RTX 3060/PCIe/SSE2"
            }
        }
        gpu_type = GPUProfileManager._detect_gpu_type(
            profile["stealth"]["webgl_vendor"],
            profile["stealth"]["webgl_renderer"]
        )
        self.assertEqual(gpu_type, "nvidia_ampere")
        flags = GPUProfileManager.get_chromium_gpu_flags(profile)
        self.assertIn("--use-gl=desktop", flags)
        self.assertNotIn("--use-angle=gl", flags)
        self.assertIn("--gl-vendor=NVIDIA Corporation", flags)
        self.assertIn("--gl-renderer=NVIDIA GeForce RTX 3060/PCIe/SSE2", flags)

if __name__ == "__main__":
    unittest.main()
