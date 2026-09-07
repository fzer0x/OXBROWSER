import unittest
import asyncio
from aiohttp.test_utils import AioHTTPTestCase, unittest_run_loop
from aiohttp import web
from storage.profile_manager import ProfileManager
from storage.proxy_manager import ProxyManager
from engine.browser import BrowserLauncher
from api.server import RestApiServer

class TestRestApiAndSSE(AioHTTPTestCase):
    async def get_application(self):
        self.pm = ProfileManager()
        self.proxy_mgr = ProxyManager()
        self.launcher = BrowserLauncher(self.pm)
        self.server = RestApiServer(self.pm, self.launcher, proxy_manager=self.proxy_mgr)
        return self.server.app

    @unittest_run_loop
    async def test_health_endpoint(self):
        resp = await self.client.get('/api/v1/health')
        self.assertEqual(resp.status, 200)
        data = await resp.json()
        self.assertEqual(data.get("status"), "healthy")
        self.assertIn("active_profiles", data)

    @unittest_run_loop
    async def test_spec_endpoint(self):
        resp = await self.client.get('/api/v1/spec')
        self.assertEqual(resp.status, 200)
        data = await resp.json()
        self.assertEqual(data.get("openapi"), "3.0.0")
        self.assertIn("/api/v1/events", data.get("paths", {}))

    @unittest_run_loop
    async def test_index_endpoint(self):
        resp = await self.client.get('/')
        self.assertEqual(resp.status, 200)
        data = await resp.json()
        self.assertEqual(data.get("status"), "running")

if __name__ == "__main__":
    unittest.main()
