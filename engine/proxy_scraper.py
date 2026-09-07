import asyncio
import aiohttp
import re
import time
import logging
from typing import List, Dict, Optional, Callable, Tuple

logger = logging.getLogger("ProxyScraper")

DEFAULT_PROXY_SOURCES = {
    "http": [
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/http.txt",
        "https://raw.githubusercontent.com/sunny9577/proxy-scraper/master/generated/http_proxies.txt",
        "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt",
        "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000&country=all"
    ],
    "socks4": [
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks4.txt",
        "https://raw.githubusercontent.com/roosterkid/openproxylist/main/SOCKS4_RAW.txt",
        "https://api.proxyscrape.com/v2/?request=getproxies&protocol=socks4&timeout=10000&country=all"
    ],
    "socks5": [
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/socks5.txt",
        "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt",
        "https://raw.githubusercontent.com/roosterkid/openproxylist/main/SOCKS5_RAW.txt",
        "https://api.proxyscrape.com/v2/?request=getproxies&protocol=socks5&timeout=10000&country=all"
    ]
}

IP_PORT_REGEX = re.compile(r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}:[0-9]{1,5}\b")

class ProxyScraperEngine:
    """High-Performance Async Proxy Scraper & Multi-Protocol Checker."""

    def __init__(self, sources: Optional[Dict[str, List[str]]] = None):
        self.sources = sources or DEFAULT_PROXY_SOURCES
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    async def fetch_source_url(self, session: aiohttp.ClientSession, url: str) -> str:
        """Fetches raw text content from a given proxy list URL."""
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as response:
                if response.status == 200:
                    return await response.text(errors="ignore")
        except Exception as e:
            logger.warning(f"Could not fetch proxy source '{url}': {e}")
        return ""

    async def scrape_proxies(
        self,
        protocols: Optional[List[str]] = None,
        protocol: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """Scrapes and parses proxies for specified protocols (default: http, socks4, socks5)."""
        self._is_cancelled = False
        if protocol and not protocols:
            target_protocols = [protocol]
        elif protocols:
            target_protocols = protocols
        else:
            target_protocols = ["http", "socks4", "socks5"]
        scraped_results: List[Dict] = []
        seen = set()

        async with aiohttp.ClientSession() as session:
            tasks = []
            for proto in target_protocols:
                proto_clean = proto.lower().strip()
                urls = self.sources.get(proto_clean, [])
                for url in urls:
                    tasks.append((proto_clean, self.fetch_source_url(session, url)))

            results = await asyncio.gather(*[t[1] for t in tasks], return_exceptions=True)

            for (proto, _), text in zip(tasks, results):
                if self._is_cancelled:
                    break
                if isinstance(text, str) and text:
                    matches = IP_PORT_REGEX.findall(text)
                    for match in matches:
                        parts = match.split(":")
                        host = parts[0].strip()
                        try:
                            port = int(parts[1])
                        except ValueError:
                            continue

                        # Validate IP format basics
                        octets = host.split(".")
                        if len(octets) != 4 or not all(o.isdigit() and 0 <= int(o) <= 255 for o in octets):
                            continue
                        if not (1 <= port <= 65535):
                            continue

                        key = f"{proto}://{host}:{port}"
                        if key not in seen:
                            seen.add(key)
                            scraped_results.append({
                                "host": host,
                                "port": port,
                                "type": proto,
                                "status": "Untested",
                                "latency_ms": -1.0,
                                "country": "Unknown",
                                "country_code": "",
                                "city": "",
                                "isp": "",
                                "anonymity": "Unknown",
                                "is_working": False
                            })

        if limit and limit > 0:
            scraped_results = scraped_results[:limit]
        logger.info(f"Scraped {len(scraped_results)} unique proxies across protocols: {target_protocols}")
        return scraped_results

    @staticmethod
    async def check_single_proxy(proxy_item: Dict, timeout: float = 6.0) -> Dict:
        """Tests connectivity, latency, geolocation, and anonymity level for a single proxy."""
        start_time = time.time()
        host = proxy_item.get("host", "").strip()
        port = int(proxy_item.get("port", 8080))
        p_type = proxy_item.get("type", "http").lower()
        scheme = "socks5" if p_type in ["socks5", "socks5h"] else ("socks4" if p_type == "socks4" else "http")

        proxy_url = f"{scheme}://{host}:{port}"
        result = dict(proxy_item)
        result["is_working"] = False
        result["status"] = "Offline "

        # 1. Test Proxy Connectivity & Geolocation via ip-api.com
        test_url = "http://ip-api.com/json/?fields=status,message,country,countryCode,city,isp,query"

        try:
            if scheme == "socks5":
                from engine.proxy_checker import ProxyChecker
                success, info, latency = await ProxyChecker._check_socks5_native(
                    {"host": host, "port": port, "type": "socks5"}, timeout=int(timeout)
                )
                if success:
                    result["is_working"] = True
                    result["status"] = "✓ Active"
                    result["latency_ms"] = latency
                    result["country"] = info.get("country", "Unknown")
                    result["country_code"] = info.get("country_code", "")
                    result["city"] = info.get("city", "")
                    result["isp"] = info.get("isp", "")
                    result["anonymity"] = "Anonymous"
                    return result
                else:
                    return result

            # For HTTP / SOCKS4 via aiohttp
            conn = aiohttp.TCPConnector(ssl=False)
            async with aiohttp.ClientSession(connector=conn) as session:
                async with session.get(test_url, proxy=proxy_url, timeout=aiohttp.ClientTimeout(total=timeout)) as response:
                    latency = round((time.time() - start_time) * 1000.0, 1)
                    if response.status == 200:
                        data = await response.json()
                        if data.get("status") == "success":
                            result["is_working"] = True
                            result["status"] = "✓ Active"
                            result["latency_ms"] = latency
                            result["country"] = data.get("country", "Unknown")
                            result["country_code"] = data.get("countryCode", "")
                            result["city"] = data.get("city", "")
                            result["isp"] = data.get("isp", "")
                            
                            # Anonymity check heuristic
                            returned_ip = data.get("query", "")
                            if returned_ip == host:
                                result["anonymity"] = "Elite"
                            elif returned_ip:
                                result["anonymity"] = "Anonymous"
                            else:
                                result["anonymity"] = "Transparent"
                            return result

        except Exception as e:
            result["latency_ms"] = -1.0
            result["status"] = f"Offline  ({type(e).__name__})"

        return result

    async def batch_check_proxies(
        self,
        proxy_list: List[Dict],
        concurrency: int = 50,
        timeout: float = 6.0,
        progress_callback: Optional[Callable[[int, int, Dict], None]] = None
    ) -> List[Dict]:
        """Checks a list of proxies concurrently using semaphore rate limiting."""
        self._is_cancelled = False
        semaphore = asyncio.Semaphore(concurrency)
        total = len(proxy_list)
        checked_count = 0
        results: List[Dict] = []

        async def worker(item: Dict):
            nonlocal checked_count
            if self._is_cancelled:
                return item

            async with semaphore:
                if self._is_cancelled:
                    return item
                res = await self.check_single_proxy(item, timeout=timeout)
                checked_count += 1
                if progress_callback:
                    try:
                        progress_callback(checked_count, total, res)
                    except Exception:
                        pass
                return res

        tasks = [asyncio.create_task(worker(p)) for p in proxy_list]
        try:
            for completed_task in asyncio.as_completed(tasks):
                if self._is_cancelled:
                    break
                try:
                    res = await completed_task
                    results.append(res)
                except Exception:
                    pass
        finally:
            if self._is_cancelled:
                for t in tasks:
                    if not t.done():
                        t.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)

        # Sort working proxies by latency (lowest ms first)
        def sort_key(p):
            if p.get("is_working"):
                lat = p.get("latency_ms", 999999.0)
                return (0, lat if lat > 0 else 999999.0)
            return (1, 999999.0)

        results.sort(key=sort_key)
        return results
