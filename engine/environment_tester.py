"""
Environment Test Suite & Autonomous Auto-Patch Engine for SoxBot.
Provides Senior/Power-User diagnostics across:
- CreepJS (Lie/Error detection, navigator anomaly detection, trust scoring)
- BrowserLeaks (WebGL, Canvas, WebRTC leak, AudioContext, Font Fingerprinting)
- Pixelscan & Iphey (Bot scoring, IP reputation harmony, hardware consistency)
- 12-Dimensional Mathematical ONNX Tensor Consistency & Hardware Harmonization
- 1-Click Autonomous Patch Generator & Remediation Engine
"""

import os
import re
import json
import time
import logging
import asyncio
from typing import Dict, Any, List, Optional, Tuple

import config
from storage.profile_manager import ProfileManager
from engine.ml_fingerprint_evaluator import MLFingerprintEvaluator
from engine.engine_security_advisor import EngineSecurityAdvisor

logger = logging.getLogger("EnvironmentTester")


class EnvironmentBenchmarkTarget:
    CREEPJS = "creepjs"
    BROWSERLEAKS = "browserleaks"
    PIXELSCAN = "pixelscan"
    IPHEY = "iphey"
    AMIUNIQUE = "amiunique"
    FULL_STEALTH_SUITE = "full_stealth_suite"


BENCHMARK_URLS = {
    EnvironmentBenchmarkTarget.CREEPJS: "https://abrahamjuliot.github.io/creepjs/",
    EnvironmentBenchmarkTarget.BROWSERLEAKS: "https://browserleaks.com/canvas",
    EnvironmentBenchmarkTarget.PIXELSCAN: "https://pixelscan.net",
    EnvironmentBenchmarkTarget.IPHEY: "https://iphey.com",
    EnvironmentBenchmarkTarget.AMIUNIQUE: "https://amiunique.org/fp"
}


class AnomalyReport:
    def __init__(self, category: str, severity: str, message: str, recommended_fix: Dict[str, Any]):
        self.category = category  # e.g., "WebGL", "WebRTC", "Kernel/OS", "Noise", "Hardware"
        self.severity = severity  # "CRITICAL", "HIGH", "MEDIUM", "LOW"
        self.message = message
        self.recommended_fix = recommended_fix  # Key-value patch for profile

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "severity": self.severity,
            "message": self.message,
            "recommended_fix": self.recommended_fix
        }


class EnvironmentAuditEngine:
    """
    Senior-Level Static & Mathematical Tensor Audit Engine.
    Examines profile configuration without requiring an active browser launch,
    running exhaustive checks across all browser subsystems.
    """

    @classmethod
    def audit_profile_configuration(cls, profile: Dict[str, Any]) -> Dict[str, Any]:
        anomalies: List[AnomalyReport] = []
        os_type = profile.get("os", "windows").lower()
        ua = profile.get("user_agent", "")
        stealth = profile.get("stealth", {})
        vendor = str(stealth.get("webgl_vendor", "")).strip()
        renderer = str(stealth.get("webgl_renderer", "")).strip()
        cores = profile.get("hardware_concurrency", 8)
        ram = profile.get("device_memory", 8)
        screen_res = profile.get("screen_resolution", "1920x1080")
        webrtc_mode = stealth.get("webrtc_mode", "altered")
        engine = profile.get("engine", "camoufox")

        # 1. OS & User-Agent Harmony
        if os_type == "windows" and "windows" not in ua.lower():
            anomalies.append(AnomalyReport(
                category="Kernel/OS",
                severity="CRITICAL",
                message=f"OS is configured as '{os_type}', but User-Agent indicates a different OS.",
                recommended_fix={"user_agent": config.get_default_user_agent("windows", engine)}
            ))
        elif os_type == "mac" and "macintosh" not in ua.lower() and "mac os" not in ua.lower():
            anomalies.append(AnomalyReport(
                category="Kernel/OS",
                severity="CRITICAL",
                message=f"OS is configured as '{os_type}', but User-Agent indicates a different OS.",
                recommended_fix={"user_agent": config.get_default_user_agent("mac", engine)}
            ))
        elif os_type == "linux" and "linux" not in ua.lower() and "x11" not in ua.lower():
            anomalies.append(AnomalyReport(
                category="Kernel/OS",
                severity="CRITICAL",
                message=f"OS is configured as '{os_type}', but User-Agent indicates a different OS.",
                recommended_fix={"user_agent": config.get_default_user_agent("linux", engine)}
            ))

        # 2. WebGL Hardware & Vendor Tensor Alignment
        valid_presets = config.get_webgl_presets_for_os(os_type)
        default_preset = valid_presets[0] if valid_presets else config.WEBGL_PRESETS[0]

        if os_type == "mac":
            if "apple" not in vendor.lower() and "intel iris" not in renderer.lower():
                anomalies.append(AnomalyReport(
                    category="WebGL",
                    severity="CRITICAL",
                    message=f"Mac profile has mismatched WebGL vendor/renderer ('{vendor}' / '{renderer}'). macOS requires Apple Metal or Intel Iris.",
                    recommended_fix={
                        "stealth.webgl_vendor": default_preset["vendor"],
                        "stealth.webgl_renderer": default_preset["renderer"]
                    }
                ))
        elif os_type == "windows":
            if "apple" in vendor.lower() or "apple" in renderer.lower():
                anomalies.append(AnomalyReport(
                    category="WebGL",
                    severity="CRITICAL",
                    message="Windows profile cannot have Apple GPU architecture in WebGL parameters.",
                    recommended_fix={
                        "stealth.webgl_vendor": default_preset["vendor"],
                        "stealth.webgl_renderer": default_preset["renderer"]
                    }
                ))
            elif "direct3d" not in renderer.lower() and "angle" not in renderer.lower() and engine != "camoufox":
                anomalies.append(AnomalyReport(
                    category="WebGL",
                    severity="MEDIUM",
                    message="Windows Chromium/Playwright stacks typically run ANGLE (Direct3D11) backends.",
                    recommended_fix={
                        "stealth.webgl_vendor": default_preset["vendor"],
                        "stealth.webgl_renderer": default_preset["renderer"]
                    }
                ))
        elif os_type == "linux":
            if "direct3d" in renderer.lower() or "d3d11" in renderer.lower():
                anomalies.append(AnomalyReport(
                    category="WebGL",
                    severity="CRITICAL",
                    message="Linux profile contains Windows Direct3D renderer strings (Direct3D11 leak on Linux kernel).",
                    recommended_fix={
                        "stealth.webgl_vendor": default_preset["vendor"],
                        "stealth.webgl_renderer": default_preset["renderer"]
                    }
                ))

        # 3. WebRTC Security & Leak Protection
        if webrtc_mode not in ["altered", "disabled", "proxy_only", "block"]:
            anomalies.append(AnomalyReport(
                category="WebRTC",
                severity="HIGH",
                message=f"WebRTC mode '{webrtc_mode}' may leak local host IPs or bypass proxy interfaces.",
                recommended_fix={"stealth.webrtc_mode": "altered"}
            ))

        # 4. Canvas & Audio Noise Protection
        canvas_noise = stealth.get("canvas_noise", True)
        audio_noise = stealth.get("audio_noise", True)
        if not canvas_noise:
            anomalies.append(AnomalyReport(
                category="Noise",
                severity="MEDIUM",
                message="Canvas noise is disabled. Anti-fingerprint tracking vectors can derive unique hash signatures.",
                recommended_fix={"stealth.canvas_noise": True}
            ))
        if not audio_noise:
            anomalies.append(AnomalyReport(
                category="Noise",
                severity="MEDIUM",
                message="AudioContext noise is disabled. Audio oscillator frequency tests can fingerprint the soundcard.",
                recommended_fix={"stealth.audio_noise": True}
            ))

        # 5. Core & RAM Plausibility (Hardware Harmony)
        if (cores >= 16 and ram <= 4) or (cores <= 2 and ram >= 32):
            suggested_ram = 16 if cores >= 8 else 8
            anomalies.append(AnomalyReport(
                category="Hardware",
                severity="HIGH",
                message=f"CPU Concurrency ({cores} cores) and Device RAM ({ram} GB) ratio is statistically anomalous.",
                recommended_fix={"device_memory": suggested_ram}
            ))

        # 6. Screen Resolution Plausibility
        if "x" in screen_res:
            try:
                w, h = map(int, screen_res.split("x"))
                if w < 1024 or h < 600:
                    anomalies.append(AnomalyReport(
                        category="Hardware",
                        severity="MEDIUM",
                        message=f"Screen resolution '{screen_res}' is unusually small for a desktop persona.",
                        recommended_fix={"screen_resolution": "1920x1080"}
                    ))
            except Exception:
                pass

        # 7. Engine Security Assessment
        sec_profile = EngineSecurityAdvisor.get_profile(engine)
        if sec_profile.risk_level == "HIGH":
            anomalies.append(AnomalyReport(
                category="EngineSecurity",
                severity="HIGH",
                message=f"Browser engine '{engine}' runs without OS sandbox isolation ({sec_profile.sandbox_type}).",
                recommended_fix={"engine": "camoufox"}
            ))

        # 8. ML Mathematical Tensor Score
        ml_score, ml_anomalies, ml_recs = MLFingerprintEvaluator.evaluate(profile)

        # Calculate Overall Health Score (0-100)
        penalty = 0
        for an in anomalies:
            if an.severity == "CRITICAL":
                penalty += 25
            elif an.severity == "HIGH":
                penalty += 15
            elif an.severity == "MEDIUM":
                penalty += 8
            elif an.severity == "LOW":
                penalty += 3

        overall_score = max(0, min(100, round((ml_score * 0.5) + ((100 - penalty) * 0.5), 1)))

        # Aggregate All Recommended Patches
        combined_patch: Dict[str, Any] = {}
        for an in anomalies:
            for k, v in an.recommended_fix.items():
                combined_patch[k] = v

        return {
            "profile_id": profile.get("id", ""),
            "profile_name": profile.get("name", "Unknown"),
            "health_score": overall_score,
            "ml_tensor_score": round(ml_score, 1),
            "ml_anomalies": ml_anomalies,
            "ml_recommendations": ml_recs,
            "engine": engine,
            "engine_risk": sec_profile.risk_level,
            "anomaly_count": len(anomalies),
            "anomalies": [an.to_dict() for an in anomalies],
            "recommended_patch": combined_patch,
            "is_clean": len(anomalies) == 0 and overall_score >= 90.0,
            "audit_timestamp": time.time()
        }


class AutoPatchEngine:
    """
    Autonomous 1-Click Auto-Patching Engine.
    Applies remediation dictionaries to profile objects atomically.
    """

    @classmethod
    def apply_patch(cls, profile: Dict[str, Any], patch: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
        """
        Applies flat or dot-notated patches (e.g. 'stealth.webgl_vendor' or 'device_memory')
        to the profile and returns (updated_profile, applied_changes_log).
        """
        changes = []
        updated = json.loads(json.dumps(profile))  # Deep copy

        for key, val in patch.items():
            if "." in key:
                parts = key.split(".", 1)
                sub_key = parts[0]
                nested_key = parts[1]
                if sub_key not in updated or not isinstance(updated[sub_key], dict):
                    updated[sub_key] = {}
                old_val = updated[sub_key].get(nested_key)
                updated[sub_key][nested_key] = val
                changes.append(f"Updated '{key}': '{old_val}' → '{val}'")
            else:
                old_val = updated.get(key)
                updated[key] = val
                changes.append(f"Updated '{key}': '{old_val}' → '{val}'")

        return updated, changes


class EnvironmentTestRunner:
    """
    Senior Live Environment Test Runner.
    Runs automated browser benchmarks (CreepJS, BrowserLeaks, Pixelscan)
    via BrowserCopilotBridge / Playwright Page evaluations.
    """

    def __init__(self, bridge=None):
        self.bridge = bridge

    async def run_live_diagnostic(self, page, target: str = EnvironmentBenchmarkTarget.FULL_STEALTH_SUITE) -> Dict[str, Any]:
        """
        Executes in-tab senior diagnostic routines extracting low-level WebGL, WebGPU,
        AudioContext, Screen, and Navigator parameters for validation.
        """
        diagnostic_js = """
        (async () => {
            const results = {};
            
            // 1. Navigator & System
            results.userAgent = navigator.userAgent;
            results.platform = navigator.platform;
            results.hardwareConcurrency = navigator.hardwareConcurrency;
            results.deviceMemory = navigator.deviceMemory || null;
            results.languages = navigator.languages;
            results.maxTouchPoints = navigator.maxTouchPoints;
            results.webdriver = navigator.webdriver;
            results.doNotTrack = navigator.doNotTrack;

            // 2. Screen & Geometry
            results.screen = {
                width: screen.width,
                height: screen.height,
                availWidth: screen.availWidth,
                availHeight: screen.availHeight,
                colorDepth: screen.colorDepth,
                pixelDepth: screen.pixelDepth
            };
            results.window = {
                innerWidth: window.innerWidth,
                innerHeight: window.innerHeight,
                outerWidth: window.outerWidth,
                outerHeight: window.outerHeight,
                devicePixelRatio: window.devicePixelRatio
            };

            // 3. WebGL Diagnostics
            try {
                const canvas = document.createElement('canvas');
                const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
                if (gl) {
                    const debugInfo = gl.getExtension('WEBGL_debug_renderer_info');
                    results.webgl = {
                        supported: true,
                        vendor: debugInfo ? gl.getParameter(debugInfo.UNMASKED_VENDOR_WEBGL) : gl.getParameter(gl.VENDOR),
                        renderer: debugInfo ? gl.getParameter(debugInfo.UNMASKED_RENDERER_WEBGL) : gl.getParameter(gl.RENDERER),
                        version: gl.getParameter(gl.VERSION),
                        shadingLanguageVersion: gl.getParameter(gl.SHADING_LANGUAGE_VERSION)
                    };
                } else {
                    results.webgl = { supported: false };
                }
            } catch (e) {
                results.webgl = { supported: false, error: e.toString() };
            }

            // 4. WebGPU Capability
            try {
                results.webgpu = { supported: !!navigator.gpu };
            } catch (e) {
                results.webgpu = { supported: false };
            }

            // 5. AudioContext Fingerprint Geometry
            try {
                const AudioCtx = window.AudioContext || window.webkitAudioContext;
                if (AudioCtx) {
                    const ctx = new AudioCtx();
                    results.audio = {
                        supported: true,
                        sampleRate: ctx.sampleRate,
                        state: ctx.state
                    };
                    await ctx.close();
                } else {
                    results.audio = { supported: false };
                }
            } catch (e) {
                results.audio = { supported: false, error: e.toString() };
            }

            // 6. Lie / Error Detections
            results.lies = [];
            if (navigator.webdriver === true) {
                results.lies.push({ key: 'webdriver', desc: 'navigator.webdriver flag is explicitly true' });
            }
            if (window.outerWidth === 0 && window.outerHeight === 0) {
                results.lies.push({ key: 'dimensions', desc: 'Zero window dimensions (headless signature)' });
            }

            return results;
        })()
        """
        try:
            if hasattr(page, "evaluate"):
                telemetry = await page.evaluate(diagnostic_js)
                return {
                    "success": True,
                    "target": target,
                    "telemetry": telemetry,
                    "timestamp": time.time()
                }
            else:
                return {
                    "success": False,
                    "error": "Page object does not support script evaluation."
                }
        except Exception as e:
            return {
                "success": False,
                "error": f"Live diagnostic evaluation failed: {e}"
            }
