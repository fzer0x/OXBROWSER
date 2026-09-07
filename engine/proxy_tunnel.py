import asyncio
import base64
import random
import socket
import logging
import time
from typing import Optional, Dict, Any, List

logger = logging.getLogger("ProxyTunnel")
logger.setLevel(logging.WARNING)


# Import from engine.port_utils (neutral shared module) to avoid circular import.
# engine.browser → engine.proxy_tunnel → engine.browser was the circular chain.
from engine.port_utils import find_free_port  # noqa: F401


class ProxyError(Exception):
    """Base exception for proxy tunnel errors."""
    pass


class UpstreamUnavailableError(ProxyError):
    """Raised when the upstream proxy server cannot be reached."""
    pass


class AuthenticationError(ProxyError):
    """Raised when upstream proxy authentication fails."""
    pass


class RateLimitError(ProxyError):
    """Raised when upstream proxy returns rate limit (HTTP 429)."""
    pass


class ProxyTimeouts:
    """Configurable timeouts for proxy operations."""

    def __init__(
        self,
        connect_timeout: float = 12.0,
        readline_timeout: float = 15.0,
        connect_resp_timeout: float = 15.0,
        idle_timeout: float = 45.0
    ):
        self.connect_timeout = connect_timeout
        self.readline_timeout = readline_timeout
        self.connect_resp_timeout = connect_resp_timeout
        self.idle_timeout = idle_timeout


class ProxyTunnelConfig:
    """Configurable domain blocklists and buffer settings for ProxyTunnel."""

    BLOCKED_DOMAINS: List[str] = [

    ]
    ALLOWED_PATHS: List[str] = ["/", "/favicon.ico"]
    CHUNK_SIZE: int = 65536
    MAX_BUFFER: int = 262144
    BURST_PROTECTION: bool = True
    BURST_STAGGER_MS: float = 10.0  # 10ms micro-staggering spacing between concurrent handshakes


class ProxyStats:
    """Real-time traffic metrics and request statistics collector."""

    def __init__(self):
        self.requests_total: int = 0
        self.requests_success: int = 0
        self.requests_failed: int = 0
        self.bytes_transferred: int = 0
        self.active_connections: int = 0

    def record_request(self, success: bool):
        self.requests_total += 1
        if success:
            self.requests_success += 1
        else:
            self.requests_failed += 1

    def record_bytes(self, n: int):
        self.bytes_transferred += n

    def inc_active(self):
        self.active_connections += 1

    def dec_active(self):
        self.active_connections = max(0, self.active_connections - 1)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_requests": self.requests_total,
            "success_requests": self.requests_success,
            "failed_requests": self.requests_failed,
            "success_rate": round(self.requests_success / max(1, self.requests_total), 4),
            "bytes_transferred": self.bytes_transferred,
            "active_connections": self.active_connections
        }


class CircuitBreaker:
    """
    3-state circuit breaker for upstream proxy connections.

    States:
      CLOSED    – normal operation, all requests pass through.
      OPEN      – upstream is considered dead; requests fail immediately
                  with 503 until the cooldown window expires.
      HALF_OPEN – one probe request is allowed through to test recovery;
                  success closes the circuit, failure re-opens it.

    Thresholds (defaults):
      failure_threshold  – consecutive failures needed to open the circuit (5)
      cooldown_seconds   – seconds to wait in OPEN before probing (30)
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(self, failure_threshold: int = 5, cooldown_seconds: float = 30.0):
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self._state = self.CLOSED
        self._consecutive_failures = 0
        self._opened_at: float = 0.0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> str:
        return self._state

    async def allow_request(self) -> bool:
        """Returns True if the request should be allowed through."""
        async with self._lock:
            if self._state == self.CLOSED:
                return True
            if self._state == self.OPEN:
                if time.monotonic() - self._opened_at >= self.cooldown_seconds:
                    self._state = self.HALF_OPEN
                    logger.warning("[CircuitBreaker] Cooldown elapsed – entering HALF_OPEN state (probe request allowed)")
                    return True
                return False
            # HALF_OPEN: only one probe at a time
            return True

    async def record_success(self):
        """Call after a successful upstream connection to close/reset the circuit."""
        async with self._lock:
            if self._state in (self.HALF_OPEN, self.OPEN):
                logger.warning(f"[CircuitBreaker] Probe succeeded – circuit CLOSED after {self._consecutive_failures} failures")
            self._state = self.CLOSED
            self._consecutive_failures = 0

    async def record_failure(self):
        """Call after any upstream connection failure to advance the failure counter."""
        async with self._lock:
            self._consecutive_failures += 1
            if self._state == self.HALF_OPEN:
                # Probe failed – re-open the circuit immediately
                self._state = self.OPEN
                self._opened_at = time.monotonic()
                logger.warning("[CircuitBreaker] Probe FAILED – circuit re-OPENED, next probe in "
                               f"{self.cooldown_seconds:.0f}s")
            elif self._state == self.CLOSED and self._consecutive_failures >= self.failure_threshold:
                self._state = self.OPEN
                self._opened_at = time.monotonic()
                logger.warning(f"[CircuitBreaker] Failure threshold reached ({self._consecutive_failures} consecutive) "
                               f"– circuit OPENED, cooling down for {self.cooldown_seconds:.0f}s")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state": self._state,
            "consecutive_failures": self._consecutive_failures,
            "cooldown_seconds": self.cooldown_seconds,
            "seconds_until_probe": max(0.0, round(self.cooldown_seconds - (time.monotonic() - self._opened_at), 1))
                                   if self._state == self.OPEN else 0.0,
        }


from engine.tls_impersonate import TLSImpersonate


class LocalProxyTunnel:
    """
    Lightweight, high-performance local proxy authentication tunnel in pure Python asyncio.
    Routes local browser traffic to upstream HTTP/SOCKS5 proxies with zero-latency
    authentication injection, flow control, rate limiting, and real-time metrics.
    """

    def __init__(
        self,
        upstream_host: str,
        upstream_port: int,
        username: str = "",
        password: str = "",
        proxy_type: str = "http",
        max_concurrency: int = 24,
        burst_protection: bool = True,
        burst_stagger_ms: float = 75.0,
        timeouts: Optional[ProxyTimeouts] = None,
        config: Optional[ProxyTunnelConfig] = None,
        tls_preset: str = "auto",
        target_os: str = "windows"
    ):
        self.upstream_host = upstream_host.strip()
        self.upstream_port = upstream_port
        self.username = username.strip()
        self.password = password.strip()
        self.proxy_type = proxy_type.lower().strip()
        if self.proxy_type in ["socks5", "socks5h"]:
            self.proxy_type = "socks5"
        else:
            self.proxy_type = "http"

        self.tls_preset = tls_preset
        self.target_os = target_os
        self.ssl_context = TLSImpersonate.create_proxy_tunnel_ssl_context(tls_preset, target_os)

        self.local_port = find_free_port()
        self.server: Optional[asyncio.Server] = None
        self._is_running = False
        self._conn_semaphore = asyncio.Semaphore(max_concurrency)
        self.burst_protection = burst_protection
        self.burst_stagger_ms = burst_stagger_ms
        self._handshake_lock = asyncio.Lock()
        self._last_handshake_time = 0.0
        self.timeouts = timeouts or ProxyTimeouts()
        self.config = config or ProxyTunnelConfig()
        self.stats = ProxyStats()
        # Circuit breaker: trips after 5 consecutive upstream failures,
        # cools down for 30s before probing with a single request.
        self.circuit_breaker = CircuitBreaker(failure_threshold=5, cooldown_seconds=30.0)

    async def start(self) -> int:
        """Starts the local tunnel server on 127.0.0.1 and returns the assigned port."""
        self.server = await asyncio.start_server(
            self._handle_client, '127.0.0.1', self.local_port
        )
        self._is_running = True
        logger.info(f"Started Local Proxy Tunnel on 127.0.0.1:{self.local_port} -> {self.proxy_type}://{self.upstream_host}:{self.upstream_port}")
        return self.local_port

    def update_upstream(
        self,
        upstream_host: str,
        upstream_port: int,
        username: str = "",
        password: str = "",
        proxy_type: str = "http"
    ):
        """
        Dynamically updates the upstream proxy target for subsequent connections
        without closing the local tunnel server or restarting the browser.
        """
        self.upstream_host = upstream_host.strip()
        self.upstream_port = upstream_port
        self.username = username.strip()
        self.password = password.strip()
        p_type = proxy_type.lower().strip()
        self.proxy_type = "socks5" if p_type in ["socks5", "socks5h"] else "http"
        logger.info(f"[ProxyTunnel 127.0.0.1:{self.local_port}] Upstream updated -> {self.proxy_type}://{self.upstream_host}:{self.upstream_port}")

    async def stop(self, timeout: float = 3.0):
        """Gracefully stops the local tunnel server, waiting for active connections up to timeout."""
        self._is_running = False

        if self.server:
            start_time = time.time()
            while self.stats.active_connections > 0 and (time.time() - start_time) < timeout:
                await asyncio.sleep(0.05)

            if self.stats.active_connections > 0:
                logger.warning(f"Force closing {self.stats.active_connections} active proxy connections on port {self.local_port}")

            self.server.close()
            try:
                await self.server.wait_closed()
            except Exception:
                pass
            logger.info(f"Stopped Local Proxy Tunnel on 127.0.0.1:{self.local_port}")

    async def check_upstream_health(self) -> bool:
        """Asynchronously tests reachability of the upstream proxy server."""
        try:
            r, w = await asyncio.wait_for(
                asyncio.open_connection(self.upstream_host, self.upstream_port),
                timeout=3.0
            )
            w.close()
            await w.wait_closed()
            return True
        except Exception:
            return False

    async def _pipe(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Pipes bytes bidirectionally between sockets with flow control, idle timeout & metrics recording."""
        try:
            while self._is_running and not reader.at_eof():
                try:
                    data = await asyncio.wait_for(
                        reader.read(self.config.CHUNK_SIZE),
                        timeout=self.timeouts.idle_timeout
                    )
                except asyncio.TimeoutError:
                    # Idle keep-alive timeout expired - reap socket to release upstream concurrency slots
                    break

                if not data:
                    break
                writer.write(data)
                await writer.drain()
                self.stats.record_bytes(len(data))
        except (ConnectionResetError, BrokenPipeError, asyncio.CancelledError):
            pass
        except Exception as e:
            logger.debug(f"Pipe stream closed: {e}")
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def _relay_traffic(self, client_reader: asyncio.StreamReader, client_writer: asyncio.StreamWriter, up_reader: asyncio.StreamReader, up_writer: asyncio.StreamWriter):
        """Relays traffic bidirectionally and cleans up immediately when either side disconnects or idles."""
        t1 = asyncio.create_task(self._pipe(client_reader, up_writer))
        t2 = asyncio.create_task(self._pipe(up_reader, client_writer))
        try:
            done, pending = await asyncio.wait([t1, t2], return_when=asyncio.FIRST_COMPLETED)
            for p in pending:
                p.cancel()
                try:
                    await p
                except (asyncio.CancelledError, Exception):
                    pass
        finally:
            for w in (up_writer, client_writer):
                try:
                    w.close()
                except Exception:
                    pass

    async def _handle_client(self, client_reader: asyncio.StreamReader, client_writer: asyncio.StreamWriter):
        self.stats.inc_active()
        try:
            if self.proxy_type == "socks5":
                await self._handle_socks5(client_reader, client_writer)
            else:
                await self._handle_http(client_reader, client_writer)
        except Exception as e:
            logger.debug(f"Tunnel client handler exception: {e}")
            try:
                client_writer.close()
            except Exception:
                pass
        finally:
            self.stats.dec_active()

    async def _pace_handshake(self):
        """Optionally paces concurrent handshakes by a few milliseconds to smooth out burst rate limits."""
        if self.burst_protection and self.burst_stagger_ms > 0:
            async with self._handshake_lock:
                now = time.monotonic()
                elapsed = (now - self._last_handshake_time) * 1000.0
                if elapsed < self.burst_stagger_ms:
                    await asyncio.sleep((self.burst_stagger_ms - elapsed) / 1000.0)
                self._last_handshake_time = time.monotonic()

    async def _handle_http(self, client_reader: asyncio.StreamReader, client_writer: asyncio.StreamWriter):
        header_buf = bytearray()
        while True:
            try:
                line = await asyncio.wait_for(client_reader.readline(), timeout=self.timeouts.readline_timeout)
            except Exception:
                client_writer.close()
                return
            if not line:
                client_writer.close()
                return
            header_buf.extend(line)
            if line in (b"\r\n", b"\n"):
                break

        header_str = header_buf.decode('latin1', errors='ignore')
        lines = [l for l in header_str.split("\r\n") if l]
        if not lines:
            client_writer.close()
            return

        req_line = lines[0]
        req_parts = req_line.strip().split()
        method = req_parts[0].upper() if len(req_parts) >= 1 else "UNKNOWN"
        target = req_parts[1] if len(req_parts) >= 2 else "UNKNOWN"

        logger.debug(f"[ProxyTunnel 127.0.0.1:{self.local_port}] Client request: '{req_line.strip()}'")

        target_lower = target.lower()
        if any(b in target_lower for b in self.config.BLOCKED_DOMAINS):
            client_writer.write(b"HTTP/1.1 403 Forbidden\r\nContent-Type: text/plain\r\nConnection: close\r\nContent-Length: 9\r\n\r\nForbidden")
            await client_writer.drain()
            client_writer.close()
            self.stats.record_request(success=False)
            return

        if len(req_parts) >= 2:
            if method == "GET" and target in self.config.ALLOWED_PATHS:
                host_hdr = ""
                for l in lines[1:]:
                    if l.lower().startswith("host:"):
                        host_hdr = l.split(":", 1)[1].strip()
                        break

                if host_hdr.startswith(f"127.0.0.1:{self.local_port}") or host_hdr.startswith(f"localhost:{self.local_port}"):
                    html = (
                        "<!DOCTYPE html><html><head><title>SoxBot Proxy Tunnel</title>"
                        "<style>body{font-family:sans-serif;background:#121214;color:#e0e0e0;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;}"
                        ".card{background:#1e1e24;padding:2rem;border-radius:12px;box-shadow:0 8px 24px rgba(0,0,0,0.5);max-width:540px;text-align:center;line-height:1.6;}"
                        "h1{color:#7c4dff;margin-top:0;}code{background:#2a2a35;padding:2px 6px;border-radius:4px;color:#00e5ff;}"
                        "a{color:#00e5ff;text-decoration:none;font-weight:bold;}a:hover{text-decoration:underline;}</style></head>"
                        "<body><div class='card'>"
                        "<h1>SoxBot Proxy Tunnel</h1>"
                        f"<p>Dieser Port (<code>127.0.0.1:{self.local_port}</code>) ist ein lokaler Proxy-Tunnel für Anti-Detect-Browser-Profile.</p>"
                        f"<p>Ziel-Proxy: <code>{self.proxy_type}://{self.upstream_host}:{self.upstream_port}</code></p>"
                        "<p>Um das SoxBot REST-API Server-Interface im Browser aufzurufen, nutze bitte:<br><br>"
                        "<a href='http://127.0.0.1:59200/' target='_blank'>http://127.0.0.1:59200/</a></p>"
                        "</div></body></html>"
                    )
                    resp = (
                        f"HTTP/1.1 200 OK\r\n"
                        f"Content-Type: text/html; charset=utf-8\r\n"
                        f"Content-Length: {len(html.encode('utf-8'))}\r\n"
                        f"Connection: close\r\n\r\n"
                        f"{html}"
                    )
                    client_writer.write(resp.encode('utf-8'))
                    await client_writer.drain()
                    client_writer.close()
                    self.stats.record_request(success=True)
                    return

        up_reader, up_writer = None, None

        # Circuit breaker: fail fast if upstream is known-dead
        if not await self.circuit_breaker.allow_request():
            cb = self.circuit_breaker.to_dict()
            logger.warning(f"[ProxyTunnel 127.0.0.1:{self.local_port}] Circuit OPEN – rejecting '{target}' fast (probe in {cb['seconds_until_probe']}s)")
            try:
                client_writer.write(b"HTTP/1.1 503 Service Unavailable\r\nContent-Type: text/plain\r\nRetry-After: 30\r\nConnection: close\r\nContent-Length: 25\r\n\r\nUpstream proxy unavailable")
                await client_writer.drain()
            except Exception:
                pass
            client_writer.close()
            self.stats.record_request(success=False)
            return

        async with self._conn_semaphore:
            max_attempts = 5
            for attempt in range(max_attempts):
                try:
                    await self._pace_handshake()
                    up_reader, up_writer = await asyncio.wait_for(
                        asyncio.open_connection(self.upstream_host, self.upstream_port),
                        timeout=self.timeouts.connect_timeout
                    )
                except Exception as e:
                    err_desc = f"{type(e).__name__}: {e}" if str(e) else type(e).__name__
                    await self.circuit_breaker.record_failure()
                    if attempt < max_attempts - 1:
                        # Exponential backoff with full jitter: delay in [0, base * 2^attempt]
                        base_delay = 0.25 * (2 ** attempt)
                        delay = random.uniform(0, min(base_delay, 8.0))
                        logger.warning(f"[ProxyTunnel 127.0.0.1:{self.local_port}] Upstream connection attempt {attempt+1} failed ({err_desc}). Retrying in {delay:.2f}s...")
                        await asyncio.sleep(delay)
                        continue
                    else:
                        logger.error(f"[ProxyTunnel 127.0.0.1:{self.local_port}] Failed to connect to upstream proxy {self.upstream_host}:{self.upstream_port} for target '{target}': {err_desc}")
                        try:
                            err_msg = f"502 Bad Gateway - Failed to connect to upstream proxy {self.upstream_host}:{self.upstream_port}\r\n".encode('utf-8')
                            client_writer.write(b"HTTP/1.1 502 Bad Gateway\r\nContent-Type: text/plain\r\nConnection: close\r\nContent-Length: " + str(len(err_msg)).encode('ascii') + b"\r\n\r\n" + err_msg)
                            await client_writer.drain()
                        except Exception:
                            pass
                        client_writer.close()
                        self.stats.record_request(success=False)
                        return

                auth_header_str = ""
                if self.username and self.password:
                    auth_bytes = f"{self.username}:{self.password}".encode('utf-8')
                    b64_auth = base64.b64encode(auth_bytes).decode('ascii')
                    auth_header_str = f"Proxy-Authorization: Basic {b64_auth}"

                new_headers = [req_line]
                if auth_header_str:
                    new_headers.append(auth_header_str)

                for l in lines[1:]:
                    if not l.lower().startswith("proxy-authorization:"):
                        new_headers.append(l)

                out_data = "\r\n".join(new_headers) + "\r\n\r\n"
                up_writer.write(out_data.encode('latin1'))
                await up_writer.drain()

                is_connect = method == "CONNECT"

                if not is_connect:
                    break

                try:
                    resp_line = await asyncio.wait_for(up_reader.readline(), timeout=self.timeouts.connect_resp_timeout)
                except Exception as e:
                    err_desc = f"{type(e).__name__}: {e}" if str(e) else type(e).__name__
                    logger.error(f"[ProxyTunnel 127.0.0.1:{self.local_port}] Timeout reading CONNECT response from upstream proxy {self.upstream_host}:{self.upstream_port} for target '{target}': {err_desc}")
                    up_writer.close()
                    if attempt < max_attempts - 1:
                        await asyncio.sleep(0.2)
                        continue
                    client_writer.close()
                    self.stats.record_request(success=False)
                    return

                if not resp_line:
                    logger.warning(f"[ProxyTunnel 127.0.0.1:{self.local_port}] Upstream proxy closed connection prematurely for target '{target}'")
                    up_writer.close()
                    if attempt < max_attempts - 1:
                        await asyncio.sleep(0.2)
                        continue
                    client_writer.close()
                    self.stats.record_request(success=False)
                    return

                resp_headers = bytearray()
                while True:
                    try:
                        h = await asyncio.wait_for(up_reader.readline(), timeout=3.0)
                    except Exception:
                        break
                    if not h or h in (b"\r\n", b"\n"):
                        break
                    resp_headers.extend(h)

                parts = resp_line.split()
                status_code = 0
                if len(parts) >= 2:
                    try:
                        status_code = int(parts[1])
                    except ValueError:
                        pass

                resp_line_str = resp_line.decode('latin1', errors='ignore').strip()
                if status_code == 429:
                    up_writer.close()
                    if attempt < max_attempts - 1:
                        # Exponential backoff with full jitter for 429s: [0, base * 2^attempt], min 0.5s
                        base_delay = 0.5 * (2 ** attempt)
                        delay = random.uniform(0.5, min(base_delay, 16.0))
                        logger.warning(f"[ProxyTunnel 127.0.0.1:{self.local_port}] Upstream proxy returned 429 Rate Limit for '{target}'. Retrying in {delay:.2f}s...")
                        await asyncio.sleep(delay)
                        continue
                    else:
                        logger.error(f"[ProxyTunnel 127.0.0.1:{self.local_port}] Upstream proxy 429 limit reached on target '{target}'. Returning 502 Bad Gateway.")
                        client_writer.write(b"HTTP/1.1 502 Bad Gateway\r\nContent-Type: text/plain\r\nConnection: close\r\nContent-Length: 32\r\n\r\nUpstream Proxy Rate Limit (429)\r\n")
                        await client_writer.drain()
                        client_writer.close()
                        self.stats.record_request(success=False)
                        return

                if 200 <= status_code < 300:
                    logger.debug(f"[ProxyTunnel 127.0.0.1:{self.local_port}] Upstream CONNECT successful for target '{target}': {resp_line_str}")
                    client_writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                    await client_writer.drain()
                    break
                elif status_code == 407:
                    logger.error(f"[ProxyTunnel 127.0.0.1:{self.local_port}] Upstream proxy REJECTED credentials for user '{self.username}' on target '{target}'! Status: {resp_line_str}")
                    client_writer.write(resp_line + resp_headers + b"\r\n")
                    await client_writer.drain()
                    break
                else:
                    logger.warning(f"[ProxyTunnel 127.0.0.1:{self.local_port}] Upstream CONNECT returned non-200 status {status_code} for target '{target}': {resp_line_str}")
                    client_writer.write(resp_line + resp_headers + b"\r\n")
                    await client_writer.drain()
                    break

            if up_reader and up_writer and not up_writer.is_closing():
                await self.circuit_breaker.record_success()
                self.stats.record_request(success=True)
                await self._relay_traffic(client_reader, client_writer, up_reader, up_writer)
            else:
                self.stats.record_request(success=False)

    async def _handle_socks5(self, client_reader: asyncio.StreamReader, client_writer: asyncio.StreamWriter):
        c_ver = await client_reader.readexactly(1)
        if c_ver != b"\x05":
            client_writer.close()
            self.stats.record_request(success=False)
            return
        nmethods = (await client_reader.readexactly(1))[0]
        methods = await client_reader.readexactly(nmethods)

        client_writer.write(b"\x05\x00")
        await client_writer.drain()

        req_hdr = await client_reader.readexactly(4)
        cmd = req_hdr[1]
        atyp = req_hdr[3]

        if atyp == 1:
            addr_bytes = await client_reader.readexactly(4)
            addr_str = socket.inet_ntoa(addr_bytes)
        elif atyp == 3:
            dlen = (await client_reader.readexactly(1))[0]
            addr_bytes = await client_reader.readexactly(dlen)
            addr_str = addr_bytes.decode('latin1')
        elif atyp == 4:
            addr_bytes = await client_reader.readexactly(16)
            addr_str = socket.inet_ntop(socket.AF_INET6, addr_bytes)
        else:
            client_writer.close()
            self.stats.record_request(success=False)
            return

        port_bytes = await client_reader.readexactly(2)
        dest_port = int.from_bytes(port_bytes, 'big')

        logger.debug(f"[ProxyTunnel 127.0.0.1:{self.local_port}] SOCKS5 client request for target '{addr_str}:{dest_port}'")
 
        up_reader, up_writer = None, None

        # Circuit breaker: fail fast if upstream is known-dead
        if not await self.circuit_breaker.allow_request():
            cb = self.circuit_breaker.to_dict()
            logger.warning(f"[ProxyTunnel 127.0.0.1:{self.local_port}] Circuit OPEN – rejecting SOCKS5 '{addr_str}:{dest_port}' fast (probe in {cb['seconds_until_probe']}s)")
            client_writer.write(b"\x05\x04\x00\x01\x00\x00\x00\x00\x00\x00")  # SOCKS5 host unreachable
            try:
                await client_writer.drain()
            except Exception:
                pass
            client_writer.close()
            self.stats.record_request(success=False)
            return

        async with self._conn_semaphore:
            max_attempts = 5
            for attempt in range(max_attempts):
                try:
                    await self._pace_handshake()
                    up_reader, up_writer = await asyncio.wait_for(
                        asyncio.open_connection(self.upstream_host, self.upstream_port),
                        timeout=self.timeouts.connect_timeout
                    )
                    break
                except Exception as e:
                    err_desc = f"{type(e).__name__}: {e}" if str(e) else type(e).__name__
                    await self.circuit_breaker.record_failure()
                    if attempt < max_attempts - 1:
                        # Exponential backoff with full jitter: delay in [0, base * 2^attempt]
                        base_delay = 0.25 * (2 ** attempt)
                        delay = random.uniform(0, min(base_delay, 8.0))
                        logger.warning(f"[ProxyTunnel 127.0.0.1:{self.local_port}] Upstream SOCKS5 connection attempt {attempt+1} failed ({err_desc}). Retrying in {delay:.2f}s...")
                        await asyncio.sleep(delay)
                    else:
                        logger.error(f"[ProxyTunnel 127.0.0.1:{self.local_port}] Failed to connect to upstream SOCKS5 proxy {self.upstream_host}:{self.upstream_port} for target '{addr_str}:{dest_port}': {err_desc}")
                        client_writer.close()
                        self.stats.record_request(success=False)
                        return

            if up_reader is None or up_writer is None:
                client_writer.close()
                self.stats.record_request(success=False)
                return

            if self.username and self.password:
                up_writer.write(b"\x05\x02\x00\x02")
            else:
                up_writer.write(b"\x05\x01\x00")
            await up_writer.drain()

            up_res = await up_reader.readexactly(2)
            if up_res[1] == 2:
                u_b = self.username.encode('utf-8')
                p_b = self.password.encode('utf-8')
                up_writer.write(bytes([1, len(u_b)]) + u_b + bytes([len(p_b)]) + p_b)
                await up_writer.drain()
                auth_res = await up_reader.readexactly(2)
                if auth_res[1] != 0:
                    logger.error(f"[ProxyTunnel 127.0.0.1:{self.local_port}] Upstream SOCKS5 proxy authentication REJECTED for user '{self.username}'!")
                    client_writer.close()
                    up_writer.close()
                    self.stats.record_request(success=False)
                    return
                logger.debug(f"[ProxyTunnel 127.0.0.1:{self.local_port}] Upstream SOCKS5 authentication SUCCESSFUL for user '{self.username}'")

            if atyp == 3:
                up_req = b"\x05" + bytes([cmd, 0, 3, len(addr_bytes)]) + addr_bytes + port_bytes
            else:
                up_req = b"\x05" + bytes([cmd, 0, atyp]) + addr_bytes + port_bytes

            up_writer.write(up_req)
            await up_writer.drain()

            up_resp = await up_reader.readexactly(4)
            if up_resp[1] != 0:
                logger.warning(f"[ProxyTunnel 127.0.0.1:{self.local_port}] Upstream SOCKS5 proxy returned error status code: {up_resp[1]} for target '{addr_str}:{dest_port}'")
                client_writer.write(b"\x05\x01\x00\x01\x00\x00\x00\x00\x00\x00")
                await client_writer.drain()
                client_writer.close()
                up_writer.close()
                self.stats.record_request(success=False)
                return

            logger.debug(f"[ProxyTunnel 127.0.0.1:{self.local_port}] Upstream SOCKS5 connection to target '{addr_str}:{dest_port}' ESTABLISHED")

            u_atyp = up_resp[3]
            if u_atyp == 1:
                u_addr = await up_reader.readexactly(6)
            elif u_atyp == 3:
                u_len = (await up_reader.readexactly(1))[0]
                u_addr = await up_reader.readexactly(u_len + 2)
            elif u_atyp == 4:
                u_addr = await up_reader.readexactly(18)
            else:
                u_addr = b"\x00\x00\x00\x00\x00\x00"

            client_writer.write(b"\x05\x00\x00" + bytes([u_atyp]) + u_addr)
            await client_writer.drain()

            if up_reader and up_writer and not up_writer.is_closing():
                await self.circuit_breaker.record_success()
                self.stats.record_request(success=True)
                await self._relay_traffic(client_reader, client_writer, up_reader, up_writer)
            else:
                self.stats.record_request(success=False)

