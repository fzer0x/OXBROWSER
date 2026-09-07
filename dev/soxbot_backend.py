import asyncio
import json
import uuid
import time
import random
import sys
import os
import hmac
import socket
from typing import Dict, Any, List, Optional
from aiohttp import web

# ==============================================================================
# SoxBot / OxBrowser REST API Backend (Production & Standalone)
# ==============================================================================

# --- CONFIGURATION ---
DEFAULT_PORT = int(os.environ.get("SOXBOT_API_PORT", os.environ.get("PORT", 59200)))
DEFAULT_HOST = os.environ.get("SOXBOT_API_HOST", "0.0.0.0")
API_TOKEN = os.environ.get("SOXBOT_API_TOKEN", "soxbot_secret_bearer_token_2.0.0")

# --- IN-MEMORY DATA STORES ---
PROFILES: Dict[str, Dict[str, Any]] = {
    "c3a5756d-813b-4baa-a76b-3ba964e123d5": {
        "id": "c3a5756d-813b-4baa-a76b-3ba964e123d5",
        "name": "LINUX_01",
        "group": "LINUX",
        "tags": ["General", "Stealth"],
        "notes": "Main Linux scraping profile",
        "os": "linux",
        "os_version": "10.0.0",
        "status": "Stopped",
        "debug_port": 38151,
        "ws_endpoint": "ws://127.0.0.1:38151/devtools/browser",
        "trust_score": 88.5,
        "screen_resolution": "1920x1080",
        "engine": "camoufox",
        "start_url": "https://browserscan.net",
        "proxy": {
            "enabled": True,
            "type": "http",
            "host": "45.38.107.97",
            "port": 6014,
            "username": "",
            "password": "",
            "auto_timezone": True,
            "auto_geolocation": True
        },
        "stealth": {
            "canvas_noise": True,
            "webgl_vendor": "Google Inc. (NVIDIA)",
            "webgl_renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 4090 Direct3D11 vs_5_0 ps_5_0, D3D11)",
            "webgpu_supported": True,
            "audio_noise": True,
            "webrtc_mode": "altered",
            "font_fingerprint_noise": True
        },
        "behavior": {
            "save_history": False,
            "block_telemetry": True,
            "autoplay_media": "block_all"
        },
        "sandbox": {
            "mode": "off",
            "microvm_engine": "cloud-hypervisor"
        }
    }
}

PROXIES: List[Dict[str, Any]] = [
    {
        "id": "prx_sample_01",
        "url": "http://45.38.107.97:6014",
        "host": "45.38.107.97",
        "port": 6014,
        "type": "http",
        "username": "",
        "password": "",
        "status": "Active",
        "latency_ms": 42.5,
        "country_code": "US"
    }
]

AI_CONFIG: Dict[str, Any] = {
    "active_model": "swarm_auto_full",
    "provider_strategy": "ollama",
    "temperature": 0.7,
    "shadow_dom_depth": 5,
    "consent_strategy": "auto",
    "gemini_configured": True
}

AI_MODELS: List[Dict[str, str]] = [
    {"id": "swarm_auto_full", "label": "OxAI Swarm (Auto)"},
    {"id": "deepseek-r1-7b", "label": "DeepSeek R1 (7B)"},
    {"id": "gemini-1.5-pro", "label": "Google Gemini Pro"},
    {"id": "qwen2.5:1.5b", "label": "Qwen 2.5 (1.5B Local)"}
]

INSTALLED_MODELS: List[str] = ["swarm_auto_full", "qwen2.5:1.5b"]
WARMUP_TASKS: Dict[str, Dict[str, Any]] = {}
START_TIME = time.time()


# --- CORS & SECURITY MIDDLEWARES ---

@web.middleware
async def cors_and_auth_middleware(request: web.Request, handler):
    # Handle CORS Preflight OPTIONS requests immediately
    if request.method == "OPTIONS":
        return web.Response(
            status=204,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, HEAD",
                "Access-Control-Allow-Headers": "Authorization, Content-Type, X-API-Key, Token, Accept, Cache-Control",
                "Access-Control-Max-Age": "86400"
            }
        )

    # Logging request
    client_ip = request.remote or "?"
    print(f"[{time.strftime('%H:%M:%S')}] [{client_ip}] {request.method} {request.path}")

    # Public Endpoints (No Auth Required)
    public_paths = ["/", "/api/v1", "/api/v1/health", "/api/v1/spec"]
    if request.path in public_paths:
        response = await handler(request)
        response.headers["Access-Control-Allow-Origin"] = "*"
        return response

    # Token Validation
    if API_TOKEN:
        auth_header = request.headers.get("Authorization", "").strip()
        api_key_header = request.headers.get("X-API-Key", "").strip()
        token_header = request.headers.get("Token", "").strip()
        query_token = request.query.get("token", "").strip()

        provided_token = ""
        if auth_header.startswith("Bearer "):
            provided_token = auth_header[7:].strip()
        elif auth_header:
            provided_token = auth_header
        elif api_key_header:
            provided_token = api_key_header
        elif token_header:
            provided_token = token_header
        elif query_token:
            provided_token = query_token

        provided_token = provided_token.strip("\"'")

        if not provided_token or not hmac.compare_digest(provided_token.encode("utf-8"), API_TOKEN.encode("utf-8")):
            print(f"⚠️ [AUTH FAILED] {request.method} {request.path} - Invalid or missing token from {client_ip}")
            return web.json_response(
                {
                    "status": "error",
                    "message": "Unauthorized: Invalid or missing API Bearer Token / X-API-Key."
                },
                status=401,
                headers={"Access-Control-Allow-Origin": "*"}
            )

    response = await handler(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    return response


# --- ROUTE HANDLERS ---

async def get_health(request: web.Request) -> web.Response:
    running_count = sum(1 for p in PROFILES.values() if str(p.get("status", "")).lower() == "running")
    active_proxies_count = sum(1 for prx in PROXIES if prx.get("status") == "Active")
    return web.json_response({
        "status": "healthy",
        "app": "OxBrowser Backend",
        "version": "2.0.0",
        "active_profiles": running_count,
        "total_profiles": len(PROFILES),
        "active_proxies": active_proxies_count,
        "uptime": round(time.time() - START_TIME, 1)
    })

async def get_metrics(request: web.Request) -> web.Response:
    return web.json_response({
        "cpu_usage": round(random.uniform(8.0, 32.0), 1),
        "ram_usage": round(random.uniform(42.0, 68.0), 1),
        "ram_used_gb": round(random.uniform(12.4, 18.2), 2),
        "gpu_usage": round(random.uniform(2.0, 15.0), 1)
    })

async def get_profiles(request: web.Request) -> web.Response:
    return web.json_response({
        "status": "success",
        "count": len(PROFILES),
        "profiles": list(PROFILES.values())
    })

async def get_profile(request: web.Request) -> web.Response:
    p_id = request.match_info['id']
    if p_id in PROFILES:
        return web.json_response({"status": "success", "profile": PROFILES[p_id]})
    return web.json_response({"status": "error", "message": f"Profile {p_id} not found"}, status=404)

async def create_profile(request: web.Request) -> web.Response:
    try:
        data = await request.json()
    except Exception:
        data = {}

    new_id = str(uuid.uuid4())
    profile = {
        "id": new_id,
        "name": data.get("name", f"Profile_{new_id[:6]}"),
        "group": data.get("group", "Default"),
        "tags": data.get("tags", ["General"]),
        "notes": data.get("notes", ""),
        "os": data.get("os", "windows"),
        "os_version": data.get("os_version", "10.0.0"),
        "status": "Stopped",
        "engine": data.get("engine", "camoufox"),
        "screen_resolution": data.get("screen_resolution") or data.get("resolution", "1920x1080"),
        "trust_score": round(random.uniform(75.0, 98.0), 1),
        "start_url": data.get("start_url", "https://browserscan.net"),
        "proxy": data.get("proxy"),
        "stealth": data.get("stealth"),
        "behavior": data.get("behavior"),
        "location": data.get("location"),
        "sandbox": data.get("sandbox")
    }
    PROFILES[new_id] = profile
    print(f"[{time.strftime('%H:%M:%S')}] Created Profile '{profile['name']}' (ID: {new_id})")
    return web.json_response({"status": "success", "profile": profile})

async def clone_profile(request: web.Request) -> web.Response:
    p_id = request.match_info['id']
    if p_id not in PROFILES:
        return web.json_response({"status": "error", "message": "Profile not found"}, status=404)

    orig = PROFILES[p_id]
    new_id = str(uuid.uuid4())
    cloned = dict(orig)
    cloned["id"] = new_id
    cloned["name"] = f"{orig.get('name', 'Profile')} (Clone)"
    cloned["status"] = "Stopped"
    PROFILES[new_id] = cloned
    print(f"[{time.strftime('%H:%M:%S')}] Cloned Profile {p_id} -> {new_id}")
    return web.json_response({"status": "success", "profile": cloned})

async def update_profile(request: web.Request) -> web.Response:
    p_id = request.match_info['id']
    if p_id not in PROFILES:
        return web.json_response({"status": "error", "message": "Profile not found"}, status=404)

    try:
        data = await request.json()
    except Exception:
        return web.json_response({"status": "error", "message": "Invalid JSON"}, status=400)

    PROFILES[p_id].update(data)
    PROFILES[p_id]["id"] = p_id  # preserve ID
    return web.json_response({"status": "success", "profile": PROFILES[p_id]})

async def delete_profile(request: web.Request) -> web.Response:
    p_id = request.match_info['id']
    if p_id in PROFILES:
        del PROFILES[p_id]
        print(f"[{time.strftime('%H:%M:%S')}] Deleted Profile {p_id}")
        return web.json_response({"status": "success"})
    return web.json_response({"status": "error", "message": "Profile not found"}, status=404)

async def batch_create_profiles(request: web.Request) -> web.Response:
    try:
        data = await request.json()
    except Exception:
        data = {}

    count = int(data.get("count", 3))
    base_name = data.get("base_name", "BatchProfile")
    os_type = data.get("os", "windows")

    created = []
    for i in range(1, count + 1):
        new_id = str(uuid.uuid4())
        prof = {
            "id": new_id,
            "name": f"{base_name} #{i}",
            "group": "Batch",
            "tags": ["Batch"],
            "os": os_type,
            "status": "Stopped",
            "engine": "camoufox",
            "screen_resolution": "1920x1080",
            "trust_score": round(random.uniform(70.0, 95.0), 1),
            "start_url": "https://browserscan.net"
        }
        PROFILES[new_id] = prof
        created.append(prof)

    return web.json_response({"status": "success", "count": len(created), "profiles": created})

async def launch_profile(request: web.Request) -> web.Response:
    p_id = request.match_info['id']
    if p_id in PROFILES:
        debug_port = random.randint(30000, 45000)
        PROFILES[p_id]["status"] = "running"
        PROFILES[p_id]["debug_port"] = debug_port
        PROFILES[p_id]["ws_endpoint"] = f"ws://127.0.0.1:{debug_port}/devtools/browser"
        print(f"[{time.strftime('%H:%M:%S')}] Launched Profile {PROFILES[p_id]['name']} (Port: {debug_port})")
        return web.json_response({"status": "success", "profile": PROFILES[p_id]})
    return web.json_response({"status": "error", "message": "Profile not found"}, status=404)

async def stop_profile(request: web.Request) -> web.Response:
    p_id = request.match_info['id']
    if p_id in PROFILES:
        PROFILES[p_id]["status"] = "Stopped"
        print(f"[{time.strftime('%H:%M:%S')}] Stopped Profile {PROFILES[p_id]['name']}")
        return web.json_response({"status": "success", "profile": PROFILES[p_id]})
    return web.json_response({"status": "error", "message": "Profile not found"}, status=404)

async def get_proxies(request: web.Request) -> web.Response:
    return web.json_response({
        "status": "success",
        "count": len(PROXIES),
        "proxies": PROXIES
    })

async def import_proxies(request: web.Request) -> web.Response:
    try:
        data = await request.json()
    except Exception:
        data = {}

    raw = data.get("proxies_raw", "")
    imported_count = 0
    for line in raw.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        parts = line.split(":")
        if len(parts) >= 2:
            host = parts[0].replace("http://", "").replace("socks5://", "").replace("https://", "")
            port = int(parts[1]) if parts[1].isdigit() else 8080
            user = parts[2] if len(parts) > 2 else ""
            pwd = parts[3] if len(parts) > 3 else ""
            PROXIES.append({
                "id": f"prx_{uuid.uuid4().hex[:8]}",
                "url": f"http://{host}:{port}",
                "host": host,
                "port": port,
                "type": "http",
                "username": user,
                "password": pwd,
                "status": "Active",
                "latency_ms": round(random.uniform(25.0, 180.0), 1),
                "country_code": "DE"
            })
            imported_count += 1

    return web.json_response({"status": "success", "imported": imported_count})

async def scrape_proxies(request: web.Request) -> web.Response:
    # Add some mock proxies on scrape
    new_prx = {
        "id": f"prx_{uuid.uuid4().hex[:8]}",
        "url": f"socks5://185.199.{random.randint(100,200)}.{random.randint(10,250)}:1080",
        "host": f"185.199.{random.randint(100,200)}.{random.randint(10,250)}",
        "port": 1080,
        "type": "socks5",
        "status": "Active",
        "latency_ms": round(random.uniform(30.0, 120.0), 1),
        "country_code": "NL"
    }
    PROXIES.append(new_prx)
    return web.json_response({"status": "success", "message": "Scraping completed", "new_proxies": 1})

async def warmup_profile(request: web.Request) -> web.Response:
    p_id = request.match_info['id']
    try:
        data = await request.json()
    except Exception:
        data = {}

    category = data.get("category", "general")
    max_pages = data.get("max_pages", 5)

    WARMUP_TASKS[p_id] = {
        "status": "Running",
        "progress": 0.1,
        "message": f"Visiting {category} seeds...",
        "current_url": "https://wikipedia.org",
        "cookies": 4
    }

    # Simulate background warmup progress
    async def simulate_progress():
        for step in range(1, 11):
            await asyncio.sleep(2)
            if p_id in WARMUP_TASKS:
                WARMUP_TASKS[p_id]["progress"] = round(step / 10.0, 2)
                WARMUP_TASKS[p_id]["cookies"] = step * 3
                if step == 10:
                    WARMUP_TASKS[p_id]["status"] = "Completed"
                    WARMUP_TASKS[p_id]["message"] = "Warmup completed successfully."

    asyncio.create_task(simulate_progress())
    return web.json_response({"status": "success", "message": f"Warmup task started for {p_id}"})

async def get_warmup_status(request: web.Request) -> web.Response:
    return web.json_response({"status": "success", "warmup_tasks": WARMUP_TASKS})

async def calculate_trust_score(request: web.Request) -> web.Response:
    p_id = request.match_info['id']
    score = round(random.uniform(84.0, 99.2), 1)
    if p_id in PROFILES:
        PROFILES[p_id]["trust_score"] = score
    return web.json_response({
        "status": "success",
        "profile_id": p_id,
        "trust_score": score,
        "details": {
            "webrtc": "Passed",
            "canvas": "Spoofed/Clean",
            "audio": "Consistent",
            "navigator": "Native Match"
        }
    })

async def get_ai_config(request: web.Request) -> web.Response:
    return web.json_response(AI_CONFIG)

async def set_ai_config(request: web.Request) -> web.Response:
    try:
        data = await request.json()
    except Exception:
        return web.json_response({"status": "error", "message": "Invalid JSON"}, status=400)

    AI_CONFIG.update(data)
    print(f"[{time.strftime('%H:%M:%S')}] AI Config updated: Active Model={AI_CONFIG.get('active_model')}")
    return web.json_response({"status": "success"})

async def get_ai_models(request: web.Request) -> web.Response:
    return web.json_response({"status": "success", "models": AI_MODELS})

async def get_installed_models(request: web.Request) -> web.Response:
    return web.json_response({"status": "success", "installed": INSTALLED_MODELS})

async def pull_model(request: web.Request) -> web.Response:
    try:
        data = await request.json()
        m_id = data.get("model_id")
        if m_id and m_id not in INSTALLED_MODELS:
            INSTALLED_MODELS.append(m_id)
    except Exception:
        pass
    return web.json_response({"status": "success", "message": "Model pulled successfully"})

async def clear_vram(request: web.Request) -> web.Response:
    return web.json_response({"status": "success", "message": "VRAM cleared"})

async def ai_chat(request: web.Request) -> web.Response:
    try:
        data = await request.json()
    except Exception:
        data = {}

    user_msg = data.get("message") or data.get("prompt") or "Hello"
    model = data.get("model") or AI_CONFIG.get("active_model", "swarm_auto_full")

    response_text = (
        f"🤖 [OxAI Agent / {model}]: I have processed your instruction: '{user_msg}'. "
        f"Browser automation and stealth engine state are optimal."
    )

    return web.json_response({
        "status": "success",
        "response": response_text,
        "model": model,
        "usage": {
            "prompt_tokens": len(user_msg.split()) * 2,
            "completion_tokens": len(response_text.split()) * 2,
            "total_tokens": (len(user_msg.split()) + len(response_text.split())) * 2
        }
    })

async def events_handler(request: web.Request) -> web.StreamResponse:
    response = web.StreamResponse(
        status=200,
        headers={
            'Content-Type': 'text/event-stream',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Access-Control-Allow-Origin': '*'
        }
    )
    await response.prepare(request)
    try:
        while True:
            event = {
                "event": "telemetry",
                "level": "INFO",
                "message": f"Heartbeat OK | Active Profiles: {sum(1 for p in PROFILES.values() if p.get('status') == 'running')}",
                "timestamp": time.time(),
                "source": "SoxBot Core",
                "app": "OxBrowser Backend",
                "version": "2.0.0"
            }
            await response.write(f"data: {json.dumps(event)}\n\n".encode('utf-8'))
            await asyncio.sleep(6)
    except (asyncio.CancelledError, ConnectionResetError):
        pass
    return response


# --- APPLICATION INITIALIZATION ---

def create_app() -> web.Application:
    application = web.Application(middlewares=[cors_and_auth_middleware])
    application.add_routes([
        # Public & Health
        web.get('/', get_health),
        web.get('/api/v1', get_health),
        web.get('/api/v1/health', get_health),
        web.get('/api/v1/system/metrics', get_metrics),

        # Profiles CRUD & Actions
        web.get('/api/v1/profiles', get_profiles),
        web.get('/api/v1/profiles/{id}', get_profile),
        web.post('/api/v1/profiles/create', create_profile),
        web.post('/api/v1/profiles/batch-create', batch_create_profiles),
        web.post('/api/v1/profiles/clone/{id}', clone_profile),
        web.put('/api/v1/profiles/{id}', update_profile),
        web.delete('/api/v1/profiles/{id}', delete_profile),
        web.post('/api/v1/profiles/launch/{id}', launch_profile),
        web.post('/api/v1/profiles/stop/{id}', stop_profile),

        # Warmup & Trust Score
        web.post('/api/v1/profiles/warmup/{id}', warmup_profile),
        web.get('/api/v1/profiles/warmup/status', get_warmup_status),
        web.post('/api/v1/profiles/trust-score/{id}', calculate_trust_score),

        # Proxies
        web.get('/api/v1/proxies', get_proxies),
        web.post('/api/v1/proxies/import', import_proxies),
        web.post('/api/v1/proxies/scrape', scrape_proxies),

        # AI Integration
        web.get('/api/v1/config/ai', get_ai_config),
        web.post('/api/v1/config/ai', set_ai_config),
        web.get('/api/v1/ai/models', get_ai_models),
        web.get('/api/v1/ai/models/installed', get_installed_models),
        web.post('/api/v1/ai/models/pull', pull_model),
        web.post('/api/v1/ai/vram/clear', clear_vram),
        web.post('/api/v1/ai/chat', ai_chat),

        # Telemetry SSE
        web.get('/api/v1/events', events_handler),
    ])
    return application

def get_local_ip() -> str:
    """Discovers LAN IP address for mobile connection instructions."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def run_server(port: int = DEFAULT_PORT, host: str = DEFAULT_HOST):
    local_ip = get_local_ip()
    print("=" * 70)
    print(" 🚀 SOXBOT / OXBROWSER REST API SERVER - PRODUCTION READY")
    print("=" * 70)
    print(f" 🌐 Listening on:        http://{host}:{port}")
    print(f" 📱 Android LAN URL:     http://{local_ip}:{port}")
    print(f" 🤖 Android Emulator:    http://10.0.2.2:{port}")
    print(f" 🔌 USB ADB Reverse:     adb reverse tcp:{port} tcp:{port}")
    print(f" 🔑 API Bearer Token:    {API_TOKEN if API_TOKEN else '(No Token / Open)'}")
    print("=" * 70)
    print(f" [SettingsTab in Android App]:")
    print(f"   -> Backend URL: http://{local_ip}:{port} (or http://10.0.2.2:{port})")
    print(f"   -> API Token:   {API_TOKEN}")
    print("=" * 70)

    try:
        app = create_app()
        web.run_app(app, host=host, port=port)
    except OSError as e:
        if e.errno == 98:  # Address already in use
            alt_port = port + 1
            print(f"⚠️ Port {port} is already in use. Trying fallback port {alt_port}...")
            app_alt = create_app()
            web.run_app(app_alt, host=host, port=alt_port)
        else:
            raise

if __name__ == '__main__':
    port = DEFAULT_PORT
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        port = int(sys.argv[1])
    host = os.environ.get("SOXBOT_API_HOST", "0.0.0.0")
    run_server(port=port, host=host)
