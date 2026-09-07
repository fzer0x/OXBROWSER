import aiohttp
import asyncio
import json
import time
import logging
from typing import Any, Dict, Tuple

logger = logging.getLogger("ProxyChecker")

class ProxyChecker:
    """Async Proxy Validator and Geolocation/Timezone Fetcher."""

    @staticmethod
    def build_proxy_url(proxy_cfg: Dict, for_chrome: bool = False, include_auth: bool = True) -> str:
        if not proxy_cfg.get("enabled") or not proxy_cfg.get("host"):
            return ""

        p_type = proxy_cfg.get("type", "http").lower()
        if p_type in ["socks5", "socks5h"]:
            p_type = "socks5"
        else:
            p_type = "http"

        host = str(proxy_cfg.get("host", "")).strip()
        port = int(proxy_cfg.get("port", 8080))
        user = str(proxy_cfg.get("username", "")).strip()
        pwd = str(proxy_cfg.get("password", "")).strip()

        if include_auth and user and pwd:
            return f"{p_type}://{user}:{pwd}@{host}:{port}"
        return f"{p_type}://{host}:{port}"

    @classmethod
    async def _check_socks5_native(cls, proxy_cfg: Dict, timeout: int = 10) -> Tuple[bool, Dict, float]:
        """Native asyncio SOCKS5 handshake & HTTP request for proxy checking without external libs."""
        start_time = time.time()
        host = str(proxy_cfg.get("host", "")).strip()
        port = int(proxy_cfg.get("port", 8080))
        user = str(proxy_cfg.get("username", "")).strip()
        pwd = str(proxy_cfg.get("password", "")).strip()

        target_host = "ip-api.com"
        target_port = 80
        target_path = "/json/?fields=status,message,country,countryCode,region,regionName,city,zip,lat,lon,timezone,isp,org,as,query"

        logger.info(f"[ProxyChecker] Performing native SOCKS5 check to {host}:{port}...")

        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=timeout
            )

            # 1. Send SOCKS5 Greeting
            if user and pwd:
                writer.write(b"\x05\x02\x00\x02")
            else:
                writer.write(b"\x05\x01\x00")
            await writer.drain()

            res = await asyncio.wait_for(reader.readexactly(2), timeout=timeout)
            if res[0] != 5:
                writer.close()
                logger.error(f"[ProxyChecker] SOCKS5 check error: Invalid header from {host}:{port}")
                return False, {"error": "Invalid SOCKS5 header"}, round((time.time() - start_time) * 1000, 2)

            auth_method = res[1]
            if auth_method == 2:  # Username/Password Auth
                u_bytes = user.encode('utf-8')
                p_bytes = pwd.encode('utf-8')
                auth_req = bytes([1, len(u_bytes)]) + u_bytes + bytes([len(p_bytes)]) + p_bytes
                writer.write(auth_req)
                await writer.drain()

                auth_res = await asyncio.wait_for(reader.readexactly(2), timeout=timeout)
                if auth_res[1] != 0:
                    writer.close()
                    logger.error(f"[ProxyChecker] SOCKS5 Authentication failed for user '{user}' on {host}:{port}")
                    return False, {"error": "SOCKS5 Authentication Failed"}, round((time.time() - start_time) * 1000, 2)
            elif auth_method != 0:
                writer.close()
                logger.error(f"[ProxyChecker] Unsupported SOCKS5 auth method {auth_method} on {host}:{port}")
                return False, {"error": f"Unsupported SOCKS5 auth method: {auth_method}"}, round((time.time() - start_time) * 1000, 2)

            # 2. Send SOCKS5 CONNECT Request for ip-api.com:80
            tgt_bytes = target_host.encode('utf-8')
            conn_req = b"\x05\x01\x00\x03" + bytes([len(tgt_bytes)]) + tgt_bytes + target_port.to_bytes(2, 'big')
            writer.write(conn_req)
            await writer.drain()

            rep = await asyncio.wait_for(reader.readexactly(4), timeout=timeout)
            if rep[1] != 0:
                writer.close()
                logger.error(f"[ProxyChecker] SOCKS5 connect request failed (code {rep[1]}) for {host}:{port}")
                return False, {"error": f"SOCKS5 Connect Failed (code {rep[1]})"}, round((time.time() - start_time) * 1000, 2)

            atyp = rep[3]
            if atyp == 1:
                await reader.readexactly(6)
            elif atyp == 3:
                dlen = (await reader.readexactly(1))[0]
                await reader.readexactly(dlen + 2)
            elif atyp == 4:
                await reader.readexactly(18)

            # 3. Send HTTP GET over SOCKS5 tunnel
            http_req = (
                f"GET {target_path} HTTP/1.1\r\n"
                f"Host: {target_host}\r\n"
                f"User-Agent: SoxBot/1.0\r\n"
                f"Connection: close\r\n\r\n"
            )
            writer.write(http_req.encode('utf-8'))
            await writer.drain()

            raw_resp = await asyncio.wait_for(reader.read(), timeout=timeout)
            writer.close()
            await writer.wait_closed()

            latency = round((time.time() - start_time) * 1000, 2)
            resp_str = raw_resp.decode('utf-8', errors='ignore')

            if "\r\n\r\n" in resp_str:
                body = resp_str.split("\r\n\r\n", 1)[1]
            elif "\n\n" in resp_str:
                body = resp_str.split("\n\n", 1)[1]
            else:
                body = resp_str

            data = json.loads(body.strip())
            if data.get("status") == "success":
                info = {
                    "ip": data.get("query", ""),
                    "country": data.get("country", ""),
                    "country_code": data.get("countryCode", ""),
                    "city": data.get("city", ""),
                    "timezone": data.get("timezone", "UTC"),
                    "lat": data.get("lat", 0.0),
                    "lon": data.get("lon", 0.0),
                    "isp": data.get("isp", "")
                }
                logger.info(f"[ProxyChecker] Native SOCKS5 check success for {host}:{port} -> IP: {info['ip']} ({info['country']}) in {latency}ms")
                return True, info, latency
            else:
                logger.error(f"[ProxyChecker] IP API error response: {data.get('message')}")
                return False, {"error": data.get("message", "IP API Error")}, latency

        except Exception as e:
            latency = round((time.time() - start_time) * 1000, 2)
            logger.error(f"[ProxyChecker] Native SOCKS5 check exception for {host}:{port} in {latency}ms: {e}")
            return False, {"error": f"SOCKS5 Error: {e}"}, latency

    @classmethod
    async def check_proxy(cls, proxy_cfg: Dict) -> Tuple[bool, Dict, float]:
        """
        Validates proxy connection and fetches IP metadata.
        Returns (success_flag, ip_info_dict, latency_ms).
        """
        if not proxy_cfg.get("enabled") or not proxy_cfg.get("host"):
            return False, {"error": "Proxy disabled or empty host"}, 0.0

        host = str(proxy_cfg.get("host", "")).strip()
        port = int(proxy_cfg.get("port", 8080))
        user = str(proxy_cfg.get("username", "")).strip()
        p_type = str(proxy_cfg.get("type", "http")).lower()

        logger.info(f"[ProxyChecker] Starting proxy check for {p_type}://{host}:{port} (auth={'YES' if user else 'NO'})...")

        if p_type in ["socks5", "socks5h"]:
            try:
                from aiohttp_socks import ProxyConnector
                proxy_url = cls.build_proxy_url(proxy_cfg)
                connector = ProxyConnector.from_url(proxy_url, ssl=False)
                start_time = time.time()
                target_url = "http://ip-api.com/json/?fields=status,message,country,countryCode,region,regionName,city,zip,lat,lon,timezone,isp,org,as,query"
                async with aiohttp.ClientSession(connector=connector) as session:
                    async with session.get(target_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                        latency = round((time.time() - start_time) * 1000, 2)
                        if resp.status == 200:
                            data = await resp.json()
                            if data.get("status") == "success":
                                info = {
                                    "ip": data.get("query", ""),
                                    "country": data.get("country", ""),
                                    "country_code": data.get("countryCode", ""),
                                    "city": data.get("city", ""),
                                    "timezone": data.get("timezone", "UTC"),
                                    "lat": data.get("lat", 0.0),
                                    "lon": data.get("lon", 0.0),
                                    "isp": data.get("isp", "")
                                }
                                logger.info(f"[ProxyChecker] SOCKS5 check success for {host}:{port} -> IP: {info['ip']} ({info['country']}) in {latency}ms")
                                return True, info, latency
                            else:
                                logger.error(f"[ProxyChecker] SOCKS5 IP API error: {data.get('message')}")
                                return False, {"error": data.get("message", "IP API Error")}, latency
                        else:
                            logger.error(f"[ProxyChecker] SOCKS5 HTTP response status {resp.status}")
                            return False, {"error": f"HTTP {resp.status}"}, latency
            except ImportError:
                return await cls._check_socks5_native(proxy_cfg)
            except Exception as e:
                logger.warning(f"[ProxyChecker] aiohttp_socks check failed ({e}), falling back to native SOCKS5 check...")
                return await cls._check_socks5_native(proxy_cfg)

        # Standard HTTP/HTTPS Proxy validation (with BoringSSL TLS Impersonation if available)
        proxy_url = cls.build_proxy_url(proxy_cfg)
        target_url = "http://ip-api.com/json/?fields=status,message,country,countryCode,region,regionName,city,zip,lat,lon,timezone,isp,org,as,query"

        try:
            from engine.tls_impersonate import TLSImpersonate
            if TLSImpersonate.is_boringssl_available():
                start_time = time.time()
                session = TLSImpersonate.create_boringssl_session(preset_key="chrome_131_win11", proxy_url=proxy_url, timeout=10.0)
                if session:
                    async with session:
                        resp = await session.get(target_url)
                        latency = round((time.time() - start_time) * 1000, 2)
                        if resp.status_code == 200:
                            data = resp.json()
                            if data.get("status") == "success":
                                info = {
                                    "ip": data.get("query", ""),
                                    "country": data.get("country", ""),
                                    "country_code": data.get("countryCode", ""),
                                    "city": data.get("city", ""),
                                    "timezone": data.get("timezone", "UTC"),
                                    "lat": data.get("lat", 0.0),
                                    "lon": data.get("lon", 0.0),
                                    "isp": data.get("isp", "")
                                }
                                logger.info(f"[ProxyChecker] BoringSSL check success for {host}:{port} -> IP: {info['ip']} ({info['country']}) in {latency}ms")
                                return True, info, latency
        except Exception as e:
            logger.debug(f"[ProxyChecker] BoringSSL check note ({e}), falling back to standard aiohttp connector...")

        start_time = time.time()
        # Use ssl=True (default) for direct connections — we are connecting directly
        # to ip-api.com, not through a proxy tunnel, so cert verification is appropriate.
        connector = aiohttp.TCPConnector(ssl=True)
        try:
            async with aiohttp.ClientSession(connector=connector) as session:
                req_kwargs: Dict[str, Any] = {"timeout": aiohttp.ClientTimeout(total=10)}
                if proxy_url:
                    req_kwargs["proxy"] = proxy_url

                async with session.get(target_url, **req_kwargs) as resp:
                    latency = round((time.time() - start_time) * 1000, 2)
                    if resp.status == 200:
                        data = await resp.json()
                        if data.get("status") == "success":
                            info = {
                                "ip": data.get("query", ""),
                                "country": data.get("country", ""),
                                "country_code": data.get("countryCode", ""),
                                "city": data.get("city", ""),
                                "timezone": data.get("timezone", "UTC"),
                                "lat": data.get("lat", 0.0),
                                "lon": data.get("lon", 0.0),
                                "isp": data.get("isp", "")
                            }
                            logger.info(f"[ProxyChecker] HTTP check success for {host}:{port} -> IP: {info['ip']} ({info['country']}) in {latency}ms")
                            return True, info, latency
                        else:
                            logger.error(f"[ProxyChecker] HTTP IP API error: {data.get('message')}")
                            return False, {"error": data.get("message", "IP API Error")}, latency
                    else:
                        logger.error(f"[ProxyChecker] HTTP Proxy returned status {resp.status}")
                        return False, {"error": f"HTTP {resp.status}"}, latency

        except Exception as e:
            latency = round((time.time() - start_time) * 1000, 2)
            logger.error(f"[ProxyChecker] HTTP Proxy check exception for {host}:{port} in {latency}ms: {e}")
            return False, {"error": str(e)}, latency


