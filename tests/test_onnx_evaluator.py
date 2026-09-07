import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine.ml_fingerprint_evaluator import MLFingerprintEvaluator, FingerprintFeatureExtractor


def test_feature_extraction():
    profile = {
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
        "webgl_vendor": "Google Inc. (NVIDIA)",
        "webgl_renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)",
        "hardware_concurrency": 8,
        "device_memory": 16,
        "screen_res": "1920x1080",
        "stealth": {"canvas_noise": True, "audio_noise": True, "webrtc_mode": "altered"}
    }
    features, meta = FingerprintFeatureExtractor.extract_features(profile)
    assert features.shape == (1, 12)
    assert meta["os"] == "windows"
    assert meta["version"] == 132
    assert meta["cores"] == 8
    assert meta["ram"] == 16


def test_onnx_evaluation_normal_profile():
    profile = {
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
        "webgl_vendor": "Google Inc. (NVIDIA)",
        "webgl_renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)",
        "hardware_concurrency": 8,
        "device_memory": 16,
        "screen_res": "1920x1080",
        "stealth": {"canvas_noise": True, "audio_noise": True, "webrtc_mode": "altered"}
    }
    t0 = time.perf_counter()
    score, anomalies, recs = MLFingerprintEvaluator.evaluate(profile)
    t_elapsed = (time.perf_counter() - t0) * 1000.0

    print(f"Normal Profile Score: {score}% (Inference latency: {t_elapsed:.2f}ms)")
    assert score >= 75.0
    assert len(anomalies) == 0


def test_onnx_evaluation_mismatch_profile():
    mismatched_profile = {
        "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.0.0 Safari/537.36",
        "webgl_vendor": "Google Inc. (NVIDIA)", # Mismatch on Mac
        "webgl_renderer": "ANGLE (NVIDIA Direct3D11)",
        "hardware_concurrency": 32, # Mismatch: 32 cores with 2GB RAM
        "device_memory": 2,
        "screen_res": "1080x1920", # Portrait on desktop Mac
        "stealth": {"canvas_noise": False, "webrtc_mode": "raw"}
    }
    score, anomalies, recs = MLFingerprintEvaluator.evaluate(mismatched_profile)
    print(f"Mismatched Profile Score: {score}% with {len(anomalies)} anomalies")
    assert score < 60.0
    assert len(anomalies) >= 2
    assert len(recs) >= 2


def test_onnx_evaluation_linux_rtx3060_profile():
    linux_rtx_profile = {
        "os": "linux",
        "user_agent": "Mozilla/5.0 (X11; Linux x86_64; rv:152.0) Gecko/20100101 Firefox/152.0",
        "webgl_vendor": "NVIDIA Corporation",
        "webgl_renderer": "NVIDIA GeForce RTX 3060/PCIe/SSE2",
        "hardware_concurrency": 12,
        "device_memory": 32,
        "screen_res": "1920x1080",
        "stealth": {"canvas_noise": True, "audio_noise": True, "webrtc_mode": "altered"}
    }
    features, meta = FingerprintFeatureExtractor.extract_features(linux_rtx_profile)
    assert meta["os"] == "linux"
    assert meta["r_match"] == 1.0
    assert meta["harmony"] == 1.0
    assert meta["cores"] == 12
    assert meta["ram"] == 32

    score, anomalies, recs = MLFingerprintEvaluator.evaluate(linux_rtx_profile)
    print(f"Linux RTX 3060 Tensor Score: {score}% (Anomalies: {len(anomalies)})")
    assert score >= 85.0
    assert len(anomalies) == 0


if __name__ == "__main__":
    test_feature_extraction()
    test_onnx_evaluation_normal_profile()
    test_onnx_evaluation_linux_rtx3060_profile()
    test_onnx_evaluation_mismatch_profile()
    print("ALL PHASE 2 ONNX & TENSOR HARMONY TESTS PASSED! ⫸")
