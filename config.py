import os

# Base Directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROFILES_DIR = os.path.join(BASE_DIR, "profiles")
EXTENSIONS_DIR = os.path.join(BASE_DIR, "extensions")
SESSIONS_DIR = os.path.join(BASE_DIR, "sessions")
CAMOUFOX_DIR = os.path.join(BASE_DIR, "camoufox")

# Ensure required directories exist
for path in [PROFILES_DIR, EXTENSIONS_DIR, SESSIONS_DIR, CAMOUFOX_DIR]:
    os.makedirs(path, exist_ok=True)

# Application Metadata
APP_NAME = "OXBROWSER"
APP_VERSION = "1.0.0"
SECRET_KEY: str = ""  # Populated from encrypted vault via SecretsManager on startup

# REST API Settings
API_HOST: str = os.environ.get("SOXBOT_API_HOST", "127.0.0.1")
API_PORT: int = int(os.environ.get("SOXBOT_API_PORT", 59200))
API_AUTH_ENABLED: bool = True
# NOTE: Token can be set via Settings UI, config vault, or SOXBOT_API_TOKEN env var.
# If empty, a cryptographically secure 32-byte token is auto-generated on startup and persisted in vault.
API_BEARER_TOKEN: str = os.environ.get("SOXBOT_API_TOKEN", "")

# Default User-Agent Templates for Chromium and Firefox (Camoufox) Engines
DEFAULT_USER_AGENTS_CHROME = {
    "windows": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
    "mac": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
    "linux": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
    "android": "Mozilla/5.0 (Linux; Android 14; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Mobile Safari/537.36",
    "ios": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Mobile/15E148 Safari/604.1"
}

DEFAULT_USER_AGENTS_FIREFOX = {
    "windows": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:152.0) Gecko/20100101 Firefox/152.0",
    "mac": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:152.0) Gecko/20100101 Firefox/152.0",
    "linux": "Mozilla/5.0 (X11; Linux x86_64; rv:152.0) Gecko/20100101 Firefox/152.0",
    "android": "Mozilla/5.0 (Android 14; Mobile; rv:152.0) Gecko/152.0 Firefox/152.0",
    "ios": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) FxiOS/152.0 Mobile/15E148 Safari/605.1.15"
}




DEFAULT_USER_AGENTS = DEFAULT_USER_AGENTS_CHROME

def get_default_user_agent(os_type: str = "windows", engine: str = "camoufox") -> str:
    os_key = (os_type or "windows").lower().strip()
    eng_key = (engine or "camoufox").lower().strip()
    if eng_key in ["camoufox", "firefox"]:
        return DEFAULT_USER_AGENTS_FIREFOX.get(os_key, DEFAULT_USER_AGENTS_FIREFOX["windows"])
    return DEFAULT_USER_AGENTS_CHROME.get(os_key, DEFAULT_USER_AGENTS_CHROME["windows"])

# WebGL Vendor / Renderer Profiles (Organized strictly by OS for Tensor Harmony)
WEBGL_PRESETS_BY_OS = {
    "windows": [
        {"vendor": "Google Inc. (NVIDIA)", "renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 4090 Direct3D11 vs_5_0 ps_5_0, D3D11)"},
        {"vendor": "Google Inc. (NVIDIA)", "renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 4080 Direct3D11 vs_5_0 ps_5_0, D3D11)"},
        {"vendor": "Google Inc. (NVIDIA)", "renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 4070 Direct3D11 vs_5_0 ps_5_0, D3D11)"},
        {"vendor": "Google Inc. (NVIDIA)", "renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)"},
        {"vendor": "Google Inc. (AMD)", "renderer": "ANGLE (AMD, AMD Radeon RX 7900 XTX Direct3D11 vs_5_0 ps_5_0, D3D11)"},
        {"vendor": "Google Inc. (AMD)", "renderer": "ANGLE (AMD, AMD Radeon RX 6700 XT Direct3D11 vs_5_0 ps_5_0, D3D11)"},
        {"vendor": "Google Inc. (Intel)", "renderer": "ANGLE (Intel, Intel(R) Arc(TM) A770 Graphics Direct3D11 vs_5_0 ps_5_0, D3D11)"},
        {"vendor": "Google Inc. (Intel)", "renderer": "ANGLE (Intel, Intel(R) Iris(R) Xe Graphics Direct3D11 vs_5_0 ps_5_0, D3D11)"}
    ],
    "linux": [
        {"vendor": "Mesa/X.org", "renderer": "Mesa DRI AMD Radeon Graphics (RENOIR, DRM 3.35.0, 5.15.0-76-generic, LLVM 15.0.7)"},
        {"vendor": "Mesa/X.org", "renderer": "Mesa Intel(R) Iris(R) Xe Graphics (TGL GT2)"},
        {"vendor": "Mesa/X.org", "renderer": "Mesa Intel(R) UHD Graphics 770 (ADL-S GT1)"},
        {"vendor": "AMD", "renderer": "AMD Radeon RX 7900 XTX (RADV NAVI31, LLVM 18.1.1, DRM 3.57)"},
        {"vendor": "AMD", "renderer": "AMD Radeon RX 6700 XT (RADV NAVI22, LLVM 18.1.1, DRM 3.57)"},
        {"vendor": "NVIDIA Corporation", "renderer": "NVIDIA GeForce RTX 4090/PCIe/SSE2"},
        {"vendor": "NVIDIA Corporation", "renderer": "NVIDIA GeForce RTX 4080/PCIe/SSE2"},
        {"vendor": "NVIDIA Corporation", "renderer": "NVIDIA GeForce RTX 3060/PCIe/SSE2"},
        {"vendor": "Mesa", "renderer": "llvmpipe (LLVM 18.1.8, 256 bits)"}
    ],
    "mac": [
        {"vendor": "Apple Inc.", "renderer": "Apple M3 Max"},
        {"vendor": "Apple Inc.", "renderer": "Apple M3 Pro"},
        {"vendor": "Apple Inc.", "renderer": "Apple M2 Max"},
        {"vendor": "Apple Inc.", "renderer": "Apple M1 Max"},
        {"vendor": "Apple Inc.", "renderer": "Apple M1"},
        {"vendor": "Intel Inc.", "renderer": "Intel Iris Plus Graphics 655"}
    ],
    "android": [
        {"vendor": "Qualcomm", "renderer": "Adreno (TM) 750"},
        {"vendor": "Qualcomm", "renderer": "Adreno (TM) 740"},
        {"vendor": "ARM", "renderer": "Mali-G715 MC11"},
        {"vendor": "ARM", "renderer": "Mali-G78 MP14"}
    ],
    "ios": [
        {"vendor": "Apple Inc.", "renderer": "Apple A18 Pro GPU"},
        {"vendor": "Apple Inc.", "renderer": "Apple A17 Pro GPU"},
        {"vendor": "Apple Inc.", "renderer": "Apple A16 Bionic GPU"},
        {"vendor": "Apple Inc.", "renderer": "Apple A15 Bionic GPU"}
    ]
}

def get_webgl_presets_for_os(os_name: str) -> list:
    """Returns the list of matching WebGL vendor/renderer presets for the specified OS."""
    os_clean = (os_name or "windows").lower().strip()
    if "mac" in os_clean:
        return WEBGL_PRESETS_BY_OS["mac"]
    elif "linux" in os_clean:
        return WEBGL_PRESETS_BY_OS["linux"]
    elif "android" in os_clean:
        return WEBGL_PRESETS_BY_OS["android"]
    elif "ios" in os_clean or "iphone" in os_clean or "ipad" in os_clean:
        return WEBGL_PRESETS_BY_OS["ios"]
    return WEBGL_PRESETS_BY_OS["windows"]

# Host System Detection & Metadata
from engine.platform_helper import PlatformHelper

HOST_OS = PlatformHelper.get_current_platform()
IS_WINDOWS = PlatformHelper.is_windows()
IS_LINUX = PlatformHelper.is_linux()
IS_MAC = PlatformHelper.is_mac()
HOST_OS_NAME = PlatformHelper.get_platform_display_name()

_CACHED_NATIVE_WEBGL = None

def detect_native_webgl_info() -> dict:
    """Detects the real/native host hardware GPU vendor and renderer using OpenGL/system diagnostics."""
    global _CACHED_NATIVE_WEBGL
    if _CACHED_NATIVE_WEBGL is not None:
        return _CACHED_NATIVE_WEBGL

    import shutil
    import subprocess
    vendor = ""
    renderer = ""
    system = HOST_OS

    # Method 1: System tool detection (glxinfo, lspci, system_profiler, wmic, powershell)
    if system == "linux":
        if shutil.which("glxinfo"):
            try:
                out = subprocess.check_output(["glxinfo", "-B"], stderr=subprocess.DEVNULL, timeout=2).decode("utf-8", "ignore")
                for line in out.splitlines():
                    if "OpenGL vendor string:" in line:
                        vendor = line.split(":", 1)[1].strip()
                    elif "OpenGL renderer string:" in line:
                        renderer = line.split(":", 1)[1].strip()
            except Exception:
                pass
        if not renderer and shutil.which("lspci"):
            try:
                out = subprocess.check_output(["lspci"], stderr=subprocess.DEVNULL, timeout=2).decode("utf-8", "ignore")
                for line in out.splitlines():
                    if "VGA" in line or "3D" in line:
                        gpu_part = line.split(":", 2)[-1].strip()
                        renderer = gpu_part
                        if "NVIDIA" in gpu_part.upper():
                            vendor = "NVIDIA Corporation"
                        elif "AMD" in gpu_part.upper() or "ATI" in gpu_part.upper():
                            vendor = "Mesa/X.org"
                        elif "INTEL" in gpu_part.upper():
                            vendor = "Mesa/X.org"
                        break
            except Exception:
                pass
    elif system == "mac":
        try:
            out = subprocess.check_output(["system_profiler", "SPDisplaysDataType"], stderr=subprocess.DEVNULL, timeout=3).decode("utf-8", "ignore")
            for line in out.splitlines():
                if "Chipset Model:" in line:
                    renderer = line.split(":", 1)[1].strip()
                elif "Vendor:" in line:
                    vendor = line.split(":", 1)[1].strip()
        except Exception:
            pass
        if not vendor:
            vendor = "Apple Inc."
        if not renderer:
            renderer = "Apple M1"
    elif system == "windows":
        flags = PlatformHelper.get_subprocess_creation_flags()
        # 1a. Try WMIC if available
        try:
            out = subprocess.check_output(
                ["wmic", "path", "win32_VideoController", "get", "name"],
                shell=False, stderr=subprocess.DEVNULL, timeout=3, creationflags=flags
            ).decode("utf-8", "ignore")
            lines = [l.strip() for l in out.splitlines() if l.strip() and "Name" not in l]
            if lines:
                renderer = lines[0]
        except Exception:
            pass

        # 1b. Fallback to PowerShell Get-CimInstance (Windows 11 24H2+ where WMIC is removed)
        if not renderer:
            try:
                out = subprocess.check_output(
                    ["powershell", "-NoProfile", "-NonInteractive", "-Command", "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name"],
                    shell=False, stderr=subprocess.DEVNULL, timeout=3, creationflags=flags
                ).decode("utf-8", "ignore")
                lines = [l.strip() for l in out.splitlines() if l.strip()]
                if lines:
                    renderer = lines[0]
            except Exception:
                pass

        if renderer:
            if "NVIDIA" in renderer.upper():
                vendor = "Google Inc. (NVIDIA)"
            elif "AMD" in renderer.upper() or "RADEON" in renderer.upper():
                vendor = "Google Inc. (AMD)"
            elif "INTEL" in renderer.upper():
                vendor = "Google Inc. (Intel)"

    # Method 2: OpenGL context query fallback
    if not renderer:
        try:
            from PyQt6.QtGui import QOpenGLContext, QSurfaceFormat, QOffscreenSurface
            from PyQt6.QtWidgets import QApplication
            import ctypes
            app = QApplication.instance()
            if app:
                ctx = QOpenGLContext()
                ctx.setFormat(QSurfaceFormat.defaultFormat())
                if ctx.create():
                    surface = QOffscreenSurface()
                    surface.create()
                    if ctx.makeCurrent(surface):
                        lib_name = "OpenGL32.dll" if system == "windows" else ("libGL.so.1" if system == "linux" else "/System/Library/Frameworks/OpenGL.framework/OpenGL")
                        libgl = ctypes.CDLL(lib_name)
                        glGetString = libgl.glGetString
                        glGetString.restype = ctypes.c_char_p
                        glGetString.argtypes = [ctypes.c_uint]
                        v = glGetString(0x1F00)
                        r = glGetString(0x1F01)
                        if v and not vendor:
                            vendor = v.decode("utf-8", "ignore").strip()
                        if r and not renderer:
                            renderer = r.decode("utf-8", "ignore").strip()
        except Exception:
            pass

    if not vendor:
        vendor = "Google Inc. (NVIDIA)" if system == "windows" else ("Mesa/X.org" if system == "linux" else "Apple Inc.")
    if not renderer:
        renderer = "NVIDIA GeForce RTX 3060 Direct3D11" if system == "windows" else ("Mesa Intel(R) UHD Graphics" if system == "linux" else "Apple M1")

    _CACHED_NATIVE_WEBGL = {
        "vendor": vendor,
        "renderer": renderer,
        "is_native": True
    }
    return _CACHED_NATIVE_WEBGL

# Flat list of all presets for backward compatibility
WEBGL_PRESETS = (
    WEBGL_PRESETS_BY_OS["windows"] +
    WEBGL_PRESETS_BY_OS["linux"] +
    WEBGL_PRESETS_BY_OS["mac"] +
    WEBGL_PRESETS_BY_OS["android"] +
    WEBGL_PRESETS_BY_OS["ios"]
)

# Popular Screen Resolutions
SCREEN_RESOLUTIONS = [
    "1920x1080",
    "2560x1440",
    "1366x768",
    "1536x864",
    "1440x900",
    "1280x720",
    "3840x2160",
    "412x915",   # Pixel 8
    "393x852"    # iPhone 15 Pro
]

# Sandbox & MicroVM Configurations
SANDBOX_MODES = ["container", "microvm", "off"]
# NOTE: The duplicate SANDBOX_CONTAINER_IMAGE below (line ~114) is the real value.

GPU_HARDWARE_PRESETS = [
    {
        "id": "auto_profile",
        "name": "★ Auto-Match Profile Settings (Dynamic GPU, OS & Screen Res)",
        "gallium_driver": "auto",
        "gl_vendor": "Dynamic Auto",
        "gl_renderer": "Dynamic Auto",
        "env": {}
    },
    {
        "id": "nvidia_rtx3060",
        "name": "NVIDIA GeForce RTX 3060 (Mesa VirGL / LLVMpipe)",
        "gallium_driver": "llvmpipe",
        "gl_vendor": "NVIDIA Corporation",
        "gl_renderer": "GeForce RTX 3060/PCIe/SSE2",
        "env": {"LIBGL_ALWAYS_SOFTWARE": "1", "GALLIUM_DRIVER": "llvmpipe", "MESA_GL_VERSION_OVERRIDE": "4.6"}
    },
    {
        "id": "amd_radeon6700",
        "name": "AMD Radeon RX 6700 XT (Mesa VirGL)",
        "gallium_driver": "virgl",
        "gl_vendor": "AMD",
        "gl_renderer": "AMD Radeon RX 6700 XT (RADV NAVI22)",
        "env": {"GALLIUM_DRIVER": "virgl", "MESA_GL_VERSION_OVERRIDE": "4.6"}
    },
    {
        "id": "intel_iris",
        "name": "Intel Iris Xe Graphics (Mesa ANGLE / Iris)",
        "gallium_driver": "iris",
        "gl_vendor": "Intel",
        "gl_renderer": "Mesa Intel(R) Iris(R) Xe Graphics (TGL GT2)",
        "env": {"MESA_LOADER_DRIVER_OVERRIDE": "iris", "MESA_GL_VERSION_OVERRIDE": "4.6"}
    },
    {
        "id": "native_passthrough",
        "name": "Native Host GPU Pass-through (/dev/dri)",
        "gallium_driver": "auto",
        "gl_vendor": "Host Native",
        "gl_renderer": "Host Hardware Passthrough",
        "env": {}
    }
]

SANDBOX_CONTAINER_IMAGE = "soxbot-browser-sandbox:latest"

# AI Model & Provider Settings
DEFAULT_AI_MODEL: str = "swarm_auto_full"
# NOTE: GEMINI_API_KEY is populated from encrypted vault at startup via load_app_config().
# Never hardcode or commit API keys. Use Settings UI or GEMINI_API_KEY env var.
GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "")
GEMINI_DEFAULT_MODEL: str = "gemini-flash-lite-latest"
AI_PROVIDER_STRATEGY: str = "hybrid_fallback"  # 'local_only', 'gemini_only', 'hybrid_fallback', 'hybrid_gemini_vision'

AI_MODEL_OPTIONS = [
    ("swarm_auto_full", "⫸ Auto-Full-Modus (7+1 KI-Team Swarm: ONNX + Whisper + Qwen + DeepSeek + Moondream + QwenVL + LLaVA + Gemini) [Maximum]"),
    ("hybrid_auto", "⭍ Hybrid Auto-Ensemble (Qwen 2.5 1.5B Text + Auto-Vision) [Empfohlen]"),
    ("hybrid_deepseek_vision", "🧠 Hybrid DeepSeek R1 Reasoning + Qwen 2.5 VL Vision [Next-Gen Local]"),
    ("hybrid_coder_tactician", "💻 Hybrid Qwen 2.5 Coder DOM + Moondream Vision [DOM Specialist]"),
    ("hybrid_high_perf", "⫸ Hybrid High-Performance (Qwen 2.5 3B Text + LLaVA 7B Spatial Vision)"),
    ("hybrid_eco", "☘ Hybrid Eco-Fast (Qwen 2.5 0.5B Text + SmolVLM Vision)"),
    ("hybrid_gemini_vision", "★ Hybrid Local Text (Qwen) + Gemini Vision Cloud (Ultra-Fast Captchas)"),
    ("hybrid_50_50_gemini", "⚡ 50/50 Hybrid Co-Pilot (50% Gemini Cloud + 50% Local VLM) [Dual-Engine Split]"),
    ("gemini-flash-lite-latest", "★ Google Gemini Flash Lite (Ultra-Fast Cloud Multimodal API) [Empfohlen]"),
    ("gemini-3.8-flash", "★ Google Gemini 3.8 Flash (High-Capacity Multimodal API)"),
    ("gemini-3.7-flash", "⭍ Google Gemini 3.7 Flash (Cloud Multimodal API)"),
    ("gemini-3.6-flash", "⭍ Google Gemini 3.6 Flash (Legacy Flash Endpoint)"),
    ("gemini-1.5-flash", "⭍ Google Gemini 1.5 Flash (Lightweight Multimodal Cloud API)"),
    ("gemini-1.5-pro", "⎔ Google Gemini 1.5 Pro (Deep Multimodal & Reasoning Cloud API)"),
    ("deepseek-r1:1.5b", "🧠 DeepSeek R1 (1.5B) - Chain-of-Thought & Strategic Reasoning (~1.1GB)"),
    ("qwen2.5-coder:1.5b", "💻 Qwen 2.5 Coder (1.5B) - DOM Scripting & Code Injection (~986MB)"),
    ("qwen2.5vl:3b", "👁 Qwen 2.5 VL (3B) - Next-Gen Multimodal Vision & UI Grounding (~3.2GB)"),
    ("qwen2.5:7b", "⎔ Qwen 2.5 (7B) - Heavyweight Desktop Copilot & Strategy (~4.5GB)"),
    ("hermes-3:3b", "⚡ Nous Hermes 3 (3B) - Function-Calling & Agentic Tool Planner (~2.0GB)"),
    ("granite3-dense:2b", "⛯ IBM Granite 3 (2B) - High-Reliability DOM & Selector Parser (~1.5GB)"),
    ("qwen2.5:1.5b", "⭍ Qwen 2.5 (1.5B) - Recommended Fast Text & Reasoning (~980MB)"),
    ("qwen2.5:3b", "⎔ Qwen 2.5 (3B) - Deep Reasoning & Complex Intent (~1.9GB)"),
    ("qwen2.5:0.5b", "☘ Qwen 2.5 (0.5B) - Ultra Fast & Lightweight Text (~350MB)"),
    ("llava:7b", "⚆ LLaVA (7B) - High-Precision Spatial Vision & UI Grounding (~4.7GB)"),
    ("smolvlm", "▨ SmolVLM (1.1GB) - Fast Vision & UI OCR (~1.1GB)"),
    ("moondream:v2", "⚆ Moondream 2 (1.4GB) - Vision & UI Text Model (~1.4GB)"),
    ("florence-2-base", "🎯 Microsoft Florence-2 Base (0.23B) - Dense Grounding & Prompt OCR (~230MB)"),
    ("got-ocr2", "📜 StepFun GOT-OCR 2.0 (0.5B) - Ultra-Dense Visual OCR & Document Parsing (~1.4GB)"),
    ("sensevoice-small", "🎙 FunAudioLLM SenseVoice Small - Multi-Lingual Audio STT (~200MB)"),
    ("faster-whisper", "🎙 Faster-Whisper Base - Local CTranslate2 Audio STT Engine (~145MB)"),
    ("mouse-trajectory-onnx", "🖱 Biomechanical Mouse Trajectory CNN (ONNX) - Micro-Tremor & Jerk (~21MB)"),
    ("onnx-anomaly", "🛡 ONNX Stealth Sentinel - Tensor Anomaly & Honeypot Detector (~751KB)")
]


def get_all_ai_model_options() -> list:
    """Returns AI_MODEL_OPTIONS merged with any custom user-created AI Hybrid Groups."""
    try:
        from engine.ai_hybrid_groups_manager import AIHybridGroupsManager
        mgr = AIHybridGroupsManager.get_instance()
        custom_groups = [g for g in mgr.get_all_groups() if not g.get("is_builtin", False)]
        if not custom_groups:
            return list(AI_MODEL_OPTIONS)
        
        custom_options = [
            (g["id"], f"{g.get('icon', '⚔')} {g.get('name', 'Custom Hybrid Group')} [Custom Hybrid]")
            for g in custom_groups
        ]
        # Insert custom groups right after the default hybrid options (index 7)
        idx = 7
        return AI_MODEL_OPTIONS[:idx] + custom_options + AI_MODEL_OPTIONS[idx:]
    except Exception:
        return list(AI_MODEL_OPTIONS)



AI_CONSENT_STRATEGY: str = "strict_reject"
AI_TEMPERATURE: float = 0.1
AI_SHADOW_DOM_DEPTH: int = 5
AI_CUSTOM_EXCLUSIONS: list = ["/do\\s*not/i", "/reject/i", "/ablehnen/i", "/opt-out/i", "/manage/i"]
DEFAULT_ENABLE_HONEYPOT_SHIELD: bool = True

CONFIG_FILE = os.path.join(BASE_DIR, "app_config.json")
VAULT_FILE = os.path.join(BASE_DIR, "app_config.vault")

def load_app_config():
    """
    Loads persistent application settings from the encrypted vault (app_config.vault)
    via SecretsManager. Falls back gracefully if vault is unavailable.
    """
    global SECRET_KEY, GEMINI_API_KEY, GEMINI_DEFAULT_MODEL, AI_PROVIDER_STRATEGY, API_HOST, API_PORT, API_BEARER_TOKEN
    global AI_CONSENT_STRATEGY, AI_TEMPERATURE, AI_SHADOW_DOM_DEPTH, AI_CUSTOM_EXCLUSIONS, DEFAULT_ENABLE_HONEYPOT_SHIELD
    try:
        from storage.secrets_manager import SecretsManager
        SecretsManager.initialize()

        val = SecretsManager.get("secret_key", "")
        if val:
            SECRET_KEY = str(val).strip()

        val = SecretsManager.get("gemini_api_key", "")
        if val:
            GEMINI_API_KEY = str(val).strip()
        val = SecretsManager.get("gemini_default_model", "")
        if val:
            val_str = str(val).strip()
            if val_str in ["gemini-3.7-flash", "gemini-3.6-flash", "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]:
                GEMINI_DEFAULT_MODEL = "gemini-flash-lite-latest"
                try:
                    SecretsManager.set("gemini_default_model", "gemini-flash-lite-latest")
                    SecretsManager.save()
                except Exception:
                    pass
            else:
                GEMINI_DEFAULT_MODEL = val_str
        else:
            GEMINI_DEFAULT_MODEL = "gemini-flash-lite-latest"
        val = SecretsManager.get("ai_provider_strategy", "")
        if val:
            AI_PROVIDER_STRATEGY = str(val).strip()
        val = SecretsManager.get("api_host", "")
        if val:
            API_HOST = str(val).strip()
        val = SecretsManager.get("api_port", "")
        if val:
            try:
                API_PORT = int(val)
            except (ValueError, TypeError):
                pass
        val = SecretsManager.get("api_bearer_token", "")
        if val:
            API_BEARER_TOKEN = str(val).strip()
            
        # AI DOM Consent & Trajectory Hyperparameters
        val = SecretsManager.get("ai_consent_strategy", "")
        if val:
            AI_CONSENT_STRATEGY = str(val).strip()
        val = SecretsManager.get("ai_temperature", "")
        if val is not None and str(val).strip() != "":
            try:
                AI_TEMPERATURE = float(val)
            except (ValueError, TypeError):
                pass
        val = SecretsManager.get("ai_shadow_dom_depth", "")
        if val is not None and str(val).strip() != "":
            try:
                AI_SHADOW_DOM_DEPTH = int(val)
            except (ValueError, TypeError):
                pass
        val = SecretsManager.get("ai_custom_exclusions", "")
        if val:
            if isinstance(val, list):
                AI_CUSTOM_EXCLUSIONS = val
            elif isinstance(val, str):
                try:
                    import json
                    AI_CUSTOM_EXCLUSIONS = json.loads(val)
                except Exception:
                    AI_CUSTOM_EXCLUSIONS = [line.strip() for line in val.splitlines() if line.strip()]
        val = SecretsManager.get("enable_honeypot_shield", "")
        if val is not None and str(val).strip() != "":
            DEFAULT_ENABLE_HONEYPOT_SHIELD = str(val).lower() in ("true", "1", "yes")
    except Exception as e:
        import logging
        logging.getLogger("Config").warning(
            f"[Config] SecretsManager unavailable, using defaults: {e}"
        )


def save_app_config():
    """
    Saves application settings to the encrypted vault (app_config.vault)
    via SecretsManager. Data is never written to plaintext on disk.
    """
    try:
        from storage.secrets_manager import SecretsManager
        if not SecretsManager.is_initialized():
            SecretsManager.initialize()
        if SECRET_KEY:
            SecretsManager.set("secret_key", SECRET_KEY)
        SecretsManager.set("gemini_api_key", GEMINI_API_KEY)
        SecretsManager.set("gemini_default_model", GEMINI_DEFAULT_MODEL)
        SecretsManager.set("ai_provider_strategy", AI_PROVIDER_STRATEGY)
        SecretsManager.set("api_host", API_HOST)
        SecretsManager.set("api_port", API_PORT)
        SecretsManager.set("api_bearer_token", API_BEARER_TOKEN)
        
        # AI DOM Consent & Trajectory Hyperparameters
        SecretsManager.set("ai_consent_strategy", AI_CONSENT_STRATEGY)
        SecretsManager.set("ai_temperature", AI_TEMPERATURE)
        SecretsManager.set("ai_shadow_dom_depth", AI_SHADOW_DOM_DEPTH)
        SecretsManager.set("ai_custom_exclusions", AI_CUSTOM_EXCLUSIONS)
        SecretsManager.set("enable_honeypot_shield", DEFAULT_ENABLE_HONEYPOT_SHIELD)
        SecretsManager.save()
    except Exception as e:
        import logging
        logging.getLogger("Config").error(f"[Config] Failed to save encrypted config: {e}")
        raise

load_app_config()



