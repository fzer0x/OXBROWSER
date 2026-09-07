import os
import json
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger("AIModelConfigManager")

CONFIG_FILE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "storage",
    "ai_model_configs.json"
)

# Standard baseline configurations for all 18 AI models across the swarm
DEFAULT_MODEL_CONFIGS: Dict[str, Dict[str, Any]] = {
    "qwen2.5:0.5b": {
        "temperature": 0.1,
        "top_p": 0.9,
        "top_k": 40,
        "repeat_penalty": 1.1,
        "presence_penalty": 0.0,
        "frequency_penalty": 0.0,
        "mirostat": 0,
        "mirostat_tau": 5.0,
        "mirostat_eta": 0.1,
        "num_ctx": 4096,
        "num_predict": 512,
        "num_gpu": -1,
        "num_thread": 0,
        "keep_alive": "15m",
        "flash_attention": True,
        "system_prompt": "You are a fast cognitive psychology dwell-time estimator and micro-DOM parser. Analyze webpage content and estimate human reading duration accurately. Always output valid JSON when requested.",
        "json_mode": True,
        "stop_sequences": ["<|im_end|>", "</s>"],
        "swarm_priority": "Primary",
        "capabilities": ["Reading Dwell Time", "Content Density", "Micro-DOM Parsing"],
        "timeout_seconds": 10,
        "fallback_model": "qwen2.5:1.5b"
    },
    "qwen2.5:1.5b": {
        "temperature": 0.05,
        "top_p": 0.85,
        "top_k": 40,
        "repeat_penalty": 1.1,
        "presence_penalty": 0.0,
        "frequency_penalty": 0.0,
        "mirostat": 0,
        "mirostat_tau": 5.0,
        "mirostat_eta": 0.1,
        "num_ctx": 4096,
        "num_predict": 1024,
        "num_gpu": -1,
        "num_thread": 0,
        "keep_alive": "30m",
        "flash_attention": True,
        "system_prompt": "You are a high-precision GDPR and ePrivacy consent solver. Identify strict reject, necessary-only, or essential buttons in cookie banners and DOM elements. Return structured candidate selection.",
        "json_mode": True,
        "stop_sequences": ["<|im_end|>", "</s>"],
        "swarm_priority": "Primary",
        "capabilities": ["GDPR Consent Resolution", "Shadow DOM Parsing", "Navigation Filtering"],
        "timeout_seconds": 15,
        "fallback_model": "deepseek-r1:1.5b"
    },
    "qwen2.5:3b": {
        "temperature": 0.35,
        "top_p": 0.9,
        "top_k": 50,
        "repeat_penalty": 1.15,
        "presence_penalty": 0.1,
        "frequency_penalty": 0.1,
        "mirostat": 0,
        "mirostat_tau": 5.0,
        "mirostat_eta": 0.1,
        "num_ctx": 8192,
        "num_predict": 2048,
        "num_gpu": -1,
        "num_thread": 0,
        "keep_alive": "30m",
        "flash_attention": True,
        "system_prompt": "You are an autonomous web trajectory planner and human simulation strategist. Maintain thematic consistency ('Roter Faden') across multi-hop browsing sessions and generate authentic search queries.",
        "json_mode": False,
        "stop_sequences": ["<|im_end|>", "</s>"],
        "swarm_priority": "Primary",
        "capabilities": ["Topic Intent Coherence", "Search Query Synthesis", "Clickstream Trajectory"],
        "timeout_seconds": 25,
        "fallback_model": "qwen2.5:7b"
    },
    "qwen2.5:7b": {
        "temperature": 0.4,
        "top_p": 0.92,
        "top_k": 50,
        "repeat_penalty": 1.15,
        "presence_penalty": 0.15,
        "frequency_penalty": 0.15,
        "mirostat": 0,
        "mirostat_tau": 5.0,
        "mirostat_eta": 0.1,
        "num_ctx": 8192,
        "num_predict": 4096,
        "num_gpu": -1,
        "num_thread": 0,
        "keep_alive": "15m",
        "flash_attention": True,
        "system_prompt": "You are a senior browser copilot and stealth strategist. Formulate complex automation workflows, analyze deep digital fingerprints, and compose authentic natural language browsing narratives.",
        "json_mode": False,
        "stop_sequences": ["<|im_end|>", "</s>"],
        "swarm_priority": "Secondary",
        "capabilities": ["Heavyweight Desktop Copilot", "Long-Form Persona Writing", "Anti-Detect Audit"],
        "timeout_seconds": 45,
        "fallback_model": "gemini-3.6-flash"
    },
    "deepseek-r1:1.5b": {
        "temperature": 0.6,
        "top_p": 0.95,
        "top_k": 60,
        "repeat_penalty": 1.1,
        "presence_penalty": 0.0,
        "frequency_penalty": 0.0,
        "mirostat": 0,
        "mirostat_tau": 5.0,
        "mirostat_eta": 0.1,
        "num_ctx": 8192,
        "num_predict": 4096,
        "num_gpu": -1,
        "num_thread": 0,
        "keep_alive": "30m",
        "flash_attention": True,
        "system_prompt": "You are a chain-of-thought anti-bot reasoning specialist. Perform rigorous multi-step cognitive analysis inside <think>...</think> blocks, then synthesize evasive rules and optimal browser actions.",
        "json_mode": False,
        "stop_sequences": ["<|im_end|>", "</s>"],
        "swarm_priority": "Primary",
        "capabilities": ["CoT Anti-Bot Reasoning", "Deep Intent Synthesis", "Countermeasure Strategy"],
        "timeout_seconds": 25,
        "fallback_model": "gemini-3.6-flash"
    },
    "qwen2.5-coder:1.5b": {
        "temperature": 0.0,
        "top_p": 0.8,
        "top_k": 30,
        "repeat_penalty": 1.05,
        "presence_penalty": 0.0,
        "frequency_penalty": 0.0,
        "mirostat": 0,
        "mirostat_tau": 5.0,
        "mirostat_eta": 0.1,
        "num_ctx": 4096,
        "num_predict": 2048,
        "num_gpu": -1,
        "num_thread": 0,
        "keep_alive": "30m",
        "flash_attention": True,
        "system_prompt": "You are an elite DOM engineer and JavaScript automation specialist. Generate error-free CSS selectors, XPath queries, and injected scripts to pierce Shadow DOM v2 boundaries without tripping bot detectors.",
        "json_mode": True,
        "stop_sequences": ["<|im_end|>", "</s>"],
        "swarm_priority": "Primary",
        "capabilities": ["Shadow DOM Scripting", "DOM Structure Analysis", "JS Injection Synthesis"],
        "timeout_seconds": 15,
        "fallback_model": "granite3-dense:2b"
    },
    "hermes-3:3b": {
        "temperature": 0.1,
        "top_p": 0.85,
        "top_k": 40,
        "repeat_penalty": 1.1,
        "presence_penalty": 0.0,
        "frequency_penalty": 0.0,
        "mirostat": 0,
        "mirostat_tau": 5.0,
        "mirostat_eta": 0.1,
        "num_ctx": 8192,
        "num_predict": 1024,
        "num_gpu": -1,
        "num_thread": 0,
        "keep_alive": "20m",
        "flash_attention": True,
        "system_prompt": "You are an autonomous function-calling and tool-execution planner. Convert user requirements into precise JSON schema function calls for Playwright and browser automation drivers.",
        "json_mode": True,
        "stop_sequences": ["<|im_end|>", "</s>"],
        "swarm_priority": "Secondary",
        "capabilities": ["Structured Tool Execution", "Function Calling", "Playwright Workflow Synthesis"],
        "timeout_seconds": 20,
        "fallback_model": "qwen2.5-coder:1.5b"
    },
    "hermes3:3b": {
        "temperature": 0.1,
        "top_p": 0.85,
        "top_k": 40,
        "repeat_penalty": 1.1,
        "presence_penalty": 0.0,
        "frequency_penalty": 0.0,
        "mirostat": 0,
        "mirostat_tau": 5.0,
        "mirostat_eta": 0.1,
        "num_ctx": 8192,
        "num_predict": 1024,
        "num_gpu": -1,
        "num_thread": 0,
        "keep_alive": "20m",
        "flash_attention": True,
        "system_prompt": "You are an autonomous function-calling and tool-execution planner. Convert user requirements into precise JSON schema function calls for Playwright and browser automation drivers.",
        "json_mode": True,
        "stop_sequences": ["<|im_end|>", "</s>"],
        "swarm_priority": "Secondary",
        "capabilities": ["Structured Tool Execution", "Function Calling", "Playwright Workflow Synthesis"],
        "timeout_seconds": 20,
        "fallback_model": "qwen2.5-coder:1.5b"
    },
    "granite3-dense:2b": {
        "temperature": 0.0,
        "top_p": 0.8,
        "top_k": 30,
        "repeat_penalty": 1.05,
        "presence_penalty": 0.0,
        "frequency_penalty": 0.0,
        "mirostat": 0,
        "mirostat_tau": 5.0,
        "mirostat_eta": 0.1,
        "num_ctx": 8192,
        "num_predict": 1024,
        "num_gpu": -1,
        "num_thread": 0,
        "keep_alive": "20m",
        "flash_attention": True,
        "system_prompt": "You are a deterministic HTML and DOM schema extractor. Parse input elements, form tags, and consent structures with 100% syntactic precision.",
        "json_mode": True,
        "stop_sequences": ["<|im_end|>", "</s>"],
        "swarm_priority": "Fallback",
        "capabilities": ["Deterministic DOM Extraction", "Shadow DOM Parsing", "Schema Generation"],
        "timeout_seconds": 15,
        "fallback_model": "qwen2.5-coder:1.5b"
    },
    "qwen2.5vl:3b": {
        "temperature": 0.1,
        "top_p": 0.85,
        "top_k": 40,
        "repeat_penalty": 1.1,
        "presence_penalty": 0.0,
        "frequency_penalty": 0.0,
        "mirostat": 0,
        "mirostat_tau": 5.0,
        "mirostat_eta": 0.1,
        "num_ctx": 8192,
        "num_predict": 1024,
        "num_gpu": -1,
        "num_thread": 0,
        "keep_alive": "30m",
        "flash_attention": True,
        "system_prompt": "You are a multimodal vision grounding model. Detect visual UI elements, bounding boxes [ymin, xmin, ymax, xmax], and solve captcha challenge grids accurately.",
        "json_mode": False,
        "stop_sequences": ["<|im_end|>", "</s>"],
        "swarm_priority": "Primary",
        "capabilities": ["Multimodal Coordinate Grounding", "reCAPTCHA Tile Analysis", "Visual Anomaly Identification"],
        "timeout_seconds": 30,
        "fallback_model": "gemini-3.6-flash"
    },
    "moondream:v2": {
        "temperature": 0.1,
        "top_p": 0.85,
        "top_k": 30,
        "repeat_penalty": 1.1,
        "presence_penalty": 0.0,
        "frequency_penalty": 0.0,
        "mirostat": 0,
        "mirostat_tau": 5.0,
        "mirostat_eta": 0.1,
        "num_ctx": 4096,
        "num_predict": 512,
        "num_gpu": -1,
        "num_thread": 0,
        "keep_alive": "20m",
        "flash_attention": True,
        "system_prompt": "You are an ultra-fast computer vision OCR assistant. Read on-screen text, verify visual banners, and describe UI components concisely.",
        "json_mode": False,
        "stop_sequences": ["<|im_end|>", "</s>"],
        "swarm_priority": "Primary",
        "capabilities": ["Fast Viewport OCR", "Visual Element Grounding", "Banner Verification"],
        "timeout_seconds": 15,
        "fallback_model": "qwen2.5vl:3b"
    },
    "llava:7b": {
        "temperature": 0.15,
        "top_p": 0.9,
        "top_k": 40,
        "repeat_penalty": 1.15,
        "presence_penalty": 0.0,
        "frequency_penalty": 0.0,
        "mirostat": 0,
        "mirostat_tau": 5.0,
        "mirostat_eta": 0.1,
        "num_ctx": 4096,
        "num_predict": 512,
        "num_gpu": -1,
        "num_thread": 0,
        "keep_alive": "15m",
        "flash_attention": True,
        "system_prompt": "You are a spatial vision specialist for high-resolution 3x3 and 4x4 reCAPTCHA classification. Identify requested target objects with extreme precision.",
        "json_mode": True,
        "stop_sequences": ["<|im_end|>", "</s>"],
        "swarm_priority": "Secondary",
        "capabilities": ["reCAPTCHA Spatial Grid Solver", "Subpixel Grounding", "Visual Anomaly Detection"],
        "timeout_seconds": 45,
        "fallback_model": "gemini-3.6-flash"
    },
    "florence-2-base": {
        "temperature": 0.0,
        "top_p": 0.8,
        "top_k": 20,
        "repeat_penalty": 1.0,
        "presence_penalty": 0.0,
        "frequency_penalty": 0.0,
        "mirostat": 0,
        "mirostat_tau": 5.0,
        "mirostat_eta": 0.1,
        "num_ctx": 2048,
        "num_predict": 256,
        "num_gpu": 0,
        "num_thread": 4,
        "keep_alive": "30m",
        "flash_attention": False,
        "system_prompt": "Sub-80ms spatial 2D bounding box detector [x1, y1, x2, y2].",
        "json_mode": True,
        "stop_sequences": [],
        "swarm_priority": "Primary",
        "capabilities": ["Sub-80ms UI Grounding", "2D Bounding Boxes", "Zero-VRAM Spatial OCR"],
        "timeout_seconds": 8,
        "fallback_model": "moondream:v2"
    },
    "got-ocr2": {
        "temperature": 0.0,
        "top_p": 0.8,
        "top_k": 20,
        "repeat_penalty": 1.0,
        "presence_penalty": 0.0,
        "frequency_penalty": 0.0,
        "mirostat": 0,
        "mirostat_tau": 5.0,
        "mirostat_eta": 0.1,
        "num_ctx": 2048,
        "num_predict": 256,
        "num_gpu": -1,
        "num_thread": 0,
        "keep_alive": "15m",
        "flash_attention": True,
        "system_prompt": "Dense optical character recognition for distorted text captchas and noisy banners.",
        "json_mode": False,
        "stop_sequences": [],
        "swarm_priority": "Primary",
        "capabilities": ["Distorted Captcha OCR", "Rotated Text Extraction", "Dense Viewport OCR"],
        "timeout_seconds": 12,
        "fallback_model": "moondream:v2"
    },
    "faster-whisper": {
        "temperature": 0.0,
        "top_p": 0.8,
        "top_k": 20,
        "repeat_penalty": 1.0,
        "presence_penalty": 0.0,
        "frequency_penalty": 0.0,
        "mirostat": 0,
        "mirostat_tau": 5.0,
        "mirostat_eta": 0.1,
        "num_ctx": 2048,
        "num_predict": 256,
        "num_gpu": 0,
        "num_thread": 4,
        "keep_alive": "30m",
        "flash_attention": False,
        "system_prompt": "Acoustic speech-to-text decoder for reCAPTCHA/hCaptcha audio fallback bypass.",
        "json_mode": False,
        "stop_sequences": [],
        "swarm_priority": "Primary",
        "capabilities": ["reCAPTCHA Audio STT", "Voice Activity Detection", "Multi-lingual Speech STT"],
        "timeout_seconds": 10,
        "fallback_model": "sensevoice-small"
    },
    "sensevoice-small": {
        "temperature": 0.0,
        "top_p": 0.8,
        "top_k": 20,
        "repeat_penalty": 1.0,
        "presence_penalty": 0.0,
        "frequency_penalty": 0.0,
        "mirostat": 0,
        "mirostat_tau": 5.0,
        "mirostat_eta": 0.1,
        "num_ctx": 1024,
        "num_predict": 128,
        "num_gpu": 0,
        "num_thread": 4,
        "keep_alive": "30m",
        "flash_attention": False,
        "system_prompt": "Sub-30ms ultra-fast acoustic captcha speech decoder.",
        "json_mode": False,
        "stop_sequences": [],
        "swarm_priority": "Primary",
        "capabilities": ["Sub-30ms Audio Challenge STT", "Multi-Lingual Numbers", "Noise Separation"],
        "timeout_seconds": 6,
        "fallback_model": "faster-whisper"
    },
    "onnx-anomaly": {
        "temperature": 0.0,
        "top_p": 1.0,
        "top_k": 1,
        "repeat_penalty": 1.0,
        "presence_penalty": 0.0,
        "frequency_penalty": 0.0,
        "mirostat": 0,
        "mirostat_tau": 5.0,
        "mirostat_eta": 0.1,
        "num_ctx": 512,
        "num_predict": 64,
        "num_gpu": 0,
        "num_thread": 2,
        "keep_alive": "-1",
        "flash_attention": False,
        "system_prompt": "Sub-millisecond mathematical feature tensor evaluation of browser fingerprint anomalies.",
        "json_mode": True,
        "stop_sequences": [],
        "swarm_priority": "Primary",
        "capabilities": ["Fingerprint Anomaly Detection", "Hardware Harmony Audit", "Sub-Millisecond CPU Inference"],
        "timeout_seconds": 2,
        "fallback_model": "qwen2.5:7b"
    },
    "mouse-trajectory-onnx": {
        "temperature": 0.0,
        "top_p": 1.0,
        "top_k": 1,
        "repeat_penalty": 1.0,
        "presence_penalty": 0.0,
        "frequency_penalty": 0.0,
        "mirostat": 0,
        "mirostat_tau": 5.0,
        "mirostat_eta": 0.1,
        "num_ctx": 512,
        "num_predict": 64,
        "num_gpu": 0,
        "num_thread": 2,
        "keep_alive": "-1",
        "flash_attention": False,
        "system_prompt": "1D-CNN tensor biomechanical mouse curve generator with Fitts's law simulation.",
        "json_mode": True,
        "stop_sequences": [],
        "swarm_priority": "Primary",
        "capabilities": ["Biomechanical Fitts's Law Curves", "Micro-Jitter Synthesis", "Sub-Millisecond Computation"],
        "timeout_seconds": 2,
        "fallback_model": "qwen2.5:3b"
    },
    "gemini-3.6-flash": {
        "temperature": 0.1,
        "top_p": 0.9,
        "top_k": 40,
        "repeat_penalty": 1.0,
        "presence_penalty": 0.0,
        "frequency_penalty": 0.0,
        "mirostat": 0,
        "mirostat_tau": 5.0,
        "mirostat_eta": 0.1,
        "num_ctx": 32768,
        "num_predict": 4096,
        "num_gpu": 0,
        "num_thread": 0,
        "keep_alive": "cloud",
        "flash_attention": True,
        "system_prompt": "You are Google Gemini 3.6 Flash. Provide lightning-fast multimodal reasoning, one-shot reCAPTCHA grid classification, and high-level agentic task orchestration without GPU memory footprint.",
        "json_mode": True,
        "stop_sequences": [],
        "swarm_priority": "Primary",
        "capabilities": ["One-Shot reCAPTCHA Grid Solver", "Zero-VRAM Cloud Fallback", "Multimodal Grounding", "Agentic Trajectory Reasoning"],
        "timeout_seconds": 15,
        "fallback_model": "qwen2.5:1.5b"
    }
}


class AIModelConfigManager:
    """
    Central Manager for persistent per-model configuration profiles in SoxBot.
    Handles loading, storing, validating and merging custom hyperparameters.
    """
    _instance: Optional['AIModelConfigManager'] = None

    def __init__(self):
        self._configs: Dict[str, Dict[str, Any]] = {}
        self.load_configs()

    @classmethod
    def get_instance(cls) -> 'AIModelConfigManager':
        if cls._instance is None:
            cls._instance = AIModelConfigManager()
        return cls._instance

    def load_configs(self):
        """Loads configuration from persistent storage file or initializes with defaults."""
        self._configs = {}
        if os.path.exists(CONFIG_FILE_PATH):
            try:
                with open(CONFIG_FILE_PATH, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    if isinstance(saved, dict):
                        self._configs = saved
            except Exception as e:
                logger.warning(f"Failed to load {CONFIG_FILE_PATH}: {e}")

        # Ensure all models have default keys populated
        for model_id, default_cfg in DEFAULT_MODEL_CONFIGS.items():
            if model_id not in self._configs:
                self._configs[model_id] = dict(default_cfg)
            else:
                # Merge missing keys from default_cfg into saved config
                for k, v in default_cfg.items():
                    if k not in self._configs[model_id]:
                        self._configs[model_id][k] = v

    def save_configs(self):
        """Persists current configuration dictionary to disk."""
        try:
            os.makedirs(os.path.dirname(CONFIG_FILE_PATH), exist_ok=True)
            with open(CONFIG_FILE_PATH, "w", encoding="utf-8") as f:
                json.dump(self._configs, f, indent=2, ensure_ascii=False)
            logger.info("AI model configuration saved successfully.")
        except Exception as e:
            logger.error(f"Failed to save AI model configuration to {CONFIG_FILE_PATH}: {e}")

    def get_model_config(self, model_id: str) -> Dict[str, Any]:
        """Returns the configuration dictionary for the specified model (or defaults)."""
        if not model_id:
            return dict(DEFAULT_MODEL_CONFIGS.get("qwen2.5:1.5b", {}))

        # Check exact or normalized key
        from engine.ai_telemetry import AITelemetryBus
        norm_id = AITelemetryBus.get_instance()._normalize_model_id(model_id)

        if norm_id in self._configs:
            return dict(self._configs[norm_id])
        elif norm_id in DEFAULT_MODEL_CONFIGS:
            return dict(DEFAULT_MODEL_CONFIGS[norm_id])
        return dict(DEFAULT_MODEL_CONFIGS.get("qwen2.5:1.5b", {}))

    def save_model_config(self, model_id: str, new_config: Dict[str, Any]):
        """Updates and persists the configuration for a specific model."""
        from engine.ai_telemetry import AITelemetryBus
        norm_id = AITelemetryBus.get_instance()._normalize_model_id(model_id)

        current = self.get_model_config(norm_id)
        current.update(new_config)
        self._configs[norm_id] = current
        self.save_configs()

    def reset_model_config(self, model_id: str) -> Dict[str, Any]:
        """Resets the model configuration to its default baseline."""
        from engine.ai_telemetry import AITelemetryBus
        norm_id = AITelemetryBus.get_instance()._normalize_model_id(model_id)

        if norm_id in DEFAULT_MODEL_CONFIGS:
            self._configs[norm_id] = dict(DEFAULT_MODEL_CONFIGS[norm_id])
            self.save_configs()
            return dict(self._configs[norm_id])
        return {}

    def get_all_configs(self) -> Dict[str, Dict[str, Any]]:
        """Returns snapshot of all model configurations."""
        return {k: dict(v) for k, v in self._configs.items()}
