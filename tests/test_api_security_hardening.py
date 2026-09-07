import unittest
import asyncio
import hmac
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
import config
from storage.profile_manager import ProfileManager
from storage.proxy_manager import ProxyManager
from engine.browser import BrowserLauncher
from api.server import RestApiServer, _ACTIVE_SESSIONS, _ACTIVE_REFRESH_TOKENS

class TestApiSecurityHardening(AioHTTPTestCase):

    async def get_application(self):
        pm = ProfileManager()
        launcher = BrowserLauncher(pm)
        proxy_mgr = ProxyManager()
        self.api_server = RestApiServer(pm, launcher, proxy_mgr, host="127.0.0.1", port=59999)
        return self.api_server.app

    @unittest_run_loop
    async def test_strict_nonce_based_csp_headers(self):
        """1. CSP: Verify that response contains nonce-based CSP without unsafe-inline or unsafe-eval."""
        resp = await self.client.get('/api/v1/health')
        self.assertEqual(resp.status, 200)

        csp = resp.headers.get("Content-Security-Policy", "")
        self.assertTrue(len(csp) > 0)
        self.assertIn("default-src 'self'", csp)
        self.assertIn("script-src 'self' 'nonce-", csp)
        self.assertIn("style-src 'self' 'nonce-", csp)
        self.assertNotIn("unsafe-inline", csp)
        self.assertNotIn("unsafe-eval", csp)

        # Verify additional OWASP security headers
        self.assertEqual(resp.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(resp.headers.get("X-Frame-Options"), "DENY")
        self.assertIn("max-age=63072000", resp.headers.get("Strict-Transport-Security", ""))
        self.assertEqual(resp.headers.get("Referrer-Policy"), "strict-origin-when-cross-origin")

    @unittest_run_loop
    async def test_httponly_secure_token_architecture(self):
        """2. Token: Verify login issues HttpOnly, Secure, SameSite=Strict cookies (0 localStorage exposure)."""
        expected_token = getattr(config, "API_BEARER_TOKEN", "").strip()
        login_data = {"token": expected_token} if expected_token else {}
        resp = await self.client.post('/api/v1/auth/login', json=login_data)
        self.assertEqual(resp.status, 200)

        # Check Set-Cookie headers
        cookies = resp.cookies
        self.assertIn("auth_token", cookies)
        self.assertIn("refresh_token", cookies)

        auth_cookie = cookies["auth_token"]
        self.assertTrue(auth_cookie["httponly"])
        self.assertTrue(auth_cookie["secure"])
        self.assertEqual(auth_cookie["samesite"], "Strict")
        self.assertEqual(auth_cookie["path"], "/api/v1")

        refresh_cookie = cookies["refresh_token"]
        self.assertTrue(refresh_cookie["httponly"])
        self.assertTrue(refresh_cookie["secure"])
        self.assertEqual(refresh_cookie["samesite"], "Strict")
        self.assertEqual(refresh_cookie["path"], "/api/v1/auth")

        # Test authenticated request via cookie
        auth_val = auth_cookie.value
        prof_resp = await self.client.get('/api/v1/profiles', cookies={"auth_token": auth_val})
        self.assertEqual(prof_resp.status, 200)

    @unittest_run_loop
    async def test_token_refresh_and_rotation(self):
        """3. Token Rotation: Verify refresh rotates tokens securely."""
        expected_token = getattr(config, "API_BEARER_TOKEN", "").strip()
        login_data = {"token": expected_token} if expected_token else {}
        resp = await self.client.post('/api/v1/auth/login', json=login_data)
        self.assertEqual(resp.status, 200)

        refresh_val = resp.cookies["refresh_token"].value
        refresh_resp = await self.client.post('/api/v1/auth/refresh', cookies={"refresh_token": refresh_val})
        self.assertEqual(refresh_resp.status, 200)

        # Old refresh token must be invalidated
        self.assertNotIn(refresh_val, _ACTIVE_REFRESH_TOKENS)

        # New tokens issued
        new_refresh_val = refresh_resp.cookies["refresh_token"].value
        self.assertIn(new_refresh_val, _ACTIVE_REFRESH_TOKENS)
        self.assertNotEqual(refresh_val, new_refresh_val)

    @unittest_run_loop
    async def test_websocket_cswsh_and_host_protection(self):
        """4. WebSocket: Verify CSWSH protection blocks untrusted origins."""
        expected_token = getattr(config, "API_BEARER_TOKEN", "").strip()

        # 4a. Attack simulation: Evil Origin
        evil_resp = await self.client.get(
            '/api/v1/ws',
            headers={
                "Origin": "http://evil-attacker.com",
                "Authorization": f"Bearer {expected_token}"
            }
        )
        self.assertEqual(evil_resp.status, 403)
        text = await evil_resp.text()
        self.assertIn("Cross-Site WebSocket Hijacking", text)

        # 4b. Attack simulation: Spoofed Host header
        fake_host_resp = await self.client.get(
            '/api/v1/ws',
            headers={
                "Host": "malicious-domain.xyz",
                "Authorization": f"Bearer {expected_token}"
            }
        )
        self.assertEqual(fake_host_resp.status, 403)

        # 4c. Valid handshake with trusted Origin
        ws = await self.client.ws_connect(
            '/api/v1/ws',
            headers={
                "Origin": "http://127.0.0.1",
                "Authorization": f"Bearer {expected_token}"
            }
        )
        await ws.send_json({"cmd": "ping"})
        msg = await ws.receive_json()
        self.assertEqual(msg.get("event"), "connected")
        await ws.close()

if __name__ == "__main__":
    unittest.main()
