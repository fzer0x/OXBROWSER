import os
import sys
import unittest
import asyncio

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.lifecycle import GlobalLifecycleManager
from engine.events import AsyncEventBus, Channel
from models.schemas import ProfileConfig, StealthConfig, LocationConfig, ProxyConfig
from engine.ai_inference_optimizer import GBNFCompiler, JSONSchemaGrammars, FlashAttentionOptimizer, SpeculativeDecodingCoordinator
from engine.ai_vla_engine import VisionLanguageActionEngine, VLAActionType, VLAActionResult


class TestArchitectureAndAI(unittest.TestCase):

    def test_lifecycle_manager_tracking(self):
        """Verifies GlobalLifecycleManager PID tracking and clean state."""
        lifecycle = GlobalLifecycleManager.get_instance()
        test_pid = 999999
        lifecycle.track_pid(test_pid)
        self.assertIn(test_pid, lifecycle._tracked_pids)
        lifecycle.untrack_pid(test_pid)
        self.assertNotIn(test_pid, lifecycle._tracked_pids)

    def test_async_event_bus_weakref(self):
        """Verifies AsyncEventBus weak reference dispatch and channel isolation."""
        async def run_event_test():
            bus = AsyncEventBus.get_instance()
            received_events = []

            class SubscriberWidget:
                def on_event(self, data: str):
                    received_events.append(data)

            widget = SubscriberWidget()
            bus.subscribe("test_event", widget.on_event)

            await bus.emit("test_event", data="hello_eventbus")
            await asyncio.sleep(0.05)
            self.assertIn("hello_eventbus", received_events)

            # Test weakref cleanup after widget deleted
            del widget
            await bus.emit("test_event", data="after_delete")
            await asyncio.sleep(0.05)
            # Length should still be 1 (second event not delivered to dead widget)
            self.assertEqual(len(received_events), 1)

        asyncio.run(run_event_test())

    def test_pydantic_schemas_and_dict_compatibility(self):
        """Verifies ProfileConfig validation and seamless dict compatibility."""
        profile = ProfileConfig(
            name="Test Architecture Profile",
            os="windows",
            screen_resolution="1920x1080",
            hardware_concurrency=16,
            device_memory=32
        )
        
        # Test dict interface access
        self.assertEqual(profile["name"], "Test Architecture Profile")
        self.assertEqual(profile["os"], "windows")
        self.assertEqual(profile["hardware_concurrency"], 16)
        
        # Test dict mutation
        profile["group"] = "Production"
        self.assertEqual(profile.get("group"), "Production")

        # Test invalid screen resolution normalization fallback
        invalid_prof = ProfileConfig(screen_resolution="invalid_res")
        self.assertEqual(invalid_prof.screen_resolution, "1920x1080")

        # Test to_dict serialization
        d = profile.to_dict()
        self.assertIsInstance(d, dict)
        self.assertEqual(d["name"], "Test Architecture Profile")

    def test_gbnf_grammar_compiler(self):
        """Verifies JSON Schema to GBNF Grammar compiler."""
        schema = {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["click", "type", "scroll"]},
                "confidence": {"type": "number"}
            },
            "required": ["action"]
        }
        gbnf = GBNFCompiler.json_schema_to_gbnf(schema)
        self.assertIn("root ::=", gbnf)
        self.assertIn("click", gbnf)
        self.assertIn("type", gbnf)
        self.assertIn("scroll", gbnf)

    def test_flash_attention_and_speculative_optimizer(self):
        """Verifies Flash-Attention 2 CLI flags and Speculative Decoding coordinator."""
        flags = FlashAttentionOptimizer.get_llama_cpp_cli_flags(
            n_gpu_layers=33,
            ctx_size=8192,
            flash_attn=True,
            kv_quant="q4_0"
        )
        flags_str = " ".join(flags)
        self.assertIn("-fa 1", flags_str)
        self.assertIn("-ctk q4_0", flags_str)
        self.assertIn("-ngl 33", flags_str)

        coordinator = SpeculativeDecodingCoordinator(draft_model="qwen2.5:0.5b", target_model="qwen2.5:7b")
        coordinator.record_acceptance(accepted=8, proposed=10)
        self.assertEqual(coordinator.acceptance_rate, 0.8)

    def test_vla_engine_coordinate_denormalization(self):
        """Verifies VLA pixel denormalization across normalized and UI-TARS spaces."""
        vla = VisionLanguageActionEngine.get_instance()
        
        # Test 0-1000 space (UI-TARS / ShowUI standard)
        px, py = vla.denormalize_coordinates(raw_x=500, raw_y=500, viewport_width=1920, viewport_height=1080)
        self.assertEqual((px, py), (960, 540))

        # Test 0.0-1.0 float space
        px2, py2 = vla.denormalize_coordinates(raw_x=0.25, raw_y=0.75, viewport_width=1000, viewport_height=1000)
        self.assertEqual((px2, py2), (250, 750))

        # Test model response JSON parsing
        json_output = '```json\n{"thought": "Click search submit button", "action": "click", "point": [500, 500], "confidence": 0.98}\n```'
        result = vla.parse_model_action_response(json_output, viewport_width=1920, viewport_height=1080)
        self.assertEqual(result.action, VLAActionType.CLICK)
        self.assertEqual(result.point, (960, 540))
        self.assertEqual(result.confidence, 0.98)

    def test_cdp_binary_patcher_and_mitigation(self):
        """Verifies binary CDC hex patching and runtime leak mitigation scripts."""
        from engine.cdp_patcher import ChromiumBinaryPatcher, CDPRestrictionMitigator
        import tempfile

        # Test in-memory binary signature replacement
        dummy_binary_content = b"\x7fELF\x02\x01\x01\x00" + b"some_code_" + b"cdc_adoQpoasnfa76pfcZLmcfl_" + b"_more_data"
        with tempfile.NamedTemporaryFile(delete=False) as tf:
            tf.write(dummy_binary_content)
            temp_path = tf.name

        try:
            ok, count, msg = ChromiumBinaryPatcher.patch_binary(temp_path, backup=False)
            self.assertTrue(ok)
            self.assertEqual(count, 1)

            with open(temp_path, "rb") as f:
                patched = f.read()
            self.assertNotIn(b"cdc_adoQpoasnfa76pfcZLmcfl_", patched)
            self.assertIn(b"sox_", patched)
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

        # Test script generation
        script = CDPRestrictionMitigator.generate_cdp_leak_protection_script()
        self.assertIn("cdc_adoQpoasnfa76pfcZLmcfl_Array", script)
        self.assertIn("__webdriver_evaluate", script)
        self.assertIn("Function.prototype.toString", script)

    def test_tls_preset_alignment_and_boringssl(self):
        """Verifies TLS 1.3 / JA4+ auto-detection and BoringSSL session capabilities."""
        from engine.tls_impersonate import TLSImpersonator, TLS_PRESETS

        # Test profile matching
        preset_chrome = TLSImpersonator.get_preset_for_profile({"engine": "chromium", "os": "windows", "user_agent": "Chrome/131.0"})
        self.assertEqual(preset_chrome, "chrome_131_win11")
        self.assertIn("ja4", TLS_PRESETS[preset_chrome])

        preset_firefox = TLSImpersonator.get_preset_for_profile({"engine": "camoufox", "os": "linux", "user_agent": "Firefox/133.0"})
        self.assertEqual(preset_firefox, "firefox_130_linux")

        preset_mac = TLSImpersonator.get_preset_for_profile({"engine": "chromium", "os": "mac", "user_agent": "Safari/605.1"})
        self.assertEqual(preset_mac, "safari_18_mac")

        # Test BoringSSL target resolution
        target = TLSImpersonator.get_boringssl_target(preset_chrome, "windows")
        self.assertEqual(target, "chrome131")

    def test_webgpu_and_sensors_stealth_generation(self):
        """Verifies WebGPU shader-f16 and Hardware Sensor API injection into stealth scripts."""
        from engine.fingerprint import FingerprintGenerator

        profile_data = {
            "id": "test_webgpu_sensor_profile",
            "name": "WebGPU Test",
            "os": "mac",
            "screen_resolution": "2560x1440",
            "stealth": {
                "webgpu_supported": True,
                "webgl_vendor": "Apple Inc.",
                "webgl_renderer": "Apple M3 Max"
            }
        }
        script = FingerprintGenerator.generate_stealth_script(profile_data)
        self.assertIn("'gpu'", script)
        self.assertIn("shader-f16", script)
        self.assertIn("Accelerometer", script)
        self.assertIn("Gyroscope", script)
        self.assertIn("maxTextureDimension1D", script)


if __name__ == "__main__":
    unittest.main()

