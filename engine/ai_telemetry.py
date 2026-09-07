import time
import asyncio
from typing import Dict, Any, List, Optional, Callable
from PyQt6.QtCore import QObject, pyqtSignal

class AITelemetryRelay(QObject):
    """Qt signal relay for thread-safe UI updates from AI engine events."""
    model_activity_started = pyqtSignal(str, str, str, dict)  # model_id, operation, prompt_summary, meta
    model_activity_finished = pyqtSignal(str, str, float, str, str, dict)  # model_id, operation, duration_ms, status, result_summary, meta
    telemetry_updated = pyqtSignal()

class AITelemetryBus:
    """
    Central event and telemetry hub for tracking all 6 AI Models and their real-time operations:
    1. Qwen 2.5 (0.5B) - Micro-Heuristics & Reading Dwell Time
    2. Qwen 2.5 (1.5B) - DOM Consent & Navigation Intent Solver
    3. Qwen 2.5 (3B) - Deep Cognitive Trajectory & Persona Planner
    4. Moondream 2 (1.4B) - Fast Multimodal Vision & OCR Grounding
    5. LLaVA (7B) - High-Precision Spatial Vision & reCAPTCHA Solver
    6. Faster-Whisper (Tiny) - Acoustic Speech-to-Text & Audio Challenge Solver
    """
    _instance: Optional['AITelemetryBus'] = None

    def __init__(self):
        self.relay = AITelemetryRelay()
        self.history: List[Dict[str, Any]] = []
        self.max_history = 200

        # Model Definitions & Default States
        self.models_meta: Dict[str, Dict[str, Any]] = {
            "qwen2.5:0.5b": {
                "id": "qwen2.5:0.5b",
                "display_name": "Qwen 2.5 (0.5B)",
                "family": "Micro-LLM",
                "icon": "⭍",
                "color": "#38bdf8",  # Sky blue
                "accent_rgb": "56, 189, 248",
                "role_title": "Micro-Heuristics & Dwell Time Engine",
                "role_description": "Instantaneous page text density analysis, reading dwell time estimation & fast regex parsing.",
                "assigned_tasks": [
                    "⏱ Human Reading Dwell Time",
                    "▤ Fast Content Density Scoring",
                    "⌕ Micro-DOM Element Parsing",
                    "⭍ Low-Latency Heuristics"
                ],
                "size_str": "397 MB",
                "params": "0.49B",
                "typical_latency": "~45 ms",
                "status": "IDLE",
                "current_task": "Standby / Ready",
                "current_target": "",
                "last_active_time": "Never",
                "total_calls": 0,
                "total_time_ms": 0.0,
                "success_count": 0,
                "error_count": 0,
                "last_duration_ms": 0.0,
                "last_result": "",
                "is_active": False
            },
            "qwen2.5:1.5b": {
                "id": "qwen2.5:1.5b",
                "display_name": "Qwen 2.5 (1.5B)",
                "family": "Micro-LLM",
                "icon": "⛊",
                "color": "#10b981",  # Emerald
                "accent_rgb": "16, 185, 129",
                "role_title": "DOM Consent & Navigation Intent Solver",
                "role_description": "High-accuracy GDPR/ePrivacy cookie banner resolution, complex consent element extraction & persona context.",
                "assigned_tasks": [
                    "⚇ GDPR / Cookie Banner Resolution",
                    "↹ Strict Reject & Smart Consent",
                    "⑆ Shadow DOM v2 Element Solver",
                    "⌖ Navigation Click Candidate Filtering"
                ],
                "size_str": "986 MB",
                "params": "1.54B",
                "typical_latency": "~120 ms",
                "status": "IDLE",
                "current_task": "Standby / Ready",
                "current_target": "",
                "last_active_time": "Never",
                "total_calls": 0,
                "total_time_ms": 0.0,
                "success_count": 0,
                "error_count": 0,
                "last_duration_ms": 0.0,
                "last_result": "",
                "is_active": False
            },
            "qwen2.5:3b": {
                "id": "qwen2.5:3b",
                "display_name": "Qwen 2.5 (3B)",
                "family": "Micro-LLM",
                "icon": "⎔",
                "color": "#818cf8",  # Indigo
                "accent_rgb": "129, 140, 248",
                "role_title": "Deep Cognitive Trajectory & Persona Planner",
                "role_description": "Multi-hop browsing trajectory planning, topic intent coherence (Roter Faden), search query synthesis & human simulation.",
                "assigned_tasks": [
                    "◵ Topic Intent Coherence (Roter Faden)",
                    "⌕ Organic Search Query Synthesis",
                    "⚲ Persona Clickstream Modeling",
                    "◪ Copilot & AI Chat Query Generation"
                ],
                "size_str": "1.9 GB",
                "params": "3.09B",
                "typical_latency": "~260 ms",
                "status": "IDLE",
                "current_task": "Standby / Ready",
                "current_target": "",
                "last_active_time": "Never",
                "total_calls": 0,
                "total_time_ms": 0.0,
                "success_count": 0,
                "error_count": 0,
                "last_duration_ms": 0.0,
                "last_result": "",
                "is_active": False
            },
            "moondream:v2": {
                "id": "moondream:v2",
                "display_name": "SmolVLM / Moondream 2",
                "family": "Vision-VLM",
                "icon": "▨",
                "color": "#f59e0b",  # Amber
                "accent_rgb": "245, 158, 11",
                "role_title": "Fast Multimodal Vision & UI OCR",
                "role_description": "Rapid screenshot analysis, visual UI element grounding, on-screen text OCR & fast banner verification.",
                "assigned_tasks": [
                    "▨ Fast Viewport Screenshot OCR",
                    "⌖ Visual UI Element Grounding",
                    "⚆ Lightweight Visual Verification",
                    "⊿ 2D Bounding Box Localization"
                ],
                "size_str": "1.7 GB",
                "params": "1.4B",
                "typical_latency": "~210 ms",
                "status": "IDLE",
                "current_task": "Standby / Ready",
                "current_target": "",
                "last_active_time": "Never",
                "total_calls": 0,
                "total_time_ms": 0.0,
                "success_count": 0,
                "error_count": 0,
                "last_duration_ms": 0.0,
                "last_result": "",
                "is_active": False
            },
            "llava:7b": {
                "id": "llava:7b",
                "display_name": "LLaVA (7B)",
                "family": "Spatial-VLM",
                "icon": "⚝",
                "color": "#ec4899",  # Pink / Magenta
                "accent_rgb": "236, 72, 153",
                "role_title": "Spatial Vision & reCAPTCHA Solver",
                "role_description": "High-precision parallel tile cropping & classification for 3x3 / 4x4 reCAPTCHAs, deep visual anomaly detection & subpixel grounding.",
                "assigned_tasks": [
                    "⎘ reCAPTCHA 3x3 / 4x4 Tile Classifier",
                    "⚗ Multi-lingual Concept Expansion",
                    "⌖ High-Precision Subpixel Coordinate Grounding",
                    "⌗ Deep Visual Anomaly Detection"
                ],
                "size_str": "4.7 GB",
                "params": "7.0B",
                "typical_latency": "~650 ms",
                "status": "IDLE",
                "current_task": "Standby / Ready",
                "current_target": "",
                "last_active_time": "Never",
                "total_calls": 0,
                "total_time_ms": 0.0,
                "success_count": 0,
                "error_count": 0,
                "last_duration_ms": 0.0,
                "last_result": "",
                "is_active": False
            },
            "deepseek-r1:1.5b": {
                "id": "deepseek-r1:1.5b",
                "display_name": "DeepSeek R1 (1.5B)",
                "family": "Reasoning-LLM",
                "icon": "🧠",
                "color": "#a855f7",  # Purple
                "accent_rgb": "168, 85, 247",
                "role_title": "Chain-of-Thought & Anti-Bot Strategy Engine",
                "role_description": "Deep multi-step reasoning, cognitive thinking blocks, anti-bot evasive planning & Google Query synthesis.",
                "assigned_tasks": [
                    "🧠 Chain-of-Thought Anti-Bot Reasoning",
                    "⌕ Deep Google Query & Intent Synthesis",
                    "⚲ Strategic Persona Clickstream Trajectory",
                    "⛉ Counter-Bot Defense Evasion Planning"
                ],
                "size_str": "1.1 GB",
                "params": "1.78B",
                "typical_latency": "~160 ms",
                "status": "IDLE",
                "current_task": "Standby / Ready",
                "current_target": "",
                "last_active_time": "Never",
                "total_calls": 0,
                "total_time_ms": 0.0,
                "success_count": 0,
                "error_count": 0,
                "last_duration_ms": 0.0,
                "last_result": "",
                "is_active": False
            },
            "qwen2.5-coder:1.5b": {
                "id": "qwen2.5-coder:1.5b",
                "display_name": "Qwen 2.5 Coder (1.5B)",
                "family": "Code-LLM",
                "icon": "💻",
                "color": "#06b6d4",  # Cyan
                "accent_rgb": "6, 182, 212",
                "role_title": "DOM Engineering & Selector Injection Tactician",
                "role_description": "Shadow DOM v2 extraction, JavaScript injection generation, precise XPath & CSS selector synthesis.",
                "assigned_tasks": [
                    "💻 Shadow DOM & Selector Script Synthesis",
                    "⚇ GDPR / Complex Consent DOM Analysis",
                    "⛉ Honeypot DOM Structural Evaluation",
                    "⎔ JavaScript Evaluation & DOM Automation"
                ],
                "size_str": "986 MB",
                "params": "1.54B",
                "typical_latency": "~110 ms",
                "status": "IDLE",
                "current_task": "Standby / Ready",
                "current_target": "",
                "last_active_time": "Never",
                "total_calls": 0,
                "total_time_ms": 0.0,
                "success_count": 0,
                "error_count": 0,
                "last_duration_ms": 0.0,
                "last_result": "",
                "is_active": False
            },
            "qwen2.5vl:3b": {
                "id": "qwen2.5vl:3b",
                "display_name": "Qwen 2.5 VL (3B)",
                "family": "Vision-VLM",
                "icon": "👁",
                "color": "#f43f5e",  # Rose
                "accent_rgb": "244, 63, 94",
                "role_title": "Next-Gen Multimodal Vision & UI Grounding",
                "role_description": "High-resolution multimodal vision grounding, subpixel UI element localization & reCAPTCHA image classification.",
                "assigned_tasks": [
                    "👁 Multimodal UI Coordinate Grounding",
                    "⎘ reCAPTCHA 3x3 / 4x4 Grid Tile Analysis",
                    "▨ Visual Banner & Viewport OCR Detection",
                    "⚆ Zero-Shot Visual Anomaly Identification"
                ],
                "size_str": "3.2 GB",
                "params": "3.1B",
                "typical_latency": "~240 ms",
                "status": "IDLE",
                "current_task": "Standby / Ready",
                "current_target": "",
                "last_active_time": "Never",
                "total_calls": 0,
                "total_time_ms": 0.0,
                "success_count": 0,
                "error_count": 0,
                "last_duration_ms": 0.0,
                "last_result": "",
                "is_active": False
            },
            "onnx-anomaly": {
                "id": "onnx-anomaly",
                "display_name": "ONNX Isolation Forest",
                "family": "ML-Sentinel",
                "icon": "⛊",
                "color": "#14b8a6",  # Teal
                "accent_rgb": "20, 184, 166",
                "role_title": "Stealth Sentinel & Anomaly Detector",
                "role_description": "Sub-millisecond mathematical feature tensor evaluation of browser profiles for anti-bot detection avoidance.",
                "assigned_tasks": [
                    "⛊ Fingerprint Anomaly Detection",
                    "↹ Hardware Concurrency & RAM Harmony",
                    "⊿ WebGL / OS Vendor Compatibility",
                    "⭍ Sub-Millisecond CPU Inference (<1ms)"
                ],
                "size_str": "< 1 MB",
                "params": "Isolation Forest",
                "typical_latency": "< 1 ms",
                "status": "IDLE",
                "current_task": "Standby / Ready",
                "current_target": "",
                "last_active_time": "Never",
                "total_calls": 0,
                "total_time_ms": 0.0,
                "success_count": 0,
                "error_count": 0,
                "last_duration_ms": 0.0,
                "last_result": "",
                "is_active": False
            },
            "faster-whisper": {
                "id": "faster-whisper",
                "display_name": "Faster-Whisper (Base/Tiny)",
                "family": "Acoustic-STT",
                "icon": "☋",
                "color": "#a855f7",  # Purple
                "accent_rgb": "168, 85, 247",
                "role_title": "Acoustic Speech-to-Text & Audio Challenge Solver",
                "role_description": "Zero-GPU acoustic voice challenge transcription for reCAPTCHA/hCaptcha audio fallback bypass.",
                "assigned_tasks": [
                    "☊ reCAPTCHA Audio Challenge STT",
                    "☊ VAD Spectral Voice Recognition",
                    "⛿ Multi-Lingual Speech Decoding",
                    "⭍ Zero-GPU CPU INT8 Execution"
                ],
                "size_str": "145 MB",
                "params": "Base / Tiny",
                "typical_latency": "~85 ms",
                "status": "IDLE",
                "current_task": "Standby / Ready",
                "current_target": "",
                "last_active_time": "Never",
                "total_calls": 0,
                "total_time_ms": 0.0,
                "success_count": 0,
                "error_count": 0,
                "last_duration_ms": 0.0,
                "last_result": "",
                "is_active": False
            },
            "gemini-3.6-flash": {
                "id": "gemini-3.6-flash",
                "display_name": "Gemini 3.6 Flash",
                "family": "Cloud-Multimodal",
                "icon": "★",
                "color": "#38bdf8",  # Cyan / Light Blue
                "accent_rgb": "56, 189, 248",
                "role_title": "Cloud Multimodal Vision & High-Speed Reasoning",
                "role_description": "Zero-VRAM ultra-fast one-shot 3x3/4x4 reCAPTCHA solver, complex multimodal UI grounding, agentic reasoning & DOM comprehension.",
                "assigned_tasks": [
                    "⭍ One-Shot reCAPTCHA Grid Solver (<500ms)",
                    "☁ Zero-VRAM Cloud AI Fallback",
                    "⚆ Multimodal Spatial Grounding",
                    "⎔ Complex Web Agent Trajectory Reasoning"
                ],
                "size_str": "Cloud API (0 MB VRAM)",
                "params": "Cloud Multimodal",
                "typical_latency": "~350 ms",
                "status": "IDLE",
                "current_task": "Standby / Ready",
                "current_target": "",
                "last_active_time": "Never",
                "total_calls": 0,
                "total_time_ms": 0.0,
                "success_count": 0,
                "error_count": 0,
                "last_duration_ms": 0.0,
                "last_result": "",
                "is_active": False
            },
            "qwen2.5:7b": {
                "id": "qwen2.5:7b",
                "display_name": "Qwen 2.5 (7B)",
                "family": "Heavy-LLM",
                "icon": "⎔",
                "color": "#eab308",  # Gold / Amber
                "accent_rgb": "234, 179, 8",
                "role_title": "Heavyweight Desktop Copilot & Strategy Planner",
                "role_description": "High-capacity deep intelligence engine for multi-step browser workflows and natural narrative writing.",
                "assigned_tasks": [
                    "⎔ High-Complexity Task Planning",
                    "✍ Long-Form Persona Narrative & Query Synthesizer",
                    "🛡 Advanced Anti-Detect Strategic Audit"
                ],
                "size_str": "4.5 GB",
                "params": "7.6B",
                "typical_latency": "~420 ms",
                "status": "IDLE",
                "current_task": "Standby / Ready",
                "current_target": "",
                "last_active_time": "Never",
                "total_calls": 0,
                "total_time_ms": 0.0,
                "success_count": 0,
                "error_count": 0,
                "last_duration_ms": 0.0,
                "last_result": "",
                "is_active": False
            },
            "hermes-3:3b": {
                "id": "hermes-3:3b",
                "display_name": "Nous Hermes 3 (3B)",
                "family": "Agentic-Tools",
                "icon": "⚡",
                "color": "#f97316",  # Orange
                "accent_rgb": "249, 115, 22",
                "role_title": "Agentic Tool-Calling & Autonomous Function Planner",
                "role_description": "Specialized in transforming natural language user intentions into exact JSON tool calls and Playwright steps.",
                "assigned_tasks": [
                    "⚡ Structured JSON Tool Execution",
                    "⚙ Multi-Step Browser Function Calling",
                    "⛭ Autonomous Playwright Workflow Synthesis"
                ],
                "size_str": "2.0 GB",
                "params": "3.2B",
                "typical_latency": "~210 ms",
                "status": "IDLE",
                "current_task": "Standby / Ready",
                "current_target": "",
                "last_active_time": "Never",
                "total_calls": 0,
                "total_time_ms": 0.0,
                "success_count": 0,
                "error_count": 0,
                "last_duration_ms": 0.0,
                "last_result": "",
                "is_active": False
            },
            "granite3-dense:2b": {
                "id": "granite3-dense:2b",
                "display_name": "IBM Granite 3 (2B)",
                "family": "DOM-Code",
                "icon": "⛯",
                "color": "#3b82f6",  # Blue
                "accent_rgb": "59, 130, 246",
                "role_title": "High-Reliability DOM & Script Code Extraktor",
                "role_description": "Enterprise-grade HTML/DOM element parsing, XPath optimization, and resilient selector generation.",
                "assigned_tasks": [
                    "⛯ Shadow DOM Selector Synthesis",
                    "⚇ Deterministic Consent Node Parser",
                    "⌨ JavaScript Injection Scripting"
                ],
                "size_str": "1.5 GB",
                "params": "2.5B",
                "typical_latency": "~160 ms",
                "status": "IDLE",
                "current_task": "Standby / Ready",
                "current_target": "",
                "last_active_time": "Never",
                "total_calls": 0,
                "total_time_ms": 0.0,
                "success_count": 0,
                "error_count": 0,
                "last_duration_ms": 0.0,
                "last_result": "",
                "is_active": False
            },
            "got-ocr2": {
                "id": "got-ocr2",
                "display_name": "GOT-OCR 2.0",
                "family": "Dense-OCR",
                "icon": "🔤",
                "color": "#ec4899",  # Pink
                "accent_rgb": "236, 72, 153",
                "role_title": "General OCR Theory for Distorted Captcha Text",
                "role_description": "Fine-grained optical character recognition on obscured, rotated, or noisy text captchas and web banners.",
                "assigned_tasks": [
                    "🔤 Distorted Captcha Text Extraction",
                    "▨ Rotated & Obscured Text Decoding",
                    "📄 High-Density Viewport OCR"
                ],
                "size_str": "1.4 GB",
                "params": "1.4B",
                "typical_latency": "~190 ms",
                "status": "IDLE",
                "current_task": "Standby / Ready",
                "current_target": "",
                "last_active_time": "Never",
                "total_calls": 0,
                "total_time_ms": 0.0,
                "success_count": 0,
                "error_count": 0,
                "last_duration_ms": 0.0,
                "last_result": "",
                "is_active": False
            },
            "florence-2-base": {
                "id": "florence-2-base",
                "display_name": "Florence-2 Base (ONNX)",
                "family": "Fast-Vision",
                "icon": "🎯",
                "color": "#06b6d4",  # Cyan
                "accent_rgb": "6, 182, 212",
                "role_title": "Sub-80ms UI 2D Bounding-Box Grounding",
                "role_description": "Ultra-lightweight spatial coordinate detector providing exact [x1, y1, x2, y2] bounding boxes for clicks.",
                "assigned_tasks": [
                    "🎯 Sub-80ms UI Element Coordinate Grounding",
                    "⎘ Real-Time Button & Input Localization",
                    "⚆ Lightweight Zero-VRAM Spatial OCR"
                ],
                "size_str": "230 MB",
                "params": "0.23B ONNX",
                "typical_latency": "~75 ms",
                "status": "IDLE",
                "current_task": "Standby / Ready",
                "current_target": "",
                "last_active_time": "Never",
                "total_calls": 0,
                "total_time_ms": 0.0,
                "success_count": 0,
                "error_count": 0,
                "last_duration_ms": 0.0,
                "last_result": "",
                "is_active": False
            },
            "sensevoice-small": {
                "id": "sensevoice-small",
                "display_name": "SenseVoice Small (Audio)",
                "family": "Fast-Audio",
                "icon": "🔊",
                "color": "#8b5cf6",  # Violet
                "accent_rgb": "139, 92, 246",
                "role_title": "Ultra-Fast Acoustic Audio Captcha STT (< 30ms)",
                "role_description": "High-speed multi-lingual speech challenge decoding with background noise filtering.",
                "assigned_tasks": [
                    "🔊 Sub-30ms Audio Challenge Transcription",
                    "⛿ Multi-Lingual Speech & Number Decoding",
                    "⚡ Background Noise & Acoustic Separation"
                ],
                "size_str": "200 MB",
                "params": "Small INT8",
                "typical_latency": "~28 ms",
                "status": "IDLE",
                "current_task": "Standby / Ready",
                "current_target": "",
                "last_active_time": "Never",
                "total_calls": 0,
                "total_time_ms": 0.0,
                "success_count": 0,
                "error_count": 0,
                "last_duration_ms": 0.0,
                "last_result": "",
                "is_active": False
            },
            "mouse-trajectory-onnx": {
                "id": "mouse-trajectory-onnx",
                "display_name": "Mouse Trajectory Gen (ONNX)",
                "family": "Biomechanical",
                "icon": "🖱",
                "color": "#10b981",  # Emerald
                "accent_rgb": "16, 185, 129",
                "role_title": "Biomechanical Human Motion & Fitts's Law Generator",
                "role_description": "1D-CNN tensor model generating physiological human mouse curves with micro-jitters and realistic acceleration.",
                "assigned_tasks": [
                    "🖱 Human-Like Fitts's Law Mouse Trajectories",
                    "〰 Micro-Jitter & Physiological Overshoot Synthesis",
                    "⚡ Sub-Millisecond (<1ms) Curve Computation"
                ],
                "size_str": "< 5 MB",
                "params": "1D-CNN ONNX",
                "typical_latency": "< 1 ms",
                "status": "IDLE",
                "current_task": "Standby / Ready",
                "current_target": "",
                "last_active_time": "Never",
                "total_calls": 0,
                "total_time_ms": 0.0,
                "success_count": 0,
                "error_count": 0,
                "last_duration_ms": 0.0,
                "last_result": "",
                "is_active": False
            }
        }

    @classmethod
    def get_instance(cls) -> 'AITelemetryBus':
        if cls._instance is None:
            cls._instance = AITelemetryBus()
        return cls._instance

    def _normalize_model_id(self, model_id: Optional[str]) -> str:
        if not model_id:
            return "qwen2.5:1.5b"
        m = model_id.lower().strip()
        if "trajectory" in m or "mouse" in m:
            return "mouse-trajectory-onnx"
        if "florence" in m:
            return "florence-2-base"
        if "sensevoice" in m:
            return "sensevoice-small"
        if "got-ocr" in m or "got_ocr" in m:
            return "got-ocr2"
        if "hermes" in m:
            return "hermes-3:3b"
        if "granite" in m:
            return "granite3-dense:2b"
        if "onnx" in m or "anomaly" in m or "sentinel" in m or "feature" in m:
            return "onnx-anomaly"
        if "gemini" in m:
            return "gemini-3.6-flash"
        if "deepseek" in m or "r1" in m:
            return "deepseek-r1:1.5b"
        if "coder" in m:
            return "qwen2.5-coder:1.5b"
        if "moondream" in m or "smol" in m:
            return "moondream:v2"
        if "vl" in m:
            return "qwen2.5vl:3b"
        if "llava" in m:
            return "llava:7b"
        if "whisper" in m or "audio" in m or "stt" in m:
            return "faster-whisper"
        if "7b" in m:
            return "qwen2.5:7b"
        if "0.5b" in m:
            return "qwen2.5:0.5b"
        if "3b" in m:
            return "qwen2.5:3b"
        if "1.5b" in m or "qwen" in m:
            return "qwen2.5:1.5b"
        return "qwen2.5:1.5b"



    def record_start(
        self,
        model_id: str,
        operation: str,
        prompt_summary: str = "",
        target_info: str = "",
        meta: Optional[Dict[str, Any]] = None
    ):
        """Records the beginning of an AI model operation."""
        norm_id = self._normalize_model_id(model_id)
        model_info = self.models_meta.get(norm_id)
        if not model_info:
            return

        model_info["is_active"] = True
        model_info["status"] = "ACTIVE"
        model_info["current_task"] = operation
        model_info["current_target"] = target_info
        model_info["last_prompt_snippet"] = prompt_summary[:120] if prompt_summary else ""

        meta_dict = meta or {}
        meta_dict["target"] = target_info
        meta_dict["start_timestamp"] = time.time()

        try:
            self.relay.model_activity_started.emit(norm_id, operation, prompt_summary, meta_dict)
            self.relay.telemetry_updated.emit()
        except Exception:
            pass

    def record_finish(
        self,
        model_id: str,
        operation: str,
        duration_ms: float,
        status: str = "SUCCESS",
        result_summary: str = "",
        meta: Optional[Dict[str, Any]] = None
    ):
        """Records the completion of an AI model operation."""
        norm_id = self._normalize_model_id(model_id)
        model_info = self.models_meta.get(norm_id)
        if not model_info:
            return

        model_info["is_active"] = False
        model_info["status"] = "IDLE" if status == "SUCCESS" else "ERROR"
        model_info["total_calls"] += 1
        model_info["total_time_ms"] += duration_ms
        model_info["last_duration_ms"] = duration_ms
        model_info["last_result"] = result_summary[:150] if result_summary else ""
        
        now_str = time.strftime("%H:%M:%S")
        model_info["last_active_time"] = now_str

        if status == "SUCCESS":
            model_info["success_count"] += 1
        else:
            model_info["error_count"] += 1

        meta_dict = meta or {}
        
        # Append to telemetry history
        event_entry = {
            "timestamp": now_str,
            "model_id": norm_id,
            "model_name": model_info["display_name"],
            "operation": operation,
            "target": model_info.get("current_target", ""),
            "duration_ms": duration_ms,
            "status": status,
            "result_summary": result_summary,
            "prompt_snippet": model_info.get("last_prompt_snippet", ""),
            "meta": meta_dict
        }

        self.history.insert(0, event_entry)
        if len(self.history) > self.max_history:
            self.history.pop()

        try:
            self.relay.model_activity_finished.emit(norm_id, operation, duration_ms, status, result_summary, meta_dict)
            self.relay.telemetry_updated.emit()
        except Exception:
            pass

    def get_model_stats(self, model_id: str) -> Optional[Dict[str, Any]]:
        norm_id = self._normalize_model_id(model_id)
        return self.models_meta.get(norm_id)

    def get_all_models_stats(self) -> Dict[str, Dict[str, Any]]:
        return self.models_meta

    def get_history(self) -> List[Dict[str, Any]]:
        return list(self.history)

    def clear_history(self):
        self.history.clear()
        try:
            self.relay.telemetry_updated.emit()
        except Exception:
            pass
