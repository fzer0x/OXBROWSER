import unittest
import time
from engine.ai_inference_optimizer import (
    JSONSchemaGrammars, AdaptiveTokenChunker,
    SpeculativeDecodingCoordinator, AIInferenceOptimizer
)


class TestAIInferenceOptimizer(unittest.TestCase):

    def test_json_schema_grammars(self):
        prof_schema = JSONSchemaGrammars.get_schema_for_action("create_profile")
        self.assertIsNotNone(prof_schema)
        self.assertIn("properties", prof_schema)
        self.assertIn("stealth", prof_schema["properties"])

        batch_schema = JSONSchemaGrammars.get_schema_for_action("create_batch_profiles")
        self.assertIsNotNone(batch_schema)
        self.assertEqual(batch_schema["type"], "array")

        warmup_schema = JSONSchemaGrammars.get_schema_for_action("save_campaign")
        self.assertIsNotNone(warmup_schema)
        self.assertIn("urls", warmup_schema["properties"])

    def test_adaptive_token_chunker(self):
        chunker = AdaptiveTokenChunker(flush_interval_ms=50.0, min_chunk_len=5)
        
        # Small token should buffer
        c1 = chunker.push("Hi")
        # Long token should flush
        c2 = chunker.push(" there, World!")
        self.assertIsNotNone(c2)
        self.assertIn("Hi there, World!", c2)

        # Flush remaining
        chunker.push("abc")
        rest = chunker.flush()
        self.assertEqual(rest, "abc")

    def test_speculative_decoding_coordinator(self):
        draft, target = SpeculativeDecodingCoordinator.get_optimal_pair("qwen2.5:7b")
        self.assertEqual(draft, "qwen2.5:0.5b")
        self.assertEqual(target, "qwen2.5:7b")

        metrics = SpeculativeDecodingCoordinator.calculate_speedup_metrics(total_tokens=100, duration_sec=2.0)
        self.assertEqual(metrics["effective_tokens_per_sec"], 50.0)
        self.assertGreater(metrics["speedup_factor"], 1.0)

    def test_inference_optimizer_options(self):
        opt = AIInferenceOptimizer.get_instance()
        options = opt.get_optimized_ollama_options("qwen2.5:3b")
        self.assertGreaterEqual(options["num_ctx"], 8192)
        self.assertIn("temperature", options)
        self.assertIn("top_p", options)


if __name__ == "__main__":
    unittest.main()
