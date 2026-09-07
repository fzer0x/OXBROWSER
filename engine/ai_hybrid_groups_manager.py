import os
import json
import time
import uuid
import copy
import logging
from typing import Dict, Any, List, Optional, Tuple

import config

logger = logging.getLogger("AIHybridGroupsManager")

HYBRID_GROUPS_STORAGE_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "storage",
    "ai_hybrid_groups.json"
)

# Standard Role Definitions with User-Friendly Labels & Category Groupings
SWARM_ROLE_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "key": "text_model",
        "label": "Text & Chat Specialist",
        "category": "core",
        "description": "Hauptmodell für interaktive Dialoge, Chat-Prompting und allgemeine Textgenerierung.",
        "recommended": ["qwen2.5:1.5b", "qwen2.5:3b", "qwen2.5:7b", "gemini-3.6-flash"]
    },
    {
        "key": "reasoning_model",
        "label": "Deep CoT Reasoning Specialist",
        "category": "logic",
        "description": "Chain-of-Thought Modell für komplexe Evasionslogik, Anti-Bot-Analyse & tiefe Schlussfolgerungen.",
        "recommended": ["deepseek-r1:1.5b", "hermes-3:3b", "gemini-1.5-pro"]
    },
    {
        "key": "coder_model",
        "label": "DOM & Code Scripting Specialist",
        "category": "dom",
        "description": "Experte für DOM-Injektionen, CSS/XPath-Selektor-Generierung und JavaScript-Skript-Reparatur.",
        "recommended": ["qwen2.5-coder:1.5b", "granite3-dense:2b"]
    },
    {
        "key": "vision_model",
        "label": "Fast Vision & Viewport OCR",
        "category": "vision",
        "description": "Sub-200ms schnelles multimodales Modell für Viewport-Scanning, Header-OCR und UI-Element-Erkennung.",
        "recommended": ["moondream:v2", "smolvlm", "florence-2-base", "got-ocr2", "qwen2.5vl:3b"]
    },
    {
        "key": "heavy_vision_model",
        "label": "Heavy Spatial & Captcha Vision",
        "category": "vision",
        "description": "Hochpräzise räumliche Bildanalyse für reCAPTCHA 3x3/4x4 Kachel-Klassifikation und visuelle Bounding-Boxes.",
        "recommended": ["llava:7b", "qwen2.5vl:3b", "gemini-3.6-flash"]
    },
    {
        "key": "strategy_model",
        "label": "Persona & Clickstream Strategist",
        "category": "trajectory",
        "description": "Plant browsing trajectories, synthetisiert organische Suchanfragen und sichert den 'Roten Faden'.",
        "recommended": ["qwen2.5:3b", "qwen2.5:7b", "gemini-3.6-flash"]
    },
    {
        "key": "micro_model",
        "label": "Micro-Scout & Dwell-Time Engine",
        "category": "scout",
        "description": "Ultra-schnelles Triage-Modell für Lesedauer-Schätzung, Content-Density und Vorfilterung.",
        "recommended": ["qwen2.5:0.5b", "qwen2.5:1.5b"]
    },
    {
        "key": "audio_model",
        "label": "Audio STT Challenge Specialist",
        "category": "audio",
        "description": "Spracherkennungs-Engine zur automatischen Lösung akustischer Captcha-Audiospuren.",
        "recommended": ["faster-whisper", "sensevoice-small"]
    },
    {
        "key": "sentinel_model",
        "label": "Stealth Sentinel & Anomaly Detector",
        "category": "sentinel",
        "description": "Mathematische Tensor- und Biomechanik-Prüfung für Fingerprint-Glaubwürdigkeit und Maus-Jitter.",
        "recommended": ["onnx-anomaly", "mouse-trajectory-onnx"]
    },
    {
        "key": "cloud_model",
        "label": "Cloud Burst & Zero-VRAM Fallback",
        "category": "cloud",
        "description": "Cloud-Beschleuniger für sofortiges Bursting ohne VRAM-Belastung oder als High-End-Fallback.",
        "recommended": ["gemini-3.6-flash", "gemini-1.5-flash", "gemini-1.5-pro", "none"]
    }
]

# Hardware VRAM & Latency Profiles per Model for accurate live computation
MODEL_HARDWARE_PROFILES: Dict[str, Dict[str, Any]] = {
    "qwen2.5:0.5b": {"vram_mb": 400, "latency_ms": 45, "tier": 0, "type": "local_llm"},
    "qwen2.5:1.5b": {"vram_mb": 986, "latency_ms": 120, "tier": 1, "type": "local_llm"},
    "qwen2.5:3b": {"vram_mb": 1950, "latency_ms": 260, "tier": 2, "type": "local_llm"},
    "qwen2.5:7b": {"vram_mb": 4600, "latency_ms": 480, "tier": 2, "type": "local_llm"},
    "deepseek-r1:1.5b": {"vram_mb": 1100, "latency_ms": 220, "tier": 1, "type": "local_llm"},
    "qwen2.5-coder:1.5b": {"vram_mb": 986, "latency_ms": 130, "tier": 1, "type": "local_llm"},
    "hermes-3:3b": {"vram_mb": 2050, "latency_ms": 240, "tier": 2, "type": "local_llm"},
    "granite3-dense:2b": {"vram_mb": 1500, "latency_ms": 180, "tier": 1, "type": "local_llm"},
    "qwen2.5vl:3b": {"vram_mb": 3200, "latency_ms": 350, "tier": 2, "type": "local_vision"},
    "moondream:v2": {"vram_mb": 1400, "latency_ms": 190, "tier": 1, "type": "local_vision"},
    "smolvlm": {"vram_mb": 1100, "latency_ms": 160, "tier": 1, "type": "local_vision"},
    "llava:7b": {"vram_mb": 4700, "latency_ms": 600, "tier": 2, "type": "local_vision"},
    "florence-2-base": {"vram_mb": 240, "latency_ms": 80, "tier": 0, "type": "local_vision"},
    "got-ocr2": {"vram_mb": 1450, "latency_ms": 120, "tier": 1, "type": "local_vision"},
    "faster-whisper": {"vram_mb": 145, "latency_ms": 90, "tier": 0, "type": "local_audio"},
    "sensevoice-small": {"vram_mb": 200, "latency_ms": 30, "tier": 0, "type": "local_audio"},
    "mouse-trajectory-onnx": {"vram_mb": 21, "latency_ms": 35, "tier": 0, "type": "onnx"},
    "onnx-anomaly": {"vram_mb": 1, "latency_ms": 2, "tier": 0, "type": "onnx"},
    "gemini-3.6-flash": {"vram_mb": 0, "latency_ms": 320, "tier": 3, "type": "cloud"},
    "gemini-1.5-flash": {"vram_mb": 0, "latency_ms": 280, "tier": 3, "type": "cloud"},
    "gemini-1.5-pro": {"vram_mb": 0, "latency_ms": 750, "tier": 3, "type": "cloud"},
    "none": {"vram_mb": 0, "latency_ms": 0, "tier": 0, "type": "disabled"}
}

# Built-in Default Hybrid Groups
BUILTIN_HYBRID_GROUPS: List[Dict[str, Any]] = [
    {
        "id": "swarm_auto_full",
        "name": "Auto-Full-Modus (7+1 Swarm Apex)",
        "description": "Vollständig synchronisiertes 7+1 KI-Team mit dynamischer VRAM-Arbiter-Steuerung und maximaler Evasionskraft.",
        "icon": "⫸",
        "accent_color": "#38bdf8",
        "is_builtin": True,
        "is_active": True,
        "created_at": 1771970000.0,
        "updated_at": 1771970000.0,
        "roles": {
            "text_model": "qwen2.5:1.5b",
            "reasoning_model": "deepseek-r1:1.5b",
            "coder_model": "qwen2.5-coder:1.5b",
            "vision_model": "gemini-3.6-flash",
            "heavy_vision_model": "gemini-3.6-flash",
            "strategy_model": "qwen2.5:3b",
            "micro_model": "qwen2.5:0.5b",
            "audio_model": "faster-whisper",
            "sentinel_model": "onnx-anomaly",
            "cloud_model": "gemini-3.6-flash"
        },
        "orchestration": {
            "vram_strategy": "dynamic_tier",
            "execution_mode": "cot_guided",
            "temperature": 0.15,
            "auto_fallback": True,
            "system_directive": "Operate as a synchronized cyber-evasion AI swarm with strict separation of concerns."
        }
    },
    {
        "id": "hybrid_deepseek_vision",
        "name": "DeepSeek R1 + Qwen VL Next-Gen",
        "description": "Kombiniert tiefste Chain-of-Thought Anti-Bot-Logik mit hochmoderner lokaler Vision-Grounding-Präzision.",
        "icon": "🧠",
        "accent_color": "#a855f7",
        "is_builtin": True,
        "is_active": False,
        "created_at": 1771970000.0,
        "updated_at": 1771970000.0,
        "roles": {
            "text_model": "deepseek-r1:1.5b",
            "reasoning_model": "deepseek-r1:1.5b",
            "coder_model": "qwen2.5-coder:1.5b",
            "vision_model": "qwen2.5vl:3b",
            "heavy_vision_model": "qwen2.5vl:3b",
            "strategy_model": "deepseek-r1:1.5b",
            "micro_model": "qwen2.5:0.5b",
            "audio_model": "faster-whisper",
            "sentinel_model": "onnx-anomaly",
            "cloud_model": "none"
        },
        "orchestration": {
            "vram_strategy": "dynamic_tier",
            "execution_mode": "cot_guided",
            "temperature": 0.6,
            "auto_fallback": True,
            "system_directive": "Execute structured cognitive reasoning before returning strategic evasive actions."
        }
    },
    {
        "id": "hybrid_coder_tactician",
        "name": "Coder Tactician & DOM Specialist",
        "description": "Spezialisiert auf Shadow DOM v2 Extraktion, Cookie-Consent-Schaltflächen-Injektion und strukturierte Schemas.",
        "icon": "💻",
        "accent_color": "#10b981",
        "is_builtin": True,
        "is_active": False,
        "created_at": 1771970000.0,
        "updated_at": 1771970000.0,
        "roles": {
            "text_model": "qwen2.5-coder:1.5b",
            "reasoning_model": "deepseek-r1:1.5b",
            "coder_model": "qwen2.5-coder:1.5b",
            "vision_model": "moondream:v2",
            "heavy_vision_model": "qwen2.5vl:3b",
            "strategy_model": "qwen2.5:3b",
            "micro_model": "qwen2.5:0.5b",
            "audio_model": "sensevoice-small",
            "sentinel_model": "onnx-anomaly",
            "cloud_model": "none"
        },
        "orchestration": {
            "vram_strategy": "resident_pinned",
            "execution_mode": "sequential_cascade",
            "temperature": 0.0,
            "auto_fallback": True,
            "system_directive": "Analyze DOM element hierarchies strictly and emit accurate JS execution directives."
        }
    },
    {
        "id": "hybrid_high_perf",
        "name": "High-Performance Heavyweight Swarm",
        "description": "Maximale Inferenz-Qualität mit 3B/7B Modellen für komplexe Workflows und anspruchsvolle Captchas.",
        "icon": "🚀",
        "accent_color": "#f59e0b",
        "is_builtin": True,
        "is_active": False,
        "created_at": 1771970000.0,
        "updated_at": 1771970000.0,
        "roles": {
            "text_model": "qwen2.5:3b",
            "reasoning_model": "qwen2.5:7b",
            "coder_model": "qwen2.5-coder:1.5b",
            "vision_model": "llava:7b",
            "heavy_vision_model": "llava:7b",
            "strategy_model": "qwen2.5:7b",
            "micro_model": "qwen2.5:1.5b",
            "audio_model": "faster-whisper",
            "sentinel_model": "mouse-trajectory-onnx",
            "cloud_model": "gemini-3.6-flash"
        },
        "orchestration": {
            "vram_strategy": "dynamic_tier",
            "execution_mode": "parallel_verified",
            "temperature": 0.35,
            "auto_fallback": True,
            "system_directive": "Prioritize strategic depth and multi-hop thematic consistency."
        }
    },
    {
        "id": "hybrid_eco",
        "name": "Eco-Fast & Lightweight Ensemble",
        "description": "Optimiert für niedrigen Speicherbedarf (~1.8GB VRAM) und minimale CPU-Auslastung auf Laptops.",
        "icon": "☘",
        "accent_color": "#34d399",
        "is_builtin": True,
        "is_active": False,
        "created_at": 1771970000.0,
        "updated_at": 1771970000.0,
        "roles": {
            "text_model": "qwen2.5:0.5b",
            "reasoning_model": "deepseek-r1:1.5b",
            "coder_model": "qwen2.5-coder:1.5b",
            "vision_model": "moondream:v2",
            "heavy_vision_model": "moondream:v2",
            "strategy_model": "qwen2.5:0.5b",
            "micro_model": "qwen2.5:0.5b",
            "audio_model": "sensevoice-small",
            "sentinel_model": "onnx-anomaly",

            "cloud_model": "none"
        },
        "orchestration": {
            "vram_strategy": "ultra_eco",
            "execution_mode": "sequential_cascade",
            "temperature": 0.1,
            "auto_fallback": True,
            "system_directive": "Execute fast, ultra-low latency heuristics with minimal memory footprint."
        }
    },
    {
        "id": "hybrid_gemini_vision",
        "name": "Local Text + Gemini Cloud Burst",
        "description": "Lokale Privatsphäre für Text/DOM kombiniert mit Google Gemini 3.6 Flash für Zero-VRAM Captchas.",
        "icon": "★",
        "accent_color": "#38bdf8",
        "is_builtin": True,
        "is_active": False,
        "created_at": 1771970000.0,
        "updated_at": 1771970000.0,
        "roles": {
            "text_model": "qwen2.5:1.5b",
            "reasoning_model": "deepseek-r1:1.5b",
            "coder_model": "qwen2.5-coder:1.5b",
            "vision_model": "gemini-3.6-flash",
            "heavy_vision_model": "gemini-3.6-flash",
            "strategy_model": "qwen2.5:3b",
            "micro_model": "qwen2.5:0.5b",
            "audio_model": "faster-whisper",
            "sentinel_model": "onnx-anomaly",
            "cloud_model": "gemini-3.6-flash"
        },
        "orchestration": {
            "vram_strategy": "cloud_zero_vram",
            "execution_mode": "parallel_verified",
            "temperature": 0.2,
            "auto_fallback": True,
            "system_directive": "Route high-resolution visual processing to cloud multimodal accelerator."
        }
    },
    {
        "id": "swarm_poker_grandmaster",
        "name": "Poker Grandmaster Multi-Task Swarm",
        "description": "Hochspezialisierter Multi-Task Swarm für Live-Poker & Games: Multi-Vision Table OCR, DeepSeek-R1 GTO Equity Matrix, Blocker-Exploits und Stealth Biomechanik.",
        "icon": "🃏",
        "accent_color": "#ef4444",
        "is_builtin": True,
        "is_active": False,
        "created_at": 1771970000.0,
        "updated_at": 1771970000.0,
        "roles": {
            "text_model": "qwen2.5:3b",
            "reasoning_model": "deepseek-r1:1.5b",
            "coder_model": "qwen2.5-coder:1.5b",
            "vision_model": "qwen2.5vl:3b",
            "heavy_vision_model": "gemini-3.6-flash",
            "strategy_model": "deepseek-r1:1.5b",
            "micro_model": "qwen2.5:0.5b",
            "audio_model": "faster-whisper",
            "sentinel_model": "mouse-trajectory-onnx",
            "cloud_model": "gemini-3.6-flash"
        },
        "orchestration": {
            "vram_strategy": "dynamic_tier",
            "execution_mode": "cot_guided",
            "temperature": 0.25,
            "auto_fallback": True,
            "system_directive": "Execute synchronized multi-task real-time game analysis: Extract cards with VLM, calculate GTO equity with DeepSeek-R1, and execute stealth humanized actions."
        }
    }
]


class AIHybridGroupsManager:
    """
    Central Manager for Defining, Storing, Validating, Calculating Hardware Budgets,
    and Orchestrating Custom Multi-Model AI Hybrid Groups in SoxBot.
    """

    _instance: Optional['AIHybridGroupsManager'] = None

    def __init__(self):
        self._groups: Dict[str, Dict[str, Any]] = {}
        self._active_group_id: str = "swarm_auto_full"
        self._load_groups()

    @classmethod
    def get_instance(cls) -> 'AIHybridGroupsManager':
        if cls._instance is None:
            cls._instance = AIHybridGroupsManager()
        return cls._instance

    def _load_groups(self):
        """Loads hybrid groups from persistent storage, merging built-in and custom entries."""
        self._groups.clear()
        
        # 1. Populate Built-in groups
        for g in BUILTIN_HYBRID_GROUPS:
            self._groups[g["id"]] = copy.deepcopy(g)

        # 2. Load from disk
        if os.path.exists(HYBRID_GROUPS_STORAGE_FILE):
            try:
                with open(HYBRID_GROUPS_STORAGE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        custom_groups = data.get("groups", {})
                        for gid, gdata in custom_groups.items():
                            if isinstance(gdata, dict):
                                gdata["is_builtin"] = False
                                self._groups[gid] = gdata
                        
                        saved_active = data.get("active_group_id")
                        if saved_active and saved_active in self._groups:
                            self._active_group_id = saved_active
            except Exception as e:
                logger.warning(f"[AIHybridGroupsManager] Could not read storage file: {e}")

        # 3. Synchronize active state
        for gid, g in self._groups.items():
            g["is_active"] = (gid == self._active_group_id)

    def _save_groups(self):
        """Persists custom hybrid groups and active group ID to disk and secrets vault."""
        try:
            os.makedirs(os.path.dirname(HYBRID_GROUPS_STORAGE_FILE), exist_ok=True)
            custom_only = {
                gid: g for gid, g in self._groups.items()
                if not g.get("is_builtin", False)
            }
            payload = {
                "active_group_id": self._active_group_id,
                "groups": custom_only,
                "version": "2.0.0",
                "updated_at": time.time()
            }
            with open(HYBRID_GROUPS_STORAGE_FILE, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            
            # Sync to vault if available
            try:
                from storage.secrets_manager import SecretsManager
                if SecretsManager.is_initialized():
                    SecretsManager.set("ai_active_hybrid_group", self._active_group_id)
                    SecretsManager.save()
            except Exception:
                pass

        except Exception as e:
            logger.error(f"[AIHybridGroupsManager] Failed to persist hybrid groups: {e}")

    # ----------------------------------------------------------------------------------
    # CRUD API
    # ----------------------------------------------------------------------------------

    def get_all_groups(self) -> List[Dict[str, Any]]:
        """Returns list of all hybrid groups (built-in + custom)."""
        return list(self._groups.values())

    def get_group(self, group_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a specific group by ID or alias."""
        clean_id = (group_id or "").lower().strip()
        if clean_id in self._groups:
            return copy.deepcopy(self._groups[clean_id])
        
        # Check by prefix or name
        for gid, g in self._groups.items():
            if gid.lower() == clean_id or g.get("name", "").lower() == clean_id:
                return copy.deepcopy(g)
        return None

    def get_active_group(self) -> Dict[str, Any]:
        """Returns the currently active hybrid group."""
        if self._active_group_id in self._groups:
            return copy.deepcopy(self._groups[self._active_group_id])
        return copy.deepcopy(BUILTIN_HYBRID_GROUPS[0])

    def set_active_group(self, group_id: str) -> bool:
        """Sets a hybrid group as active and updates all group states."""
        if group_id not in self._groups:
            logger.warning(f"[AIHybridGroupsManager] Cannot activate unknown group: {group_id}")
            return False
        
        self._active_group_id = group_id
        for gid, g in self._groups.items():
            g["is_active"] = (gid == group_id)
        
        self._save_groups()
        logger.info(f"[AIHybridGroupsManager] Activated hybrid group '{group_id}'")
        return True

    def create_group(
        self,
        name: str,
        description: str = "",
        icon: str = "⚔",
        accent_color: str = "#38bdf8",
        roles: Optional[Dict[str, str]] = None,
        orchestration: Optional[Dict[str, Any]] = None,
        tasks: Optional[Dict[str, Any]] = None,
        custom_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Creates and registers a new custom AI hybrid group."""
        group_id = custom_id or f"custom_hybrid_{uuid.uuid4().hex[:8]}"
        now = time.time()
        
        # Default fallback roles
        base_roles = {
            "text_model": "qwen2.5:1.5b",
            "reasoning_model": "deepseek-r1:1.5b",
            "coder_model": "qwen2.5-coder:1.5b",
            "vision_model": "moondream:v2",
            "heavy_vision_model": "llava:7b",
            "strategy_model": "qwen2.5:3b",
            "micro_model": "qwen2.5:0.5b",
            "audio_model": "faster-whisper",
            "sentinel_model": "onnx-anomaly",
            "cloud_model": "gemini-3.6-flash"
        }
        if roles:
            base_roles.update(roles)

        base_orch = {
            "vram_strategy": "dynamic_tier",
            "execution_mode": "cot_guided",
            "temperature": 0.2,
            "auto_fallback": True,
            "system_directive": "Custom AI Swarm Team with dedicated role specializations."
        }
        if orchestration:
            base_orch.update(orchestration)

        new_group = {
            "id": group_id,
            "name": name.strip() or "Custom Hybrid Group",
            "description": description.strip(),
            "icon": icon or "⚔",
            "accent_color": accent_color or "#38bdf8",
            "is_builtin": False,
            "is_active": False,
            "created_at": now,
            "updated_at": now,
            "roles": base_roles,
            "orchestration": base_orch,
            "tasks": copy.deepcopy(tasks) if tasks else {}
        }

        self._groups[group_id] = new_group
        self._save_groups()
        logger.info(f"[AIHybridGroupsManager] Created custom hybrid group '{group_id}' ({name})")
        return copy.deepcopy(new_group)

    def update_group(self, group_id: str, group_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Updates an existing hybrid group. Built-in groups can have roles/orchestration/tasks edited."""
        if group_id not in self._groups:
            logger.warning(f"[AIHybridGroupsManager] Cannot update non-existent group '{group_id}'")
            return None
        
        target = self._groups[group_id]
        if "name" in group_data and not target.get("is_builtin", False):
            target["name"] = group_data["name"]
        if "description" in group_data:
            target["description"] = group_data["description"]
        if "icon" in group_data:
            target["icon"] = group_data["icon"]
        if "accent_color" in group_data:
            target["accent_color"] = group_data["accent_color"]
        if "roles" in group_data and isinstance(group_data["roles"], dict):
            target["roles"].update(group_data["roles"])
        if "orchestration" in group_data and isinstance(group_data["orchestration"], dict):
            target["orchestration"].update(group_data["orchestration"])
        if "tasks" in group_data and isinstance(group_data["tasks"], dict):
            if "tasks" not in target:
                target["tasks"] = {}
            target["tasks"].update(group_data["tasks"])
        
        target["updated_at"] = time.time()
        self._save_groups()
        logger.info(f"[AIHybridGroupsManager] Updated hybrid group '{group_id}'")
        return copy.deepcopy(target)

    def push_group_config(self, config_input: Any, target_group_id: Optional[str] = None) -> Dict[str, Any]:
        """
        In-App Configuration Pusher:
        Parses JSON/YAML/Dict string, validates schema, and updates or registers a custom swarm.
        Supports multi-purpose task definitions (poker, chess, consent, stealth, etc.).
        """
        if isinstance(config_input, str):
            clean_str = config_input.strip()
            try:
                data = json.loads(clean_str)
            except Exception as e_json:
                try:
                    import yaml  # type: ignore
                    data = yaml.safe_load(clean_str)
                except Exception:
                    raise ValueError(f"Ungültige JSON/YAML Konfiguration: {e_json}")
        elif isinstance(config_input, dict):
            data = copy.deepcopy(config_input)
        else:
            raise ValueError("Konfigurations-Input muss ein JSON-String oder Dictionary sein.")

        if not isinstance(data, dict):
            raise ValueError("Root-Element der Konfiguration muss ein JSON-Objekt sein.")

        gid = target_group_id or data.get("id")
        name = data.get("name", "Custom Swarm")
        
        if gid and gid in self._groups:
            existing = self._groups[gid]
            if not existing.get("is_builtin", False) and "name" in data:
                existing["name"] = data["name"]
            if "description" in data:
                existing["description"] = data["description"]
            if "icon" in data:
                existing["icon"] = data["icon"]
            if "accent_color" in data:
                existing["accent_color"] = data["accent_color"]
            if "roles" in data and isinstance(data["roles"], dict):
                existing["roles"].update(data["roles"])
            if "orchestration" in data and isinstance(data["orchestration"], dict):
                existing["orchestration"].update(data["orchestration"])
            if "tasks" in data and isinstance(data["tasks"], dict):
                if "tasks" not in existing:
                    existing["tasks"] = {}
                existing["tasks"].update(data["tasks"])
            existing["updated_at"] = time.time()
            self._save_groups()
            logger.info(f"[AIHybridGroupsManager] Pushed config to existing swarm '{gid}' ({existing['name']})")
            return copy.deepcopy(existing)
        else:
            new_grp = self.create_group(
                name=name,
                description=data.get("description", "Custom Multi-Purpose Swarm"),
                icon=data.get("icon", "⚔"),
                accent_color=data.get("accent_color", "#38bdf8"),
                roles=data.get("roles", {}),
                orchestration=data.get("orchestration", {}),
                tasks=data.get("tasks", {}),
                custom_id=gid
            )
            logger.info(f"[AIHybridGroupsManager] Pushed config created new custom swarm '{new_grp['id']}' ({name})")
            return new_grp

    def get_group_task_config(self, group_id: str, task_name: str) -> Dict[str, Any]:
        """Retrieves task-specific configuration (e.g. 'poker', 'chess') for a hybrid group."""
        grp = self.get_group(group_id)
        if not grp:
            return {}
        tasks = grp.get("tasks", {})
        if isinstance(tasks, dict) and task_name in tasks and isinstance(tasks[task_name], dict):
            return copy.deepcopy(tasks[task_name])
        return {}

    @staticmethod
    def get_preset_config_template(preset_type: str = "poker") -> Dict[str, Any]:
        """Generates ready-to-use Swarm configuration templates for in-app editor pasting."""
        p_type = (preset_type or "").lower().strip()
        if p_type == "poker":
            return {
                "name": "🃏 Poker Grandmaster Multi-Task Swarm",
                "description": "Autonomer Browser-Poker Swarm: Multimodale Kartenerkennung (Qwen-VL), Monte Carlo Math-Engine, DeepSeek-R1 CoT GTO/Exploit Reasoning & Stealth Click Execution.",
                "icon": "🃏",
                "accent_color": "#f59e0b",
                "roles": {
                    "text_model": "qwen2.5:1.5b",
                    "reasoning_model": "deepseek-r1:1.5b",
                    "coder_model": "qwen2.5-coder:1.5b",
                    "vision_model": "qwen2.5vl:3b",
                    "heavy_vision_model": "qwen2.5vl:3b",
                    "strategy_model": "deepseek-r1:1.5b",
                    "micro_model": "qwen2.5:0.5b",
                    "audio_model": "faster-whisper",
                    "sentinel_model": "onnx-anomaly",
                    "cloud_model": "gemini-3.6-flash"
                },
                "orchestration": {
                    "vram_strategy": "dynamic_tier",
                    "execution_mode": "cot_guided",
                    "temperature": 0.2,
                    "auto_fallback": True,
                    "system_directive": "You are a professional GTO/Exploitative Texas Hold'em Poker Bot swarm. Execute high-EV actions with precise sizing."
                },
                "tasks": {
                    "poker": {
                        "vision_ocr_role": "vision_model",
                        "reasoning_role": "reasoning_model",
                        "strategy_role": "strategy_model",
                        "action_execution_role": "coder_model",
                        "sentinel_role": "sentinel_model",
                        "equity_eval_iterations": 3000,
                        "auto_bet_sizing": "gto_geometric",
                        "fold_equity_threshold": 0.20,
                        "custom_gto_prompt": "You are an elite Texas Hold'em Poker AI Grandmaster and Game Theory Optimal (GTO) Solver. Analyze live table cards, Monte Carlo equity, pot odds, opponent tendencies, and table position. Determine the highest Expected Value (EV) play ('fold', 'check', 'call', 'bet', 'raise', 'all_in') with optimal chip sizing.",
                        "custom_vision_prompt": "Analyze this live browser poker table screenshot. Extract: 1. Hero 2 hole cards. 2. Community board cards (flop/turn/river). 3. Total pot size and bet to call. 4. Active action buttons."
                    }
                }
            }
        elif p_type == "chess":
            return {
                "name": "♟️ Chess Grandmaster Hybrid Swarm",
                "description": "Schach-Ensemble mit FEN-Vision-Extraktion, Stockfish-Berechnung und DeepSeek-R1 positionellem Meisterdenken.",
                "icon": "♟️",
                "accent_color": "#10b981",
                "roles": {
                    "text_model": "qwen2.5:1.5b",
                    "reasoning_model": "deepseek-r1:1.5b",
                    "coder_model": "qwen2.5-coder:1.5b",
                    "vision_model": "qwen2.5vl:3b",
                    "heavy_vision_model": "llava:7b",
                    "strategy_model": "deepseek-r1:1.5b",
                    "micro_model": "qwen2.5:0.5b",
                    "audio_model": "faster-whisper",
                    "sentinel_model": "onnx-anomaly",
                    "cloud_model": "gemini-3.6-flash"
                },
                "orchestration": {
                    "vram_strategy": "dynamic_tier",
                    "execution_mode": "cot_guided",
                    "temperature": 0.1,
                    "auto_fallback": True,
                    "system_directive": "Calculate absolute top engine moves and positional advantages."
                },
                "tasks": {
                    "chess": {
                        "vision_role": "vision_model",
                        "reasoning_role": "reasoning_model",
                        "depth": 18
                    }
                }
            }
        elif p_type == "stealth":
            return {
                "name": "🛡️ Stealth Cyber-Evasion Swarm",
                "description": "Multi-Modell Evasions-Swarm für Cloudflare Turnstile, reCAPTCHA v3 & komplexe Bot-Detection.",
                "icon": "🛡️",
                "accent_color": "#38bdf8",
                "roles": {
                    "text_model": "qwen2.5:1.5b",
                    "reasoning_model": "deepseek-r1:1.5b",
                    "coder_model": "qwen2.5-coder:1.5b",
                    "vision_model": "moondream:v2",
                    "heavy_vision_model": "qwen2.5vl:3b",
                    "strategy_model": "qwen2.5:3b",
                    "micro_model": "qwen2.5:0.5b",
                    "audio_model": "faster-whisper",
                    "sentinel_model": "onnx-anomaly",
                    "cloud_model": "gemini-3.6-flash"
                },
                "orchestration": {
                    "vram_strategy": "dynamic_tier",
                    "execution_mode": "cot_guided",
                    "temperature": 0.15,
                    "auto_fallback": True,
                    "system_directive": "Operate as a synchronized cyber-evasion AI swarm with strict separation of concerns."
                },
                "tasks": {
                    "evasion": {
                        "anti_detection_level": "maximum",
                        "mouse_jitter": True
                    }
                }
            }
        else:
            return {
                "name": "⚔️ Custom Multi-Purpose Swarm",
                "description": "Eigenes Multi-Modell Team für spezialisierte Aufgaben.",
                "icon": "⚔️",
                "accent_color": "#818cf8",
                "roles": {
                    "text_model": "qwen2.5:1.5b",
                    "reasoning_model": "deepseek-r1:1.5b",
                    "coder_model": "qwen2.5-coder:1.5b",
                    "vision_model": "moondream:v2",
                    "heavy_vision_model": "qwen2.5vl:3b",
                    "strategy_model": "qwen2.5:3b",
                    "micro_model": "qwen2.5:0.5b",
                    "audio_model": "faster-whisper",
                    "sentinel_model": "onnx-anomaly",
                    "cloud_model": "none"
                },
                "orchestration": {
                    "vram_strategy": "dynamic_tier",
                    "execution_mode": "cot_guided",
                    "temperature": 0.2,
                    "auto_fallback": True,
                    "system_directive": "Custom AI Swarm Team"
                },
                "tasks": {}
            }

    def delete_group(self, group_id: str) -> bool:
        """Deletes a custom hybrid group. Built-in groups cannot be deleted."""
        if group_id not in self._groups:
            return False
        
        if self._groups[group_id].get("is_builtin", False):
            logger.warning(f"[AIHybridGroupsManager] Cannot delete protected built-in group '{group_id}'")
            return False
        
        del self._groups[group_id]
        if self._active_group_id == group_id:
            self._active_group_id = "swarm_auto_full"
            if "swarm_auto_full" in self._groups:
                self._groups["swarm_auto_full"]["is_active"] = True

        self._save_groups()
        logger.info(f"[AIHybridGroupsManager] Deleted hybrid group '{group_id}'")
        return True

    def duplicate_group(self, source_group_id: str, new_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Clones an existing group into a new editable custom group."""
        source = self.get_group(source_group_id)
        if not source:
            return None
        
        clone_name = new_name or f"{source.get('name', 'Group')} (Copy)"
        return self.create_group(
            name=clone_name,
            description=source.get("description", ""),
            icon=source.get("icon", "⚔"),
            accent_color=source.get("accent_color", "#818cf8"),
            roles=copy.deepcopy(source.get("roles", {})),
            orchestration=copy.deepcopy(source.get("orchestration", {})),
            tasks=copy.deepcopy(source.get("tasks", {}))
        )

    def export_group_json(self, group_id: str) -> str:
        """Exports a single hybrid group definition as formatted JSON."""
        g = self.get_group(group_id)
        if not g:
            raise ValueError(f"Hybrid group '{group_id}' not found.")
        export_payload = copy.deepcopy(g)
        export_payload["export_timestamp"] = time.time()
        export_payload["app_version"] = getattr(config, "APP_VERSION", "2.0.0")
        return json.dumps(export_payload, indent=2, ensure_ascii=False)

    def import_group_json(self, json_content: str) -> Dict[str, Any]:
        """Imports and validates a hybrid group from a JSON string, creating a new custom group."""
        data = json.loads(json_content) if isinstance(json_content, str) else json_content
        if not isinstance(data, dict) or "name" not in data:
            raise ValueError("Invalid hybrid group JSON structure: missing 'name'")

        name = data.get("name", "Imported Hybrid Group")
        desc = data.get("description", "Imported AI Hybrid Swarm Group")
        icon = data.get("icon", "📥")
        color = data.get("accent_color", "#38bdf8")
        roles = data.get("roles", {})
        orch = data.get("orchestration", {})
        tasks = data.get("tasks", {})

        return self.create_group(
            name=f"{name} (Imported)",
            description=desc,
            icon=icon,
            accent_color=color,
            roles=roles,
            orchestration=orch,
            tasks=tasks
        )

    def reset_to_defaults(self):
        """Restores all built-in hybrid groups to standard factory presets."""
        for b in BUILTIN_HYBRID_GROUPS:
            self._groups[b["id"]] = copy.deepcopy(b)
        self._active_group_id = "swarm_auto_full"
        self._save_groups()
        logger.info("[AIHybridGroupsManager] Reset all hybrid groups to default presets.")

    # ----------------------------------------------------------------------------------
    # HARDWARE & METRICS COMPUTATION (Live VRAM & Latency Estimator)
    # ----------------------------------------------------------------------------------

    @staticmethod
    def calculate_group_metrics(roles: Dict[str, str], orchestration: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Calculates dynamic peak GPU VRAM budget, typical end-to-end latency,
        and hardware classification for a given role configuration.
        """
        orch = orchestration or {}
        vram_strategy = orch.get("vram_strategy", "dynamic_tier")

        # Collect unique models across assigned roles
        unique_models = set()
        for r_val in roles.values():
            if r_val and r_val.lower() != "none":
                unique_models.add(r_val)

        total_installed_vram = 0
        tier0_vram = 0
        tier1_vram = 0
        tier2_max_vram = 0
        tier2_sum_vram = 0
        cloud_count = 0
        total_latency_ms = 0

        for m_id in unique_models:
            prof = MODEL_HARDWARE_PROFILES.get(m_id, {"vram_mb": 1000, "latency_ms": 150, "tier": 1, "type": "local_llm"})
            v_mb = prof.get("vram_mb", 0)
            lat = prof.get("latency_ms", 100)
            tier = prof.get("tier", 1)

            total_installed_vram += v_mb
            total_latency_ms += lat

            if tier == 0:
                tier0_vram += v_mb
            elif tier == 1:
                tier1_vram += v_mb
            elif tier == 2:
                tier2_max_vram = max(tier2_max_vram, v_mb)
                tier2_sum_vram += v_mb
            elif tier == 3:
                cloud_count += 1

        # Calculate estimated peak active VRAM depending on arbiter strategy
        if vram_strategy == "dynamic_tier":
            # Tier 0 (CPU/RAM) + Tier 1 (Resident) + Max single Tier 2 (Arbiter eviction)
            estimated_peak_vram_mb = tier0_vram + tier1_vram + tier2_max_vram
        elif vram_strategy == "resident_pinned":
            # All local models pinned in VRAM simultaneously
            estimated_peak_vram_mb = total_installed_vram
        elif vram_strategy == "ultra_eco":
            # Aggressive CPU offloading & single-model execution
            estimated_peak_vram_mb = max(tier1_vram // 2, tier2_max_vram)
        elif vram_strategy == "cloud_zero_vram":
            # Only light local text + zero cloud VRAM
            estimated_peak_vram_mb = tier0_vram + (tier1_vram // 2)
        else:
            estimated_peak_vram_mb = tier0_vram + tier1_vram + tier2_max_vram

        # Pipeline Latency calculation based on execution mode
        exec_mode = orch.get("execution_mode", "cot_guided")
        if exec_mode == "sequential_cascade":
            # Cascade: Triage (Micro) -> DOM (Coder/Text) -> Vision Grounding -> Intent
            micro_lat = MODEL_HARDWARE_PROFILES.get(roles.get("micro_model", ""), {}).get("latency_ms", 45)
            text_lat = MODEL_HARDWARE_PROFILES.get(roles.get("text_model", ""), {}).get("latency_ms", 120)
            vis_lat = MODEL_HARDWARE_PROFILES.get(roles.get("vision_model", ""), {}).get("latency_ms", 190)
            est_pipeline_latency_ms = micro_lat + text_lat + vis_lat
        elif exec_mode == "cot_guided":
            # CoT guided: Sentinel + Micro + Reasoner + Vision + Finalizer
            cot_lat = MODEL_HARDWARE_PROFILES.get(roles.get("reasoning_model", ""), {}).get("latency_ms", 220)
            text_lat = MODEL_HARDWARE_PROFILES.get(roles.get("text_model", ""), {}).get("latency_ms", 120)
            vis_lat = MODEL_HARDWARE_PROFILES.get(roles.get("vision_model", ""), {}).get("latency_ms", 190)
            est_pipeline_latency_ms = cot_lat + text_lat + vis_lat
        else:
            # Parallel verified
            est_pipeline_latency_ms = max([
                MODEL_HARDWARE_PROFILES.get(m, {}).get("latency_ms", 100)
                for m in unique_models
            ] or [150]) + 60

        # Classification Tag & Color
        peak_gb = round(estimated_peak_vram_mb / 1024.0, 2)
        if estimated_peak_vram_mb <= 800:
            classification = "☘ Ultra-Eco (Zero GPU Pressure)"
            class_color = "#34d399"
        elif estimated_peak_vram_mb <= 2800:
            classification = "⚖ Balanced Efficiency (Recommended)"
            class_color = "#38bdf8"
        elif estimated_peak_vram_mb <= 5500:
            classification = "🚀 High-Precision Heavyweight"
            class_color = "#f59e0b"
        else:
            classification = "🔥 Extreme VRAM Workstation"
            class_color = "#f87171"

        return {
            "estimated_peak_vram_mb": estimated_peak_vram_mb,
            "estimated_peak_vram_gb": peak_gb,
            "estimated_pipeline_latency_ms": est_pipeline_latency_ms,
            "unique_models_count": len(unique_models),
            "cloud_models_count": cloud_count,
            "classification": classification,
            "class_color": class_color,
            "vram_strategy_used": vram_strategy
        }

    # ----------------------------------------------------------------------------------
    # ROLE RESOLUTION HELPER FOR SWARM ENGINE
    # ----------------------------------------------------------------------------------

    def resolve_roles_for_mode(self, mode_name: Optional[str] = None) -> Optional[Dict[str, str]]:
        """
        Attempts to resolve roles if the given mode_name corresponds to any
        built-in or custom hybrid group. Returns None if not matched.
        """
        if not mode_name:
            target_id = self._active_group_id
        else:
            target_id = mode_name.lower().strip()

        group = self.get_group(target_id)
        if group and "roles" in group:
            roles_dict = copy.deepcopy(group["roles"])
            # Map aliases for backwards compatibility
            if roles_dict.get("vision_model", "").startswith("gemini"):
                roles_dict["local_vision_fallback"] = "moondream:v2"
                roles_dict["local_heavy_vision_fallback"] = "llava:7b"
                roles_dict["local_vision_nextgen"] = "qwen2.5vl:3b"
            else:
                roles_dict.setdefault("local_vision_fallback", roles_dict.get("vision_model", "moondream:v2"))
                roles_dict.setdefault("local_heavy_vision_fallback", roles_dict.get("heavy_vision_model", "llava:7b"))
                roles_dict.setdefault("local_vision_nextgen", roles_dict.get("vision_model", "qwen2.5vl:3b"))
            return roles_dict

        return None
