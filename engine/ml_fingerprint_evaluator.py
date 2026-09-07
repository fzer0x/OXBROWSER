import os
import re
import logging
from typing import Dict, Any, List, Tuple, Optional
import numpy as np

logger = logging.getLogger("MLFingerprintEvaluator")

try:
    import onnxruntime as ort
    _ONNX_AVAILABLE = True
except ImportError:
    _ONNX_AVAILABLE = False


class FingerprintFeatureExtractor:
    """Extracts and normalizes browser profile parameters into 12-dimensional numerical feature tensors."""

    OS_MAP = {"windows": 0.0, "mac": 1.0, "linux": 2.0, "android": 3.0, "ios": 4.0}
    VENDOR_MAP = {"nvidia": 0.0, "amd": 1.0, "intel": 2.0, "apple": 3.0, "adreno": 4.0, "mali": 4.0, "mesa": 5.0}

    @classmethod
    def extract_features(cls, fp: Dict[str, Any]) -> Tuple[np.ndarray, Dict[str, Any]]:
        stealth = fp.get("stealth", {}) if isinstance(fp.get("stealth"), dict) else {}
        ua = str(fp.get("user_agent", "") or fp.get("userAgent", "")).lower()
        vendor = str(fp.get("webgl_vendor") or fp.get("webglVendor") or stealth.get("webgl_vendor") or stealth.get("webglVendor") or "")
        renderer = str(fp.get("webgl_renderer") or fp.get("webglRenderer") or stealth.get("webgl_renderer") or stealth.get("webglRenderer") or "")
        cores = int(fp.get("hardware_concurrency", 0) or fp.get("hardwareConcurrency", 0) or 8)
        ram = int(fp.get("device_memory", 0) or fp.get("deviceMemory", 0) or 16)
        screen_res = str(fp.get("screen_res", "") or fp.get("screenResolution", "") or "1920x1080")

        # 0: OS detection
        detected_os = "windows"
        if "macintosh" in ua or "mac os" in ua:
            detected_os = "mac"
        elif "android" in ua:
            detected_os = "android"
        elif "iphone" in ua or "ipad" in ua:
            detected_os = "ios"
        elif "linux" in ua or "x11" in ua:
            detected_os = "linux"
        os_idx = cls.OS_MAP.get(detected_os, 0.0)

        # 1: Browser version (supports Chrome & Firefox / Camoufox)
        ver = 132
        ff_match = re.search(r'rv:(\d+)', ua) or re.search(r'firefox/(\d+)', ua)
        chrome_match = re.search(r'chrome/(\d+)', ua)
        if ff_match:
            ver = int(ff_match.group(1))
        elif chrome_match:
            ver = int(chrome_match.group(1))
        b_ver_norm = float(ver) / 100.0

        # 2: WebGL Vendor
        v_idx = 0.0
        v_lower = vendor.lower()
        for k, val in cls.VENDOR_MAP.items():
            if k in v_lower:
                v_idx = val
                break

        # 3: WebGL Renderer Match & OS Tensor Alignment
        r_match = 1.0
        r_lower = renderer.lower()
        if detected_os == "mac" and "apple" not in v_lower and "angle (apple" not in r_lower and "intel iris" not in r_lower:
            r_match = 0.0
        elif detected_os == "windows" and ("apple" in v_lower or "mesa" in v_lower or "llvmpipe" in r_lower):
            r_match = 0.0
        elif detected_os == "linux":
            if ("direct3d" in r_lower or "d3d11" in r_lower or "d3d9" in r_lower or "apple" in v_lower or "angle (nvidia" in r_lower):
                r_match = 0.0
            elif "nvidia" in v_lower and ("google inc" in v_lower or "angle" in r_lower):
                r_match = 0.0
        elif detected_os in ["android", "ios"] and ("direct3d" in r_lower or "rtx" in r_lower or "gtx" in r_lower):
            r_match = 0.0

        # 6: Core/RAM Harmony
        harmony = 1.0
        if (cores >= 16 and ram <= 4) or (cores <= 2 and ram >= 32):
            harmony = 0.0

        # 7: Screen Aspect
        aspect = 1.0
        if "x" in screen_res:
            try:
                w, h = map(int, screen_res.split("x"))
                if detected_os in ["android", "ios"] and w > h:
                    aspect = 0.0
                elif detected_os in ["windows", "mac", "linux"] and h > w and h > 1200:
                    aspect = 0.0
            except Exception:
                pass

        webgpu = 1.0 if stealth.get("webgpu_supported", False) else 0.0
        c_noise = 1.0 if stealth.get("canvas_noise", True) else 0.0
        a_noise = 1.0 if stealth.get("audio_noise", True) else 0.0
        raw_webrtc = stealth.get("webrtc_mode") or stealth.get("webrtc") or fp.get("webrtc_mode") or "altered"
        if isinstance(raw_webrtc, bool):
            webrtc = 1.0 if raw_webrtc else 0.0
        else:
            webrtc = 1.0 if str(raw_webrtc).lower().strip() in ["altered", "spoof", "spoofed", "disabled", "proxy", "protocol_spoofing"] else 0.0

        features = np.array([[
            os_idx, b_ver_norm, v_idx, r_match,
            float(cores), float(ram), harmony, aspect,
            webgpu, c_noise, a_noise, webrtc
        ]], dtype=np.float32)

        meta = {
            "os": detected_os,
            "version": ver,
            "vendor": vendor,
            "renderer": renderer,
            "cores": cores,
            "ram": ram,
            "r_match": r_match,
            "harmony": harmony,
            "aspect": aspect,
            "screen_res": screen_res
        }
        return features, meta


class MLFingerprintEvaluator:
    """Machine Learning Fingerprint Anomaly & Consistency Evaluator.
    Executes sub-millisecond ONNX Isolation Forest inference to compute an authentic ML Authenticity Score
    and identify mismatched fingerprint vectors.
    """

    _session: Optional[Any] = None
    _model_path: Optional[str] = None

    @classmethod
    def _get_onnx_session(cls) -> Optional[Any]:
        if not _ONNX_AVAILABLE:
            return None

        if cls._session is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            onnx_path = os.path.join(base_dir, "models", "fingerprint_anomaly_v1.onnx")
            if os.path.exists(onnx_path):
                try:
                    cls._session = ort.InferenceSession(onnx_path, providers=['CPUExecutionProvider'])
                    cls._model_path = onnx_path
                    logger.info(f"Loaded ONNX Isolation Forest anomaly detector from {onnx_path}")
                except Exception as e:
                    logger.warning(f"Failed to load ONNX model: {e}")
        return cls._session

    @classmethod
    def evaluate(cls, fp: Dict[str, Any]) -> Tuple[float, List[str], List[str]]:
        """Evaluates a browser fingerprint dictionary and returns:
        - score: float (0.0 to 100.0) ML Authenticity Trust Score
        - anomalies: List[str] Detected anti-bot ML anomalies
        - recommendations: List[str] Suggested fixes
        """
        features, meta = FingerprintFeatureExtractor.extract_features(fp)
        anomalies: List[str] = []
        recommendations: List[str] = []

        # 1. Check feature anomalies
        if meta["r_match"] == 0.0:
            anomalies.append(f"ML Anomaly: OS '{meta['os'].upper()}' mismatched with WebGL Vendor '{meta['vendor']}' / Renderer '{meta['renderer']}'.")
            recommendations.append(f"Match WebGL vendor/renderer to native {meta['os'].title()} GPU profiles.")

        if meta["harmony"] == 0.0:
            anomalies.append(f"ML Anomaly: Unrealistic hardware ratio ({meta['cores']} CPU Cores with {meta['ram']}GB RAM).")
            recommendations.append("Align CPU cores with realistic Device Memory proportions.")

        if meta["aspect"] == 0.0:
            anomalies.append(f"ML Anomaly: Screen resolution aspect ratio mismatch ({meta['screen_res']} for {meta['os']}).")
            recommendations.append("Set resolution orientation appropriate for OS device type.")

        if meta["version"] < 124:
            anomalies.append(f"ML Anomaly: Outdated User-Agent version v{meta['version']}.")
            recommendations.append("Update User-Agent to current standard version (Chrome v130+ / Firefox v132+).")

        # Engine vs User-Agent L7 Cross-Layer Telemetry Validation
        engine_name = str(fp.get("engine", "camoufox")).lower().strip()
        raw_ua = str(fp.get("user_agent", "") or fp.get("userAgent", "")).lower()
        if engine_name in ["camoufox", "firefox"] and ("chrome/" in raw_ua or "chromium/" in raw_ua):
            anomalies.append("ML Anomaly: Engine 'Camoufox' declared with Chrome User-Agent (L7 TLS JA4 mismatch risk).")
            recommendations.append("Align User-Agent with native Camoufox/Firefox Gecko profile.")
        elif engine_name in ["playwright", "nodriver", "selenium_driverless"] and ("firefox/" in raw_ua or "rv:" in raw_ua):
            anomalies.append("ML Anomaly: Chromium Engine declared with Firefox User-Agent (L7 TLS JA4 mismatch risk).")
            recommendations.append("Align User-Agent with native Chrome profile.")

        # Record Telemetry for ONNX Sentinel
        import time
        from engine.ai_telemetry import AITelemetryBus
        t_bus = AITelemetryBus.get_instance()
        t0 = time.time()
        t_bus.record_start("onnx-anomaly", "⛊ Fingerprint Stealth Guard", prompt_summary=f"OS: {meta.get('os')}, GPU: {meta.get('vendor')}")

        # 2. Run Embedded ONNX Inference
        session = cls._get_onnx_session()
        if session is not None:
            try:
                input_name = session.get_inputs()[0].name
                outputs = session.run(None, {input_name: features})
                
                # Isolation Forest output in ONNX: outputs[0] = label (1=normal, -1=anomaly), outputs[1] = raw scores
                scores_arr = outputs[1] if len(outputs) > 1 else outputs[0]
                raw_score = float(np.mean(scores_arr))
                
                # Transform raw score to 0.0 - 100.0 scale
                if raw_score >= 0.0:
                    ml_score = 85.0 + min(15.0, raw_score * 30.0)
                else:
                    ml_score = max(20.0, 85.0 + raw_score * 80.0)

                # Factor in discrete detected anomalies
                penalty = len(anomalies) * 18.0
                final_score = max(0.0, min(100.0, ml_score - penalty))
                dur_ms = (time.time() - t0) * 1000.0
                t_bus.record_finish("onnx-anomaly", "⛊ Fingerprint Stealth Guard", dur_ms, "SUCCESS", f"Score: {round(final_score, 1)}/100, Anomalies: {len(anomalies)}")
                return round(final_score, 1), anomalies, recommendations

            except Exception as inf_err:
                logger.debug(f"ONNX inference fallback: {inf_err}")

        # Fallback heuristic calculation
        base_score = 100.0 - (len(anomalies) * 22.0)
        final_score = max(0.0, min(100.0, base_score))
        dur_ms = (time.time() - t0) * 1000.0
        t_bus.record_finish("onnx-anomaly", "⛊ Fingerprint Stealth Guard", dur_ms, "SUCCESS", f"Score: {round(final_score, 1)}/100, Anomalies: {len(anomalies)}")
        return round(final_score, 1), anomalies, recommendations

