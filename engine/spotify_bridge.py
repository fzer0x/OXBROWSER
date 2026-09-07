"""
Spotify Bridge & Headless Automation Engine for SoxBot.
Provides token extraction from Camoufox cookies, Web API interaction,
and headless playback telemetry simulation over profile proxies without DRM fingerprint risk.
"""

import json
import logging
import urllib.parse
from typing import Dict, Any, Optional, List, Tuple
import aiohttp

logger = logging.getLogger("SpotifyBridge")

class SpotifyBridge:
    """
    Manages lightweight Spotify Web API communication and session handling
    decoupled from the browser UI to avoid DRM tracking risks.
    """

    def __init__(self, profile_id: str, proxy_url: Optional[str] = None):
        self.profile_id = profile_id
        self.proxy_url = proxy_url
        self.access_token: Optional[str] = None
        self.token_expiry: float = 0.0
        self.session_cookies: Dict[str, str] = {}
        self.user_data: Dict[str, Any] = {}

    def load_cookies_from_profile(self, profile: Dict[str, Any]) -> bool:
        """Extracts sp_dc and sp_key cookies from profile cookie storage."""
        cookies = profile.get("cookies", [])
        extracted = {}
        for c in cookies:
            domain = c.get("domain", "")
            name = c.get("name", "")
            value = c.get("value", "")
            if "spotify.com" in domain and name in ["sp_dc", "sp_key", "sp_t", "sp_m", "sp_landing"]:
                extracted[name] = value

        if "sp_dc" in extracted:
            self.session_cookies = extracted
            logger.info(f"[SpotifyBridge] Loaded Spotify session credentials (sp_dc) for profile '{self.profile_id}'")
            return True
        return False

    def set_session_cookie(self, sp_dc: str, sp_key: Optional[str] = None):
        """Directly sets session cookies."""
        self.session_cookies["sp_dc"] = sp_dc.strip()
        if sp_key:
            self.session_cookies["sp_key"] = sp_key.strip()

    async def get_access_token(self, timeout_sec: int = 15) -> Optional[str]:
        """
        Exchanges session cookies (sp_dc) for a bearer OAuth access token
        from Spotify's web player authorization endpoint.
        """
        if not self.session_cookies.get("sp_dc"):
            logger.warning(f"[SpotifyBridge] No sp_dc session cookie available for profile '{self.profile_id}'")
            return None

        cookie_header = "; ".join([f"{k}={v}" for k, v in self.session_cookies.items()])
        url = "https://open.spotify.com/get_access_token?reason=transport&productType=web_player"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:135.0) Gecko/20100101 Firefox/135.0",
            "Accept": "application/json",
            "Cookie": cookie_header,
            "Referer": "https://open.spotify.com/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin"
        }

        try:
            connector = aiohttp.TCPConnector(ssl=False)
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(url, headers=headers, proxy=self.proxy_url, timeout=aiohttp.ClientTimeout(total=timeout_sec)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        token = data.get("accessToken")
                        if token:
                            self.access_token = token
                            logger.info(f"[SpotifyBridge] Successfully retrieved Spotify Access Token for profile '{self.profile_id}'")
                            return token
                    else:
                        text = await resp.text()
                        logger.warning(f"[SpotifyBridge] Failed to get access token (HTTP {resp.status}): {text[:200]}")
        except Exception as e:
            logger.error(f"[SpotifyBridge] Error requesting Spotify access token: {e}")

        return None

    async def get_current_user_profile(self) -> Optional[Dict[str, Any]]:
        """Fetches profile info of authenticated user."""
        if not self.access_token:
            await self.get_access_token()
        if not self.access_token:
            return None

        url = "https://api.spotify.com/v1/me"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:135.0) Gecko/20100101 Firefox/135.0"
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, proxy=self.proxy_url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        self.user_data = data
                        return data
                    elif resp.status == 401:
                        # Refresh token and retry once
                        await self.get_access_token()
                        if self.access_token:
                            headers["Authorization"] = f"Bearer {self.access_token}"
                            async with session.get(url, headers=headers, proxy=self.proxy_url) as retry_resp:
                                if retry_resp.status == 200:
                                    return await retry_resp.json()
        except Exception as e:
            logger.error(f"[SpotifyBridge] Error fetching user profile: {e}")
        return None

    async def get_user_playlists(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Fetches playlists for current authenticated user."""
        if not self.access_token:
            await self.get_access_token()
        if not self.access_token:
            return []

        url = f"https://api.spotify.com/v1/me/playlists?limit={limit}"
        headers = {"Authorization": f"Bearer {self.access_token}"}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, proxy=self.proxy_url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("items", [])
        except Exception as e:
            logger.error(f"[SpotifyBridge] Error fetching playlists: {e}")
        return []

    async def follow_playlist(self, playlist_id: str, public: bool = True) -> bool:
        """Follows / saves a playlist to user library."""
        if not self.access_token:
            await self.get_access_token()
        if not self.access_token:
            return False

        url = f"https://api.spotify.com/v1/playlists/{playlist_id}/followers"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        payload = {"public": public}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.put(url, headers=headers, json=payload, proxy=self.proxy_url) as resp:
                    return resp.status in [200, 201, 204]
        except Exception as e:
            logger.error(f"[SpotifyBridge] Error following playlist {playlist_id}: {e}")
            return False

    async def follow_artists_or_users(self, ids: List[str], target_type: str = "artist") -> bool:
        """Follows artists or users."""
        if not self.access_token or not ids:
            await self.get_access_token()
        if not self.access_token:
            return False

        ids_param = ",".join(ids)
        url = f"https://api.spotify.com/v1/me/following?type={target_type}&ids={ids_param}"
        headers = {"Authorization": f"Bearer {self.access_token}"}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.put(url, headers=headers, proxy=self.proxy_url) as resp:
                    return resp.status in [200, 204]
        except Exception as e:
            logger.error(f"[SpotifyBridge] Error following {target_type}: {e}")
            return False

    async def search(self, query: str, search_type: str = "track,artist,album", limit: int = 10) -> Dict[str, Any]:
        """Searches Spotify catalog."""
        if not self.access_token:
            await self.get_access_token()
        if not self.access_token:
            return {}

        params = urllib.parse.urlencode({"q": query, "type": search_type, "limit": limit})
        url = f"https://api.spotify.com/v1/search?{params}"
        headers = {"Authorization": f"Bearer {self.access_token}"}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, proxy=self.proxy_url) as resp:
                    if resp.status == 200:
                        return await resp.json()
        except Exception as e:
            logger.error(f"[SpotifyBridge] Error searching catalog: {e}")
        return {}
