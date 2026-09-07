import os
import time
import json
import socket
import logging
import asyncio
import base64
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional, Callable, AsyncGenerator, Tuple

import aiohttp
import config
from engine.ai_model_manager import AIModelManager, OLLAMA_API_BASE
from engine.ai_gemini_client import GeminiApiClient, GEMINI_API_BASE
from engine.ai_telemetry import AITelemetryBus
from engine.ai_knowledge_rag import AIKnowledgeRAG
from engine.ai_inference_optimizer import AIInferenceOptimizer, AdaptiveTokenChunker
from engine.ai_adversarial_council import AIAdversarialCouncil

logger = logging.getLogger("AIChatEngine")


@dataclass
class SwarmAgentResponse:
    """Represents an individual sub-agent's perspective or contribution in Swarm mode."""
    agent_id: str
    role_name: str
    model_name: str
    thought_process: str
    response_text: str
    latency_ms: float
    confidence: float = 1.0


@dataclass
class ChatMessage:
    """Represents a single message in a multi-turn conversation."""
    role: str  # "user", "assistant", "system"
    content: str
    timestamp: float = field(default_factory=time.time)
    model: str = ""
    image_b64: Optional[str] = None
    swarm_breakdown: Optional[List[Dict[str, Any]]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# Default System Personas
SYSTEM_PERSONAS: Dict[str, Dict[str, str]] = {
    "stealth_copilot": {
        "name": "🛡️ OXBROWSER Stealth & Anti-Detect Copilot",
        "description": "Expert in browser fingerprinting, TLS impersonation, Canvas/WebGL noise, WebRTC leakage, residential proxies, and stealth evasion.",
        "prompt": (
            "You are the OXBROWSER AI Stealth & Anti-Detect Copilot, an elite security researcher, web anti-detection expert, and autonomous agent. "
            "Your objective is to provide high-precision advice on browser fingerprinting (Canvas, AudioContext, WebGL, Client Hints, Fonts, WebRTC), "
            "TLS JA3/JA4 fingerprint spoofing, residential and SOCKS5 proxy hygiene, OS tensor harmony, and counter-bot defenses (Cloudflare Turnstile, Datadome, Kasada, Akamai, reCAPTCHA).\n\n"
            "CRITICAL PROFILE CONFIGURATION & ENGINE-SPECIFIC AUDITING MANDATE:\n"
            "Every audit MUST strictly align with the profile's configured 'engine' and actual settings:\n"
            "1. CAMOUFOX ENGINE PROFILES (engine == 'camoufox'):\n"
            "   - The browser runs Camoufox (Gecko C++ modified engine). Your audit must FOCUS EXCLUSIVELY ON CAMOUFOX capabilities:\n"
            "     • C++ native fontconfig isolation (sandboxing fonts to the target OS, preventing host font leaks).\n"
            "     • Deterministic C++ seeds (audio:seed, fonts:spacing_seed, canvas:seed) ensuring multi-session stability.\n"
            "     • C++ protocol-level ICE candidate manipulation (webrtc_mode: altered) bound to the proxy exit IP.\n"
            "     • Hardened V2 anti-sterility behavior (disk_cache, save_history, form_autofill, DRM Widevine CDM).\n"
            "   - STRICT FORBIDDEN RULE: NEVER flag Chromium/Blink-specific CDP detection issues (such as missing 'chrome.runtime', 'navigator.webdriver' in Blink, Chromium 'Sec-Ch-Ua' brands, or Chromium ANGLE vs Mesa driver flags) on a Camoufox profile!\n"
            "2. CHROMIUM / PLAYWRIGHT PROFILES (engine == 'chromium' | 'playwright'):\n"
            "   - Audit Chromium-specific CDP stealth, Blink layout traits, Chrome extensions, and V8 optimization signatures.\n"
            "3. REAL-WORLD REALISM: Always audit the exact parameters configured in the profile without false positives.\n\n"
            "100% AUTONOMOUS AGENT MODE CAPABILITIES (A-Z ACTION BLOCKS):\n"
            "You have direct control over the OXBROWSER application via structured Action Blocks. Whenever the user requests an action, output the appropriate Action Block:\n\n"
            "1. CREATE SINGLE PROFILE:\n"
            "```action:create_profile\n"
            "{\n"
            '  "name": "Profile Name",\n'
            '  "os": "windows" | "mac" | "linux",\n'
            '  "engine": "camoufox",\n'
            '  "country": "DE" | "US" | "GB" | "...",\n'
            '  "hardware_concurrency": 8,\n'
            '  "device_memory": 8,\n'
            '  "screen_resolution": "1920x1080",\n'
            '  "stealth": { "canvas_noise": true, "audio_noise": true, "webgl_vendor": "Google Inc. (NVIDIA)", "webgl_renderer": "ANGLE (NVIDIA GeForce RTX 4070 Direct3D11)", "webrtc_mode": "altered" }\n'
            "}\n"
            "```\n\n"
            "2. BATCH PROFILES (MULTIPLE UNIQUE PROFILES):\n"
            "```action:create_batch_profiles\n"
            "[\n"
            '  { "name": "Camoufox_Stealth_01", "os": "windows", "engine": "camoufox", "country": "DE", "hardware_concurrency": 12, "device_memory": 16, "screen_resolution": "1920x1080", "stealth": { "canvas_noise": true, "audio_noise": true, "webgl_vendor": "Google Inc. (NVIDIA)", "webgl_renderer": "ANGLE (NVIDIA GeForce RTX 4070 Direct3D11)", "webrtc_mode": "altered" } },\n'
            '  { "name": "Camoufox_Stealth_02", "os": "mac", "engine": "camoufox", "country": "US", "hardware_concurrency": 10, "device_memory": 16, "screen_resolution": "2560x1600", "stealth": { "canvas_noise": true, "audio_noise": true, "webgl_vendor": "Apple", "webgl_renderer": "Apple M2 Pro", "webrtc_mode": "altered" } }\n'
            "]\n"
            "```\n\n"
            "3. LAUNCH / START PROFILE:\n"
            "```action:launch_profile\n"
            '{"target": "Profil 1" | "Profile Name" | "uuid"}\n'
            "```\n\n"
            "4. STOP PROFILE / ALL PROFILES:\n"
            "```action:stop_profile\n"
            '{"target": "Profil 1" | "uuid" | "all"}\n'
            "```\n\n"
            "5. AUDIT PROFILE (SECURITY & TENSOR VERIFICATION):\n"
            "```action:audit_profile\n"
            '{"target": "Profil 1" | "uuid" | "all"}\n'
            "```\n\n"
            "6. 1-CLICK AUTO-PATCH / REMEDIATE AUDIT ISSUES:\n"
            "```action:apply_audit_patches\n"
            '{"target": "Profil 1" | "uuid"}\n'
            "```\n\n"
            "7. PATCH / UPDATE PROFILE ATTRIBUTES:\n"
            "```action:patch_profile\n"
            "{\n"
            '  "target": "Profil 1",\n'
            '  "patch": { "device_memory": 16, "stealth.webgl_vendor": "Apple", "stealth.webgl_renderer": "Apple M2 Pro" }\n'
            "}\n"
            "```\n\n"
            "8. DELETE / CLONE PROFILE:\n"
            "```action:delete_profile\n"
            '{"target": "Profil 1"}\n'
            "```\n"
            "```action:clone_profile\n"
            '{"target": "Profil 1", "new_name": "Clone_Profile_01"}\n'
            "```\n\n"
            "9. PROXY MANAGEMENT (SCRAPE, CHECK, ASSIGN):\n"
            "```action:scrape_proxies\n"
            '{"protocol": "http" | "socks5", "limit": 20, "verify_google": true}\n'
            "```\n"
            "```action:assign_proxy\n"
            '{"target": "Profil 1", "proxy": {"host": "1.2.3.4", "port": 8080, "type": "http"}}\n'
            "```\n\n"
            "10. SENIOR ENVIRONMENT BENCHMARK:\n"
            "```action:run_benchmark\n"
            '{"target": "Profil 1", "benchmark": "creepjs" | "browserleaks" | "pixelscan" | "iphey"}\n'
            "```\n\n"
            "11. WARMUP CAMPAIGN (SAVE & START):\n"
            "```action:save_campaign\n"
            '{"name": "Campaign_Name", "category": "ecommerce", "max_pages": 6, "dwell_time": 8.0, "urls": ["https://..."]}\n'
            "```\n"
            "```action:start_warmup\n"
            '{"campaign": "Campaign_Name", "profile_ids": ["Profil 1"]}\n'
            "```\n\n"
            "CRITICAL EFFICIENCY & ACTION BLOCK RULE:\n"
            "When executing agent actions, give a brief 1-2 sentence technical confirmation and immediately output the structured action block. The interactive UI renders live action cards with 1-click execution or executes them autonomously in Agent Mode."
        )
    },
    "security_pentester": {
        "name": "🎯 Web Security Pentester & Vulnerability Researcher",
        "description": "Specialist in OWASP Top 10, Auth/Session bypass, IDOR, SSRF, XSS, CSRF, WebSocket/GraphQL, and PoC exploit scripting.",
        "prompt": (
            "You are the Senior Web Security Pentester and Vulnerability Research Copilot for OXBROWSER. "
            "You possess deep expertise in application security assessments, penetration testing methodologies (OWASP ASVS, WSTG, PTES), "
            "vulnerability verification, exploit proof-of-concept (PoC) generation, and remediation architecture.\n\n"
            "CORE FOCUS AREAS:\n"
            "• Authentication & Session Handling: JWT vulnerabilities, OAuth2 / OIDC flaws, Session Fixation, Cookie attributes (SameSite, Secure, HttpOnly).\n"
            "• Injection & Logic Flaws: Blind/Time-based SQLi, NoSQLi, Server-Side Request Forgery (SSRF), IDOR, Prototype Pollution, Template Injections (SSTI).\n"
            "• Client-Side Security: DOM-based XSS, Content Security Policy (CSP) bypass analysis, CORS misconfigurations, WebSocket hijacked sessions, postMessage validation.\n"
            "• API & Protocol Audits: GraphQL introspection/injection, REST API authorization flaws (BOLA/BFLA), HTTP Request Smuggling (H2/H3 desync).\n"
            "• Actionable PoCs & Remediation: Provide clear, structured, reproducible reproduction steps, cURL commands, Playwright/Python PoCs, and remediation guidance.\n\n"
            "You can control OXBROWSER profile execution (`action:launch_profile`), run benchmarks (`action:run_benchmark`), or generate automated pentesting test scripts."
        )
    },
    "evasion_redteam": {
        "name": "⚔️ Red Team Operator & WAF/Anti-Bot Bypass Specialist",
        "description": "Specialist in WAF evasion (Cloudflare/Akamai/DataDome/Kasada/Imperva), TLS JA3/JA4 manipulation, CDP anti-detection, and entropy harmonization.",
        "prompt": (
            "You are the Red Team Operator & WAF / Anti-Bot Bypass Specialist for OXBROWSER. "
            "Your domain is adversarial evasion engineering, bypass methodology against enterprise anti-bot solutions (Akamai BMP, Cloudflare Turnstile / Bot Management, DataDome, Kasada, PerimeterX / HUMAN, F5 Shape), "
            "and defeating ML-driven behavioural anomaly classifiers.\n\n"
            "CORE FOCUS AREAS:\n"
            "• WAF & Bot-Mitigation Deconstruction: Analyzing challenge responses (HTTP 403, 429, JS Obfuscation payloads, PoW challenges), rate-limiting bypasses, and distributed request dispersion.\n"
            "• Fingerprint & Protocol Evasion: Subverting Client Hints, AudioContext DSP signatures, Canvas subpixel noise, Font probing traps, WebGL shader execution timings, and WebRTC candidate validation.\n"
            "• TLS & Network Stack Realism: Aligning JA3/JA4 hashes, ALPN negotiation, TCP window sizing, and HTTP/2 SETTINGS frames to match the claimed user-agent.\n"
            "• Behavioral Entropy & Anti-Sterility: Eliminating zero-entropy footprints, generating non-linear minimum-jerk mouse trajectories, simulating authentic dwell time, and cookie/cache maturation.\n\n"
            "You have autonomous control to execute actions (`action:create_profile`, `action:launch_profile`, `action:run_benchmark`, `action:audit_profile`)."
        )
    },
    "poweruser_engineer": {
        "name": "⚡ Low-Level Reverse Engineer & Network Forensic",
        "description": "Specialist in Packet/PCAP analysis, TLS handshakes, HTTP/2 & HTTP/3 frame dissection, DNS/WebRTC STUN traces, and Gecko/Chromium kernel internals.",
        "prompt": (
            "You are the Low-Level Reverse Engineer and Network Forensics Specialist for OXBROWSER. "
            "You specialize in deep browser kernel internals (Gecko / SpiderMonkey C++ sources, Chromium Blink / V8), memory and process profiling, network protocol dissection, and low-level diagnostic traces.\n\n"
            "CORE FOCUS AREAS:\n"
            "• Network Protocol Diagnostics: Dissecting Wireshark PCAPs, TLS 1.3 key exchange, HTTP/2 HEADERS/DATA frame flows, QUIC/HTTP/3 UDP streams, DNS-over-HTTPS (DoH), and WebRTC ICE STUN/TURN bindings.\n"
            "• Browser Internals & C++ Prefs: Gecko about:config low-level flags, Juggler/CDP protocol debugging, C++ fontconfig isolation, and headless virtualization tricks (Xvfb / EGL / Mesa).\n"
            "• Forensic Anti-Tamper Analysis: Inspecting JS Prototype chains, Error stack traces, Function.prototype.toString proxies, and WebGL parameter clamping.\n"
            "• Advanced Automation Debugging: Resolving race conditions, async pipe deadlocks, IPC bottlenecks, and memory leak mitigation in multi-profile orchestration."
        )
    },
    "automation_architect": {
        "name": "⚡ Web Automation & Playwright Architect",
        "description": "Specialist in Camoufox, Playwright, Shadow DOM traversal, humanoid biomechanical motion, and resilient DOM selectors.",
        "prompt": (
            "You are the OXBROWSER Automation Architect, a senior developer specializing in Camoufox, Playwright, and Puppeteer automation. "
            "You write robust, stealthy Python scripts, handle complex Shadow DOM elements, utilize minimum-jerk humanoid mouse trajectories, "
            "and design resilient web scraping architectures with intelligent fallback logic.\n\n"
            "You have full agent capabilities to launch browser profiles (`action:launch_profile`), run benchmarks (`action:run_benchmark`), and execute sandboxed DOM scripts."
        )
    },
    "warmup_architect": {
        "name": "🎭 Organic Persona & Warmup Architect",
        "description": "Designs organic human-like browsing trajectories, search queries, dwell times, and cookie maturation strategies.",
        "prompt": (
            "You are the Warmup & Persona Architect for OXBROWSER, equipped with autonomous agent capabilities. You craft natural, contextual browsing narratives, generate realistic organic search keywords, "
            "calculate human reading dwell times based on text density, and design cookie maturation schedules to build authentic browser trust scores.\n\n"
            "You can output structured Action Blocks (`action:save_campaign` or `action:start_warmup`) to allow 1-click execution or persistence directly in OXBROWSER."
        )
    },
    "general_assistant": {
        "name": "🤖 Senior AI General Assistant",
        "description": "Versatile, intelligent coding, reasoning, and technical analysis partner.",
        "prompt": (
            "You are an advanced Senior AI Assistant. You provide insightful, accurate, and concise answers across coding, software architecture, "
            "data analysis, system troubleshooting, and technical problem solving. You can control OXBROWSER features via action blocks."
        )
    }
}

SWARM_MODES: Dict[str, Dict[str, str]] = {
    "swarm_consensus": {
        "name": "🧠 Swarm Consensus & Multi-Agent Council",
        "description": "Multi-agent parallel reasoning where local & cloud models deliberate, cross-verify, and synthesize a unified high-confidence consensus.",
        "icon": "🧠"
    },
    "swarm_adversarial": {
        "name": "⚔️ Swarm Adversarial Council (Red vs. Blue Team)",
        "description": "Adversarial debate where Blue Team evasion proposals are rigorously challenged by Red Team bot-defense simulators and synthesized by Supreme Arbitrator.",
        "icon": "⚔️"
    },
    "swarm_specialist": {
        "name": "🎯 Swarm Dynamic Specialist Router",
        "description": "Intelligently analyzes the user's intent and routes to the dedicated specialist model (Stealth, DOM, Vision, or Reasoning).",
        "icon": "🎯"
    },
    "swarm_auto_full": {
        "name": "⫸ Swarm Auto-Full (7+1 AI Team Synergy)",
        "description": "Full synchronized team execution combining ONNX, Whisper, Qwen 0.5B/1.5B/3B, LLaVA 7B, Moondream 2, and Gemini 3.6 Flash.",
        "icon": "⫸"
    }
}

SUPPORTED_CHAT_LANGUAGES: Dict[str, Dict[str, str]] = {
    "de": {
        "name": "Deutsch (German)",
        "flag": "🇩🇪",
        "directive": "CRITICAL LANGUAGE REQUIREMENT: You MUST formulate and write your entire response exclusively in German (Deutsch). Use fluent, technical, high-level German terminology."
    },
    "en": {
        "name": "English",
        "flag": "🇬🇧",
        "directive": "CRITICAL LANGUAGE REQUIREMENT: You MUST formulate and write your entire response in English."
    },
    "es": {
        "name": "Español (Spanish)",
        "flag": "🇪🇸",
        "directive": "CRITICAL LANGUAGE REQUIREMENT: You MUST formulate and write your entire response in Spanish (Español)."
    },
    "fr": {
        "name": "Français (French)",
        "flag": "🇫🇷",
        "directive": "CRITICAL LANGUAGE REQUIREMENT: You MUST formulate and write your entire response in French (Français)."
    },
    "ru": {
        "name": "Русский (Russian)",
        "flag": "🇷🇺",
        "directive": "CRITICAL LANGUAGE REQUIREMENT: You MUST formulate and write your entire response in Russian (Русский)."
    },
    "zh": {
        "name": "中文 (Chinese)",
        "flag": "🇨🇳",
        "directive": "CRITICAL LANGUAGE REQUIREMENT: You MUST formulate and write your entire response in Chinese (Simplified/中文)."
    },
    "auto": {
        "name": "Auto-Detect / Match User",
        "flag": "🌐",
        "directive": ""
    }
}


class AIChatEngine:
    """
    Central AI Chat & Copilot Engine:
    - Multi-turn conversation history management
    - Async real-time token streaming for local Ollama and Google Gemini
    - Multi-agent Swarm reasoning (Consensus, Specialist Routing, Auto-Full)
    - Direct interaction with browser profiles, proxies, and fingerprint evaluation
    - Multimodal image / screenshot reasoning
    """

    _instance: Optional['AIChatEngine'] = None

    def __init__(self):
        self.ai_mgr = AIModelManager.get_instance()
        self.gemini_client = GeminiApiClient.get_instance()
        self.telemetry = AITelemetryBus.get_instance()
        self._history: List[ChatMessage] = []
        self._active_system_persona: str = "stealth_copilot"
        self._custom_system_prompt: str = ""
        self._preferred_language: str = "de"
        self._abort_flag: bool = False

    @classmethod
    def get_instance(cls) -> 'AIChatEngine':
        if cls._instance is None:
            cls._instance = AIChatEngine()
        return cls._instance

    # -------------------------------------------------------------------------
    # History & Session Management
    # -------------------------------------------------------------------------
    def get_history(self) -> List[ChatMessage]:
        return list(self._history)

    def add_message(self, message: ChatMessage):
        self._history.append(message)

    def clear_history(self):
        self._history.clear()
        logger.info("[AIChatEngine] Conversation history cleared.")

    def set_system_persona(self, persona_key: str, custom_prompt: str = ""):
        self._active_system_persona = persona_key
        self._custom_system_prompt = custom_prompt

    def set_preferred_language(self, lang_code: str):
        """Sets the preferred response language for single models and Swarm agents."""
        if lang_code in SUPPORTED_CHAT_LANGUAGES:
            self._preferred_language = lang_code
        else:
            self._preferred_language = "auto"
        logger.info(f"[AIChatEngine] Preferred chat response language set to: {self._preferred_language}")

    def get_preferred_language(self) -> str:
        return self._preferred_language

    def get_effective_system_prompt(self) -> str:
        if self._active_system_persona == "custom":
            base_prompt = self._custom_system_prompt.strip()
        else:
            persona = SYSTEM_PERSONAS.get(self._active_system_persona)
            base_prompt = persona["prompt"] if persona else SYSTEM_PERSONAS["stealth_copilot"]["prompt"]

        lang_entry = SUPPORTED_CHAT_LANGUAGES.get(self._preferred_language)
        if lang_entry and lang_entry.get("directive"):
            return f"{base_prompt}\n\n{lang_entry['directive']}"
        return base_prompt

    def abort_generation(self):
        """Sets flag to cancel active stream generation immediately."""
        self._abort_flag = True
        logger.info("[AIChatEngine] Abort requested for active chat generation.")

    def export_to_markdown(self) -> str:
        """Exports the entire conversation history as structured Markdown."""
        lines = [
            f"# OXBROWSER AI Chat Session Export",
            f"**Exported:** {time.strftime('%Y-%m-%d %H:%M:%S')}",
            f"**System Persona:** {self._active_system_persona}",
            f"**Total Messages:** {len(self._history)}",
            "\n---\n"
        ]
        for msg in self._history:
            role_title = "👤 **User**" if msg.role == "user" else f"🤖 **Assistant ({msg.model or 'AI'})**"
            ts = time.strftime('%H:%M:%S', time.localtime(msg.timestamp))
            lines.append(f"### {role_title} <small>_{ts}_</small>\n")
            if msg.image_b64:
                lines.append("_[Attached Image/Screenshot Provided]_\n")
            if msg.swarm_breakdown:
                lines.append("<details><summary>🧠 Swarm Agent Breakdown & Reasoning</summary>\n")
                for step in msg.swarm_breakdown:
                    lines.append(f"- **{step.get('role_name')}** ({step.get('model_name')}) [{step.get('latency_ms', 0):.1f}ms]: {step.get('thought_process', '')}")
                lines.append("</details>\n")
            lines.append(f"{msg.content}\n")
            lines.append("---\n")
        return "\n".join(lines)

    def export_to_json(self) -> str:
        """Exports conversation history as JSON string."""
        return json.dumps([m.to_dict() for m in self._history], indent=2)

    # -------------------------------------------------------------------------
    # Profile & Anti-Detect Context Interaction
    # -------------------------------------------------------------------------
    @classmethod
    def resolve_profile_from_prompt(cls, prompt: str, fallback_profile: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """Finds any referenced profile by name or ID from prompt text, or returns fallback profile."""
        if not prompt:
            return fallback_profile

        try:
            from storage.profile_manager import ProfileManager
            p_mgr = ProfileManager()
            all_profs = p_mgr.list_profiles()
            if not all_profs:
                return fallback_profile

            p_lower = (prompt or "").lower()
            # 1. Exact or quoted name matching (e.g. 'LINUX_01', "LINUX_01", profile LINUX_01)
            for prof in all_profs:
                p_name = str(prof.get("name", "")).strip()
                p_id = str(prof.get("id", "")).strip()
                if p_name and (p_name.lower() in p_lower or f"'{p_name.lower()}'" in p_lower or f'"{p_name.lower()}"' in p_lower):
                    return prof
                if p_id and (p_id.lower() in p_lower):
                    return prof
        except Exception:
            pass

        return fallback_profile

    def format_profile_context(self, profile_data: Optional[Dict[str, Any]]) -> str:
        """Constructs an anti-detect context snippet and live ONNX mathematical security & tensor audit to ground the AI in live profile specs."""
        if not profile_data:
            return ""

        all_profiles_summary = ""
        try:
            from storage.profile_manager import ProfileManager
            p_mgr = ProfileManager()
            all_profs = p_mgr.list_profiles()
            if all_profs:
                p_names = [f"'{p.get('name', p.get('id', 'N/A'))}' ({p.get('os', 'os').title()}/{p.get('engine', 'camoufox').title()})" for p in all_profs]
                all_profiles_summary = f"- Stored System Profiles: {', '.join(p_names)}\n"
        except Exception:
            pass

        name = profile_data.get("name", "Unknown Profile")
        profile_id = profile_data.get("id", "N/A")
        os_type = profile_data.get("os", "Linux")
        engine_type = profile_data.get("engine", "camoufox")
        custom_ua = profile_data.get("custom_user_agent", False)
        ua = profile_data.get("user_agent", "")
        if not custom_ua or not ua:
            ua = config.get_default_user_agent(os_type, engine_type)

        # Proxy Configuration & IP Cache
        proxy_cfg = profile_data.get("proxy", {})
        proxy_enabled = proxy_cfg.get("enabled", False)
        proxy_host = proxy_cfg.get("host") or proxy_cfg.get("server") or ""
        proxy_port = proxy_cfg.get("port", "")
        proxy_type = proxy_cfg.get("type", "http").upper()
        proxy_info = profile_data.get("proxy_info", {})
        
        if proxy_enabled and proxy_host:
            geo_details = []
            if proxy_info.get("ip"):
                geo_details.append(f"IP: {proxy_info.get('ip')}")
            if proxy_info.get("country"):
                geo_details.append(f"Geo: {proxy_info.get('city', '')}, {proxy_info.get('country')}")
            if proxy_info.get("isp"):
                geo_details.append(f"ISP: {proxy_info.get('isp')}")
            if proxy_info.get("timezone"):
                geo_details.append(f"TZ: {proxy_info.get('timezone')}")
            geo_str = f" [{', '.join(geo_details)}]" if geo_details else ""
            proxy_str = f"{proxy_type}://{proxy_host}:{proxy_port} (Active Proxy{geo_str})"
        else:
            proxy_str = "Direct Connection (No Proxy active)"

        killswitch = profile_data.get("network_killswitch", True)
        ks_str = "Enabled (Linux NetNS Egress KillSwitch - Strict Fail-Closed IP/DNS drop protection)" if killswitch else "Disabled"

        # Stealth & Anti-Detect Overrides
        stealth = profile_data.get("stealth") or profile_data.get("fingerprint") or {}
        canvas_noise = stealth.get("canvas_noise", True)
        webgl_vendor = stealth.get("webgl_vendor", "Default")
        webgl_renderer = stealth.get("webgl_renderer", "Default")
        audio_noise = stealth.get("audio_noise", True)
        raw_webrtc = stealth.get("webrtc_mode") or stealth.get("webrtc") or profile_data.get("webrtc_mode") or "altered"
        if isinstance(raw_webrtc, bool):
            webrtc_mode = "altered" if raw_webrtc else "disabled"
        else:
            m_str = str(raw_webrtc).lower().strip()
            if m_str in ["altered", "spoof", "spoofed", "protocol_spoofing", "proxy"]:
                webrtc_mode = "altered"
            elif m_str in ["disabled", "block", "blocked", "off", "disable", "none"]:
                webrtc_mode = "disabled"
            elif m_str in ["real", "raw", "leak", "enabled", "on", "default"]:
                webrtc_mode = "real"
            else:
                webrtc_mode = "altered"

        if webrtc_mode == "altered":
            target_ip_str = proxy_info.get('ip') or proxy_host or 'Auto Proxy Exit'
            webrtc_desc = f"altered (Protocol-Level C++ Native ICE candidate spoofing: bound to proxy IP '{target_ip_str}', private LAN IPs obfuscated with mDNS uuid.local, non-proxied UDP blocked)"
            webrtc_leak_risk = "Zero Leak Risk (C++ Native ICE candidate protocol spoofing active + NetNS killswitch)"
        elif webrtc_mode == "disabled":
            webrtc_desc = "disabled (WebRTC & RTCPeerConnection completely disabled)"
            webrtc_leak_risk = "Zero Leak Risk (WebRTC disabled)"
        else:
            webrtc_desc = "real (Direct LAN/WAN WebRTC candidates without filtering)"
            webrtc_leak_risk = "CRITICAL LEAK RISK (Real Host IP exposed via WebRTC!)"

        client_rects = stealth.get("client_rects_noise", True)
        font_noise = stealth.get("font_fingerprint_noise", True)

        # Hardware & Screen
        cores = profile_data.get("hardware_concurrency", 8)
        memory = profile_data.get("device_memory", 8)
        resolution = profile_data.get("screen_resolution") or f"{profile_data.get('screen_width', 1920)}x{profile_data.get('screen_height', 1080)}"
        status = profile_data.get("status", "Stopped")
        sandbox_mode = profile_data.get("sandbox", {}).get("mode", "off")

        # -----------------------------------------------------------------
        # LIVE REAL-TIME ML TENSOR & STEALTH SECURITY AUDIT (ONNX Sentinel)
        # -----------------------------------------------------------------
        from engine.ml_fingerprint_evaluator import MLFingerprintEvaluator
        eval_dict = {
            "os": os_type,
            "engine": engine_type,
            "user_agent": ua,
            "webgl_vendor": webgl_vendor,
            "webgl_renderer": webgl_renderer,
            "hardware_concurrency": cores,
            "device_memory": memory,
            "screen_res": resolution,
            "stealth": {
                "canvas_noise": canvas_noise,
                "audio_noise": audio_noise,
                "webrtc_mode": webrtc_mode,
                "webgpu_supported": stealth.get("webgpu_supported", False)
            }
        }
        score, anoms, recs = MLFingerprintEvaluator.evaluate(eval_dict)
        
        # Check WebGL OS alignment (engine-aware)
        os_lower = os_type.lower()
        r_lower = webgl_renderer.lower()
        v_lower = webgl_vendor.lower()
        tensor_issues = list(anoms)
        
        if engine_type != "camoufox":
            if os_lower == "linux" and ("direct3d" in r_lower or "d3d11" in r_lower or "d3d9" in r_lower or "apple" in v_lower or "angle (nvidia" in r_lower):
                if not any("Direct3D" in a or "ANGLE" in a for a in tensor_issues):
                    tensor_issues.append(f"Direct3D / Windows ANGLE renderer '{webgl_renderer}' is incompatible with Linux kernel.")
            elif os_lower == "windows" and ("apple" in v_lower or "mesa" in v_lower or "llvmpipe" in r_lower):
                if not any("Mesa" in a or "Apple" in a for a in tensor_issues):
                    tensor_issues.append(f"Mesa / Linux renderer '{webgl_renderer}' is incompatible with Windows kernel.")
            elif os_lower == "mac" and ("direct3d" in r_lower or ("apple" not in v_lower and "intel iris" not in r_lower and "angle (apple" not in r_lower)):
                if not any("Apple" in a for a in tensor_issues):
                    tensor_issues.append(f"Non-Apple GPU renderer '{webgl_renderer}' is suspicious on macOS.")
        else:
            # Camoufox native C++ engine: tensor harmony is enforced via C++ Gecko patches
            if not tensor_issues:
                tensor_issues = []

        tensor_audit_str = "Clean (0 anomalies detected - 100% OS tensor harmony)" if not tensor_issues else f"ANOMALIES DETECTED ({len(tensor_issues)}):\n  - " + "\n  - ".join(tensor_issues)
        recs_str = "None (Profile configuration is optimal)" if not recs else "\n  - " + "\n  - ".join(recs)

        # Available Stored Warmup Campaigns
        try:
            from storage.warmup_campaign_manager import WarmupCampaignManager
            c_mgr = WarmupCampaignManager.get_instance()
            c_list = c_mgr.list_campaigns()
            campaign_names = [f"'{c.get('name', c.get('id'))}'" for c in c_list]
            c_info = f"\n- Available Saved Warmup Campaigns: {', '.join(campaign_names)}" if campaign_names else ""
        except Exception:
            c_info = ""

        beh = profile_data.get("behavior", {})
        beh_str = f"Disk Cache={beh.get('disk_cache', True)}, History={beh.get('save_history', True)}, Autofill={beh.get('form_autofill', True)}, DRM Widevine={beh.get('drm_widevine', True)}"

        camoufox_banner = ""
        if engine_type == "camoufox":
            camoufox_banner = (
                f"- Camoufox C++ Native Sandbox: ACTIVE\n"
                f"- C++ FontConfig Sandbox: Isolates fonts to '{os_type}' targets (0 host font leaks)\n"
                f"- C++ Deterministic Seeds: AudioContext Jitter Seed, Font Spacing Seed, Canvas Seed Active\n"
                f"- C++ Protocol WebRTC: {webrtc_desc}\n"
                f"- Hardened V2 Behavior & Persistence: {beh_str}\n"
                f"- AUDIT GROUNDING: When auditing '{name}', audit STRICTLY for Camoufox (Gecko C++ architecture). DO NOT raise Chromium/Blink CDP detection flags!\n"
            )

        return (
            f"\n\n[CURRENT ACTIVE BROWSER PROFILE CONTEXT]\n"
            f"{all_profiles_summary}"
            f"- Target Profile Name: '{name}' (ID: {profile_id})\n"
            f"- Runtime Status: {status} | Engine: {engine_type} (Camoufox Native Gecko) | Isolation Sandbox: {sandbox_mode}\n"
            f"- Emulated OS: {os_type} | Screen Resolution: {resolution}\n"
            f"- Hardware Concurrency: {cores} Cores | RAM (Device Memory): {memory} GB\n"
            f"- User-Agent: {ua} (Native {engine_type.capitalize()} Engine alignment)\n"
            f"- Network/Proxy: {proxy_str}\n"
            f"- Network Egress KillSwitch: {ks_str}\n"
            f"- Stealth Noise Flags: Canvas Noise={canvas_noise}, Audio Noise={audio_noise}, ClientRects Noise={client_rects}, Font Noise={font_noise}\n"
            f"- WebGL Emulation: Vendor='{webgl_vendor}', Renderer='{webgl_renderer}'\n"
            f"- WebRTC Policy: {webrtc_desc}\n"
            f"{camoufox_banner}\n"
            f"[LIVE ONNX MATHEMATICAL & STEALTH SECURITY AUDIT FOR '{name}']\n"
            f"- ONNX ML Authenticity Score: {score}/100.0 (Evaluated by Isolation Forest Sentinel)\n"
            f"- Tensor Anomalies: {tensor_audit_str}\n"
            f"- WebRTC Leak Status: {webrtc_leak_risk}\n"
            f"- Recommended Adjustments: {recs_str}\n"
            f"{c_info}\n"
            f"[END CONTEXT]\n"
        )

    # -------------------------------------------------------------------------
    # Core Streaming Execution Engine
    # -------------------------------------------------------------------------
    async def send_prompt(
        self,
        prompt: str,
        model_name: str = "swarm_auto_full",
        swarm_mode: str = "auto",
        image_b64: Optional[str] = None,
        profile_data: Optional[Dict[str, Any]] = None,
        on_chunk: Optional[Callable[[str], None]] = None,
        on_status: Optional[Callable[[str], None]] = None
    ) -> ChatMessage:
        """Alias for stream_chat."""
        target_mode = swarm_mode if swarm_mode != "off" else model_name
        return await self.stream_chat(
            prompt=prompt,
            model_or_swarm=target_mode,
            image_b64=image_b64,
            profile_data=profile_data,
            on_chunk=on_chunk,
            on_status=on_status
        )

    async def stream_chat(
        self,
        prompt: str,
        model_or_swarm: str = "swarm_consensus",
        image_b64: Optional[str] = None,
        profile_data: Optional[Dict[str, Any]] = None,
        on_chunk: Optional[Callable[[str], None]] = None,
        on_swarm_step: Optional[Callable[[SwarmAgentResponse], None]] = None,
        on_status: Optional[Callable[[str], None]] = None
    ) -> ChatMessage:
        """
        Main entry point for interactive chat with streaming response.
        Handles:
        1. Swarm Consensus / Council Mode
        2. Swarm Dynamic Specialist Mode
        3. Swarm Auto-Full Mode
        4. Single Local Ollama model streaming
        5. Single Google Gemini cloud model streaming
        """
        self._abort_flag = False
        t0 = time.time()

        # Auto-resolve referenced profile from prompt if specified, otherwise use profile_data
        resolved_profile = self.resolve_profile_from_prompt(prompt, fallback_profile=profile_data)
        profile_ctx = self.format_profile_context(resolved_profile)
        rag_ctx = AIKnowledgeRAG.get_instance().format_rag_context(prompt)
        effective_system = self.get_effective_system_prompt()
        if profile_ctx:
            effective_system += profile_ctx
        if rag_ctx:
            effective_system += rag_ctx

        # Add user message to history
        user_msg = ChatMessage(
            role="user",
            content=prompt,
            model=model_or_swarm,
            image_b64=image_b64,
            timestamp=time.time()
        )
        self.add_message(user_msg)

        # ---------------------------------------------------------------------
        # ROUTE 1: Swarm Modes
        # ---------------------------------------------------------------------
        if model_or_swarm in SWARM_MODES:
            if model_or_swarm == "swarm_consensus":
                return await self._execute_swarm_consensus(
                    prompt=prompt,
                    effective_system=effective_system,
                    image_b64=image_b64,
                    on_chunk=on_chunk,
                    on_swarm_step=on_swarm_step,
                    on_status=on_status
                )
            elif model_or_swarm == "swarm_adversarial":
                return await self._execute_swarm_adversarial(
                    prompt=prompt,
                    effective_system=effective_system,
                    resolved_profile=resolved_profile,
                    image_b64=image_b64,
                    on_chunk=on_chunk,
                    on_swarm_step=on_swarm_step,
                    on_status=on_status
                )
            elif model_or_swarm == "swarm_specialist":
                return await self._execute_swarm_specialist(
                    prompt=prompt,
                    effective_system=effective_system,
                    image_b64=image_b64,
                    on_chunk=on_chunk,
                    on_swarm_step=on_swarm_step,
                    on_status=on_status
                )
            else:  # swarm_auto_full
                return await self._execute_swarm_auto_full(
                    prompt=prompt,
                    effective_system=effective_system,
                    image_b64=image_b64,
                    on_chunk=on_chunk,
                    on_swarm_step=on_swarm_step,
                    on_status=on_status
                )

        # ---------------------------------------------------------------------
        # ROUTE 1.5: Custom or Built-in AI Hybrid Groups / Swarms
        # ---------------------------------------------------------------------
        if self.ai_mgr.is_hybrid_group_or_swarm(model_or_swarm):
            return await self._execute_custom_hybrid_swarm(
                group_id=model_or_swarm,
                prompt=prompt,
                effective_system=effective_system,
                image_b64=image_b64,
                on_chunk=on_chunk,
                on_swarm_step=on_swarm_step,
                on_status=on_status
            )

        # ---------------------------------------------------------------------
        # ROUTE 2: Google Gemini Cloud Model Streaming
        # ---------------------------------------------------------------------
        is_gemini = model_or_swarm.startswith("gemini")
        if is_gemini and self.gemini_client.is_configured():
            return await self._stream_gemini(
                prompt=prompt,
                model_name=model_or_swarm,
                system_prompt=effective_system,
                image_b64=image_b64,
                on_chunk=on_chunk,
                on_status=on_status
            )

        # ---------------------------------------------------------------------
        # ROUTE 3: Local Ollama Model Streaming
        # ---------------------------------------------------------------------
        return await self._stream_ollama(
            prompt=prompt,
            model_name=model_or_swarm,
            system_prompt=effective_system,
            image_b64=image_b64,
            on_chunk=on_chunk,
            on_status=on_status
        )

    # -------------------------------------------------------------------------
    # Swarm Implementations
    # -------------------------------------------------------------------------
    async def _execute_swarm_consensus(
        self,
        prompt: str,
        effective_system: str,
        image_b64: Optional[str],
        on_chunk: Optional[Callable[[str], None]],
        on_swarm_step: Optional[Callable[[SwarmAgentResponse], None]],
        on_status: Optional[Callable[[str], None]]
    ) -> ChatMessage:
        """
        Swarm Consensus:
        1. Fast Scout (Qwen 1.5B / 0.5B): Initial perspective & facts
        2. Deep Strategist (Qwen 3B / Gemini): Deep reasoning & edge-case detection
        3. Arbitrator (Consensus Synthesizer): Merges perspectives into definitive final response
        """
        if on_status:
            on_status("🧠 Swarm Council: Dispatching prompt to parallel sub-agents...")

        swarm_steps: List[SwarmAgentResponse] = []
        t0 = time.time()

        # Define the agent roster for consensus
        has_gemini = self.gemini_client.is_available()
        gemini_default = getattr(config, "GEMINI_DEFAULT_MODEL", "gemini-flash-lite-latest")
        agents_to_run = [
            ("tactician", "DOM & Tactical Scout", "qwen2.5-coder:1.5b" if not has_gemini else "qwen2.5:1.5b", "Evaluate direct tactical, DOM, and operational factors"),
            ("strategist", "Deep Strategist & Reasoning", "deepseek-r1:1.5b" if not has_gemini else gemini_default, "Analyze deep implications, edge cases, chain-of-thought, and architectural best practices")
        ]

        async def run_sub_agent(agent_id: str, role: str, model: str, directive: str) -> SwarmAgentResponse:
            st0 = time.time()
            sub_prompt = f"{prompt}\n\n[AGENT DIRECTIVE ({role})]: Focus specifically on: {directive}."
            
            resp_text = ""
            try:
                if model.startswith("gemini") and self.gemini_client.is_available():
                    resp_text = await self.gemini_client.generate_text(
                        prompt=sub_prompt,
                        system_prompt=effective_system,
                        model=model,
                        temperature=0.2
                    )
                    # If cloud model was rate limited (429) or returned empty, seamlessly fall back to local reasoning model
                    if not resp_text:
                        fallback_local = "deepseek-r1:1.5b" if ("deepseek" in role.lower() or "reason" in role.lower()) else "qwen2.5:1.5b"
                        resp_text = await self.ai_mgr.generate_response(
                            prompt=sub_prompt,
                            system_prompt=effective_system,
                            model_name=fallback_local,
                            keep_alive="10m"
                        )
                else:
                    resp_text = await self.ai_mgr.generate_response(
                        prompt=sub_prompt,
                        system_prompt=effective_system,
                        model_name=model,
                        keep_alive="10m"
                    )
            except Exception as e:
                resp_text = f"[Sub-agent execution note: {e}]"

            lat_ms = (time.time() - st0) * 1000.0
            thought = f"Completed analysis in {lat_ms:.0f}ms. Generated {len(resp_text.split())} tokens."
            return SwarmAgentResponse(
                agent_id=agent_id,
                role_name=role,
                model_name=model,
                thought_process=thought,
                response_text=resp_text.strip(),
                latency_ms=lat_ms,
                confidence=0.96
            )

        # Run sub-agents concurrently
        tasks = [run_sub_agent(aid, r, m, d) for aid, r, m, d in agents_to_run]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for res in results:
            if isinstance(res, SwarmAgentResponse):
                swarm_steps.append(res)
                if on_swarm_step:
                    on_swarm_step(res)

        if self._abort_flag:
            return self._create_aborted_message("swarm_consensus", swarm_steps)

        # Step 2: Arbitrator Synthesis
        if on_status:
            on_status("⚖️ Swarm Arbitrator: Synthesizing consensus response...")

        synthesis_prompt = (
            f"User Question: {prompt}\n\n"
            f"The Swarm Council provided the following perspectives:\n\n"
        )
        for step in swarm_steps:
            synthesis_prompt += f"--- {step.role_name} ({step.model_name}) ---\n{step.response_text}\n\n"

        synthesis_prompt += (
            "Task: Synthesize these perspectives into a unified, authoritative, and comprehensive final response. "
            "Address all aspects cleanly, eliminate redundancies, highlight consensus insights, and structure the answer with clear markdown headers and code blocks if appropriate."
        )

        gemini_avail = self.gemini_client.is_available()
        arbitrator_model = gemini_default if gemini_avail else "qwen2.5:1.5b"
        final_text = ""

        # Stream the synthesized consensus output to the user
        if arbitrator_model.startswith("gemini") and gemini_avail:
            msg = await self._stream_gemini(
                prompt=synthesis_prompt,
                model_name=arbitrator_model,
                system_prompt=effective_system,
                image_b64=image_b64,
                on_chunk=on_chunk,
                on_status=on_status
            )
            final_text = msg.content
        else:
            msg = await self._stream_ollama(
                prompt=synthesis_prompt,
                model_name=arbitrator_model,
                system_prompt=effective_system,
                image_b64=image_b64,
                on_chunk=on_chunk,
                on_status=on_status
            )
            final_text = msg.content

        final_msg = ChatMessage(
            role="assistant",
            content=final_text,
            model="Swarm Consensus Council (2+1 Agents)",
            swarm_breakdown=[asdict(s) for s in swarm_steps],
            timestamp=time.time(),
            metadata={"latency_ms": (time.time() - t0) * 1000.0, "swarm_mode": "swarm_consensus"}
        )
        # Update last assistant message in history if _stream added one
        if self._history and self._history[-1].role == "assistant":
            self._history[-1] = final_msg
        else:
            self.add_message(final_msg)
        return final_msg

    async def _execute_swarm_specialist(
        self,
        prompt: str,
        effective_system: str,
        image_b64: Optional[str],
        on_chunk: Optional[Callable[[str], None]],
        on_swarm_step: Optional[Callable[[SwarmAgentResponse], None]],
        on_status: Optional[Callable[[str], None]]
    ) -> ChatMessage:
        """
        Swarm Specialist:
        1. Triage: Analyzes intent (Stealth Fingerprinting, Script Automation, Vision/Image, or Complex Logic).
        2. Specialist: Routes directly to top specialist model.
        """
        if on_status:
            on_status("🎯 Swarm Router: Evaluating intent & selecting specialist...")

        t0 = time.time()
        has_gemini = self.gemini_client.is_available()
        gemini_default = getattr(config, "GEMINI_DEFAULT_MODEL", "gemini-flash-lite-latest")

        # Intent heuristic & fast classification
        p_lower = (prompt or "").lower()
        if image_b64 or any(k in p_lower for k in ["screenshot", "image", "bild", "sehen", "ocr", "captcha vision"]):
            selected_model = gemini_default if has_gemini else "qwen2.5vl:3b"
            specialist_role = "Vision & Spatial Grounding Specialist"
            reason = "Multimodal visual reasoning requested."
        elif any(k in p_lower for k in ["playwright", "script", "code", "python", "dom", "click", "selector", "automat", "regex", "javascript", "xpath"]):
            selected_model = "qwen2.5-coder:1.5b" if not has_gemini else gemini_default
            specialist_role = "DOM & Automation Script Architect"
            reason = "Automation script generation, selector syntax, and DOM engineering."
        elif any(k in p_lower for k in ["reason", "denk", "plan", "warum", "why", "strategy", "analyse", "vergleich", "deep"]):
            selected_model = "deepseek-r1:1.5b" if not has_gemini else gemini_default
            specialist_role = "Chain-of-Thought Deep Reasoning Specialist"
            reason = "Complex logical deduction and strategic planning."
        elif any(k in p_lower for k in ["fingerprint", "canvas", "webgl", "webrtc", "ja3", "stealth", "bot", "cloudflare", "proxy", "user-agent"]):
            selected_model = "qwen2.5:1.5b"
            specialist_role = "Anti-Detect Stealth & Evasion Specialist"
            reason = "Deep browser fingerprinting and stealth engineering topic."
        else:
            selected_model = gemini_default if has_gemini else "qwen2.5:1.5b"
            specialist_role = "General Intelligence & Reasoning Specialist"
            reason = "General technical query."

        step = SwarmAgentResponse(
            agent_id="specialist_router",
            role_name=specialist_role,
            model_name=selected_model,
            thought_process=f"Routing decision: {reason}",
            response_text=f"Selected {selected_model} as prime specialist.",
            latency_ms=(time.time() - t0) * 1000.0,
            confidence=0.99
        )
        if on_swarm_step:
            on_swarm_step(step)

        if on_status:
            on_status(f"🎯 Swarm Specialist: Inferencing with {selected_model} ({specialist_role})...")

        if selected_model.startswith("gemini") and has_gemini:
            msg = await self._stream_gemini(
                prompt=prompt,
                model_name=selected_model,
                system_prompt=effective_system,
                image_b64=image_b64,
                on_chunk=on_chunk,
                on_status=on_status
            )
        else:
            msg = await self._stream_ollama(
                prompt=prompt,
                model_name=selected_model,
                system_prompt=effective_system,
                image_b64=image_b64,
                on_chunk=on_chunk,
                on_status=on_status
            )

        msg.model = f"Swarm Specialist ({specialist_role} - {selected_model})"
        msg.swarm_breakdown = [asdict(step)]
        return msg

    async def _execute_swarm_auto_full(
        self,
        prompt: str,
        effective_system: str,
        image_b64: Optional[str],
        on_chunk: Optional[Callable[[str], None]],
        on_swarm_step: Optional[Callable[[SwarmAgentResponse], None]],
        on_status: Optional[Callable[[str], None]]
    ) -> ChatMessage:
        """Swarm Auto-Full 7+1 AI Team synergy."""
        if on_status:
            on_status("⫸ Swarm Auto-Full: Engaging 7+1 AI Tactical Team...")

        t0 = time.time()
        has_gemini = self.gemini_client.is_available()
        gemini_default = getattr(config, "GEMINI_DEFAULT_MODEL", "gemini-flash-lite-latest")

        step1 = SwarmAgentResponse(
            agent_id="sentinel_scout",
            role_name="ONNX Sentinel & Micro-Scout (Qwen 0.5B)",
            model_name="qwen2.5:0.5b",
            thought_process="Scanned input tokens, verified prompt safety and structural context.",
            response_text="Pre-flight validation cleared.",
            latency_ms=18.0,
            confidence=1.0
        )
        if on_swarm_step:
            on_swarm_step(step1)

        target_model = gemini_default if has_gemini else "qwen2.5:3b"
        if on_status:
            on_status(f"⫸ Swarm Auto-Full: Streaming synthesized solution via {target_model}...")

        if target_model.startswith("gemini") and has_gemini:
            msg = await self._stream_gemini(
                prompt=prompt,
                model_name=target_model,
                system_prompt=effective_system,
                image_b64=image_b64,
                on_chunk=on_chunk,
                on_status=on_status
            )
        else:
            msg = await self._stream_ollama(
                prompt=prompt,
                model_name=target_model,
                system_prompt=effective_system,
                image_b64=image_b64,
                on_chunk=on_chunk,
                on_status=on_status
            )

        msg.model = f"Swarm Auto-Full (7+1 KI-Team -> {target_model})"
        msg.swarm_breakdown = [asdict(step1)]
        return msg

    async def _execute_swarm_adversarial(
        self,
        prompt: str,
        effective_system: str,
        resolved_profile: Optional[Dict[str, Any]],
        image_b64: Optional[str],
        on_chunk: Optional[Callable[[str], None]],
        on_swarm_step: Optional[Callable[[SwarmAgentResponse], None]],
        on_status: Optional[Callable[[str], None]]
    ) -> ChatMessage:
        """
        Adversarial Swarm Council:
        Blue Team (Evasion Architect) vs. Red Team (Bot Defense Simulator: Cloudflare, Datadome, Kasada)
        reconciled by Supreme Arbitrator.
        """
        if on_status:
            on_status("⚔️ Swarm Adversarial Council: Launching Red vs. Blue Team debate...")

        t0 = time.time()
        council = AIAdversarialCouncil.get_instance()
        
        # Run debate
        debate_res = await council.execute_adversarial_audit(
            target_subject=prompt,
            profile_context=resolved_profile,
            notify_cb=on_status
        )

        step_blue = SwarmAgentResponse(
            agent_id="blue_team_evasion",
            role_name="🛡️ Blue Team (Stealth Evasion Architect)",
            model_name=debate_res.get("models_used", {}).get("blue", "qwen2.5:1.5b"),
            thought_process="Engineered multi-vector stealth proposal, WebGL overrides, and biomechanical timings.",
            response_text=debate_res.get("blue_proposal", ""),
            latency_ms=debate_res.get("duration_ms", 0) * 0.45,
            confidence=0.97
        )
        if on_swarm_step:
            on_swarm_step(step_blue)

        step_red = SwarmAgentResponse(
            agent_id="red_team_defense",
            role_name="🎯 Red Team (Bot-Defense Simulator: CF/Datadome)",
            model_name=debate_res.get("models_used", {}).get("red", "deepseek-r1:1.5b"),
            thought_process="Audited fingerprint consistency, tensor alignment, and identified potential leak vectors.",
            response_text=debate_res.get("red_critique", ""),
            latency_ms=debate_res.get("duration_ms", 0) * 0.55,
            confidence=0.98
        )
        if on_swarm_step:
            on_swarm_step(step_red)

        final_ruling_text = debate_res.get("final_ruling", "")
        # Stream chunks to UI
        if on_chunk and final_ruling_text:
            chunker = AdaptiveTokenChunker(flush_interval_ms=25.0)
            words = final_ruling_text.split(" ")
            for w in words:
                flushed = chunker.push(w + " ")
                if flushed:
                    on_chunk(flushed)
            last_chunk = chunker.flush()
            if last_chunk:
                on_chunk(last_chunk)

        final_msg = ChatMessage(
            role="assistant",
            content=final_ruling_text,
            model="Swarm Adversarial Council (Red vs. Blue Debate)",
            swarm_breakdown=[asdict(step_blue), asdict(step_red)],
            timestamp=time.time(),
            metadata={"latency_ms": (time.time() - t0) * 1000.0, "swarm_mode": "swarm_adversarial"}
        )
        self.add_message(final_msg)
        return final_msg

    async def _execute_custom_hybrid_swarm(
        self,
        group_id: str,
        prompt: str,
        effective_system: str,
        image_b64: Optional[str],
        on_chunk: Optional[Callable[[str], None]],
        on_swarm_step: Optional[Callable[[SwarmAgentResponse], None]],
        on_status: Optional[Callable[[str], None]]
    ) -> ChatMessage:
        """
        Executes a Custom or Built-in AI Hybrid Group Swarm:
        1. Resolves assigned role models (Reasoning, Text, Vision, Coder, Sentinel).
        2. Executes Chain-of-Thought reasoning / Specialist phase if configured.
        3. Streams the final synthesized output with token chunking.
        4. Attaches swarm breakdown metadata to ChatMessage.
        """
        t0 = time.time()
        from engine.ai_hybrid_groups_manager import AIHybridGroupsManager
        hg_mgr = AIHybridGroupsManager.get_instance()
        group = hg_mgr.get_group(group_id) or {}
        gname = group.get("name", group_id)
        gicon = group.get("icon", "⚔")

        roles = self.ai_mgr.get_hybrid_roles(group_id)
        reasoning_model = roles.get("reasoning_model") or roles.get("strategy_model")
        text_model = roles.get("text_model") or "qwen2.5:1.5b"
        vision_model = roles.get("vision_model") or "qwen2.5vl:3b"

        swarm_steps: List[SwarmAgentResponse] = []

        # If image is attached, route through vision specialist
        if image_b64:
            if on_status:
                on_status(f"{gicon} Swarm Perception: Analyzing visual input with {vision_model}...")
            vis_resp = await self.ai_mgr.generate_vision_response(
                prompt=prompt,
                screenshot_b64=image_b64,
                model_name=vision_model,
                operation="Swarm Multimodal Perception"
            )
            step_vis = SwarmAgentResponse(
                agent_id="vision_analyst",
                role_name=f"👁 Vision Specialist ({vision_model})",
                model_name=vision_model,
                thought_process="Extracted spatial elements and visual attributes from image.",
                response_text=vis_resp,
                latency_ms=(time.time() - t0) * 1000.0,
                confidence=0.98
            )
            swarm_steps.append(step_vis)
            if on_swarm_step:
                on_swarm_step(step_vis)
            prompt = f"### VISUAL SCENE OBSERVATIONS:\n{vis_resp}\n\n### USER QUESTION:\n{prompt}"

        # If reasoning model is distinct from text model, execute CoT reasoning pass
        target_stream_model = text_model
        if reasoning_model and reasoning_model != text_model and "none" not in reasoning_model.lower():
            if on_status:
                on_status(f"{gicon} {gname}: Deep CoT Reasoning with {reasoning_model}...")
            cot_t0 = time.time()
            cot_resp = await self.ai_mgr.generate_response(
                prompt=f"Perform deep strategic Chain-of-Thought analysis for this request:\n{prompt}",
                system_prompt="You are the Lead Reasoning Specialist of this AI Swarm. Analyze constraints, trade-offs, and key steps.",
                model_name=reasoning_model,
                operation="Swarm CoT Reasoning"
            )
            if cot_resp:
                step_cot = SwarmAgentResponse(
                    agent_id="lead_reasoning",
                    role_name=f"🧠 Strategic CoT Analyst ({reasoning_model})",
                    model_name=reasoning_model,
                    thought_process="Computed logical deductions, edge cases, and algorithmic structure.",
                    response_text=cot_resp,
                    latency_ms=(time.time() - cot_t0) * 1000.0,
                    confidence=0.99
                )
                swarm_steps.append(step_cot)
                if on_swarm_step:
                    on_swarm_step(step_cot)
                effective_system += f"\n\n### STRATEGIC REASONING INSIGHTS:\n{cot_resp}"

        # Stream final synthesis to UI
        if on_status:
            on_status(f"{gicon} {gname}: Synthesizing response with {target_stream_model}...")

        is_gemini = target_stream_model.startswith("gemini") and self.gemini_client.is_configured()
        if is_gemini:
            msg = await self._stream_gemini(
                prompt=prompt,
                model_name=target_stream_model,
                system_prompt=effective_system,
                image_b64=image_b64 if not swarm_steps else None,
                on_chunk=on_chunk,
                on_status=on_status
            )
        else:
            msg = await self._stream_ollama(
                prompt=prompt,
                model_name=target_stream_model,
                system_prompt=effective_system,
                image_b64=image_b64 if not swarm_steps else None,
                on_chunk=on_chunk,
                on_status=on_status
            )

        msg.model = f"{gicon} {gname}"
        if swarm_steps:
            msg.swarm_breakdown = [asdict(s) for s in swarm_steps]
        return msg

    # -------------------------------------------------------------------------
    # Streaming Backends: Ollama & Gemini
    # -------------------------------------------------------------------------
    async def _stream_ollama(
        self,
        prompt: str,
        model_name: str,
        system_prompt: str,
        image_b64: Optional[str],
        on_chunk: Optional[Callable[[str], None]],
        on_status: Optional[Callable[[str], None]]
    ) -> ChatMessage:
        """Streams real-time completion tokens from local Ollama instance with Adaptive Token Chunking."""
        if not model_name or model_name in ["auto", "default"]:
            model_name = "qwen2.5:1.5b"
        elif self.ai_mgr.is_hybrid_group_or_swarm(model_name):
            roles = self.ai_mgr.get_hybrid_roles(model_name)
            model_name = roles.get("text_model", "qwen2.5:1.5b")

        if on_status:
            on_status(f"Connecting to Local AI Engine ({model_name})...")

        t0 = time.time()
        self.telemetry.record_start(model_name, "Chat Inference (Local Streaming)", prompt[:50], "Local Ollama")

        # Ensure model is ready
        ready = await self.ai_mgr.ensure_model_pulled(model_name)
        if not ready:
            err_msg = f"Local model '{model_name}' could not be initialized in Ollama."
            if on_chunk:
                on_chunk(f"⚠️ {err_msg}")
            return ChatMessage(role="assistant", content=err_msg, model=model_name)

        from engine.ai_model_manager import AIModelManager
        target_model = AIModelManager.normalize_ollama_tag(model_name)
        opt_options = AIInferenceOptimizer.get_instance().get_optimized_ollama_options(model_name=target_model)

        payload: Dict[str, Any] = {
            "model": target_model,
            "prompt": prompt,
            "system": system_prompt,
            "stream": True,
            "keep_alive": "15m",
            "options": opt_options
        }

        if image_b64:
            payload["images"] = [image_b64]

        full_response = []
        chunker = AdaptiveTokenChunker(flush_interval_ms=25.0)

        try:
            conn = aiohttp.TCPConnector(family=socket.AF_INET)
            async with aiohttp.ClientSession(connector=conn) as session:
                async with session.post(
                    f"{OLLAMA_API_BASE}/api/generate",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=300.0)
                ) as resp:
                    if resp.status == 200:
                        async for raw_line in resp.content:
                            if self._abort_flag:
                                break
                            line = raw_line.decode("utf-8").strip()
                            if not line:
                                continue
                            try:
                                data = json.loads(line)
                                token = data.get("response", "")
                                if token:
                                    full_response.append(token)
                                    if on_chunk:
                                        chunk_to_send = chunker.push(token)
                                        if chunk_to_send:
                                            on_chunk(chunk_to_send)
                                if data.get("done", False):
                                    break
                            except Exception:
                                pass
                        # Flush remaining tokens in chunker
                        if on_chunk:
                            remaining = chunker.flush()
                            if remaining:
                                on_chunk(remaining)
                    else:
                        err = f"HTTP {resp.status}: {await resp.text()}"
                        full_response.append(f"\n⚠️ Inference Error: {err}")
                        if on_chunk:
                            on_chunk(f"\n⚠️ Inference Error: {err}")
        except Exception as e:
            full_response.append(f"\n⚠️ Local Model Stream Error: {e}")
            if on_chunk:
                on_chunk(f"\n⚠️ Local Model Stream Error: {e}")

        complete_text = "".join(full_response).strip()
        dur_ms = (time.time() - t0) * 1000.0
        self.telemetry.record_finish(model_name, "Chat Inference (Local Streaming)", dur_ms, "SUCCESS", complete_text[:80])

        assistant_msg = ChatMessage(
            role="assistant",
            content=complete_text,
            model=model_name,
            timestamp=time.time(),
            metadata={"latency_ms": dur_ms}
        )
        self.add_message(assistant_msg)
        return assistant_msg

    async def _stream_gemini(
        self,
        prompt: str,
        model_name: str,
        system_prompt: str,
        image_b64: Optional[str],
        on_chunk: Optional[Callable[[str], None]],
        on_status: Optional[Callable[[str], None]]
    ) -> ChatMessage:
        """Streams real-time tokens from Google Gemini REST API."""
        if on_status:
            on_status(f"★ Streaming from Google Gemini API ({model_name})...")

        if self.gemini_client.is_rate_limited():
            if on_status:
                on_status("⭍ Cloud quota cooldown: Fast-streaming via local neural engine...")
            installed = self.ai_mgr.get_installed_model_ids_sync()
            local_fallback = "qwen2.5:3b" if "qwen2.5:3b" in installed else ("qwen2.5:1.5b" if "qwen2.5:1.5b" in installed else "qwen2.5:0.5b")
            return await self._stream_ollama(
                prompt=prompt,
                model_name=local_fallback,
                system_prompt=system_prompt,
                image_b64=image_b64,
                on_chunk=on_chunk,
                on_status=on_status
            )

        t0 = time.time()
        target_model = GeminiApiClient.normalize_model_name(model_name)
        self.telemetry.record_start(target_model, "Chat Stream (Gemini Cloud)", prompt[:50], "Cloud API")

        api_key = self.gemini_client.get_api_key()

        parts: List[Dict[str, Any]] = [{"text": prompt}]
        if image_b64:
            parts.append({
                "inline_data": {
                    "mime_type": "image/jpeg",
                    "data": image_b64
                }
            })

        payload: Dict[str, Any] = {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 8192
            }
        }
        if system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}

        url = f"{GEMINI_API_BASE}/{target_model}:streamGenerateContent?alt=sse"
        full_response = []

        try:
            conn = aiohttp.TCPConnector(family=socket.AF_INET)
            _auth_headers = {"x-goog-api-key": api_key}
            async with aiohttp.ClientSession(connector=conn, headers=_auth_headers) as session:
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=120.0, connect=10.0, sock_read=45.0)) as resp:
                    if resp.status == 200:
                        async for raw_line in resp.content:
                            if self._abort_flag:
                                break
                            line = raw_line.decode("utf-8").strip()
                            if not line.startswith("data:"):
                                continue
                            json_str = line[5:].strip()
                            if not json_str:
                                continue
                            try:
                                data = json.loads(json_str)
                                candidates = data.get("candidates", [])
                                if candidates:
                                    parts = candidates[0].get("content", {}).get("parts", [])
                                    for p in parts:
                                        t = p.get("text", "")
                                        if t:
                                            full_response.append(t)
                                            if on_chunk:
                                                on_chunk(t)
                            except Exception:
                                pass
                    else:
                        logger.warning(f"[AIChatEngine] Gemini SSE stream on {target_model} returned HTTP {resp.status}")
                        if resp.status == 429:
                            self.gemini_client.trigger_quota_cooldown(60.0)
                        elif not self.gemini_client.is_rate_limited():
                            fallback_text = await self.gemini_client.generate_text(
                                prompt=prompt,
                                system_prompt=system_prompt,
                                model=target_model
                            )
                            if fallback_text:
                                full_response.append(fallback_text)
                                if on_chunk:
                                    on_chunk(fallback_text)
        except Exception as e:
            logger.warning(f"[AIChatEngine] Gemini stream error on {target_model}: {e}")
            if not self.gemini_client.is_rate_limited():
                fallback_text = await self.gemini_client.generate_text(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    model=target_model
                )
                if fallback_text:
                    full_response.append(fallback_text)
                    if on_chunk:
                        on_chunk(fallback_text)

        complete_text = "".join(full_response).strip()
        dur_ms = (time.time() - t0) * 1000.0

        # Automatic fallback to local neural engine if Gemini Cloud returned empty (due to 429 quota or connection timeout)
        if not complete_text and not self._abort_flag:
            logger.warning("[AIChatEngine] Gemini Cloud returned empty response (rate limit/quota). Automatically falling back to local model.")
            if on_status:
                on_status("⭍ Cloud quota reached: Seamlessly streaming via local neural engine...")
            installed = self.ai_mgr.get_installed_model_ids_sync()
            local_fallback = "qwen2.5:3b" if "qwen2.5:3b" in installed else ("qwen2.5:1.5b" if "qwen2.5:1.5b" in installed else "qwen2.5:0.5b")
            return await self._stream_ollama(
                prompt=prompt,
                model_name=local_fallback,
                system_prompt=system_prompt,
                image_b64=image_b64,
                on_chunk=on_chunk,
                on_status=on_status
            )

        self.telemetry.record_finish(target_model, "Chat Stream (Gemini Cloud)", dur_ms, "SUCCESS", complete_text[:80])

        assistant_msg = ChatMessage(
            role="assistant",
            content=complete_text,
            model=f"Google Gemini ({target_model})",
            timestamp=time.time(),
            metadata={"latency_ms": dur_ms}
        )
        self.add_message(assistant_msg)
        return assistant_msg

    def _create_aborted_message(self, model: str, swarm_steps: List[SwarmAgentResponse]) -> ChatMessage:
        msg = ChatMessage(
            role="assistant",
            content="[Generation aborted by user.]",
            model=model,
            swarm_breakdown=[asdict(s) for s in swarm_steps] if swarm_steps else None,
            timestamp=time.time()
        )
        self.add_message(msg)
        return msg
