import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import tempfile
from unittest.mock import AsyncMock, MagicMock
from engine.browser import BrowserLauncher
from storage.profile_manager import ProfileManager

class MockBrowserContext:
    def __init__(self):
        self.injected_cookies = []

    async def add_cookies(self, cookies):
        self.injected_cookies.extend(cookies)

def test_cookie_sanitization_and_injection():
    import asyncio
    with tempfile.TemporaryDirectory() as tmpdir:
        pm = ProfileManager(profiles_dir=tmpdir)
        profile_data = {
            "name": "Cookie Test Profile",
            "browser_engine": "camoufox",
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "stealth": {"fingerprint_protection": True}
        }
        created = pm.create_profile(profile_data)
        pid = created["id"] if isinstance(created, dict) else created
        prof_path = pm.get_profile_path(pid)

        # Create cookies.json with diverse cookie formats (Netscape-style, JSON, microsecond expiry, lax sameSite)
        test_cookies = [
            {
                "name": "session_id",
                "value": "abc123xyz789",
                "domain": ".google.com",
                "path": "/",
                "expiry": 1893456000000,  # Milliseconds timestamp
                "httpOnly": True,
                "secure": True,
                "sameSite": "lax"
            },
            {
                "name": "tracking_token",
                "value": "token_val_456",
                "domain": "example.com",
                "path": "/api",
                "expires": 1893456000,     # Seconds timestamp
                "httpOnly": False,
                "secure": False,
                "sameSite": "STRICT"
            },
            {
                "name": "legacy_netscape_cookie",
                "value": "val999",
                "url": "https://service.org/login",
                "httponly": True,
                "secure": True
            }
        ]

        cookie_json_file = os.path.join(prof_path, "cookies.json")
        with open(cookie_json_file, "w", encoding="utf-8") as f:
            json.dump(test_cookies, f)

        launcher = BrowserLauncher(profile_manager=pm)
        mock_ctx = MockBrowserContext()

        async def run_test():
            count = await launcher._inject_cookies_for_profile(pid, mock_ctx)
            return count

        injected_count = asyncio.run(run_test())

        assert injected_count == 3, f"Expected 3 cookies injected, got {injected_count}"
        assert len(mock_ctx.injected_cookies) == 3

        # Verify field normalization
        c1 = next(c for c in mock_ctx.injected_cookies if c["name"] == "session_id")
        assert c1["domain"] == ".google.com"
        assert c1["expires"] == 1893456000  # Converted from ms to s
        assert c1["httpOnly"] is True
        assert c1["secure"] is True
        assert c1["sameSite"] == "Lax"

        c2 = next(c for c in mock_ctx.injected_cookies if c["name"] == "tracking_token")
        assert c2["sameSite"] == "Strict"
        assert c2["path"] == "/api"

        c3 = next(c for c in mock_ctx.injected_cookies if c["name"] == "legacy_netscape_cookie")
        assert c3["url"] == "https://service.org/login"
        assert c3["httpOnly"] is True

        print(" All cookies parsed, sanitized, normalized and injected successfully!")

if __name__ == "__main__":
    test_cookie_sanitization_and_injection()
    print("ALL COOKIE INJECTION TESTS PASSED! ⫸")
