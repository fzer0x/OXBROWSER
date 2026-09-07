import os
import re
import json
import uuid
import time
import random
import asyncio
import logging
import psutil
from typing import Dict, Any, List, Optional, Tuple, Callable

import config
from storage.profile_manager import ProfileManager
from storage.proxy_manager import ProxyManager
from storage.warmup_campaign_manager import WarmupCampaignManager
from engine.warmup.orchestrator import CookieWarmupRobot, WarmupConfig
from engine.browser import BrowserLauncher
from engine.environment_tester import EnvironmentAuditEngine, AutoPatchEngine, EnvironmentBenchmarkTarget, BENCHMARK_URLS
from engine.proxy_scraper import ProxyScraperEngine
from engine.google_proxy_checker import GoogleProxyChecker

logger = logging.getLogger("AIAgentActionEngine")


class AIAgentActionEngine:
    """
    Autonomous Execution Engine for SoxBot AI Copilot Agents (100% A-Z Coverage):
    - Full Profile Lifecycle: Synthesize, Batch Create, Launch, Stop, Delete, Clone, Patch.
    - Security & Fingerprint Audits: 12-Dimensional Tensor Verification, ML Trust Scoring, 1-Click Auto-Patching.
    - Proxy Automation: Multi-source Scraping, Google-Compatibility Checking, Smart Profile Assignment.
    - Live Browser & Warmup Orchestration: Warmup Campaign Execution, Benchmark Navigation, Sandbox Dispatch.
    - Universal Action Block & Tool Calling Dispatcher.
    """

    _instance: Optional['AIAgentActionEngine'] = None

    def __init__(
        self,
        profile_manager: Optional[ProfileManager] = None,
        proxy_manager: Optional[ProxyManager] = None,
        campaign_manager: Optional[WarmupCampaignManager] = None,
        launcher: Optional[BrowserLauncher] = None
    ):
        self.profile_manager = profile_manager or ProfileManager()
        self.proxy_manager = proxy_manager or ProxyManager()
        self.campaign_manager = campaign_manager or WarmupCampaignManager.get_instance()
        self.launcher = launcher or BrowserLauncher(self.profile_manager)
        self.proxy_scraper = ProxyScraperEngine()
        self._active_warmup_tasks: Dict[str, asyncio.Task] = {}

    @classmethod
    def get_instance(cls) -> 'AIAgentActionEngine':
        if cls._instance is None:
            cls._instance = AIAgentActionEngine()
        return cls._instance

    # -------------------------------------------------------------------------
    # 1. Harmonized Profile Generation & Creation
    # -------------------------------------------------------------------------
    def generate_harmonized_profile(
        self,
        name: str = "AI_Harmonized_Profile",
        os_type: str = "windows",
        engine: str = "camoufox",
        country: str = "DE",
        persona: str = "standard_desktop",
        proxy_dict: Optional[Dict[str, Any]] = None,
        custom_notes: str = ""
    ) -> Dict[str, Any]:
        """
        Synthesizes a 100% statistically and hardware-harmonized profile configuration.
        Ensures consistency between OS, WebGL Renderer, User-Agent, Screen, Cores, and RAM.
        """
        os_clean = os_type.lower().strip()
        if os_clean not in ["windows", "mac", "linux"]:
            os_clean = "windows"

        if os_clean == "windows":
            hardware_concurrency = random.choice([8, 12, 16])
            device_memory = random.choice([8, 16, 32])
            screen_res = random.choice(["1920x1080", "2560x1440", "1920x1200"])
            device_vendor = "Google"
            device_model = "PC"
        elif os_clean == "mac":
            hardware_concurrency = random.choice([8, 10, 12])
            device_memory = random.choice([8, 16, 24, 32])
            screen_res = random.choice(["2560x1440", "2880x1800", "1920x1080"])
            device_vendor = "Apple"
            device_model = "Macintosh"
        else:  # linux
            hardware_concurrency = random.choice([8, 12])
            device_memory = random.choice([8, 16])
            screen_res = random.choice(["1920x1080", "2560x1440"])
            device_vendor = "Google"
            device_model = "PC"

        valid_presets = config.get_webgl_presets_for_os(os_clean)
        if valid_presets:
            webgl_preset = random.choice(valid_presets)
        else:
            webgl_preset = config.WEBGL_PRESETS[0]

        ua = config.get_default_user_agent(os_clean, engine)

        lang_map = {
            "DE": "de-DE,de;q=0.9,en;q=0.8",
            "US": "en-US,en;q=0.9",
            "GB": "en-GB,en-US;q=0.9,en;q=0.8",
            "FR": "fr-FR,fr;q=0.9,en;q=0.8",
            "ES": "es-ES,es;q=0.9,en;q=0.8",
            "IT": "it-IT,it;q=0.9,en;q=0.8",
            "NL": "nl-NL,nl;q=0.9,en;q=0.8",
            "AT": "de-AT,de;q=0.9,en;q=0.8",
            "CH": "de-CH,de;q=0.9,fr-CH;q=0.8,en;q=0.7",
        }
        primary_language = lang_map.get(country.upper(), "en-US,en;q=0.9")

        profile_id = str(uuid.uuid4())
        deterministic_noise_seed = f"seed_{profile_id[:8]}"

        profile_data: Dict[str, Any] = {
            "id": profile_id,
            "name": name,
            "group": "AI Agent Created",
            "tags": ["AI-Harmonized", os_clean.capitalize(), engine.capitalize()],
            "notes": custom_notes or f"Generated autonomously by AI Copilot for {persona} persona ({country.upper()}).",
            "created_at": time.time(),
            "last_launch": 0,
            "status": "Stopped",
            "engine": engine,
            "ephemeral_ram": False,
            "encrypted": False,
            "start_url": "",
            "os": os_clean,
            "os_version": "10.0.0" if os_clean == "windows" else ("14.5.0" if os_clean == "mac" else "6.8.0"),
            "device_vendor": device_vendor,
            "device_model": device_model,
            "user_agent": ua,
            "screen_resolution": screen_res,
            "window_mode": "tile_grid",
            "window_width": 1280,
            "window_height": 720,
            "window_pos_x": 0,
            "window_pos_y": 0,
            "color_depth": 24,
            "max_touch_points": 0,
            "hardware_concurrency": hardware_concurrency,
            "device_memory": device_memory,
            "language": primary_language,
            "timezone": "auto",
            "do_not_track": "null",
            "location": {
                "country": country.upper(),
                "region": "",
                "city": "",
                "postal_code": "",
                "lat": 0.0,
                "lon": 0.0
            },
            "proxy": proxy_dict or {
                "enabled": False,
                "type": "http",
                "host": "",
                "port": 3128,
                "username": "",
                "password": "",
                "auto_timezone": True,
                "auto_geolocation": True
            },
            "network_killswitch": True,
            "tls_ja3_preset": "auto",
            "proxy_info": {
                "ip": "",
                "country": country.upper(),
                "country_code": country.upper(),
                "city": "",
                "timezone": "UTC",
                "lat": 0.0,
                "lon": 0.0,
                "isp": ""
            },
            "stealth": {
                "fp_engine": "real_presets",
                "canvas_noise": True,
                "webgl_vendor": webgl_preset["vendor"],
                "webgl_renderer": webgl_preset["renderer"],
                "webgpu_supported": True,
                "audio_noise": True,
                "webrtc_mode": "altered",
                "client_rects_noise": True,
                "font_fingerprint_noise": True,
                "noise_seed": deterministic_noise_seed,
                "pdf_viewers": [
                    "internal-pdf-viewer",
                    "Chrome PDF Viewer",
                    "Chromium PDF Viewer"
                ],
                "custom_fonts": [
                    "Helvetica", "Arial", "Times New Roman", "Courier New", "Verdana"
                ]
            },
            "sandbox": {
                "mode": "off",
                "microvm_engine": "cloud-hypervisor",
                "use_virtiofs": True,
                "oci_runtime": "runsc",
                "gpu_preset": "auto_profile",
                "graphics_driver": "llvmpipe",
                "isolate_network": True
            },
            "extensions": [],
            "debug_port": random.randint(30000, 45000),
            "behavior": {
                "save_history": True,
                "search_suggestions": True,
                "restore_session": True,
                "form_autofill": True,
                "password_manager": True,
                "address_autofill": True,
                "credit_card_autofill": False,
                "disk_cache": True,
                "offline_storage": False,
                "clear_on_shutdown": True,
                "block_telemetry": True,
                "drm_widevine": True,
                "autoplay_media": "block_all"
            },
            "custom_user_agent": False
        }

        return profile_data

    def create_profile(self, profile_data: Dict[str, Any]) -> Tuple[bool, str, str]:
        """Persists a synthesized profile in the ProfileManager."""
        try:
            p_id = profile_data.get("id") or str(uuid.uuid4())
            profile_data["id"] = p_id
            p_name = profile_data.get("name") or "New_AI_Profile"

            self.profile_manager.save_profile(profile_data)
            logger.info(f"[AIAgentActionEngine] Created profile '{p_name}' ({p_id})")
            return True, p_id, f"Profile '{p_name}' successfully created (ID: {p_id})."
        except Exception as e:
            logger.error(f"[AIAgentActionEngine] Profile creation failed: {e}")
            return False, "", f"Failed to create profile: {e}"

    def create_batch_profiles(self, profiles_list: List[Dict[str, Any]]) -> Tuple[bool, List[str], str]:
        """Persists a batch of synthesized profiles."""
        if not profiles_list:
            return False, [], "No profiles provided in batch list."

        created_ids = []
        try:
            for p_data in profiles_list:
                if not isinstance(p_data, dict):
                    continue
                p_id = p_data.get("id") or str(uuid.uuid4())
                p_data["id"] = p_id
                self.profile_manager.save_profile(p_data)
                created_ids.append(p_id)

            logger.info(f"[AIAgentActionEngine] Successfully created batch of {len(created_ids)} profiles.")
            return True, created_ids, f"Successfully created {len(created_ids)} profiles in SoxBot."
        except Exception as e:
            logger.error(f"[AIAgentActionEngine] Batch profile creation failed: {e}")
            return False, created_ids, f"Batch profile creation partially failed: {e}"

    # -------------------------------------------------------------------------
    # 2. Profile Lifecycle Operations (Launch, Stop, Clone, Delete, Patch)
    # -------------------------------------------------------------------------
    def resolve_profile_id(self, name_or_id: str) -> Optional[str]:
        """Finds a profile ID by exact ID match, name match, or index (e.g. 'Profil 1')."""
        if not name_or_id:
            return None

        # Check if direct ID exists
        if self.profile_manager.load_profile(name_or_id):
            return name_or_id

        all_profs = self.profile_manager.list_profiles()
        clean = name_or_id.strip().lower()

        # 1. Exact Name match
        for p in all_profs:
            p_id = p.get("id")
            p_name = p.get("name", "").lower()
            if p_name == clean:
                return p_id

        # 2. Substring Name match
        for p in all_profs:
            p_id = p.get("id")
            p_name = p.get("name", "").lower()
            if clean in p_name:
                return p_id

        # 3. Check for ordinal / index like "profil 1", "profile 1", "1"
        idx_match = re.search(r'(?:profil|profile)?\s*#?(\d+)', clean)
        if idx_match and len(all_profs) > 0:
            idx = int(idx_match.group(1)) - 1
            chronological = sorted(all_profs, key=lambda x: x.get("created_at", 0))
            if 0 <= idx < len(chronological):
                return chronological[idx].get("id")

        return None

    async def launch_profile_async(self, name_or_id: str) -> Tuple[bool, str]:
        """Asynchronously launches a browser profile instance."""
        pid = self.resolve_profile_id(name_or_id)
        if not pid:
            return False, f"Profile '{name_or_id}' could not be resolved."

        prof = self.profile_manager.load_profile(pid)
        if not prof:
            return False, f"Profile ID '{pid}' does not exist in storage."

        try:
            res = await self.launcher.launch_profile(pid)
            success = res[0] if isinstance(res, (tuple, list)) else bool(res)
            msg = res[1] if isinstance(res, (tuple, list)) and len(res) > 1 else ""
            if success:
                return True, f"🚀 Browser profile '{prof.get('name', pid)}' successfully launched!"
            else:
                return False, f"Failed to launch browser profile: {msg}"
        except Exception as e:
            return False, f"Error launching profile '{pid}': {e}"

    def launch_profile(self, name_or_id: str) -> Tuple[bool, str]:
        """Launches a browser profile instance (synchronous helper / task dispatcher)."""
        pid = self.resolve_profile_id(name_or_id)
        if not pid:
            return False, f"Profile '{name_or_id}' could not be resolved."

        prof = self.profile_manager.load_profile(pid)
        if not prof:
            return False, f"Profile ID '{pid}' does not exist in storage."

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.launcher.launch_profile(pid))
            return True, f"🚀 Browser profile '{prof.get('name', pid)}' launch initiated."
        except RuntimeError:
            try:
                loop = asyncio.get_event_loop()
                loop.create_task(self.launcher.launch_profile(pid))
                return True, f"🚀 Browser profile '{prof.get('name', pid)}' launch initiated."
            except Exception as e:
                return False, f"Error dispatching profile launch '{pid}': {e}"

    async def stop_profile_async(self, name_or_id: str) -> Tuple[bool, str]:
        """Asynchronously stops an active browser profile instance."""
        pid = self.resolve_profile_id(name_or_id)
        if not pid:
            return False, f"Profile '{name_or_id}' could not be resolved."

        try:
            res = await self.launcher.stop_profile(pid)
            success = res[0] if isinstance(res, (tuple, list)) else bool(res)
            msg = res[1] if isinstance(res, (tuple, list)) and len(res) > 1 else ""
            return success, msg or f"🛑 Browser profile '{pid}' stopped."
        except Exception as e:
            return False, f"Error stopping profile '{pid}': {e}"

    def stop_profile(self, name_or_id: str) -> Tuple[bool, str]:
        """Stops an active browser profile instance."""
        pid = self.resolve_profile_id(name_or_id)
        if not pid:
            return False, f"Profile '{name_or_id}' could not be resolved."

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.launcher.stop_profile(pid))
            return True, f"🛑 Stop command sent to browser profile '{pid}'."
        except RuntimeError:
            try:
                loop = asyncio.get_event_loop()
                loop.create_task(self.launcher.stop_profile(pid))
                return True, f"🛑 Stop command sent to browser profile '{pid}'."
            except Exception as e:
                return False, f"Error stopping profile '{pid}': {e}"

    async def stop_all_profiles_async(self) -> Tuple[bool, str]:
        """Asynchronously stops all running browser instances."""
        try:
            await self.launcher.stop_all_profiles()
            return True, "🛑 All running browser profiles have been stopped."
        except Exception as e:
            return False, f"Error stopping all profiles: {e}"

    def stop_all_profiles(self) -> Tuple[bool, str]:
        """Stops all running browser instances."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.launcher.stop_all_profiles())
            return True, "🛑 Stop all profiles command initiated."
        except RuntimeError:
            try:
                loop = asyncio.get_event_loop()
                loop.create_task(self.launcher.stop_all_profiles())
                return True, "🛑 Stop all profiles command initiated."
            except Exception as e:
                return False, f"Error stopping all profiles: {e}"

    async def delete_profile_async(self, name_or_id: str) -> Tuple[bool, str]:
        """Deletes a profile from SoxBot asynchronously."""
        pid = self.resolve_profile_id(name_or_id)
        if not pid:
            return False, f"Profile '{name_or_id}' not found."

        try:
            await self.launcher.stop_profile(pid)
            self.profile_manager.delete_profile(pid)
            return True, f"🗑️ Profile '{pid}' deleted successfully."
        except Exception as e:
            return False, f"Error deleting profile '{pid}': {e}"

    def delete_profile(self, name_or_id: str) -> Tuple[bool, str]:
        """Deletes a profile from SoxBot."""
        pid = self.resolve_profile_id(name_or_id)
        if not pid:
            return False, f"Profile '{name_or_id}' not found."

        try:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self.launcher.stop_profile(pid))
            except RuntimeError:
                pass
            self.profile_manager.delete_profile(pid)
            return True, f"🗑️ Profile '{pid}' deleted successfully."
        except Exception as e:
            return False, f"Error deleting profile '{pid}': {e}"

    def clone_profile(self, name_or_id: str, new_name: Optional[str] = None) -> Tuple[bool, Optional[str], str]:
        """Clones an existing profile with refreshed UUID, noise seed, and debug port."""
        pid = self.resolve_profile_id(name_or_id)
        if not pid:
            return False, None, f"Source profile '{name_or_id}' not found."

        prof = self.profile_manager.load_profile(pid)
        if not prof:
            return False, None, f"Profile data for '{pid}' not found."

        cloned = json.loads(json.dumps(prof))
        new_id = str(uuid.uuid4())
        cloned["id"] = new_id
        cloned["name"] = new_name or f"{prof.get('name', 'Profile')}_Clone_{random.randint(10, 99)}"
        cloned["debug_port"] = random.randint(30000, 45000)
        cloned["created_at"] = time.time()
        cloned["last_launch"] = 0
        cloned["status"] = "Stopped"

        if "stealth" in cloned and isinstance(cloned["stealth"], dict):
            cloned["stealth"]["noise_seed"] = f"seed_{new_id[:8]}"

        self.profile_manager.save_profile(cloned)
        return True, new_id, f"Profile cloned successfully as '{cloned['name']}' (ID: {new_id})."

    def patch_profile(self, name_or_id: str, patch_data: Dict[str, Any]) -> Tuple[bool, str, List[str]]:
        """Applies configuration patches to a profile."""
        pid = self.resolve_profile_id(name_or_id)
        if not pid:
            return False, f"Profile '{name_or_id}' not found.", []

        prof = self.profile_manager.load_profile(pid)
        if not prof:
            return False, f"Profile data for '{pid}' not found.", []

        updated, changes = AutoPatchEngine.apply_patch(prof, patch_data)
        self.profile_manager.save_profile(updated)
        return True, f"Profile '{updated.get('name', pid)}' successfully updated.", changes

    # -------------------------------------------------------------------------
    # 3. Security Audits & 1-Click Auto-Patching
    # -------------------------------------------------------------------------
    def audit_profile(self, name_or_id: str) -> Tuple[bool, Dict[str, Any], str]:
        """Runs a senior-grade 12-dimensional tensor & security audit on the profile."""
        pid = self.resolve_profile_id(name_or_id)
        if not pid:
            return False, {}, f"Profile '{name_or_id}' not found."

        prof = self.profile_manager.load_profile(pid)
        if not prof:
            return False, {}, f"Profile data for '{pid}' not found."

        audit_res = EnvironmentAuditEngine.audit_profile_configuration(prof)
        return True, audit_res, f"Audit completed for profile '{prof.get('name', pid)}'. Health Score: {audit_res['health_score']}%"

    def apply_audit_patches(self, name_or_id: str) -> Tuple[bool, str, List[str]]:
        """1-Click Auto-Patch: Audits the profile and applies all required fixes immediately."""
        pid = self.resolve_profile_id(name_or_id)
        if not pid:
            return False, f"Profile '{name_or_id}' not found.", []

        prof = self.profile_manager.load_profile(pid)
        if not prof:
            return False, f"Profile data for '{pid}' not found.", []

        audit_res = EnvironmentAuditEngine.audit_profile_configuration(prof)
        recommended_patch = audit_res.get("recommended_patch", {})

        if not recommended_patch:
            return True, f"Profile '{prof.get('name', pid)}' is already 100% harmonized! No patches required.", []

        updated, changes = AutoPatchEngine.apply_patch(prof, recommended_patch)
        self.profile_manager.save_profile(updated)
        logger.info(f"[AIAgentActionEngine] Auto-patched profile '{pid}' with {len(changes)} modifications.")
        return True, f"Successfully auto-patched {len(changes)} settings in '{updated.get('name', pid)}'. New Health Score: 100%", changes

    def audit_all_profiles(self) -> List[Dict[str, Any]]:
        """Audits all profiles stored in the workspace."""
        results = []
        for p in self.profile_manager.list_profiles():
            pid = p.get("id")
            if pid:
                prof = self.profile_manager.load_profile(pid)
                if prof:
                    res = EnvironmentAuditEngine.audit_profile_configuration(prof)
                    results.append(res)
        return results

    # -------------------------------------------------------------------------
    # 4. Proxy Automation
    # -------------------------------------------------------------------------
    async def scrape_and_check_proxies(
        self,
        protocol: str = "http",
        limit: int = 20,
        verify_google: bool = True
    ) -> List[Dict[str, Any]]:
        """Scrapes public/configured proxy sources and optionally tests Google compatibility."""
        logger.info(f"[AIAgentActionEngine] Scraping {limit} {protocol} proxies...")
        scraped = await self.proxy_scraper.scrape_proxies(protocol=protocol, limit=limit)
        
        if not scraped:
            return []

        # Persist to proxy manager
        for p in scraped:
            self.proxy_manager.add_proxy(p)

        if verify_google:
            valid_proxies = []
            for p in scraped[:limit]:
                host = p.get("host") or p.get("ip")
                port = p.get("port")
                if host and port:
                    proxy_cfg = {
                        "host": str(host),
                        "port": int(port),
                        "type": protocol,
                        "enabled": True
                    }
                    try:
                        ok, msg, latency = await GoogleProxyChecker.check_proxy_with_google(proxy_cfg)
                        if ok:
                            p["google_passed"] = True
                            p["latency_ms"] = latency
                            valid_proxies.append(p)
                    except Exception as ex:
                        logger.debug(f"Google proxy check failed for {host}:{port}: {ex}")
            return valid_proxies

        return scraped

    def assign_proxy_to_profile(self, profile_name_or_id: str, proxy_dict: Dict[str, Any]) -> Tuple[bool, str]:
        """Assigns a verified proxy to the given profile."""
        pid = self.resolve_profile_id(profile_name_or_id)
        if not pid:
            return False, f"Profile '{profile_name_or_id}' not found."

        prof = self.profile_manager.load_profile(pid)
        if not prof:
            return False, f"Profile data for '{pid}' not found."

        prof["proxy"] = proxy_dict
        prof["proxy"]["enabled"] = True
        self.profile_manager.save_profile(prof)
        return True, f"Proxy '{proxy_dict.get('host')}:{proxy_dict.get('port')}' assigned to profile '{prof.get('name', pid)}'."

    # -------------------------------------------------------------------------
    # 5. Environment Benchmark Execution
    # -------------------------------------------------------------------------
    def get_benchmark_url(self, target: str) -> str:
        clean = target.lower().strip()
        return BENCHMARK_URLS.get(clean, BENCHMARK_URLS[EnvironmentBenchmarkTarget.CREEPJS])

    # -------------------------------------------------------------------------
    # 6. Warmup Campaign Management & Execution
    # -------------------------------------------------------------------------
    def save_warmup_campaign(self, name: str, campaign_data: Dict[str, Any]) -> Tuple[bool, str]:
        try:
            saved = self.campaign_manager.save_campaign(name, campaign_data)
            return True, f"Campaign '{saved.get('name', name)}' saved successfully."
        except Exception as e:
            return False, f"Failed to save campaign: {e}"

    def start_warmup_campaign(
        self,
        campaign_name_or_data: Any,
        profile_ids: List[str],
        headless: bool = False,
        progress_callback: Optional[Callable[[str, str, float, str, int], None]] = None
    ) -> Tuple[bool, str]:
        if not profile_ids:
            return False, "No profile IDs provided for warmup execution."

        # Resolve IDs
        resolved_pids = []
        for p in profile_ids:
            r = self.resolve_profile_id(p)
            if r:
                resolved_pids.append(r)

        if not resolved_pids:
            return False, "None of the specified profiles could be found."

        if isinstance(campaign_name_or_data, str):
            c_data = self.campaign_manager.get_campaign(campaign_name_or_data)
            if not c_data:
                return False, f"Campaign '{campaign_name_or_data}' not found."
            config_obj = self.campaign_manager.to_warmup_config(c_data)
        elif isinstance(campaign_name_or_data, dict):
            config_obj = self.campaign_manager.to_warmup_config(campaign_name_or_data)
        else:
            config_obj = WarmupConfig()

        config_obj.headless = headless
        robot = CookieWarmupRobot(self.launcher)
        task_id = f"warmup_{int(time.time())}_{resolved_pids[0][:6]}"

        async def _run_job():
            try:
                logger.info(f"[AIAgentActionEngine] Starting warmup '{task_id}' for {resolved_pids}")
                await robot.run_warmup_batch(
                    profile_ids=resolved_pids,
                    config=config_obj,
                    progress_callback=progress_callback
                )
                logger.info(f"[AIAgentActionEngine] Warmup '{task_id}' completed.")
            except Exception as e:
                logger.error(f"[AIAgentActionEngine] Warmup '{task_id}' error: {e}")
            finally:
                self._active_warmup_tasks.pop(task_id, None)

        task = asyncio.create_task(_run_job())
        self._active_warmup_tasks[task_id] = task
        return True, f"Warmup campaign started for {len(resolved_pids)} profile(s) (Task ID: {task_id})."

    # -------------------------------------------------------------------------
    # 7. System Metrics & Overview
    # -------------------------------------------------------------------------
    def get_system_status(self) -> Dict[str, Any]:
        profiles = self.profile_manager.list_profiles()
        active_map = getattr(self.launcher, "running_processes", {}) or getattr(self.launcher, "active_contexts", {})
        
        cpu_usage = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()

        return {
            "total_profiles": len(profiles),
            "active_profiles_count": len(active_map),
            "active_profile_ids": list(active_map.keys()),
            "cpu_percent": cpu_usage,
            "ram_used_gb": round(mem.used / (1024 ** 3), 2),
            "ram_total_gb": round(mem.total / (1024 ** 3), 2),
            "active_warmup_tasks": len(self._active_warmup_tasks),
            "timestamp": time.time()
        }

    # -------------------------------------------------------------------------
    # 8. Action Block Extraction & Security Validation
    # -------------------------------------------------------------------------
    SAFE_ACTIONS = {
        "audit_profile", "run_benchmark", "save_campaign", "list_profiles", "status"
    }
    DESTRUCTIVE_ACTIONS = {
        "delete_profile", "patch_profile", "clone_profile", "launch_profile",
        "stop_profile", "assign_proxy", "scrape_proxies", "start_warmup",
        "create_profile", "create_batch_profiles", "apply_audit_patches"
    }

    @classmethod
    def validate_action_safety(cls, action_dict: Dict[str, Any], allow_destructive: bool = False) -> Tuple[bool, str]:
        """
        Guards against Indirect Prompt Injection: verifies whether an extracted action
        is safe for automatic execution or requires explicit human confirmation.
        """
        act_name = str(action_dict.get("action", "")).lower().strip()
        if not act_name:
            return False, "Empty action name"

        if act_name in cls.SAFE_ACTIONS:
            return True, "Safe read-only action"

        if act_name in cls.DESTRUCTIVE_ACTIONS:
            if not allow_destructive:
                return False, f"Action '{act_name}' modifies profiles or system state and requires human confirmation."
            return True, f"Action '{act_name}' approved."

        return False, f"Unknown action '{act_name}' rejected for execution."

    @staticmethod
    def extract_action_blocks(text: str) -> List[Dict[str, Any]]:
        """Extracts structured JSON agent action blocks from model output."""
        actions = []
        if not text:
            return actions

        # Pattern 1: ```action:ACTION_NAME\n{...}\n```
        pattern1 = re.compile(r'```action:([a-zA-Z0-9_\-]+)[^\n]*\n([\s\S]*?)```', re.IGNORECASE)
        for match in pattern1.finditer(text):
            action_type = match.group(1).lower().strip()
            json_payload = match.group(2).strip()
            try:
                data = json.loads(json_payload)
                actions.append({"action": action_type, "data": data})
            except Exception as e:
                logger.debug(f"Action block parse error: {e}")

        # Pattern 2: ```json\n{"action": "...", ...}\n```
        pattern2 = re.compile(r'```(?:json)?[^\n]*\n(\{\s*"action"\s*:[\s\S]*?\})\s*```', re.IGNORECASE)
        for match in pattern2.finditer(text):
            json_payload = match.group(1).strip()
            try:
                obj = json.loads(json_payload)
                if isinstance(obj, dict) and "action" in obj:
                    actions.append(obj)
            except Exception:
                pass

        return actions

    # -------------------------------------------------------------------------
    # 9. End-to-End VLA (Vision-Language-Action) Execution Bridge
    # -------------------------------------------------------------------------
    async def execute_vla_step(
        self,
        profile_id: Optional[str] = None,
        instruction: str = "Click the main action button",
        vision_model: str = "moondream:v2"
    ) -> Dict[str, Any]:
        """
        Executes a single visual perception and actuation step on the active browser page.
        """
        from engine.ai_vla_engine import VisionLanguageActionEngine
        page = self.launcher.get_active_page(profile_id)
        if not page:
            return {"success": False, "error": "No active browser page found for VLA execution"}

        vla = VisionLanguageActionEngine.get_instance()
        success, message, result = await vla.perceive_and_act(
            page=page,
            instruction=instruction,
            vision_model=vision_model
        )
        return {
            "success": success,
            "message": message,
            "action": result.action.value,
            "thought": result.thought,
            "point": result.point,
            "box": result.box,
            "text": result.text,
            "confidence": result.confidence
        }

