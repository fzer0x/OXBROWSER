import asyncio
import logging
import random
import hmac
import uuid
import re
import os
import json
import time
import secrets
import urllib.parse
import psutil
import subprocess
from typing import Optional, Dict, Any, List, Callable, Union
from aiohttp import web
import config
from storage.profile_manager import ProfileManager
from storage.proxy_manager import ProxyManager
from engine.browser import BrowserLauncher
from engine.cookie_warmup import CookieWarmupRobot, WarmupConfig
from engine.events import AsyncEventBus
from engine.ai_model_manager import AIModelManager
from engine.ai_gemini_client import GeminiApiClient
from engine.proxy_scraper import ProxyScraperEngine
from engine.workflow_service import WorkflowExecutionService

logger = logging.getLogger("APIServer")

# In-Memory Active Session & Token Vault (Access & Refresh Tokens)
_ACTIVE_SESSIONS: Dict[str, Dict[str, Any]] = {}
_ACTIVE_REFRESH_TOKENS: Dict[str, Dict[str, Any]] = {}

# [F-19] Rate-limiting state for login endpoint: ip -> (attempt_count, first_attempt_ts)
_LOGIN_ATTEMPTS: Dict[str, tuple] = {}
_LOGIN_MAX_ATTEMPTS = 10
_LOGIN_LOCKOUT_SECONDS = 300


async def _session_cleanup_worker() -> None:
    """[F-03] Background task: purge expired sessions and refresh tokens every 5 minutes."""
    while True:
        try:
            await asyncio.sleep(300)
            now = time.time()
            expired_sessions = [t for t, s in list(_ACTIVE_SESSIONS.items()) if s.get("expires_at", 0) < now]
            for token in expired_sessions:
                _ACTIVE_SESSIONS.pop(token, None)
            expired_refresh = [t for t, s in list(_ACTIVE_REFRESH_TOKENS.items()) if s.get("expires_at", 0) < now]
            for token in expired_refresh:
                _ACTIVE_REFRESH_TOKENS.pop(token, None)
            # Also clean up stale rate-limit entries older than lockout period
            stale_ips = [ip for ip, (cnt, ts) in list(_LOGIN_ATTEMPTS.items()) if (now - ts) > _LOGIN_LOCKOUT_SECONDS]
            for ip in stale_ips:
                _LOGIN_ATTEMPTS.pop(ip, None)
            if expired_sessions or expired_refresh:
                logger.debug(f"[APIServer] Session cleanup: removed {len(expired_sessions)} sessions, {len(expired_refresh)} refresh tokens")
        except Exception as e:
            logger.debug(f"[APIServer] Session cleanup worker error: {e}")

# Allowed Origins & Hosts for WebSocket CSWSH Mitigation
ALLOWED_WS_HOSTS = {"127.0.0.1", "localhost"}
ALLOWED_WS_ORIGINS = {
    "http://127.0.0.1", "http://localhost",
    "https://127.0.0.1", "https://localhost",
    "null", "app://soxbot", "app://oxbrowser", "file://"
}

# Valid UUID4 pattern for profile ID validation
_VALID_UUID_RE = re.compile(
    r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$',
    re.IGNORECASE
)

CSP_NONCE_KEY = web.RequestKey("csp_nonce", str)
REQUEST_ID_KEY = web.RequestKey("request_id", str)

def _is_valid_profile_id(profile_id: str) -> bool:
    """Validates that profile_id is a proper UUID4 string (prevents path traversal)."""
    return bool(profile_id and _VALID_UUID_RE.match(profile_id))

@web.middleware
async def security_headers_middleware(request: web.Request, handler):
    """
    OWASP Hardened Security Headers Middleware with CORS Preflight:
    - Handles OPTIONS preflight requests for Android / Mobile / Web clients.
    - Generates per-request cryptographic nonce for CSP.
    - Injects Strict-Transport-Security, X-Content-Type-Options, X-Frame-Options, and Permissions-Policy.
    """
    origin = request.headers.get("Origin", "")
    is_allowed_origin = False
    if origin:
        try:
            parsed = urllib.parse.urlparse(origin)
            if origin in ALLOWED_WS_ORIGINS or (parsed.hostname and parsed.hostname in ALLOWED_WS_HOSTS) or parsed.scheme in ["app", "file"]:
                is_allowed_origin = True
        except Exception:
            is_allowed_origin = False

    if request.method == "OPTIONS":
        allow_origin = origin if is_allowed_origin else "http://127.0.0.1:59200"
        return web.Response(
            status=204,
            headers={
                "Access-Control-Allow-Origin": allow_origin,
                "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, HEAD",
                "Access-Control-Allow-Headers": "Authorization, Content-Type, X-API-Key, Token, Accept, Cache-Control",
                "Access-Control-Allow-Credentials": "true",
                "Access-Control-Max-Age": "86400"
            }
        )

    nonce = secrets.token_hex(16)
    request[CSP_NONCE_KEY] = nonce

    response = await handler(request)

    if is_allowed_origin:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
    elif origin:
        response.headers["Access-Control-Allow-Origin"] = "http://127.0.0.1:59200"
    # 1. Nonce-based Content Security Policy (No unsafe-inline, No unsafe-eval)
    csp_policy = (
        f"default-src 'self'; "
        f"script-src 'self' 'nonce-{nonce}'; "
        f"style-src 'self' 'nonce-{nonce}'; "
        f"img-src 'self' data: blob:; "
        f"font-src 'self' data:; "
        f"connect-src 'self' ws: wss:; "
        f"frame-ancestors 'none'; "
        f"base-uri 'self'; "
        f"form-action 'self'; "
        f"object-src 'none';"
    )
    response.headers["Content-Security-Policy"] = csp_policy
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=(), payment=(), usb=()"
    response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"

    return response

@web.middleware
async def auth_middleware(request: web.Request, handler):
    # Attach a short request ID for tracing errors across log lines
    request[REQUEST_ID_KEY] = uuid.uuid4().hex[:8]

    # Allow root index, spec, health endpoints, and auth routes without pre-auth
    public_paths = [
        "/", "/api/v1", "/api/v1/health", "/api/v1/spec",
        "/api/v1/auth/login", "/api/v1/auth/refresh"
    ]
    if request.path in public_paths:
        return await handler(request)

    if getattr(config, "API_AUTH_ENABLED", True):
        expected_token = getattr(config, "API_BEARER_TOKEN", "").strip()
        auth_header = request.headers.get("Authorization", "")
        api_key_header = request.headers.get("X-API-Key", "")
        token_header = request.headers.get("Token", "")
        cookie_token = request.cookies.get("auth_token", "")

        provided_token = ""
        if auth_header.startswith("Bearer "):
            provided_token = auth_header[7:].strip()
        elif api_key_header:
            provided_token = api_key_header.strip()
        elif token_header:
            provided_token = token_header.strip()
        elif cookie_token:
            provided_token = cookie_token.strip()

        provided_token = provided_token.strip("\"'")

        # 1. Check against master API_BEARER_TOKEN (Timing-safe comparison)
        token_valid = False
        if expected_token and provided_token:
            token_valid = hmac.compare_digest(
                provided_token.encode("utf-8"),
                expected_token.encode("utf-8")
            )

        # 2. Check against active session vault (HttpOnly token session)
        if not token_valid and provided_token in _ACTIVE_SESSIONS:
            sess = _ACTIVE_SESSIONS[provided_token]
            if sess.get("expires_at", 0) > time.time():
                token_valid = True
            else:
                _ACTIVE_SESSIONS.pop(provided_token, None)

        # [F-04] Always require authentication when API_AUTH_ENABLED is True.
        # If no token is configured at server start, one is auto-generated (see RestApiServer.start()).
        if not token_valid:
            req_id = request.get(REQUEST_ID_KEY, "?")
            logger.warning(
                f"[APIServer] Unauthorized request [{req_id}] to {request.path}."
            )
            return web.json_response({
                "status": "error",
                "message": "Unauthorized: Invalid, expired, or missing Bearer token / HttpOnly auth cookie.",
                "request_id": req_id
            }, status=401)

    return await handler(request)

class RestApiServer:
    """Embedded REST API server for external script automation of profiles with Bearer & HttpOnly Cookie authentication, Nonce CSP, and secure WebSocket streaming."""

    _instance: Optional['RestApiServer'] = None

    def __init__(self, profile_manager: ProfileManager, launcher: BrowserLauncher, proxy_manager: ProxyManager | None = None, host: str = config.API_HOST, port: int = config.API_PORT):
        RestApiServer._instance = self
        self.profile_manager = profile_manager
        self.launcher = launcher
        self.proxy_manager = proxy_manager or ProxyManager()
        self.ai_mgr = AIModelManager.get_instance()
        self.scraper = ProxyScraperEngine()
        self.warmup_robot = CookieWarmupRobot(launcher)
        self.warmup_statuses: dict = {}
        self.host = host
        self.port = port

        # Ensure a cryptographically secure token is present from initialization
        expected_token = getattr(config, "API_BEARER_TOKEN", "").strip()
        if not expected_token and getattr(config, "API_AUTH_ENABLED", True):
            generated_token = secrets.token_urlsafe(32)
            config.API_BEARER_TOKEN = generated_token
            try:
                from storage.secrets_manager import SecretsManager
                if SecretsManager.is_initialized():
                    SecretsManager.set("api_bearer_token", generated_token)
                    SecretsManager.save()
            except Exception:
                pass
        self.app = web.Application(
            middlewares=[security_headers_middleware, auth_middleware],
            client_max_size=10 * 1024 * 1024  # [F-06] 10 MB max payload size
        )
        self.runner: Optional[web.AppRunner] = None
        self._site: Optional[web.TCPSite] = None
        self._setup_routes()

    @classmethod
    def get_instance(cls) -> Optional['RestApiServer']:
        return cls._instance

    def is_running(self) -> bool:
        return self._site is not None and self.runner is not None

    def _setup_routes(self):
        self.app.router.add_get('/', self.handle_index)
        self.app.router.add_get('/api/v1', self.handle_index)
        self.app.router.add_get('/api/v1/health', self.handle_health)
        self.app.router.add_get('/api/v1/spec', self.handle_spec)
        self.app.router.add_get('/api/v1/events', self.handle_events_stream)
        
        # Secure WebSocket real-time stream (with Host & Origin CSWSH protection)
        self.app.router.add_get('/api/v1/ws', self.handle_websocket_stream)
        self.app.router.add_get('/api/v1/events/ws', self.handle_websocket_stream)

        # Hardened Authentication & HttpOnly Cookie Endpoints
        self.app.router.add_post('/api/v1/auth/login', self.handle_auth_login)
        self.app.router.add_post('/api/v1/auth/token', self.handle_auth_login)
        self.app.router.add_post('/api/v1/auth/refresh', self.handle_auth_refresh)
        self.app.router.add_post('/api/v1/auth/logout', self.handle_auth_logout)

        # Profile routes
        self.app.router.add_get('/api/v1/profiles', self.handle_list_profiles)
        self.app.router.add_get('/api/v1/profiles/active', self.handle_active_profiles)
        self.app.router.add_post('/api/v1/profiles/create', self.handle_create_profile)
        self.app.router.add_post('/api/v1/profiles/batch-create', self.handle_batch_create)
        self.app.router.add_get('/api/v1/profiles/{id}', self.handle_get_profile)
        self.app.router.add_put('/api/v1/profiles/{id}', self.handle_update_profile)
        self.app.router.add_delete('/api/v1/profiles/{id}', self.handle_delete_profile)
        self.app.router.add_post('/api/v1/profiles/launch/{id}', self.handle_launch_profile)
        self.app.router.add_post('/api/v1/profiles/stop/{id}', self.handle_stop_profile)
        self.app.router.add_post('/api/v1/profiles/clone/{id}', self.handle_clone_profile)
        self.app.router.add_post('/api/v1/profiles/warmup/{id}', self.handle_warmup_profile)
        self.app.router.add_get('/api/v1/profiles/warmup/status', self.handle_warmup_status)
        self.app.router.add_post('/api/v1/profiles/trust-score/{id}', self.handle_trust_score)
        
        # Proxy routes
        self.app.router.add_get('/api/v1/proxies', self.handle_list_proxies)
        self.app.router.add_post('/api/v1/proxies/import', self.handle_import_proxies)
        self.app.router.add_post('/api/v1/proxies/scrape', self.handle_scrape_proxies)
        
        # AI & Config routes
        self.app.router.add_get('/api/v1/config/ai', self.handle_get_ai_config)
        self.app.router.add_post('/api/v1/config/ai', self.handle_set_ai_config)
        self.app.router.add_get('/api/v1/ai/models', self.handle_list_ai_models)
        self.app.router.add_get('/api/v1/ai/models/installed', self.handle_list_installed_models)
        self.app.router.add_post('/api/v1/ai/models/pull', self.handle_pull_model)
        self.app.router.add_post('/api/v1/ai/vram/clear', self.handle_clear_vram)
        self.app.router.add_post('/api/v1/ai/chat', self.handle_ai_chat)
        
        # Workflow routes (Headless Execution & Orchestration)
        self.app.router.add_get('/api/v1/workflows', self.handle_list_workflows)
        self.app.router.add_get('/api/v1/workflows/{id}', self.handle_get_workflow)
        self.app.router.add_post('/api/v1/workflows/run', self.handle_run_workflow)
        self.app.router.add_get('/api/v1/workflows/status/{execution_id}', self.handle_workflow_status)
        self.app.router.add_post('/api/v1/workflows/stop/{execution_id}', self.handle_stop_workflow)

        # System routes
        self.app.router.add_get('/api/v1/system/metrics', self.handle_system_metrics)

    async def handle_health(self, request: web.Request) -> web.Response:
        active_count = len(self.launcher.active_drivers)
        total_profiles = len(self.profile_manager.list_profiles())
        return web.json_response({
            "status": "healthy",
            "app": config.APP_NAME,
            "version": config.APP_VERSION,
            "active_profiles": active_count,
            "total_profiles": total_profiles,
            "timestamp": time.time(),
            "ai_ready": await self.ai_mgr.is_engine_ready()
        })

    async def handle_spec(self, request: web.Request) -> web.Response:
        """Returns OpenAPI/Swagger spec dictionary for the REST API."""
        return web.json_response({
            "openapi": "3.0.0",
            "info": {
                "title": f"{config.APP_NAME} REST API",
                "version": config.APP_VERSION,
                "description": "AntiDetect Browser Management, AI Swarm Operations & Automation API"
            },
            "paths": {
                "/api/v1/health": {"get": {"summary": "Health check & engine status"}},
                "/api/v1/spec": {"get": {"summary": "OpenAPI API Specification"}},
                "/api/v1/events": {"get": {"summary": "Real-time Server-Sent Events (SSE) stream"}},
                "/api/v1/system/metrics": {"get": {"summary": "Live CPU, RAM, GPU telemetry"}},
                "/api/v1/profiles": {"get": {"summary": "List all browser profiles"}},
                "/api/v1/profiles/active": {"get": {"summary": "List currently active browser instances"}},
                "/api/v1/profiles/create": {"post": {"summary": "Create a new fingerprint profile"}},
                "/api/v1/profiles/launch/{id}": {"post": {"summary": "Launch browser profile"}},
                "/api/v1/profiles/stop/{id}": {"post": {"summary": "Stop active browser profile"}},
                "/api/v1/ai/models": {"get": {"summary": "List available AI models"}},
                "/api/v1/ai/models/installed": {"get": {"summary": "List installed AI models"}},
            }
        })

    async def handle_system_metrics(self, request: web.Request) -> web.Response:
        cpu = psutil.cpu_percent()
        mem = psutil.virtual_memory()
        
        gpu_pct = 0.0
        try:
            res = subprocess.run(
                ['nvidia-smi', '--query-gpu=utilization.gpu', '--format=csv,noheader,nounits'],
                capture_output=True, text=True, timeout=0.5
            )
            if res.returncode == 0:
                gpu_pct = float(res.stdout.strip())
        except Exception:
            pass

        return web.json_response({
            "cpu_usage": cpu,
            "ram_usage": mem.percent,
            "ram_used_gb": mem.used / (1024**3),
            "gpu_usage": gpu_pct
        })

    async def handle_events_stream(self, request: web.Request) -> web.StreamResponse:
        """Streams real-time engine telemetry, profile state changes, and AI operations via Server-Sent Events."""
        response = web.StreamResponse(
            status=200,
            reason='OK',
            headers={
                'Content-Type': 'text/event-stream',
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'Access-Control-Allow-Origin': 'http://127.0.0.1:59200',  # [F-17] Restrict CORS
            }
        )
        await response.prepare(request)

        # Initial handshake
        handshake = {
            "event": "connected",
            "app": config.APP_NAME,
            "version": config.APP_VERSION,
            "timestamp": time.time()
        }
        await response.write(f"data: {json.dumps(handshake)}\n\n".encode('utf-8'))

        queue: asyncio.Queue = asyncio.Queue(maxsize=150)

        def on_event(**kwargs):
            try:
                queue.put_nowait(kwargs)
            except Exception:
                pass

        event_bus = AsyncEventBus.get_instance()
        event_bus.subscribe("telemetry_event", on_event)
        event_bus.subscribe("profile_event", on_event)
        event_bus.subscribe("warmup_event", on_event)

        try:
            while True:
                try:
                    evt = await asyncio.wait_for(queue.get(), timeout=15.0)
                    line = f"data: {json.dumps(evt)}\n\n"
                    await response.write(line.encode('utf-8'))
                except asyncio.TimeoutError:
                    await response.write(b": heartbeat\n\n")
        except (asyncio.CancelledError, ConnectionResetError):
            pass
        finally:
            event_bus.unsubscribe("telemetry_event", on_event)
            event_bus.unsubscribe("profile_event", on_event)
            event_bus.unsubscribe("warmup_event", on_event)

        return response

    async def handle_websocket_stream(self, request: web.Request) -> web.StreamResponse:
        """
        Hardened WebSocket Endpunkt mit strikter Host- und Origin-Prüfung (CSWSH-Schutz)
        und Pre-Upgrade Token-Authentifizierung.
        """
        # 1. Strikte Host-Header-Validierung
        host_header = request.headers.get("Host", "").split(":")[0].strip().lower()
        allowed_hosts = ALLOWED_WS_HOSTS | {self.host.lower(), "0.0.0.0"}
        if host_header and host_header not in allowed_hosts:
            logger.warning(f"[WebSocket] Rejected invalid Host header: '{host_header}'")
            return web.Response(text="Forbidden: Host header not permitted", status=403)

        # 2. Strikte Origin-Validierung (Cross-Site WebSocket Hijacking / CSWSH Schutz)
        origin_header = request.headers.get("Origin", "").strip().lower()
        if origin_header:
            parsed_origin = urllib.parse.urlparse(origin_header)
            origin_host = parsed_origin.hostname or ""
            if origin_host not in allowed_hosts and origin_header not in ALLOWED_WS_ORIGINS:
                logger.warning(f"[WebSocket] CSWSH attempt blocked from untrusted Origin: '{origin_header}'")
                return web.Response(text="Forbidden: Cross-Site WebSocket Hijacking (CSWSH) rejected", status=403)

        # 3. Pre-Upgrade Authentifizierung (Bearer Token, Query-Token oder HttpOnly-Cookie)
        if getattr(config, "API_AUTH_ENABLED", True):
            expected_token = getattr(config, "API_BEARER_TOKEN", "").strip()
            auth_header = request.headers.get("Authorization", "")
            cookie_token = request.cookies.get("auth_token", "")
            query_token = request.query.get("token", "")

            provided_token = ""
            if auth_header.startswith("Bearer "):
                provided_token = auth_header[7:].strip()
            elif cookie_token:
                provided_token = cookie_token.strip()
            elif query_token:
                provided_token = query_token.strip()

            token_valid = False
            if expected_token and provided_token:
                token_valid = hmac.compare_digest(
                    provided_token.encode("utf-8"),
                    expected_token.encode("utf-8")
                )

            if not token_valid and provided_token in _ACTIVE_SESSIONS:
                sess = _ACTIVE_SESSIONS[provided_token]
                if sess.get("expires_at", 0) > time.time():
                    token_valid = True

            if not token_valid and (expected_token or _ACTIVE_SESSIONS):
                logger.warning(f"[WebSocket] Unauthorized WebSocket handshake attempt from {request.remote}")
                return web.Response(text="Unauthorized: Invalid or missing token", status=401)

        # 4. WebSocket Upgrade mit Heartbeat & Max-Payload Härtung
        ws = web.WebSocketResponse(heartbeat=15.0, max_msg_size=1024 * 1024)
        await ws.prepare(request)
        logger.info(f"[WebSocket] Client connected: {request.remote} (CSWSH & Host Validated)")

        # Initial Welcome Message
        await ws.send_json({
            "event": "connected",
            "app": config.APP_NAME,
            "version": config.APP_VERSION,
            "transport": "websocket_hardened",
            "timestamp": time.time()
        })

        queue: asyncio.Queue = asyncio.Queue(maxsize=200)

        def on_event(**kwargs):
            try:
                queue.put_nowait(kwargs)
            except Exception:
                pass

        event_bus = AsyncEventBus.get_instance()
        event_bus.subscribe("telemetry_event", on_event)
        event_bus.subscribe("profile_event", on_event)
        event_bus.subscribe("warmup_event", on_event)

        async def send_events():
            try:
                while not ws.closed:
                    evt = await queue.get()
                    await ws.send_json(evt)
            except (asyncio.CancelledError, ConnectionResetError):
                pass

        sender_task = asyncio.create_task(send_events())

        try:
            async for msg in ws:
                if msg.type == web.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        cmd = data.get("action") or data.get("cmd")
                        if cmd == "ping":
                            await ws.send_json({"event": "pong", "timestamp": time.time()})
                        elif cmd == "health":
                            await ws.send_json({
                                "event": "health",
                                "active_profiles": len(self.launcher.active_drivers),
                                "total_profiles": len(self.profile_manager.list_profiles()),
                                "timestamp": time.time()
                            })
                    except Exception:
                        pass
                elif msg.type == web.WSMsgType.ERROR:
                    logger.debug(f"[WebSocket] Connection closed with error: {ws.exception()}")
        finally:
            sender_task.cancel()
            event_bus.unsubscribe("telemetry_event", on_event)
            event_bus.unsubscribe("profile_event", on_event)
            event_bus.unsubscribe("warmup_event", on_event)
            logger.info(f"[WebSocket] Client disconnected: {request.remote}")

        return ws

    # -------------------------------------------------------------------------
    # Hardened Token-Architektur & HttpOnly Cookie Endpunkte
    # -------------------------------------------------------------------------
    async def handle_auth_login(self, request: web.Request) -> web.Response:
        """
        Hardened Token Login:
        - Erzeugt sichere Access- und Refresh-Tokens (secrets.token_urlsafe).
        - Setzt Tokens ausschließlich in 'HttpOnly', 'Secure', 'SameSite=Strict' Cookies.
        - Verhindert jegliche Ablage in unsicherem localStorage!
        """
        try:
            data = await request.json()
        except Exception:
            data = {}

        expected_token = getattr(config, "API_BEARER_TOKEN", "").strip()
        provided_key = str(data.get("api_key") or data.get("password") or data.get("token") or "").strip()

        # [F-19] Rate limiting: block IPs after too many failed attempts
        client_ip = request.remote or "unknown"
        now_ts = time.time()
        if client_ip in _LOGIN_ATTEMPTS:
            attempt_count, first_ts = _LOGIN_ATTEMPTS[client_ip]
            if (now_ts - first_ts) > _LOGIN_LOCKOUT_SECONDS:
                _LOGIN_ATTEMPTS.pop(client_ip, None)  # Reset after lockout period
            elif attempt_count >= _LOGIN_MAX_ATTEMPTS:
                return web.json_response({
                    "status": "error",
                    "message": f"Too many failed login attempts. Try again in {_LOGIN_LOCKOUT_SECONDS // 60} minutes."
                }, status=429)

        authenticated = False
        if not expected_token:
            authenticated = True
        elif provided_key and hmac.compare_digest(provided_key.encode("utf-8"), expected_token.encode("utf-8")):
            authenticated = True

        if not authenticated:
            # [F-19] Increment failed login attempt counter
            if client_ip in _LOGIN_ATTEMPTS:
                cnt, first_ts = _LOGIN_ATTEMPTS[client_ip]
                _LOGIN_ATTEMPTS[client_ip] = (cnt + 1, first_ts)
            else:
                _LOGIN_ATTEMPTS[client_ip] = (1, now_ts)
            return web.json_response({
                "status": "error",
                "message": "Invalid API credentials."
            }, status=401)

        # Successful login: reset rate limit counter
        _LOGIN_ATTEMPTS.pop(client_ip, None)
        # Generate cryptographically secure tokens
        access_token = secrets.token_urlsafe(32)
        refresh_token = secrets.token_urlsafe(48)
        now = time.time()

        _ACTIVE_SESSIONS[access_token] = {
            "created_at": now,
            "expires_at": now + 3600,  # 1 Hour
            "user": "authenticated_admin"
        }
        _ACTIVE_REFRESH_TOKENS[refresh_token] = {
            "created_at": now,
            "expires_at": now + (30 * 86400),  # 30 Days
            "access_token": access_token
        }

        response = web.json_response({
            "status": "success",
            "message": "Authenticated successfully. Tokens issued via HttpOnly, Secure, SameSite=Strict cookies (Zero-localStorage policy).",
            "token_type": "Bearer",
            "expires_in": 3600
        })

        # Set HttpOnly, Secure, SameSite=Strict Cookie for Access Token (Path=/api/v1)
        response.set_cookie(
            name="auth_token",
            value=access_token,
            max_age=3600,
            path="/api/v1",
            httponly=True,
            secure=True,
            samesite="Strict"
        )

        # Set HttpOnly, Secure, SameSite=Strict Cookie for Refresh Token (Path=/api/v1/auth)
        response.set_cookie(
            name="refresh_token",
            value=refresh_token,
            max_age=30 * 86400,
            path="/api/v1/auth",
            httponly=True,
            secure=True,
            samesite="Strict"
        )

        return response

    async def handle_auth_refresh(self, request: web.Request) -> web.Response:
        """
        Token-Rotation & Refresh:
        Liest den Refresh-Token aus dem HttpOnly-Cookie, rolliert den Token und setzt neue Cookies.
        """
        refresh_token = request.cookies.get("refresh_token", "").strip()
        if not refresh_token or refresh_token not in _ACTIVE_REFRESH_TOKENS:
            return web.json_response({
                "status": "error",
                "message": "Invalid or expired refresh token cookie."
            }, status=401)

        r_info = _ACTIVE_REFRESH_TOKENS.pop(refresh_token)
        if r_info.get("expires_at", 0) < time.time():
            return web.json_response({
                "status": "error",
                "message": "Refresh token expired. Please login again."
            }, status=401)

        # Invalidate old access token
        old_access = r_info.get("access_token")
        if old_access:
            _ACTIVE_SESSIONS.pop(old_access, None)

        # Issue new token pair (Token Rotation against replay attacks)
        new_access = secrets.token_urlsafe(32)
        new_refresh = secrets.token_urlsafe(48)
        now = time.time()

        _ACTIVE_SESSIONS[new_access] = {
            "created_at": now,
            "expires_at": now + 3600,
            "user": "authenticated_admin"
        }
        _ACTIVE_REFRESH_TOKENS[new_refresh] = {
            "created_at": now,
            "expires_at": now + (30 * 86400),
            "access_token": new_access
        }

        response = web.json_response({
            "status": "success",
            "message": "Token refreshed and rotated successfully.",
            "expires_in": 3600
        })

        response.set_cookie(
            name="auth_token",
            value=new_access,
            max_age=3600,
            path="/api/v1",
            httponly=True,
            secure=True,
            samesite="Strict"
        )
        response.set_cookie(
            name="refresh_token",
            value=new_refresh,
            max_age=30 * 86400,
            path="/api/v1/auth",
            httponly=True,
            secure=True,
            samesite="Strict"
        )
        return response

    async def handle_auth_logout(self, request: web.Request) -> web.Response:
        """Löscht alle aktiven Tokens und invalidiert die Cookies."""
        auth_tok = request.cookies.get("auth_token")
        ref_tok = request.cookies.get("refresh_token")
        if auth_tok:
            _ACTIVE_SESSIONS.pop(auth_tok, None)
        if ref_tok:
            _ACTIVE_REFRESH_TOKENS.pop(ref_tok, None)

        response = web.json_response({
            "status": "success",
            "message": "Logged out successfully. All authentication cookies cleared."
        })
        response.set_cookie("auth_token", "", max_age=0, path="/api/v1", httponly=True, secure=True, samesite="Strict")
        response.set_cookie("refresh_token", "", max_age=0, path="/api/v1/auth", httponly=True, secure=True, samesite="Strict")
        return response


    async def handle_index(self, request: web.Request) -> web.Response:
        return web.json_response({
            "app": config.APP_NAME,
            "version": config.APP_VERSION,
            "status": "running",
            "auth_required": getattr(config, "API_AUTH_ENABLED", True)
        })

    async def handle_list_profiles(self, request: web.Request) -> web.Response:
        profiles = self.profile_manager.list_profiles()
        return web.json_response({"status": "success", "count": len(profiles), "profiles": profiles})

    async def handle_get_profile(self, request: web.Request) -> web.Response:
        profile_id = request.match_info.get('id', '')
        profile = self.profile_manager.load_profile(profile_id)
        if not profile:
            return web.json_response({"status": "error", "message": "Profile not found"}, status=404)
        return web.json_response({"status": "success", "profile": profile})

    async def handle_update_profile(self, request: web.Request) -> web.Response:
        profile_id = request.match_info.get('id', '')
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"status": "error", "message": "Invalid JSON"}, status=400)
        
        profile = self.profile_manager.load_profile(profile_id)
        if not profile:
            return web.json_response({"status": "error", "message": "Profile not found"}, status=404)
        
        profile.update(data)
        profile["id"] = profile_id
        self.profile_manager.save_profile(profile)
        return web.json_response({"status": "success", "profile": profile})

    async def handle_delete_profile(self, request: web.Request) -> web.Response:
        profile_id = request.match_info.get('id', '')
        if self.profile_manager.delete_profile(profile_id):
            return web.json_response({"status": "success", "message": "Profile deleted"})
        return web.json_response({"status": "error", "message": "Failed to delete profile"}, status=400)

    async def handle_active_profiles(self, request: web.Request) -> web.Response:
        active_list = []
        for pid, driver in self.launcher.active_drivers.items():
            pdata = self.profile_manager.load_profile(pid) or {}
            dport = pdata.get("debug_port", 0)
            active_list.append({
                "profile_id": pid,
                "name": pdata.get("name"),
                "debug_port": dport,
                "ws_endpoint": f"ws://127.0.0.1:{dport}/devtools/browser" if dport else None
            })
        return web.json_response({"status": "success", "count": len(active_list), "active": active_list})

    async def handle_create_profile(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
        except Exception:
            data = {}

        name = data.get("name", "API Profile")
        os_type = data.get("os", "windows")
        default_data = self.profile_manager.create_default_profile_data(name=name, os_type=os_type)
        default_data.update({k: v for k, v in data.items() if k != "id"})
        created = self.profile_manager.create_profile(default_data)

        return web.json_response({"status": "success", "profile": created}, status=201)

    async def handle_batch_create(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
        except Exception:
            data = {}

        count = max(1, min(int(data.get("count", 5)), 50))
        base_name = str(data.get("base_name", "Batch Profile"))[:80]
        target_os = str(data.get("os", "windows"))[:20]
        created_list = []

        for i in range(1, count + 1):
            p_data = self.profile_manager.create_default_profile_data(name=f"{base_name} #{i}", os_type=target_os)
            p_data["os"] = target_os
            created = self.profile_manager.create_profile(p_data)
            created_list.append(created)

        return web.json_response({"status": "success", "count": len(created_list), "profiles": created_list}, status=201)

    async def handle_launch_profile(self, request: web.Request) -> web.Response:
        profile_id = request.match_info.get('id', '')
        if not _is_valid_profile_id(profile_id):
            return web.json_response({"status": "error", "message": "Invalid or missing profile_id."}, status=400)
        success, msg, driver = await self.launcher.launch_profile(profile_id)
        if success:
            profile = self.profile_manager.load_profile(profile_id) or {}
            engine_type = str(profile.get("engine", "camoufox")).lower().strip()
            dport = profile.get("debug_port", 0)
            is_chromium_cdp = engine_type in ["chromium", "playwright", "nodriver", "selenium_driverless"]
            ws_endpoint = f"ws://127.0.0.1:{dport}/devtools/browser" if (dport and is_chromium_cdp) else None
            return web.json_response({
                "status": "success",
                "message": msg,
                "profile_id": profile_id,
                "engine": engine_type,
                "debug_port": dport,
                "ws_endpoint": ws_endpoint,
                "connection_protocol": "cdp" if is_chromium_cdp else "camoufox_native"
            })
        else:
            return web.json_response({"status": "error", "message": msg}, status=400)

    async def handle_stop_profile(self, request: web.Request) -> web.Response:
        profile_id = request.match_info.get('id', '')
        if not _is_valid_profile_id(profile_id):
            return web.json_response({"status": "error", "message": "Invalid or missing profile_id."}, status=400)
        success, msg = await self.launcher.stop_profile(profile_id)
        if success:
            return web.json_response({"status": "success", "message": msg, "profile_id": profile_id})
        else:
            return web.json_response({"status": "error", "message": msg}, status=400)

    async def handle_clone_profile(self, request: web.Request) -> web.Response:
        profile_id = request.match_info.get('id', '')
        cloned = self.profile_manager.clone_profile(profile_id)
        if cloned:
            return web.json_response({"status": "success", "profile": cloned})
        return web.json_response({"status": "error", "message": "Failed to clone profile"}, status=400)

    async def handle_warmup_profile(self, request: web.Request) -> web.Response:
        profile_id = request.match_info.get('id', '')
        data = {}
        try:
            if request.has_body:
                data = await request.json()
        except Exception:
            pass

        cfg = WarmupConfig(
            category=data.get("category", "general"),
            max_pages=data.get("max_pages", 5),
            dwell_time=data.get("dwell_time", 8.0),
            urls=data.get("urls", [])
        )

        self.warmup_statuses[profile_id] = {"status": "running", "progress": 0.0, "message": "Started"}
        def status_cb(msg, pct, curl, cookies):
            self.warmup_statuses[profile_id] = {"status": "completed" if pct >= 100.0 else "running", "progress": pct, "message": msg, "cookies": cookies}

        asyncio.create_task(self.warmup_robot.run_warmup(profile_id, config=cfg, progress_callback=status_cb))
        return web.json_response({"status": "success", "profile_id": profile_id})

    async def handle_warmup_status(self, request: web.Request) -> web.Response:
        return web.json_response({"status": "success", "warmup_tasks": self.warmup_statuses})

    async def handle_trust_score(self, request: web.Request) -> web.Response:
        profile_id = request.match_info.get('id', '')
        profile = self.profile_manager.load_profile(profile_id)
        if not profile:
            return web.json_response({"status": "error", "message": "Profile not found"}, status=404)

        from engine.trust_score_evaluator import ProfileTrustEvaluator
        trust_score, details = await ProfileTrustEvaluator.evaluate_profile_trust(profile)
        profile["trust_score"] = trust_score
        profile["trust_details"] = details
        self.profile_manager.save_profile(profile)
        return web.json_response({"status": "success", "profile_id": profile_id, "trust_score": trust_score, "details": details})

    async def handle_list_proxies(self, request: web.Request) -> web.Response:
        proxies = self.proxy_manager.list_proxies()
        return web.json_response({"status": "success", "count": len(proxies), "proxies": proxies})

    async def handle_import_proxies(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
            raw_text = data.get("proxies_raw", "")
        except Exception:
            raw_text = ""
        imported_count = self.proxy_manager.import_raw_proxies(raw_text)
        return web.json_response({"status": "success", "imported": imported_count}, status=201)

    async def handle_scrape_proxies(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
            protocols = data.get("protocols", ["http", "socks4", "socks5"])
        except Exception:
            protocols = ["http", "socks4", "socks5"]
            
        async def scrape_task():
            proxies = await self.scraper.scrape_proxies(protocols=protocols)
            for p in proxies:
                self.proxy_manager.add_proxy(p)
            self.proxy_manager.save_proxies()
            
        asyncio.create_task(scrape_task())
        return web.json_response({"status": "success", "message": "Scraping started in background"})

    async def handle_get_ai_config(self, request: web.Request) -> web.Response:
        return web.json_response({
            "status": "success",
            "active_model": self.ai_mgr.get_active_model(),
            "provider_strategy": config.AI_PROVIDER_STRATEGY,
            "temperature": config.AI_TEMPERATURE,
            "shadow_dom_depth": config.AI_SHADOW_DOM_DEPTH,
            "consent_strategy": config.AI_CONSENT_STRATEGY,
            "gemini_configured": GeminiApiClient.get_instance().is_configured()
        })

    async def handle_set_ai_config(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"status": "error", "message": "Invalid JSON"}, status=400)
        
        if "active_model" in data:
            self.ai_mgr.set_active_model(data["active_model"])
        if "provider_strategy" in data:
            config.AI_PROVIDER_STRATEGY = data["provider_strategy"]
        if "temperature" in data:
            config.AI_TEMPERATURE = float(data["temperature"])
        if "shadow_dom_depth" in data:
            config.AI_SHADOW_DOM_DEPTH = int(data["shadow_dom_depth"])
        if "consent_strategy" in data:
            config.AI_CONSENT_STRATEGY = data["consent_strategy"]
        
        return web.json_response({"status": "success", "message": "AI config updated"})

    async def handle_list_ai_models(self, request: web.Request) -> web.Response:
        return web.json_response({
            "status": "success",
            "models": [{"id": m[0], "label": m[1]} for m in config.get_all_ai_model_options()]
        })

    async def handle_list_installed_models(self, request: web.Request) -> web.Response:
        installed = self.ai_mgr.get_installed_model_ids_sync()
        return web.json_response({"status": "success", "installed": installed})

    async def handle_pull_model(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
            model_id = data.get("model_id")
        except Exception:
            return web.json_response({"status": "error", "message": "Invalid JSON"}, status=400)
        
        asyncio.create_task(self.ai_mgr.ensure_model_pulled(model_id))
        return web.json_response({"status": "success", "message": f"Started pulling model {model_id}"})

    async def handle_clear_vram(self, request: web.Request) -> web.Response:
        await self.ai_mgr.unload_all_models_from_vram()
        return web.json_response({"status": "success", "message": "VRAM cleared"})

    async def handle_ai_chat(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"status": "error", "message": "Invalid JSON"}, status=400)

        prompt = data.get("prompt") or data.get("message", "")
        model = data.get("model") or getattr(config, "AI_DEFAULT_TEXT_MODEL", "qwen2.5:1.5b")
        swarm_mode = data.get("swarm_mode", "off")
        image_b64 = data.get("image_b64") or data.get("image")

        from engine.ai_chat_engine import AIChatEngine
        engine = AIChatEngine.get_instance()
        target_mode = swarm_mode if (swarm_mode and swarm_mode != "off") else model
        response_msg = await engine.stream_chat(
            prompt=prompt,
            model_or_swarm=target_mode,
            image_b64=image_b64
        )

        return web.json_response({
            "status": "success",
            "response": response_msg.content,
            "model": response_msg.model,
            "role": response_msg.role,
            "timestamp": response_msg.timestamp,
            "metadata": response_msg.metadata
        })

    # ── Workflow Handlers ────────────────────────────────────────────────────

    async def handle_list_workflows(self, request: web.Request) -> web.Response:
        service = WorkflowExecutionService.get_instance()
        workflows = service.list_workflows()
        return web.json_response({
            "status": "success",
            "count": len(workflows),
            "workflows": workflows
        })

    async def handle_get_workflow(self, request: web.Request) -> web.Response:
        workflow_id = request.match_info.get("id", "")
        service = WorkflowExecutionService.get_instance()
        wf = service.get_workflow(workflow_id)
        if not wf:
            return web.json_response({"status": "error", "message": f"Workflow '{workflow_id}' not found."}, status=404)
        return web.json_response({
            "status": "success",
            "workflow": wf
        })

    async def handle_run_workflow(self, request: web.Request) -> web.Response:
        data = {}
        try:
            if request.has_body:
                data = await request.json()
        except Exception:
            return web.json_response({"status": "error", "message": "Invalid JSON body."}, status=400)

        workflow_spec = data.get("workflow_id") or data.get("workflow") or data.get("dag")
        if not workflow_spec:
            return web.json_response({"status": "error", "message": "Missing 'workflow_id' or 'workflow' definition in request."}, status=400)

        profile_ids = data.get("profile_ids") or []
        if isinstance(profile_ids, str):
            profile_ids = [profile_ids]
        elif not isinstance(profile_ids, list):
            profile_ids = []

        if not profile_ids:
            single_pid = data.get("profile_id")
            if single_pid:
                profile_ids = [str(single_pid)]

        if not profile_ids:
            return web.json_response({"status": "error", "message": "At least one target 'profile_id' or 'profile_ids' list is required."}, status=400)

        concurrency = max(1, min(int(data.get("concurrency", 4)), 20))
        variables = data.get("variables", {})

        service = WorkflowExecutionService.get_instance()
        ok, msg, exec_id = await service.start_workflow(
            workflow_id_or_dict=workflow_spec,
            profile_ids=profile_ids,
            launcher=self.launcher,
            concurrency=concurrency,
            variables=variables
        )
        if not ok:
            return web.json_response({"status": "error", "message": msg}, status=400)

        return web.json_response({
            "status": "success",
            "message": msg,
            "execution_id": exec_id,
            "profile_ids": profile_ids,
            "concurrency": concurrency
        }, status=202)

    async def handle_workflow_status(self, request: web.Request) -> web.Response:
        exec_id = request.match_info.get("execution_id", "")
        service = WorkflowExecutionService.get_instance()
        status_rec = service.get_execution_status(exec_id)
        if not status_rec:
            return web.json_response({"status": "error", "message": f"Workflow execution '{exec_id}' not found."}, status=404)
        return web.json_response({
            "status": "success",
            "execution": status_rec
        })

    async def handle_stop_workflow(self, request: web.Request) -> web.Response:
        exec_id = request.match_info.get("execution_id", "")
        service = WorkflowExecutionService.get_instance()
        stopped = service.stop_execution(exec_id)
        if not stopped:
            return web.json_response({"status": "error", "message": f"Active workflow execution '{exec_id}' not found or already stopped."}, status=404)
        return web.json_response({
            "status": "success",
            "message": f"Workflow execution '{exec_id}' stopping initiated.",
            "execution_id": exec_id
        })

    async def start(self, host: Optional[str] = None, port: Optional[int] = None) -> bool:
        if host:
            self.host = host
        if port:
            self.port = port

        if self.is_running():
            logger.info(f"REST API Server is already running on http://{self.host}:{self.port}")
            return True

        logging.getLogger("aiohttp.access").setLevel(logging.WARNING)
        logging.getLogger("aiohttp.server").setLevel(logging.WARNING)

        # [F-04] Ensure API is never accidentally open: auto-generate token if none configured
        expected_token = getattr(config, "API_BEARER_TOKEN", "").strip()
        if not expected_token and getattr(config, "API_AUTH_ENABLED", True):
            generated_token = secrets.token_urlsafe(32)
            config.API_BEARER_TOKEN = generated_token
            try:
                from storage.secrets_manager import SecretsManager
                if SecretsManager.is_initialized():
                    SecretsManager.set("api_bearer_token", generated_token)
                    SecretsManager.save()
            except Exception as se:
                logger.debug(f"[APIServer] Could not persist token to vault: {se}")

            logger.warning(
                f"[APIServer] SECURITY: No API_BEARER_TOKEN configured. "
                f"A secure 32-byte cryptographic session token has been auto-generated and stored in the encrypted vault. "
                f"API Token: {generated_token}"
            )

        # [F-03] Start background session cleanup task
        asyncio.create_task(_session_cleanup_worker())

        self.runner = web.AppRunner(self.app, access_log=None)
        await self.runner.setup()
        bind_host = self.host if (self.host and self.host.strip()) else "127.0.0.1"
        try:
            self._site = web.TCPSite(self.runner, bind_host, self.port)
            await self._site.start()
            logger.info(f"REST API Server running at http://{bind_host}:{self.port} (configured host: {self.host})")
            return True
        except OSError as e:
            logger.warning(f"REST API Server port {self.port} already in use or unavailable: {e}")
            return False

    async def stop(self) -> bool:
        if self._site:
            try:
                await self._site.stop()
            except Exception:
                pass
            self._site = None

        if self.runner:
            try:
                await self.runner.cleanup()
            except Exception:
                pass
            self.runner = None
            logger.info("REST API Server stopped.")
            return True
        return False

    async def restart(self, host: Optional[str] = None, port: Optional[int] = None) -> bool:
        await self.stop()
        return await self.start(host=host, port=port)
