import os
import re
import json
import logging
from typing import Dict, Any, List, Optional, Set, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger("AntiBotScriptDeobfuscator")


@dataclass
class DeobfuscationAnalysisResult:
    is_analyzed: bool
    total_probes_detected: int
    detected_apis: List[str] = field(default_factory=list)
    probed_categories: List[str] = field(default_factory=list)
    deobfuscated_preview: str = ""
    suggested_patches: List[Dict[str, str]] = field(default_factory=list)
    risk_score: float = 0.0  # 0.0 to 1.0


class AntiBotScriptDeobfuscator:
    """
    Local AST & String-Array Normalizer for Anti-Bot Fingerprinting Payloads.
    Analyzes obfuscated JavaScript from DataDome, Cloudflare Turnstile/Challenge,
    Kasada, and Akamai to identify newly injected fingerprinting probes.
    """

    _instance: Optional['AntiBotScriptDeobfuscator'] = None

    # High-value anti-detect evasion fingerprinting targets
    KNOWN_PROBE_PATTERNS: Dict[str, Tuple[str, str]] = {
        "navigator.webdriver": ("CDP / Automation", "Set navigator.webdriver = undefined & suppress CDP automation flag"),
        "navigator.plugins": ("Browser Hygiene", "Ensure native plugin array length > 0 matching platform"),
        "navigator.languages": ("Locale Alignment", "Align languages with residential proxy geo-location"),
        "navigator.useragentdata": ("Client Hints", "Emulate Chromium Sec-CH-UA brand tensors"),
        "webgl": ("WebGL Hardware", "Enforce OS-aligned ANGLE / Mesa GPU vendor string"),
        "unmasked_vendor_webgl": ("WebGL Vendor", "Spoof WebGL debug vendor parameter 37445"),
        "unmasked_renderer_webgl": ("WebGL Renderer", "Spoof WebGL debug renderer parameter 37446"),
        "todataurl": ("Canvas Fingerprint", "Inject deterministic cryptographic noise into canvas toDataURL"),
        "getimagedata": ("Canvas 2D", "Add subtle pixel-level canvas noise in getImageData"),
        "audiocontext": ("Audio Frequency", "Normalize AudioContext oscillator and analyser FFT buffers"),
        "webrtc": ("WebRTC Egress", "Bind local ICE candidate IPs to active proxy exit IP"),
        "screen.colordepth": ("Display Metrics", "Enforce authentic screen resolution and 24-bit color depth"),
        "performance.timing": ("Timing Resolution", "Clamp Performance API microsecond timestamps"),
        "chrome.runtime": ("Extension Runtime", "Emulate or isolate window.chrome namespace"),
        "permissions.query": ("Permissions API", "Emulate authentic Notification.permission states")
    }

    @classmethod
    def get_instance(cls) -> 'AntiBotScriptDeobfuscator':
        if cls._instance is None:
            cls._instance = AntiBotScriptDeobfuscator()
        return cls._instance

    @classmethod
    def normalize_hex_literals(cls, code: str) -> str:
        """Decodes hex escape sequences \\xHH and unicode \\uHHHH into clean ASCII/UTF-8 strings."""
        if not code:
            return ""

        # Decode \xHH
        def replace_hex(match):
            try:
                return chr(int(match.group(1), 16))
            except Exception:
                return match.group(0)

        code_decoded = re.sub(r'\\x([0-9a-fA-F]{2})', replace_hex, code)

        # Decode \uHHHH
        def replace_unicode(match):
            try:
                return chr(int(match.group(1), 16))
            except Exception:
                return match.group(0)

        code_decoded = re.sub(r'\\u([0-9a-fA-F]{4})', replace_unicode, code_decoded)
        return code_decoded

    @classmethod
    def resolve_string_arrays(cls, code: str) -> str:
        """
        Locates simple string arrays (e.g. var _0x1a2b = ['webdriver', 'plugins', 'webgl'])
        and inlines array index accesses _0x1a2b[0] with their literal values.
        """
        if not code:
            return ""

        # Match simple array declarations: var _0xabc = ['str1', 'str2', ...];
        array_pattern = r'(?:var|const|let)\s+([a-zA-Z0-9_$]+)\s*=\s*\[([^\]]+)\];'
        arrays: Dict[str, List[str]] = {}

        for m in re.finditer(array_pattern, code):
            arr_name = m.group(1)
            raw_elements = m.group(2)
            # Extract string literals
            elems = re.findall(r'[\'"]([^\'"]*)[\'"]', raw_elements)
            if elems:
                arrays[arr_name] = elems

        result = code
        # Replace simple array lookups: arr[0] -> 'webdriver'
        for arr_name, items in arrays.items():
            def replacer(match):
                idx = int(match.group(1))
                if 0 <= idx < len(items):
                    return f"'{items[idx]}'"
                return match.group(0)

            result = re.sub(rf'{re.escape(arr_name)}\[(\d+)\]', replacer, result)

        return result

    def analyze_script(self, script_code: str, script_url: str = "") -> DeobfuscationAnalysisResult:
        """
        Deobfuscates client sensor script and reports all detected anti-bot probe vectors.
        """
        if not script_code:
            return DeobfuscationAnalysisResult(is_analyzed=False, total_probes_detected=0)

        # 1. Normalize hex and unicode literals
        normalized = self.normalize_hex_literals(script_code)

        # 2. Resolve string array lookups
        normalized = self.resolve_string_arrays(normalized)

        detected_apis: List[str] = []
        categories: Set[str] = set()
        suggested_patches: List[Dict[str, str]] = []

        norm_lower = normalized.lower()

        # 3. Check for high-value detection vectors
        for probe_key, (category, patch_advice) in self.KNOWN_PROBE_PATTERNS.items():
            if probe_key in norm_lower:
                detected_apis.append(probe_key)
                categories.add(category)
                suggested_patches.append({
                    "probe": probe_key,
                    "category": category,
                    "mitigation": patch_advice
                })

        # Calculate risk score based on detection diversity
        risk_score = min(1.0, len(detected_apis) * 0.12)

        return DeobfuscationAnalysisResult(
            is_analyzed=True,
            total_probes_detected=len(detected_apis),
            detected_apis=detected_apis,
            probed_categories=list(categories),
            deobfuscated_preview=normalized[:300].strip(),
            suggested_patches=suggested_patches,
            risk_score=risk_score
        )
