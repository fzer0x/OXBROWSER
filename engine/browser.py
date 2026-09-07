import sys
import os
import shutil
import json
import time
import asyncio
import zipfile
import logging
import re
import socket
from typing import List, Dict, Optional, Tuple, Any, Union, cast
from playwright.async_api import async_playwright, Playwright, BrowserContext, Page, Geolocation, ProxySettings

import config
from storage.profile_manager import ProfileManager
from engine.fingerprint import FingerprintGenerator
from engine.proxy_checker import ProxyChecker
from engine.proxy_tunnel import LocalProxyTunnel
from engine.sandbox import SandboxManager, BaseSandbox
from engine.sandbox.network_killswitch import NetworkKillSwitchManager
from engine.cdp_patcher import ChromiumBinaryPatcher
from engine.platform_helper import PlatformHelper, CREATE_NO_WINDOW


from engine.port_utils import find_free_port, release_port  # noqa: F401 (re-exported)



logger = logging.getLogger("BrowserEngine")


def _safe_extractall(zipf: zipfile.ZipFile, target_dir: str) -> None:
    """[F-02] Zip-Slip-safe extraction: validates all member paths stay within target_dir."""
    target_dir = os.path.realpath(target_dir)
    for member in zipf.namelist():
        member_path = os.path.realpath(os.path.join(target_dir, member))
        if not member_path.startswith(target_dir + os.sep) and member_path != target_dir:
            raise ValueError(f"[Security] Zip Slip blocked: '{member}' would escape target directory.")
    zipf.extractall(target_dir)


def get_system_timezone() -> str:
    """Returns the local system timezone ID (e.g. Europe/Berlin) cross-platform."""
    return PlatformHelper.get_system_timezone()


class BrowserLauncher:
    """Manages spawning and lifecycle of Chromium/Firefox instances via Sandbox Manager, Playwright, or Driverless."""

    _instance: Optional['BrowserLauncher'] = None
    # [F-10] Shared State Documentation:
    # _shared_active_contexts maintains a global registry of running browser instances
    # to prevent multiple simultaneous launches of the same profile across different
    # launcher instances (e.g., API vs GUI).
    _shared_active_contexts: Dict[str, Any] = {}
    _shared_contexts_lock: Optional[asyncio.Lock] = None

    def __init__(self, profile_manager: ProfileManager):
        self.profile_manager = profile_manager
        self.playwright: Optional[Playwright] = None
        self.active_contexts: Dict[str, Any] = BrowserLauncher._shared_active_contexts
        # active_drivers is maintained as an alias to active_contexts for backward compatibility
        self.active_drivers: Dict[str, Any] = self.active_contexts
        self.active_tunnels: Dict[str, LocalProxyTunnel] = {}
        self.active_sandboxes: Dict[str, BaseSandbox] = {}
        self._launch_lock: Optional[asyncio.Lock] = None

        if BrowserLauncher._instance is None:
            BrowserLauncher._instance = self

    @classmethod
    def get_instance(cls, profile_manager: Optional[ProfileManager] = None) -> 'BrowserLauncher':
        if cls._instance is None:
            cls._instance = BrowserLauncher(profile_manager or ProfileManager())
        return cls._instance

    @property
    def running_processes(self) -> Dict[str, Any]:
        """Returns map of running profile IDs to their active contexts."""
        return self.active_contexts

    def get_active_page(self, profile_id: Optional[str] = None) -> Optional[Any]:
        """Retrieves active page for given profile ID or the primary active running browser tab."""
        if not self.active_contexts:
            return None

        target_pid = profile_id
        if not target_pid or target_pid == "default":
            target_pid = next(iter(self.active_contexts.keys()))

        ctx = self.active_contexts.get(target_pid)
        if ctx is None:
            # Fallback search by ID substring or name
            for pid, c in self.active_contexts.items():
                if pid == target_pid or (target_pid and target_pid.lower() in pid.lower()):
                    ctx = c
                    break

        if ctx is None and len(self.active_contexts) > 0:
            ctx = next(iter(self.active_contexts.values()))

        if ctx is None:
            return None

        if hasattr(ctx, "pages") and ctx.pages:
            return ctx.pages[-1]
        if hasattr(ctx, "contexts") and ctx.contexts:
            sub_ctx = ctx.contexts[0]
            if hasattr(sub_ctx, "pages") and sub_ctx.pages:
                return sub_ctx.pages[-1]
        if hasattr(ctx, "main_tab") and ctx.main_tab:
            return ctx.main_tab
        if hasattr(ctx, "tabs") and ctx.tabs:
            return ctx.tabs[-1]
        if hasattr(ctx, "page"):
            return ctx.page
        if hasattr(ctx, "evaluate"):
            return ctx
        return ctx

    def rotate_proxy_for_profile(self, profile_id: str, new_proxy_data: Dict[str, Any]) -> bool:
        """
        Dynamically updates the running LocalProxyTunnel and active profile config for a running profile.
        All subsequent requests in the browser will immediately route via the new upstream proxy.
        """
        if not profile_id or not new_proxy_data:
            return False

        # 1. Update running tunnel upstream if it exists
        tunnel = self.active_tunnels.get(profile_id)
        if tunnel:
            tunnel.update_upstream(
                upstream_host=new_proxy_data.get("host", ""),
                upstream_port=int(new_proxy_data.get("port", 8080)),
                username=new_proxy_data.get("username", ""),
                password=new_proxy_data.get("password", ""),
                proxy_type=new_proxy_data.get("type", "http")
            )
            logger.info(f"[BrowserLauncher] Active LocalProxyTunnel for profile '{profile_id}' rotated to {new_proxy_data.get('type', 'http')}://{new_proxy_data.get('host')}:{new_proxy_data.get('port')}")

        # 2. Update persistent profile data in profile_manager
        try:
            if hasattr(self, "profile_manager") and self.profile_manager:
                prof = self.profile_manager.get_profile(profile_id)
                if prof:
                    p_cfg = prof.get("proxy", {})
                    p_cfg["enabled"] = True
                    p_cfg["type"] = new_proxy_data.get("type", "http")
                    p_cfg["host"] = new_proxy_data.get("host", "")
                    p_cfg["port"] = int(new_proxy_data.get("port", 8080))
                    p_cfg["username"] = new_proxy_data.get("username", "")
                    p_cfg["password"] = new_proxy_data.get("password", "")
                    p_cfg["change_ip_url"] = new_proxy_data.get("change_ip_url", "")
                    prof["proxy"] = p_cfg
                    if new_proxy_data.get("ip"):
                        prof["proxy_info"] = {
                            "ip": new_proxy_data.get("ip", ""),
                            "country": new_proxy_data.get("country", ""),
                            "city": new_proxy_data.get("city", ""),
                            "timezone": new_proxy_data.get("timezone", "")
                        }
                    self.profile_manager.save_profile(prof)
                    return True
        except Exception as e:
            logger.error(f"[BrowserLauncher] Failed to update profile '{profile_id}' proxy in storage: {e}")

        return tunnel is not None

    def _get_launch_lock(self) -> asyncio.Lock:
        if BrowserLauncher._shared_contexts_lock is None:
            BrowserLauncher._shared_contexts_lock = asyncio.Lock()
        return BrowserLauncher._shared_contexts_lock

    async def _ensure_playwright(self) -> Playwright:
        if self.playwright is None:
            self.playwright = await async_playwright().start()
        return self.playwright

    @classmethod
    def _ensure_camoufox_h264_codecs(cls, camoufox_dir: str):
        """
        Ensures essential FFmpeg / H.264 codec libraries are available in library path.
        """
        if not camoufox_dir or not os.path.isdir(camoufox_dir):
            return

        if PlatformHelper.is_windows():
            curr_path = os.environ.get("PATH", "")
            if camoufox_dir not in curr_path.split(";"):
                os.environ["PATH"] = f"{camoufox_dir};{curr_path}".strip(";")
            return

        # Linux / Unix handling
        curr_ld = os.environ.get("LD_LIBRARY_PATH", "")
        if camoufox_dir not in curr_ld.split(":"):
            os.environ["LD_LIBRARY_PATH"] = f"{camoufox_dir}:{curr_ld}".strip(":")

        if os.path.exists(os.path.join(camoufox_dir, "libavcodec.so.58")):
            return

        src_dirs = [
            os.path.join(config.BASE_DIR, "camoufox", "camoufox"),
            os.path.join(config.BASE_DIR, "camoufox"),
            "/usr/lib/ffmpeg4.4"
        ]
        codec_prefixes = ["libavcodec.so.58", "libavformat.so.58", "libavutil.so.56", "libswresample.so.3", "libswscale.so.5"]

        for s_dir in src_dirs:
            if os.path.exists(s_dir):
                for fname in os.listdir(s_dir):
                    for pref in codec_prefixes:
                        if fname.startswith(pref):
                            src_f = os.path.join(s_dir, fname)
                            dst_f = os.path.join(camoufox_dir, fname)
                            if not os.path.exists(dst_f):
                                try:
                                    shutil.copy2(src_f, dst_f)
                                except Exception:
                                    pass

    @classmethod
    def _find_camoufox_binary(cls) -> Optional[str]:
        """Finds Camoufox executable binary from official pkgman cache or project directory."""
        target_bin = PlatformHelper.find_camoufox_binary(config.BASE_DIR)
        if target_bin:
            cls._ensure_camoufox_h264_codecs(os.path.dirname(target_bin))
        return target_bin

    def prepare_extensions(self, extensions_list: list, user_data_dir: str = "") -> List[str]:
        """
        Unpacks and prepares .xpi, .crx, and directory extensions.
        - Unpacks archives to directory containing manifest.json (required by Camoufox & Chromium).
        - For Firefox user profiles, also installs .xpi files into <user_data_dir>/extensions/<id>.xpi.
        Returns a list of extracted extension folder paths containing manifest.json.
        """
        loaded_unpacked_dirs: List[str] = []
        ext_folder = config.EXTENSIONS_DIR
        if not os.path.exists(ext_folder) or not extensions_list:
            return loaded_unpacked_dirs

        ff_ext_dir = os.path.join(user_data_dir, "extensions") if user_data_dir else None
        if ff_ext_dir:
            os.makedirs(ff_ext_dir, exist_ok=True)

        for item_name in extensions_list:
            if not item_name:
                continue
            
            if os.path.isabs(item_name) and os.path.exists(item_name):
                item_path = item_name
            else:
                item_path = os.path.join(ext_folder, item_name)

            if not os.path.exists(item_path):
                logger.warning(f"[BrowserLauncher] Extension file not found: {item_path}")
                continue

            clean_name = os.path.splitext(os.path.basename(item_path))[0]
            unzip_path = os.path.join(ext_folder, f"{clean_name}_unpacked")

            if os.path.isdir(item_path):
                if os.path.exists(os.path.join(item_path, "manifest.json")):
                    loaded_unpacked_dirs.append(item_path)
                continue

            if item_path.endswith(('.xpi', '.crx', '.zip')):
                os.makedirs(unzip_path, exist_ok=True)
                addon_id = None
                try:
                    with zipfile.ZipFile(item_path, 'r') as zip_ref:
                        _safe_extractall(zip_ref, unzip_path)  # [F-02] Zip-Slip-safe extraction
                        try:
                            m_data = json.loads(zip_ref.read("manifest.json").decode("utf-8"))
                            addon_id = (
                                m_data.get("browser_specific_settings", {}).get("gecko", {}).get("id") or
                                m_data.get("applications", {}).get("gecko", {}).get("id")
                            )
                        except Exception:
                            addon_id = None

                    if os.path.exists(os.path.join(unzip_path, "manifest.json")):
                        loaded_unpacked_dirs.append(unzip_path)

                    if ff_ext_dir and item_path.endswith('.xpi'):
                        target_filename = f"{addon_id}.xpi" if addon_id else os.path.basename(item_path)
                        target_xpi = os.path.join(ff_ext_dir, target_filename)
                        shutil.copy2(item_path, target_xpi)
                        logger.info(f"[BrowserLauncher] Installed Firefox addon: {target_filename}")

                except Exception as e:
                    logger.error(f"[BrowserLauncher] Error extracting extension {item_path}: {e}")

        return loaded_unpacked_dirs

    @staticmethod
    def _ensure_chromium_webrtc_preferences(user_data_dir: str, webrtc_mode: str):
        """Writes hardened WebRTC non-proxied IP leak prevention preferences directly into Chromium user profile."""
        try:
            for p_dir in [os.path.join(user_data_dir, "Default"), user_data_dir]:
                os.makedirs(p_dir, exist_ok=True)
                p_file = os.path.join(p_dir, "Preferences")
                prefs_dict = {}
                if os.path.exists(p_file):
                    try:
                        with open(p_file, "r", encoding="utf-8") as f:
                            prefs_dict = json.load(f)
                    except Exception:
                        prefs_dict = {}
                if not isinstance(prefs_dict, dict):
                    prefs_dict = {}
                if "webrtc" not in prefs_dict:
                    prefs_dict["webrtc"] = {}
                if webrtc_mode in ["disabled", "altered"]:
                    prefs_dict["webrtc"]["ip_handling_policy"] = "disable_non_proxied_udp"
                    prefs_dict["webrtc"]["multiple_routes_enabled"] = False
                    prefs_dict["webrtc"]["nonproxied_udp_enabled"] = False
                    if webrtc_mode == "disabled":
                        prefs_dict["webrtc"]["udp_port_range"] = "0-0"
                with open(p_file, "w", encoding="utf-8") as f:
                    json.dump(prefs_dict, f, indent=2)
        except Exception as e:
            logger.debug(f"Could not write Chromium WebRTC preferences: {e}")

    @staticmethod
    async def _safe_goto(page: Any, url: str):
        """Safely navigates to the initial start URL and silently catches normal navigation interruptions."""
        try:
            if url and page and hasattr(page, "goto"):
                await page.goto(url, timeout=20000, wait_until="domcontentloaded")
        except Exception as e:
            err_str = str(e)
            if "NS_BINDING_ABORTED" not in err_str and "ERR_ABORTED" not in err_str and "Target page, context or browser has been closed" not in err_str and "Target closed" not in err_str:
                logger.debug(f"[BrowserLauncher] Initial navigation notice for '{url}': {e}")

    async def launch_profile(
        self,
        profile_id: str,
        window_override_pos: Optional[Tuple[int, int]] = None,
        window_override_size: Optional[Tuple[int, int]] = None,
        headless: Optional[bool] = None,
        navigate_start_url: bool = True
    ) -> Tuple[bool, str, Optional[Any]]:
        """Launches a Chrome/Firefox browser profile asynchronously via Playwright, Camoufox, Nodriver or Selenium Driverless."""
        profile = self.profile_manager.load_profile(profile_id)
        if not profile:
            return False, f"Profile ID '{profile_id}' not found.", None

        if profile_id in self.active_contexts:
            return False, "Profile is already running.", self.active_contexts[profile_id]

        # Resource Governor Pre-Flight Check
        try:
            from engine.lifecycle import GlobalLifecycleManager
            has_headroom, headroom_msg, _ = GlobalLifecycleManager.check_system_headroom(min_free_ram_mb=400)
            if not has_headroom:
                logger.error(f"[BrowserLauncher] Cannot launch profile '{profile_id}': {headroom_msg}")
                return False, f"Resource Governor: {headroom_msg}", None
        except Exception:
            pass

        engine_type = profile.get("engine", "camoufox").lower().strip()
        proxy_cfg = profile.get("proxy", {})
        proxy_info = profile.get("proxy_info", {})
        
        # Determine whether manual or auto timezone is desired
        sys_tz = get_system_timezone()
        prof_tz = str(profile.get("timezone") or "").strip()
        is_manual_tz = bool(prof_tz and prof_tz.lower() != "auto")

        # Mandatory fresh proxy telemetry check before EVERY browser start
        if proxy_cfg.get("enabled") and proxy_cfg.get("host"):
            try:
                logger.info(f"[BrowserLauncher] Running mandatory pre-launch proxy check for {proxy_cfg.get('host')}...")
                success, info, latency = await asyncio.wait_for(ProxyChecker.check_proxy(proxy_cfg), timeout=5.0)
                if success and info:
                    proxy_info = info
                    profile["proxy_info"] = info
                    self.profile_manager.save_profile(profile)
                    logger.info(f"[BrowserLauncher] Pre-launch proxy check success: IP={info.get('ip')} ({info.get('country')}, TZ={info.get('timezone')}) in {latency}ms")
                else:
                    err_msg = info.get("error", "Unknown error") if isinstance(info, dict) else "Unknown error"
                    logger.warning(f"[BrowserLauncher] Pre-launch proxy check failed: {err_msg}. Using existing telemetry fallback.")
            except Exception as p_err:
                logger.warning(f"[BrowserLauncher] Pre-launch proxy check timed out or failed: {p_err}. Using existing telemetry fallback.")

        # Determine Target Timezone ID
        auto_tz_enabled = bool(proxy_cfg.get("auto_timezone", profile.get("auto_timezone", True)))
        p_tz = str(proxy_info.get("timezone") or "").strip()

        if proxy_cfg.get("enabled") and proxy_cfg.get("host") and auto_tz_enabled and p_tz:
            # When proxy is enabled and auto_timezone is active (default), align directly to proxy IP timezone!
            tz_id = p_tz
            if profile.get("timezone") != p_tz:
                profile["timezone"] = p_tz
                self.profile_manager.save_profile(profile)
        elif is_manual_tz:
            # 1. User explicitly configured a specific timezone in the profile - HIGHEST PRIORITY
            tz_id = prof_tz
        elif proxy_cfg.get("enabled") and proxy_cfg.get("host") and p_tz:
            tz_id = p_tz
        else:
            # 3. Auto mode without proxy or default: use host machine's system timezone
            tz_id = sys_tz

        # Determine Target Language & Accept-Language Header (Pure IP Language)
        from engine.geo_ip_aligner import GeoIPAligner
        prof_lang = str(profile.get("language") or "").strip()
        auto_lang = proxy_cfg.get("auto_language", True)
        is_manual_lang = bool(prof_lang and prof_lang.lower() not in ["auto", "default", ""] and not auto_lang)

        if is_manual_lang:
            raw_lang = prof_lang
            primary_lang = raw_lang.split(",")[0].split(";")[0].strip() or "en-US"
            clean_langs = [p.split(";")[0].strip() for p in raw_lang.split(",") if p.strip()]
            clean_lang_str = ",".join(clean_langs) if clean_langs else primary_lang
        elif proxy_cfg.get("enabled") and proxy_cfg.get("host") and proxy_info:
            geo_alignment = GeoIPAligner.align_from_proxy_info(proxy_info)
            raw_lang = geo_alignment.accept_language
            primary_lang = geo_alignment.locale
            clean_lang_str = ",".join(geo_alignment.languages) if geo_alignment.languages else primary_lang
            logger.info(f"[BrowserLauncher] Pure IP Language aligned to Proxy ({proxy_info.get('country_code', 'US')}): locale='{primary_lang}', Accept-Language='{raw_lang}', languages='{clean_lang_str}'")
        elif prof_lang and prof_lang.lower() not in ["auto", "default", ""]:
            raw_lang = prof_lang
            primary_lang = raw_lang.split(",")[0].split(";")[0].strip() or "en-US"
            clean_langs = [p.split(";")[0].strip() for p in raw_lang.split(",") if p.strip()]
            clean_lang_str = ",".join(clean_langs) if clean_langs else primary_lang
        else:
            raw_lang = "en-US,en;q=0.9"
            primary_lang = "en-US"
            clean_lang_str = "en-US,en"

        # Determine Geolocation (Latitude & Longitude)
        loc_cfg = profile.get("location", {})
        geo_dict: Optional[Geolocation] = None
        permissions_list: Optional[list[str]] = None

        if proxy_cfg.get("enabled") and proxy_cfg.get("host") and proxy_cfg.get("auto_geolocation", True) and proxy_info.get("lat"):
            try:
                geo_dict = cast(Geolocation, {
                    "latitude": float(proxy_info.get("lat", 0.0)),
                    "longitude": float(proxy_info.get("lon", 0.0)),
                    "accuracy": 100.0
                })
                permissions_list = ["geolocation"]
            except (ValueError, TypeError):
                pass
        elif loc_cfg.get("lat") or loc_cfg.get("lon"):
            try:
                geo_dict = cast(Geolocation, {
                    "latitude": float(loc_cfg.get("lat", 0.0)),
                    "longitude": float(loc_cfg.get("lon", 0.0)),
                    "accuracy": 100.0
                })
                permissions_list = ["geolocation"]
            except (ValueError, TypeError):
                pass

        logger.info(f"[BrowserLauncher] Launching profile '{profile_id}' with timezone: '{tz_id}', locale='{primary_lang}', accept_lang='{raw_lang}', geo={geo_dict} (proxy_enabled={proxy_cfg.get('enabled', False)}, manual_tz={is_manual_tz})")
        
        # Build child environment dictionary with profile timezone & locale (avoiding global process pollution)
        child_env = os.environ.copy()
        child_env["TZ"] = tz_id

        profile_dir = self.profile_manager.get_profile_path(profile_id)
        user_data_dir = self.profile_manager.get_user_data_dir(profile_id)
        self._cleanup_orphaned_profile_processes(user_data_dir)

        # Pre-launch offline SQLite cookie sync before browser engine locks files
        try:
            from engine.cookie_manager import CookieManager
            cookie_json_path = os.path.join(profile_dir, "cookies.json")
            if os.path.exists(cookie_json_path):
                raw_c = CookieManager.import_cookies_from_file(cookie_json_path)
                if raw_c:
                    CookieManager.sync_cookies_to_profile(profile_dir, raw_c)
        except Exception as pre_sync_err:
            logger.debug(f"[BrowserLauncher] Pre-launch cookie SQLite sync notice: {pre_sync_err}")

        # Allocate a fresh, non-colliding Remote Debugging Port for Playwright/Puppeteer automation
        debug_port = find_free_port()
        profile["debug_port"] = debug_port
        self.profile_manager.save_profile(profile)

        # Instantiate & Start Profile Sandbox (Container / MicroVM / Mesa GL virtualization)
        sandbox = SandboxManager.create_sandbox(profile_id, profile, user_data_dir, debug_port)
        sb_ok, sb_msg, debug_port = await sandbox.start()
        if sb_ok:
            self.active_sandboxes[profile_id] = sandbox
            logger.info(f"[BrowserLauncher] Sandbox initialized for '{profile_id}': {sb_msg}")

        # Strict Engine-to-User-Agent Alignment (Eliminates L7 JA4 Mismatch)
        target_os_clean = profile.get("os", "windows").lower()
        ua = profile.get("user_agent")
        if not ua:
            ua = config.get_default_user_agent(target_os_clean, engine_type)
        elif engine_type in ["camoufox", "firefox"] and ("Chrome/" in ua or "Chromium/" in ua or ("Safari/" in ua and "Firefox/" not in ua)):
            logger.info(f"[BrowserLauncher] Rectified User-Agent for Camoufox profile '{profile_id}' to match native Firefox NSS TLS stack.")
            ua = config.get_default_user_agent(target_os_clean, "camoufox")
        elif engine_type in ["playwright", "nodriver", "selenium_driverless"] and ("Firefox/" in ua or "rv:" in ua):
            logger.info(f"[BrowserLauncher] Rectified User-Agent for Chromium profile '{profile_id}' to match Chromium BoringSSL TLS stack.")
            ua = config.get_default_user_agent(target_os_clean, "chrome")
        lang_raw = raw_lang
        accept_langs = raw_lang

        # Configure child process locale without mutating global process state
        env_lang = primary_lang.replace("-", "_") + ".UTF-8"
        child_env["LANG"] = env_lang
        child_env["LC_ALL"] = env_lang

        raw_webrtc = profile.get("stealth", {}).get("webrtc_mode") or profile.get("stealth", {}).get("webrtc") or profile.get("webrtc_mode") or "altered"
        if isinstance(raw_webrtc, bool):
            webrtc_mode = "altered" if raw_webrtc else "disabled"
        else:
            m_str = str(raw_webrtc).lower().strip()
            if m_str in ["altered", "spoof", "spoofed", "protocol_spoofing", "proxy"]:
                webrtc_mode = "altered"
            elif m_str in ["disabled", "block", "blocked", "off", "disable", "none"]:
                webrtc_mode = "disabled"
            elif m_str in ["real", "raw", "leak", "enabled", "on", "default"]:
                webrtc_mode = "real"
            else:
                webrtc_mode = "altered"

        cloudflare_doh_url = "https://chrome.cloudflare-dns.com/dns-query"

        # Build Chromium Command Line Arguments with Anti-DNS Leak & Anti-DoH protection
        chromium_args = [
            f"--remote-debugging-port={debug_port}",
            f"--lang={primary_lang}",
            "--no-first-run",
            "--no-default-browser-check",
            "--no-sandbox",
            "--test-type",
            "--disable-infobars",
            "--disable-dev-shm-usage",
            "--dns-prefetch-disable",
            "--disable-async-dns",
            "--disable-background-networking",
            "--disable-component-update",
            "--disable-component-cloud-policy",
            "--disable-domain-reliability",
            "--disable-client-side-phishing-detection",
            "--disable-sync",
            "--disable-default-apps",
            "--disable-gcm",
            "--disable-breakpad",
            "--disable-speech-api",
            "--force-fieldtrials=*DnsOverHttps/Disabled/",
            "--disable-features=DnsOverHttps,AsyncDns,BuiltInDnsClient,LookalikeUrlNavigationSuggestionsUI,AudioServiceOutOfProcess,MediaRouter,MediaRouterComponent,NetworkTimeServiceQuerying,CertificateTransparencyComponentUpdater,SafeBrowsingEnhancedProtection,AutofillServerCommunication,OptimizationGuideModelDownloading,OptimizationHints,OptimizationTargetPrediction,OptimizationGuideConsumer,PushMessaging,GCMDriver"
        ]

        # Determine Window Dimensions & Display Position
        if window_override_size:
            win_w, win_h = window_override_size
        else:
            win_w = int(profile.get("window_width") or 1280)
            win_h = int(profile.get("window_height") or 720)

        if window_override_pos:
            win_x, win_y = window_override_pos
        else:
            win_x = int(profile.get("window_pos_x") or 0)
            win_y = int(profile.get("window_pos_y") or 0)

        chromium_args.extend([
            f"--window-size={win_w},{win_h}",
            f"--window-position={win_x},{win_y}"
        ])

        if webrtc_mode in ["disabled", "altered"]:
            chromium_args.extend([
                "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
                "--enforce-webrtc-ip-permission-check",
                "--disable-webrtc-multiple-routes",
                "--disable-webrtc-hw-decoding",
                "--disable-webrtc-hw-encoding"
            ])


        # Behavior, History & Privacy Chromium Flags
        beh = profile.get("behavior", {})
        if not beh.get("save_history", True):
            chromium_args.append("--incognito")
        if not beh.get("disk_cache", True):
            chromium_args.extend(["--disable-application-cache", "--disk-cache-size=0"])
        if not beh.get("form_autofill", True):
            chromium_args.append("--disable-features=AutofillServerCommunication,AutofillAddressProfile")
        if beh.get("block_telemetry", True):
            chromium_args.extend(["--disable-breakpad", "--disable-sync", "--no-report-upload", "--disable-telemetry"])
        if beh.get("autoplay_media", "allow") == "block_all":
            chromium_args.append("--autoplay-policy=user-gesture-required")
        elif beh.get("autoplay_media", "allow") == "block_audio":
            chromium_args.append("--autoplay-policy=document-user-activation-required")

        # Extensions
        ext_paths = self.prepare_extensions(profile.get("extensions", []))
        if ext_paths:
            ext_arg = ",".join(ext_paths)
            chromium_args.extend([
                f"--load-extension={ext_arg}",
                f"--disable-extensions-except={ext_arg}"
            ])
            logger.info(f"[BrowserLauncher] Configured Chrome extension flags: --load-extension={ext_arg}")

        # Proxy Configuration
        proxy_dict: Optional[ProxySettings] = None
        if proxy_cfg.get("enabled") and proxy_cfg.get("host"):
            host = proxy_cfg.get("host", "").strip()
            port = int(proxy_cfg.get("port", 8080))
            p_type = proxy_cfg.get("type", "http").lower()
            user = proxy_cfg.get("username", "").strip()
            pwd = proxy_cfg.get("password", "").strip()
            scheme = "socks5h" if p_type in ["socks5", "socks5h"] else "http"

            # Proxy configured via LocalProxyTunnel / --proxy-server (forces 100% of requests and DNS through proxy)

            change_ip_url = proxy_cfg.get("change_ip_url", "").strip()
            if change_ip_url:
                try:
                    import aiohttp
                    async with aiohttp.ClientSession() as session:
                        async with session.get(change_ip_url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                            logger.info(f"Triggered proxy IP rotation URL: status {resp.status}")
                except Exception as e:
                    logger.warning(f"Could not trigger proxy IP rotation URL: {e}")

            tls_preset = profile.get("tls_ja3_preset", "auto")
            target_os_val = profile.get("os", "windows")

            burst_prot = bool(proxy_cfg.get("burst_protection", profile.get("burst_protection", True)))
            burst_ms = float(proxy_cfg.get("burst_stagger_ms", profile.get("burst_stagger_ms", 20.0)))

            if user or pwd or tls_preset != "auto":
                tunnel = LocalProxyTunnel(
                    upstream_host=host,
                    upstream_port=port,
                    username=user,
                    password=pwd,
                    proxy_type=p_type,
                    max_concurrency=128,
                    burst_protection=burst_prot,
                    burst_stagger_ms=burst_ms,
                    tls_preset=tls_preset,
                    target_os=target_os_val
                )
                local_port = await tunnel.start()
                self.active_tunnels[profile_id] = tunnel
                proxy_dict = {"server": f"http://127.0.0.1:{local_port}"}

                # Setup Linux Network Namespace Egress Kill Switch if enabled
                if profile.get("network_killswitch", True) and sys.platform == "linux":
                    ns_ok, ns_msg, ns_name = NetworkKillSwitchManager.setup_profile_netns(profile_id, local_port)
                    if ns_ok:
                        logger.info(f"[BrowserLauncher] {ns_msg}")
                    else:
                        logger.error(f"[BrowserLauncher] FAIL-CLOSED GUARD ACTIVATED: {ns_msg}")
                        if profile_id in self.active_tunnels:
                            try:
                                await self.active_tunnels[profile_id].stop()
                            except Exception:
                                pass
                            del self.active_tunnels[profile_id]
                        return False, f"LAUNCH ABORTED FOR SECURITY (Fail-Closed Guard): {ns_msg}", None
            else:
                proxy_dict = {"server": f"{scheme}://{host}:{port}"}
        else:
            logger.info(f"[BrowserLauncher] Profile '{profile_id}' proxy is disabled or host is empty.")

        res_str = profile.get("screen_resolution", "1920x1080")
        raw_start_url = profile.get("start_url", "").strip()
        # Fallback to first auto-login account login_url if start_url is empty
        if not raw_start_url:
            for acc in profile.get("accounts", []):
                if acc.get("auto_login_on_launch") and acc.get("login_url"):
                    raw_start_url = acc.get("login_url")
                    break

        if raw_start_url:
            if not raw_start_url.startswith(("http://", "https://", "about:", "chrome://")):
                start_url = "https://" + raw_start_url
            else:
                start_url = raw_start_url
        else:
            start_url = ""

        # Branch 0: Camoufox C++ Native Anti-Detect Launch Path (Primary Engine)
        # Camoufox is Firefox-based — --no-sandbox does not apply to this engine.
        # No security warnings needed: Camoufox has native C++ sandbox mechanisms.
        if engine_type == "camoufox":
            save_history = beh.get("save_history", False)
            search_suggestions = beh.get("search_suggestions", False)
            restore_session = beh.get("restore_session", False)
            form_autofill = beh.get("form_autofill", False)
            password_manager = beh.get("password_manager", False)
            address_autofill = beh.get("address_autofill", False)
            credit_card_autofill = beh.get("credit_card_autofill", False)
            disk_cache = beh.get("disk_cache", False)
            offline_storage = beh.get("offline_storage", False)
            clear_on_shutdown = beh.get("clear_on_shutdown", False)
            block_telemetry = beh.get("block_telemetry", True)
            drm_widevine = beh.get("drm_widevine", True)
            autoplay_media = beh.get("autoplay_media", "block_all")
            effective_restore = bool(restore_session and not clear_on_shutdown)

            ff_prefs: Dict[str, Any] = {
                "dom.webgpu.enabled": True,
                "gfx.webgpu.force-enabled": True,
                "gfx.webgpu.ignore-status": True,
                "security.enterprise_roots.enabled": True,
                "security.certerror.test.root_issuer": True,
                "security.insecure_connection_icon.enabled": False,
                "security.insecure_connection_icon.pbmode.enabled": False,
                "network.proxy.allow_hijacking_localhost": True,
                "security.OCSP.enabled": 0,
                "security.ssl.enable_ocsp_stapling": False,
                "network.http.http2.enabled": True,
                "network.http.http3.enable": True,
                "network.http.http3.enabled": True,
                "network.dns.disablePrefetch": True,
                "network.prefetch-next": False,
                "network.http.max-persistent-connections-per-proxy": 16,
                "network.http.max-persistent-connections-per-server": 6,
                "network.http.keep-alive.timeout": 30,
                "network.http.response.timeout": 60,
                "network.proxy.socks_remote_dns": True,
                "network.trr.mode": 5,
                "extensions.ublock0.filterLists.autoUpdate": False,
                "media.peerconnection.use_document_iceservers": False,
                "places.history.enabled": save_history,
                "browser.startup.page": 3 if effective_restore else 0,
                "browser.startup.homepage": "about:blank",
                "startup.homepage_welcome_url": "about:blank",
                "startup.homepage_override_url": "about:blank",
                "browser.sessionstore.resume_from_crash": effective_restore,
                "browser.urlbar.suggest.searches": search_suggestions,
                "browser.search.suggest.enabled": search_suggestions,
                "browser.urlbar.suggest.history": search_suggestions,
                "browser.formfill.enable": form_autofill,
                "signon.autofillForms": form_autofill,
                "signon.rememberSignons": password_manager,
                "extensions.formautofill.addresses.enabled": address_autofill,
            "extensions.formautofill.creditCards.enabled": credit_card_autofill,
                "browser.cache.disk.enable": disk_cache,
                "dom.indexedDB.enabled": offline_storage,
                "privacy.sanitize.sanitizeOnShutdown": clear_on_shutdown,
                
                # Universal Native Video & Codec Unlocking (TikTok, HTML5 MSE without DRM tracking)
                "media.ffmpeg.vaapi.enabled": False,  # Prevent Linux VAAPI crash on NVIDIA/Xvfb/VMs
                "media.hardware-video-decoding.failed": False,
                "media.hardware-video-decoding.enabled": True,
                "media.rdd-ffmpeg.enabled": True,
                "media.rdd-vpx.enabled": True,
                "media.ffvpx.enabled": True,
                "media.av1.enabled": True,
                "media.navigator.mediadatadecoder_vpx_enabled": True,
                "media.fragmented-mp4.exposed": True,
                "media.fragmented-mp4.ffmpeg.enabled": True,
                "media.mp4.enabled": True,
                "media.webm.enabled": True,
                "media.ogg.enabled": True,
                "media.wave.enabled": True,
                "media.hls.enabled": True,
                "media.wmf.enabled": True,
                "media.gmp-gmpopenh264.enabled": True,
                "media.gmp-gmpopenh264.autoupdate": True,
                "media.gmp-gmpopenh264.provider.enabled": True,
                "media.gmp-manager.updateEnabled": True,

                # Full W3C Standard EME (ClearKey) & Widevine CDM Media Decryption
                "media.eme.enabled": drm_widevine,
                "media.eme.clearkey.enabled": True,
                "media.eme.widevine.enabled": drm_widevine,
                "media.gmp-widevinecdm.enabled": drm_widevine,
                "media.gmp-widevinecdm.visible": drm_widevine,
                "media.gmp-widevinecdm.autoupdate": drm_widevine,
                "media.gmp.decoder.enabled": True,
                "media.gmp-provider.enabled": True,
                "media.mediasource.enabled": True,
                "media.mediasource.mp4.enabled": True,
                "media.mediasource.webm.enabled": True,
                "media.mediasource.vp9.enabled": True,
                "media.eme.hdcp-policy.check": True,

                # Autoplay policy (enables smooth video playback on TikTok / Web feeds)
                "media.autoplay.default": 0 if autoplay_media == "allow" else (5 if autoplay_media == "block_all" else 1),
                "media.autoplay.allow-muted": True,
                "media.autoplay.blocking_policy": 0,
                "media.autoplay.ask-permission": False,

                "datareporting.healthreport.uploadEnabled": not block_telemetry,
                "toolkit.telemetry.enabled": not block_telemetry,
                "app.shield.optoutstudies.enabled": not block_telemetry,
                "xpinstall.signatures.required": False,
                "extensions.autoDisableScopes": 0,
                "extensions.enabledScopes": 15,
                "extensions.installDistroAddons": True,
                "extensions.experiments.enabled": True,
                "extensions.systemAddon.update.enabled": False,
            }

            try:
                camoufox_bin = self._find_camoufox_binary()
                has_camoufox_lib = False
                try:
                    import camoufox
                    has_camoufox_lib = True
                except ImportError:
                    pass

                from engine.browser_downloader import BrowserDownloader
                is_cf_ready, _ = BrowserDownloader.is_engine_installed("camoufox")
                if not is_cf_ready or not has_camoufox_lib or not camoufox_bin:
                    from engine.sandbox.sandbox_installer import SandboxInstaller
                    ok, msg = await SandboxInstaller.ensure_camoufox_installed()
                    if ok:
                        try:
                            import camoufox
                            has_camoufox_lib = True
                        except ImportError:
                            pass
                    if not camoufox_bin:
                        camoufox_bin = self._find_camoufox_binary()

                if has_camoufox_lib:
                    from camoufox.async_api import AsyncCamoufox  # type: ignore[import-not-found, missing-import]
                    from camoufox.virtdisplay import VirtualDisplay  # type: ignore[import-not-found, missing-import]

                    logger.info(f"[BrowserLauncher] Launching Camoufox for profile '{profile_id}' (User-Agent: {ua})")
                    user_data_dir = self.profile_manager.get_user_data_dir(profile_id)
                    os.makedirs(user_data_dir, exist_ok=True)

                    screen_obj = None
                    w_res, h_res = 1920, 1080
                    try:
                        w_res, h_res = map(int, res_str.split("x"))
                        from browserforge.fingerprints import Screen
                        screen_obj = Screen(min_width=w_res, max_width=w_res, min_height=h_res, max_height=h_res)
                    except Exception:
                        pass

                    custom_ua_enabled = profile.get("custom_user_agent", False)
                    camou_config: Dict[str, Any] = {}
                    if custom_ua_enabled and ua:
                        camou_config["navigator.userAgent"] = ua
                        ff_prefs["general.useragent.override"] = ua

                    # Dynamic Custom User-Agent & Essential Preferences writing to profile user.js
                    try:
                        user_js_path = os.path.join(user_data_dir, "user.js")
                        existing_lines = []
                        if os.path.exists(user_js_path):
                            with open(user_js_path, "r", encoding="utf-8") as f_r:
                                existing_lines = f_r.readlines()
                        managed_keys = [
                            "general.useragent.override",
                            "browser.startup.page",
                            "browser.startup.homepage",
                            "startup.homepage_welcome_url",
                            "startup.homepage_override_url",
                            "browser.sessionstore.resume_from_crash",
                            "media.eme.enabled",
                            "media.eme.clearkey.enabled",
                            "media.eme.widevine.enabled",
                            "media.gmp-widevinecdm.enabled",
                            "media.gmp-widevinecdm.visible",
                            "media.gmp-widevinecdm.autoupdate",
                            "media.gmp-manager.updateEnabled",
                            "media.gmp-gmpopenh264.enabled",
                            "media.gmp-gmpopenh264.autoupdate",
                            "media.ffmpeg.vaapi.enabled",
                            "media.rdd-ffmpeg.enabled",
                            "media.fragmented-mp4.ffmpeg.enabled",
                            "media.mediasource.enabled",
                            "media.mediasource.mp4.enabled",
                            "media.mediasource.vp9.enabled",
                            "media.autoplay.default",
                            "media.autoplay.allow-muted",
                            "media.autoplay.blocking_policy",
                            "intl.accept_languages",
                            "intl.locale.requested",
                            "roverfox.s.timezone"
                        ]
                        filtered_ujs = [l for l in existing_lines if not any(k in l for k in managed_keys)]
                        filtered_ujs.append(f'user_pref("intl.accept_languages", {json.dumps(clean_lang_str)});\n')
                        filtered_ujs.append(f'user_pref("intl.locale.requested", {json.dumps(primary_lang)});\n')
                        filtered_ujs.append(f'user_pref("roverfox.s.timezone_0", {json.dumps(tz_id)});\n')
                        filtered_ujs.append(f'user_pref("roverfox.s.timezone_1", {json.dumps(tz_id)});\n')

                        # Sanitize any stale roverfox timezone preference in existing prefs.js
                        prefs_js_path = os.path.join(user_data_dir, "prefs.js")
                        if os.path.exists(prefs_js_path):
                            try:
                                with open(prefs_js_path, "r", encoding="utf-8") as f_p:
                                    p_lines = f_p.readlines()
                                clean_p_lines = [l for l in p_lines if not l.strip().startswith('user_pref("roverfox.s.timezone_')]
                                clean_p_lines.append(f'user_pref("roverfox.s.timezone_0", {json.dumps(tz_id)});\n')
                                with open(prefs_js_path, "w", encoding="utf-8") as f_p:
                                    f_p.writelines(clean_p_lines)
                            except Exception as e_p:
                                logger.debug(f"Could not sanitize prefs.js timezone: {e_p}")
                        if custom_ua_enabled and ua:
                            filtered_ujs.append(f'user_pref("general.useragent.override", {json.dumps(ua)});\n')
                        filtered_ujs.append(f'user_pref("browser.startup.page", {3 if effective_restore else 0});\n')
                        filtered_ujs.append('user_pref("browser.startup.homepage", "about:blank");\n')
                        filtered_ujs.append('user_pref("startup.homepage_welcome_url", "about:blank");\n')
                        filtered_ujs.append('user_pref("startup.homepage_override_url", "about:blank");\n')
                        
                        # Universal video decoding
                        filtered_ujs.append('user_pref("media.ffmpeg.vaapi.enabled", false);\n')
                        filtered_ujs.append('user_pref("media.rdd-ffmpeg.enabled", true);\n')
                        filtered_ujs.append('user_pref("media.fragmented-mp4.ffmpeg.enabled", true);\n')
                        filtered_ujs.append('user_pref("media.mediasource.enabled", true);\n')
                        filtered_ujs.append('user_pref("media.mediasource.mp4.enabled", true);\n')
                        filtered_ujs.append('user_pref("media.mediasource.vp9.enabled", true);\n')
                        filtered_ujs.append('user_pref("media.gmp-gmpopenh264.enabled", true);\n')
                        filtered_ujs.append('user_pref("media.gmp-gmpopenh264.autoupdate", true);\n')
                        filtered_ujs.append('user_pref("media.gmp-manager.updateEnabled", true);\n')
                        filtered_ujs.append('user_pref("media.autoplay.default", 0);\n')
                        filtered_ujs.append('user_pref("media.autoplay.allow-muted", true);\n')
                        filtered_ujs.append('user_pref("media.autoplay.blocking_policy", 0);\n')

                        if drm_widevine:
                            filtered_ujs.append('user_pref("media.eme.enabled", true);\n')
                            filtered_ujs.append('user_pref("media.eme.clearkey.enabled", true);\n')
                            filtered_ujs.append('user_pref("media.eme.widevine.enabled", true);\n')
                            filtered_ujs.append('user_pref("media.gmp-widevinecdm.enabled", true);\n')
                            filtered_ujs.append('user_pref("media.gmp-widevinecdm.visible", true);\n')
                            filtered_ujs.append('user_pref("media.gmp-widevinecdm.autoupdate", true);\n')
                        else:
                            filtered_ujs.append('user_pref("media.eme.enabled", false);\n')
                            filtered_ujs.append('user_pref("media.eme.widevine.enabled", false);\n')
                            filtered_ujs.append('user_pref("media.gmp-widevinecdm.enabled", false);\n')

                        with open(user_js_path, "w", encoding="utf-8") as f_w:
                            f_w.writelines(filtered_ujs)
                    except Exception as ujs_err:
                        logger.debug(f"Could not write user.js startup configuration: {ujs_err}")

                    s_cfg = profile.get("stealth", {})
                    fp_engine = s_cfg.get("fp_engine", "real_presets")
                    target_os_val = profile.get("os", "windows").lower()

                    # -------------------------------------------------------------
                    # 100% Comprehensive Camoufox C++ Engine Configuration Mapping
                    # -------------------------------------------------------------
                    # 1. Screen & Window Dimensions
                    color_depth_val = int(profile.get("color_depth", 24))
                    camou_config["screen.width"] = w_res
                    camou_config["screen.height"] = h_res
                    camou_config["screen.availWidth"] = w_res
                    camou_config["screen.availHeight"] = max(100, h_res - 40)
                    camou_config["screen.colorDepth"] = color_depth_val
                    camou_config["screen.pixelDepth"] = color_depth_val

                    # 2. Hardware Concurrency & Max Touch Points
                    cpu_val = int(profile.get("hardware_concurrency", 8))
                    touch_val = int(profile.get("max_touch_points", 0))
                    camou_config["navigator.hardwareConcurrency"] = cpu_val
                    camou_config["navigator.maxTouchPoints"] = touch_val

                    # 3. Timezone (Native C++ SpiderMonkey Engine & glibc)
                    camou_config["timezone"] = tz_id
                    child_env["TZ"] = tz_id

                    # 4. Language & Locale (Pure IP Language)
                    camou_config["locale:all"] = clean_lang_str
                    camou_config["locale:language"] = primary_lang.split("-")[0]
                    camou_config["locale:region"] = primary_lang.split("-")[1] if "-" in primary_lang else ""
                    ff_prefs["intl.accept_languages"] = clean_lang_str
                    ff_prefs["intl.locale.requested"] = primary_lang
                    ff_prefs["roverfox.s.timezone_0"] = tz_id
                    ff_prefs["roverfox.s.timezone_1"] = tz_id
                    child_env["LANG"] = f"{primary_lang.replace('-', '_')}.UTF-8"

                    # 5. OS & Platform Alignment
                    if target_os_val in ["win", "windows"]:
                        camou_config["navigator.platform"] = "Win32"
                        camou_config["navigator.oscpu"] = "Windows NT 10.0; Win64; x64"
                    elif target_os_val in ["mac", "macos"]:
                        camou_config["navigator.platform"] = "MacIntel"
                        camou_config["navigator.oscpu"] = "Intel Mac OS X 10.15"
                    else:
                        camou_config["navigator.platform"] = "Linux x86_64"
                        camou_config["navigator.oscpu"] = "Linux x86_64"

                    # 6. User Agent
                    if ua:
                        camou_config["navigator.userAgent"] = ua
                        ff_prefs["general.useragent.override"] = ua

                    # 7. Do Not Track Header
                    dnt_val = str(profile.get("do_not_track", "null")).strip()
                    camou_config["navigator.doNotTrack"] = "unspecified" if dnt_val == "null" else dnt_val
                    ff_prefs["privacy.donottrackheader.enabled"] = (dnt_val == "1")
                    ff_prefs["privacy.donottrackheader.value"] = 1 if dnt_val == "1" else 0

                    # 8. Geolocation
                    if geo_dict:
                        camou_config["geolocation:latitude"] = geo_dict["latitude"]
                        camou_config["geolocation:longitude"] = geo_dict["longitude"]
                        geo_acc = geo_dict.get("accuracy")
                        camou_config["geolocation:accuracy"] = geo_acc if geo_acc is not None else 100.0

                    extra_headers: Dict[str, str] = {"Accept-Language": raw_lang}
                    if ua:
                        extra_headers["User-Agent"] = ua

                    camoufox_kwargs: Dict[str, Any] = {
                        "user_data_dir": user_data_dir,
                        "persistent_context": True,
                        "headless": "virtual" if headless else False,
                        "os": target_os_val,
                        "locale": primary_lang,
                        "timezone_id": tz_id,
                        "env": child_env,
                        "ignore_https_errors": True,
                        "firefox_user_prefs": ff_prefs,
                        "i_know_what_im_doing": True,
                        "window": (win_w, win_h),
                        "extra_http_headers": extra_headers,
                    }
                    if geo_dict:
                        camoufox_kwargs["geolocation"] = geo_dict
                        camoufox_kwargs["permissions"] = ["geolocation"]
                    if ua:
                        camoufox_kwargs["user_agent"] = ua

                    # WebRTC Protection Policy for Camoufox C++ Native Engine
                    if webrtc_mode == "disabled":
                        camoufox_kwargs["block_webrtc"] = True
                        ff_prefs["media.peerconnection.enabled"] = False
                        ff_prefs["media.peerconnection.ice.proxy_only"] = True
                    elif webrtc_mode == "real":
                        camoufox_kwargs["block_webrtc"] = False
                        ff_prefs["media.peerconnection.enabled"] = True
                        ff_prefs["media.peerconnection.ice.proxy_only"] = False
                        ff_prefs["media.peerconnection.ice.proxy_only_if_behind_proxy"] = False
                        ff_prefs["media.peerconnection.ice.obfuscate_host_addresses"] = False
                        ff_prefs["media.peerconnection.ice.default_address_only"] = False
                    else:  # "altered" -> Protocol-Level IP Spoofing (C++ Native ICE - Undetectable)
                        camoufox_kwargs["block_webrtc"] = False
                        ff_prefs["media.peerconnection.enabled"] = True
                        ff_prefs["media.peerconnection.ice.no_host"] = False  # Preserves mDNS uuid.local host candidate to match real Firefox 2-candidate shape
                        ff_prefs["media.peerconnection.ice.default_address_only"] = True
                        ff_prefs["media.peerconnection.ice.proxy_only_if_behind_proxy"] = True
                        ff_prefs["media.peerconnection.ice.proxy_only_if_pbmode"] = True
                        ff_prefs["media.peerconnection.ice.obfuscate_host_addresses"] = True
                        ff_prefs["network.proxy.socks_remote_dns"] = True

                        # Derive Spoofed WebRTC IP from Proxy exit IP or Host
                        target_webrtc_ip = ""
                        if proxy_cfg.get("enabled"):
                            target_webrtc_ip = str(proxy_info.get("ip") or proxy_cfg.get("host") or "").strip()

                        if target_webrtc_ip and target_webrtc_ip not in ["127.0.0.1", "localhost", "0.0.0.0"]:
                            camou_config["webrtc:ipv4"] = target_webrtc_ip
                            ff_prefs["network.dns.disableIPv6"] = True
                            logger.info(f"[BrowserLauncher] Configured Protocol-Level WebRTC C++ ICE IP Spoofing for '{profile_id}': {target_webrtc_ip}")
                    
                    # -------------------------------------------------------------
                    # C++ Native Anti-Fingerprinting (Deterministic Seeds, Fonts & Audio)
                    # -------------------------------------------------------------
                    target_os_norm = profile.get("os", "windows").lower()
                    seed_str_val = str(s_cfg.get("noise_seed") or profile_id).strip()

                    camou_seeds = FingerprintGenerator.derive_camoufox_seeds(profile, profile_id)
                    for s_k, s_v in camou_seeds.items():
                        camou_config[s_k] = s_v

                    # Font Spoofing & OS Isolation
                    camou_fonts = FingerprintGenerator.get_deterministic_camoufox_fonts(
                        target_os=target_os_norm,
                        seed_str=seed_str_val,
                        locale=primary_lang
                    )
                    if camou_fonts:
                        camoufox_kwargs["fonts"] = camou_fonts

                    # Audio Speech Synthesis Voices Spoofing
                    camou_voices = FingerprintGenerator.get_deterministic_camoufox_voices(
                        target_os=target_os_norm,
                        seed_str=seed_str_val,
                        locale=primary_lang
                    )
                    if camou_voices and "voices" not in camou_config:
                        camou_config["voices"] = camou_voices

                    if "voices" in camou_config and isinstance(camou_config["voices"], list):
                        sanitized_voices = []
                        for v in camou_config["voices"]:
                            if isinstance(v, dict):
                                voice_entry = dict(v)
                                if "voiceUri" not in voice_entry and "voiceURI" in voice_entry:
                                    voice_entry["voiceUri"] = voice_entry["voiceURI"]
                                if "isDefault" not in voice_entry:
                                    voice_entry["isDefault"] = voice_entry.get("default", False)
                                if "isLocalService" not in voice_entry:
                                    voice_entry["isLocalService"] = voice_entry.get("localService", True)
                                sanitized_voices.append(voice_entry)
                            else:
                                sanitized_voices.append(v)
                        camou_config["voices"] = sanitized_voices

                    # Headless Device Realism (mediaDevices enumeration)
                    if not any(k.startswith("mediaDevices:") for k in camou_config):
                        camou_config["mediaDevices:enabled"] = True
                        camou_config["mediaDevices:micros"] = 1
                        camou_config["mediaDevices:webcams"] = 1
                        camou_config["mediaDevices:speakers"] = 0

                    if fp_engine == "real_presets":
                        camoufox_kwargs["fingerprint_preset"] = True
                        # Guard against Camoufox's bundled 8800 GTX preset on Linux
                        if target_os_val in ["linux", "lin"]:
                            camoufox_kwargs["webgl_config"] = ("NVIDIA Corporation", "NVIDIA GeForce GTX 980, or similar")

                    if custom_ua_enabled and ua:
                        camoufox_kwargs["user_agent"] = ua
                        camoufox_kwargs["extra_http_headers"] = {"User-Agent": ua}

                    # Addons & Extensions for Camoufox
                    ext_unpacked_dirs = self.prepare_extensions(profile.get("extensions", []), user_data_dir=user_data_dir)
                    if ext_unpacked_dirs:
                        camoufox_kwargs["addons"] = ext_unpacked_dirs
                        camou_config["addons"] = ext_unpacked_dirs
                        logger.info(f"[BrowserLauncher] Configured {len(ext_unpacked_dirs)} extension(s) in Camoufox: {ext_unpacked_dirs}")

                    if camou_config:
                        camoufox_kwargs["config"] = camou_config
                    if screen_obj:
                        camoufox_kwargs["screen"] = screen_obj
                    if proxy_dict and "server" in proxy_dict:
                        camoufox_kwargs["proxy"] = proxy_dict
                        camoufox_kwargs["geoip"] = False
                    self._cleanup_orphaned_profile_processes(user_data_dir, engine_type="camoufox")
                    context = None

                    async def _start_camoufox_safely(kwargs: Dict[str, Any]) -> Any:
                        nonlocal user_data_dir
                        import copy
                        # Deepcopy kwargs so in-place mutations by Camoufox launch_options do not corrupt retries
                        base_kwargs = copy.deepcopy(kwargs)
                        if "timezone" in base_kwargs:
                            tz_val = base_kwargs.pop("timezone")
                            if tz_val and "timezone_id" not in base_kwargs:
                                base_kwargs["timezone_id"] = tz_val

                        # Attempt 1: Standard launch with profile preset
                        try:
                            attempt_kwargs = copy.deepcopy(base_kwargs)
                            inst = AsyncCamoufox(**attempt_kwargs)
                            ctx = await inst.start()
                            return ctx or getattr(inst, "browser", None)
                        except Exception as first_err:
                            err_str = str(first_err)
                            if not any(k in err_str.lower() for k in ["webgl", "fingerprint", "preset", "vendor", "renderer", "timezone"]):
                                raise first_err
                            logger.warning(f"[BrowserLauncher] Camoufox launch note ({first_err}). Retrying with safe fingerprint config...")

                        # Attempt 2: Disable fingerprint_preset and sanitize any WebGL config
                        self._cleanup_orphaned_profile_processes(user_data_dir, engine_type="camoufox")
                        retry_kwargs = copy.deepcopy(base_kwargs)
                        retry_kwargs.pop("fingerprint_preset", None)
                        retry_kwargs.pop("webgl_config", None)
                        retry_kwargs.pop("timezone", None)
                        if "config" in retry_kwargs and isinstance(retry_kwargs["config"], dict):
                            # Remove all WebGL vendor/renderer overrides (handling all casing variants)
                            cfg_clean = {k: v for k, v in retry_kwargs["config"].items() if not k.lower().startswith("webgl")}
                            retry_kwargs["config"] = cfg_clean

                        try:
                            inst = AsyncCamoufox(**retry_kwargs)
                            ctx = await inst.start()
                            return ctx or getattr(inst, "browser", None)
                        except Exception as second_err:
                            logger.warning(f"[BrowserLauncher] Camoufox retry note ({second_err}). Retrying with verified WebGL pair...")

                        # Attempt 3: Provide explicit verified WebGL pair from database
                        self._cleanup_orphaned_profile_processes(user_data_dir, engine_type="camoufox")
                        safe_kwargs = copy.deepcopy(retry_kwargs)
                        target_os = str(safe_kwargs.get("os", "windows")).lower()
                        if target_os in ["linux", "lin"]:
                            safe_kwargs["webgl_config"] = ("NVIDIA Corporation", "NVIDIA GeForce GTX 980, or similar")
                        elif target_os in ["macos", "mac"]:
                            safe_kwargs["webgl_config"] = ("Apple", "Apple M1")
                        else:
                            safe_kwargs["webgl_config"] = ("Google Inc. (NVIDIA)", "ANGLE (NVIDIA, NVIDIA GeForce GTX 1060 6GB Direct3D11 vs_5_0 ps_5_0), or similar")

                        try:
                            inst = AsyncCamoufox(**safe_kwargs)
                            ctx = await inst.start()
                            return ctx or getattr(inst, "browser", None)
                        except Exception as third_err:
                            logger.warning(f"[BrowserLauncher] Camoufox fallback note ({third_err}). Retrying with block_webgl=True...")
                            self._cleanup_orphaned_profile_processes(user_data_dir, engine_type="camoufox")
                            final_kwargs = copy.deepcopy(safe_kwargs)
                            final_kwargs.pop("webgl_config", None)
                            final_kwargs["block_webgl"] = True
                            inst = AsyncCamoufox(**final_kwargs)
                            ctx = await inst.start()
                            return ctx or getattr(inst, "browser", None)

                    try:
                        if camoufox_bin:
                            try:
                                camoufox_kwargs["executable_path"] = camoufox_bin
                                context = await _start_camoufox_safely(camoufox_kwargs)
                            except Exception as bin_err:
                                logger.warning(f"Custom Camoufox binary launch failed ({bin_err}). Retrying with native Camoufox engine...")
                                self._cleanup_orphaned_profile_processes(user_data_dir, engine_type="camoufox")
                                camoufox_kwargs.pop("executable_path", None)
                                context = await _start_camoufox_safely(camoufox_kwargs)
                        else:
                            context = await _start_camoufox_safely(camoufox_kwargs)
                    except Exception as ex:
                        if "not installed" in str(ex).lower() or "camoufox fetch" in str(ex).lower() or "process did exit" in str(ex).lower():
                            from engine.sandbox.sandbox_installer import SandboxInstaller
                            await SandboxInstaller.ensure_camoufox_installed()
                            self._cleanup_orphaned_profile_processes(user_data_dir, engine_type="camoufox")
                            camoufox_kwargs.pop("executable_path", None)
                            context = await _start_camoufox_safely(camoufox_kwargs)
                        else:
                            raise ex

                    # Ensure context is an active BrowserContext (not raw Browser object)
                    if hasattr(context, "contexts"):
                        if getattr(context, "contexts"):
                            context = getattr(context, "contexts")[0]
                        elif hasattr(context, "new_context") and callable(getattr(context, "new_context")):
                            context = await context.new_context()

                    if not context:
                        return False, "Failed to initialize Camoufox browser context.", None

                    self.active_contexts[profile_id] = context
                    if custom_ua_enabled and ua and hasattr(context, "set_extra_http_headers"):
                        try:
                            await context.set_extra_http_headers({"User-Agent": ua})
                        except Exception:
                            pass
                    await self._inject_cookies_for_profile(profile_id, context)
                    
                    # In-Browser Login Assistant HUD & Native Timezone Assertion
                    try:
                        if hasattr(context, "add_init_script"):
                            await context.add_init_script(f'try {{ if (typeof window.setTimezone === "function") window.setTimezone({json.dumps(tz_id)}); }} catch(e) {{}}')
                        accs = profile.get("accounts", [])
                        if accs:
                            from engine.account_manager import AccountManager
                            hud_js = AccountManager.generate_in_browser_hud_script(accs)
                            if hud_js and hasattr(context, "add_init_script"):
                                await context.add_init_script(hud_js)
                    except Exception as init_err:
                        logger.debug(f"[BrowserLauncher] Notice on Camoufox init script injection: {init_err}")

                    try:
                        ctx_obj: Any = context
                        pages_list = getattr(ctx_obj, "pages", [])
                        p_start = pages_list[0] if pages_list else await ctx_obj.new_page()
                        try:
                            await p_start.set_viewport_size({"width": win_w, "height": win_h})
                            await p_start.evaluate(f"window.moveTo({win_x}, {win_y}); window.resizeTo({win_w}, {win_h});")
                            await p_start.evaluate(f"if (typeof window.setTimezone === 'function') window.setTimezone({json.dumps(tz_id)});");
                        except Exception:
                            pass
                        if navigate_start_url and start_url:
                            try:
                                cur_url = getattr(p_start, "url", "")
                                if not cur_url or cur_url in ["about:blank", "about:home", "about:newtab", "chrome://browser/content/blanktab.html"]:
                                    await self._safe_goto(p_start, start_url)
                                asyncio.create_task(self._handle_profile_auto_logins(profile, p_start))
                            except Exception as e_nav:
                                logger.debug(f"[BrowserLauncher] Camoufox startup navigation notice: {e_nav}")
                        else:
                            cur_url = getattr(p_start, "url", "")
                            if cur_url and not any(cur_url.startswith(pref) for pref in ["about:", "chrome:", "edge:"]):
                                try:
                                    await p_start.reload()
                                except Exception:
                                    pass
                    except Exception as nav_err:
                        logger.warning(f"Camoufox initial navigation warning: {nav_err}")

                    profile["status"] = "Running"
                    profile["last_launch"] = asyncio.get_running_loop().time()
                    self.profile_manager.save_profile(profile)

                    if hasattr(context, "on"):
                        context.on("close", lambda ctx: asyncio.create_task(self._handle_context_closed(profile_id)))
                    self._start_continuous_cookie_sync(profile_id, context)
                    logger.info(f"Profile '{profile_id}' launched successfully via Camoufox C++ Engine ({start_url}).")
                    return True, "Profile launched successfully (Camoufox C++ Engine).", context

                # Fallback: Playwright Firefox with custom executable if binary present
                pw = await self._ensure_playwright()
                ff_args: Dict[str, Any] = {
                    "user_data_dir": user_data_dir,
                    "headless": bool(headless),
                    "user_agent": ua,
                    "locale": primary_lang,
                    "timezone_id": tz_id,
                    "geolocation": geo_dict,
                    "permissions": permissions_list,
                    "proxy": proxy_dict,
                    "firefox_user_prefs": ff_prefs,
                    "ignore_https_errors": True,
                    "no_viewport": True,
                    "env": child_env
                }
                if camoufox_bin:
                    ff_args["executable_path"] = camoufox_bin

                context = await pw.firefox.launch_persistent_context(**ff_args)
                self.active_contexts[profile_id] = context
                await self._inject_cookies_for_profile(profile_id, context)
                
                # Inject W3C Standard EME, DRM & Anti-Detect Compatibility Layer + In-Browser Login Assistant HUD
                try:
                    drm_init_js = FingerprintGenerator.generate_stealth_script(profile, target_timezone=tz_id)
                    if hasattr(context, "add_init_script"):
                        await context.add_init_script(drm_init_js)
                        accs = profile.get("accounts", [])
                        if accs:
                            from engine.account_manager import AccountManager
                            hud_js = AccountManager.generate_in_browser_hud_script(accs)
                            if hud_js:
                                await context.add_init_script(hud_js)
                except Exception as init_err:
                    logger.debug(f"[BrowserLauncher] Notice on Playwright Firefox init script injection: {init_err}")
                try:
                    ctx_obj: Any = context
                    pages_list = getattr(ctx_obj, "pages", [])
                    p_start = pages_list[0] if pages_list else await ctx_obj.new_page()
                    if navigate_start_url and start_url:
                        try:
                            await self._safe_goto(p_start, start_url)
                            asyncio.create_task(self._handle_profile_auto_logins(profile, p_start))
                        except Exception as e_nav:
                            logger.debug(f"[BrowserLauncher] Playwright Firefox startup navigation notice: {e_nav}")
                    else:
                        cur_url = getattr(p_start, "url", "")
                        if cur_url and not any(cur_url.startswith(pref) for pref in ["about:", "chrome:", "edge:"]):
                            try:
                                await p_start.reload()
                            except Exception:
                                pass
                except Exception as nav_err:
                    logger.warning(f"Playwright initial navigation warning: {nav_err}")

                profile["status"] = "Running"
                profile["last_launch"] = asyncio.get_running_loop().time()
                self.profile_manager.save_profile(profile)

                if hasattr(context, "on"):
                    context.on("close", lambda ctx: asyncio.create_task(self._handle_context_closed(profile_id)))
                self._start_continuous_cookie_sync(profile_id, context)
                logger.info(f"Profile '{profile_id}' launched successfully via Playwright Firefox ({start_url}).")
                return True, "Profile launched successfully (Playwright Firefox).", context

            except Exception as e:
                logger.error(f"Failed to launch profile {profile_id} via Camoufox: {e}")
                profile["status"] = "Error"
                self.profile_manager.save_profile(profile)
                return False, f"Camoufox launch error: {str(e)}", None

        # Branch 1: Nodriver Stealth CDP Launch Path (Optional Engine)
        if engine_type == "nodriver":
            try:
                from engine.engine_security_advisor import EngineSecurityAdvisor
                EngineSecurityAdvisor.emit_startup_warnings("nodriver", profile_id)
            except Exception:
                pass
            try:
                self._ensure_chromium_webrtc_preferences(user_data_dir, webrtc_mode)
                import nodriver as uc

                browser_args = [
                    f"--user-agent={ua}",
                    f"--lang={primary_lang}",
                    f"--window-size={res_str.replace('x', ',')}",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--remote-allow-origins=*"
                ]
                # Enforce non-incognito profile persistence for Nodriver
                nd_chromium_args = [arg for arg in chromium_args if arg not in ["--incognito", "-incognito"]]
                for arg in nd_chromium_args:
                    if arg and arg not in browser_args:
                        browser_args.append(arg)

                if proxy_dict and "server" in proxy_dict:
                    browser_args.append(f"--proxy-server={proxy_dict['server']}")

                try:
                    browser = await uc.start(
                        user_data_dir=user_data_dir,
                        browser_args=browser_args,
                        sandbox=False,
                        headless=bool(headless)
                    )
                except Exception as uc_err:
                    logger.warning(f"Nodriver uc.start direct spawn notice ({uc_err}). Connecting via CDP port {debug_port}...")
                    try:
                        connect_fn: Any = getattr(uc, "connect", None)
                        if callable(connect_fn):
                            browser = await cast(Any, connect_fn(port=debug_port))
                        else:
                            browser = await uc.start(port=debug_port, browser_args=browser_args, sandbox=False, headless=bool(headless))
                    except Exception as conn_err:
                        raise Exception(f"Nodriver launch failed: {uc_err} | CDP Connect error: {conn_err}")

                if not browser:
                    return False, "Failed to launch Nodriver instance.", None

                self.active_contexts[profile_id] = browser
                await self._inject_cookies_for_profile(profile_id, browser)

                page = browser.main_tab
                if page:
                    stealth_js = FingerprintGenerator.generate_stealth_script(profile, target_timezone=tz_id)
                    os_name = profile.get("os", "windows")
                    cdp_platform = "Win32" if os_name == "windows" else ("MacIntel" if os_name == "mac" else "Linux x86_64")
                    cdp_os_brand = "Windows" if os_name == "windows" else ("macOS" if os_name == "mac" else "Linux")
                    ver_match = re.search(r"Chrome/(\d+)\.(\d+\.\d+\.\d+)", ua)
                    major_ver = ver_match.group(1) if ver_match else "131"
                    full_ver = f"{major_ver}.0.0.0" if ver_match else "131.0.0.0"

                    async def configure_nodriver_page(p):
                        try:
                            await p.send(uc.cdp.page.enable())
                        except Exception:
                            pass
                        try:
                            await p.send(uc.cdp.emulation.set_timezone_override(timezone_id=tz_id))
                        except Exception:
                            pass
                        if geo_dict:
                            try:
                                await p.send(uc.cdp.emulation.set_geolocation_override(
                                    latitude=geo_dict["latitude"],
                                    longitude=geo_dict["longitude"],
                                    accuracy=geo_dict["accuracy"]
                                ))
                            except Exception:
                                pass
                        try:
                            await p.send(uc.cdp.emulation.set_user_agent_override(
                                user_agent=ua,
                                accept_language=accept_langs,
                                platform=cdp_platform,
                                user_agent_metadata=uc.cdp.emulation.UserAgentMetadata(
                                    brands=[
                                        uc.cdp.emulation.UserAgentBrandVersion(brand='Chromium', version=major_ver),
                                        uc.cdp.emulation.UserAgentBrandVersion(brand='Google Chrome', version=major_ver),
                                        uc.cdp.emulation.UserAgentBrandVersion(brand='Not-A.Brand', version='99')
                                    ],
                                    full_version_list=[
                                        uc.cdp.emulation.UserAgentBrandVersion(brand='Chromium', version=full_ver),
                                        uc.cdp.emulation.UserAgentBrandVersion(brand='Google Chrome', version=full_ver),
                                        uc.cdp.emulation.UserAgentBrandVersion(brand='Not-A.Brand', version='99.0.0.0')
                                    ],
                                    full_version=full_ver,
                                    platform=cdp_os_brand,
                                    platform_version='10.0.0' if os_name == 'windows' else ('14.4.1' if os_name == 'mac' else '6.5.0'),
                                    architecture='x86',
                                    model='',
                                    mobile=False,
                                    bitness='64'
                                )
                            ))
                        except Exception:
                            pass
                        try:
                            await p.send(uc.cdp.page.add_script_to_evaluate_on_new_document(source=stealth_js))
                        except Exception:
                            pass

                    # Configure all initial tabs
                    try:
                        for tab in getattr(browser, 'tabs', [page]):
                            asyncio.create_task(configure_nodriver_page(tab))
                    except Exception:
                        await configure_nodriver_page(page)

                    # Attach handler for newly created tabs/windows in Nodriver
                    async def on_nodriver_target_created(event: uc.cdp.target.TargetCreated):
                        try:
                            if getattr(event.target_info, 'type_', '') == "page":
                                t_id = getattr(event.target_info, 'target_id', None)
                                if t_id and hasattr(browser, 'targets'):
                                    for target in browser.targets:
                                        if getattr(getattr(target, 'target', None), 'target_id', None) == t_id:
                                            await configure_nodriver_page(target)
                                            break
                        except Exception:
                            pass

                    try:
                        if hasattr(browser, 'connection') and browser.connection:
                            browser.connection.add_handler(uc.cdp.target.TargetCreated, on_nodriver_target_created)
                            await browser.send(uc.cdp.target.set_discover_targets(discover=True))
                    except Exception as e:
                        logger.warning(f"Error attaching TargetCreated handler in Nodriver: {e}")

                if page and navigate_start_url and start_url:
                    try:
                        await page.get(start_url)
                        asyncio.create_task(self._handle_profile_auto_logins(profile, page))
                    except Exception as e_nav:
                        logger.debug(f"[BrowserLauncher] Nodriver startup navigation notice: {e_nav}")

                profile["status"] = "Running"
                profile["last_launch"] = asyncio.get_running_loop().time()
                self.profile_manager.save_profile(profile)

                async def _monitor_nodriver_close():
                    import psutil
                    b_proc = getattr(browser, 'process', None)
                    b_pid = getattr(b_proc, 'pid', None) if b_proc else None
                    while profile_id in self.active_contexts:
                        await asyncio.sleep(1.5)
                        try:
                            if b_proc and b_proc.poll() is not None:
                                break
                            if b_pid and not psutil.pid_exists(b_pid):
                                break
                        except Exception:
                            pass
                    await self._handle_context_closed(profile_id)

                asyncio.create_task(_monitor_nodriver_close())
                self._start_continuous_cookie_sync(profile_id, browser)
                logger.info(f"Profile '{profile_id}' launched successfully via Nodriver ({start_url}).")
                return True, "Profile launched successfully (Nodriver).", browser

            except Exception as e:
                logger.error(f"Failed to launch profile {profile_id} via Nodriver: {e}")
                profile["status"] = "Error"
                self.profile_manager.save_profile(profile)
                return False, str(e), None

        # Branch 2: Selenium Driverless Launch Path (Optional Engine – Legacy)
        if engine_type == "selenium_driverless":
            try:
                from engine.engine_security_advisor import EngineSecurityAdvisor
                EngineSecurityAdvisor.emit_startup_warnings("selenium_driverless", profile_id)
            except Exception:
                pass
            try:
                self._ensure_chromium_webrtc_preferences(user_data_dir, webrtc_mode)
                from selenium_driverless import webdriver
                options: Any = cast(Any, webdriver.ChromeOptions)()
                options.user_data_dir = user_data_dir

                # Enforce non-incognito profile persistence for Selenium Driverless
                sd_args = [arg for arg in chromium_args if arg not in ["--incognito", "-incognito"]]
                for arg in sd_args:
                    options.add_argument(arg)

                options.add_argument("--no-sandbox")
                options.add_argument("--disable-setuid-sandbox")
                options.add_argument("--remote-allow-origins=*")

                if proxy_dict and "server" in proxy_dict:
                    options.add_argument(f"--proxy-server={proxy_dict['server']}")

                if headless:
                    options.add_argument("--headless=new")

                driver = await webdriver.Chrome(options=options)
                self.active_contexts[profile_id] = driver
                await self._inject_cookies_for_profile(profile_id, driver)

                stealth_js = FingerprintGenerator.generate_stealth_script(profile, target_timezone=tz_id)
                os_name = profile.get("os", "windows")
                cdp_platform = "Win32" if os_name == "windows" else ("MacIntel" if os_name == "mac" else "Linux x86_64")
                cdp_os_brand = "Windows" if os_name == "windows" else ("macOS" if os_name == "mac" else "Linux")
                ver_match = re.search(r"Chrome/(\d+)\.(\d+\.\d+\.\d+)", ua)
                major_ver = ver_match.group(1) if ver_match else "131"
                full_ver = f"{major_ver}.0.0.0" if ver_match else "131.0.0.0"

                async def configure_sd_target(target):
                    try:
                        await target.execute_cdp_cmd("Page.enable", {})
                    except Exception:
                        pass
                    try:
                        await target.execute_cdp_cmd("Emulation.setTimezoneOverride", {"timezoneId": tz_id})
                    except Exception:
                        pass
                    if geo_dict:
                        try:
                            await target.execute_cdp_cmd("Emulation.setGeolocationOverride", {
                                "latitude": geo_dict["latitude"],
                                "longitude": geo_dict["longitude"],
                                "accuracy": geo_dict["accuracy"]
                            })
                        except Exception:
                            pass
                    try:
                        await target.execute_cdp_cmd("Emulation.setUserAgentOverride", {
                            'userAgent': ua,
                            'acceptLanguage': accept_langs,
                            'platform': cdp_platform,
                            'userAgentMetadata': {
                                'brands': [
                                    {'brand': 'Chromium', 'version': major_ver},
                                    {'brand': 'Google Chrome', 'version': major_ver},
                                    {'brand': 'Not-A.Brand', 'version': '99'}
                                ],
                                'fullVersionList': [
                                    {'brand': 'Chromium', 'version': full_ver},
                                    {'brand': 'Google Chrome', 'version': full_ver},
                                    {'brand': 'Not-A.Brand', 'version': '99.0.0.0'}
                                ],
                                'fullVersion': full_ver,
                                'platform': cdp_os_brand,
                                'platformVersion': '10.0.0' if os_name == 'windows' else ('14.4.1' if os_name == 'mac' else '6.5.0'),
                                'architecture': 'x86',
                                'model': '',
                                'mobile': False,
                                'bitness': '64'
                            }
                        })
                    except Exception:
                        pass
                    try:
                        await target.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {"source": stealth_js})
                    except Exception:
                        pass
                    try:
                        await target.execute_cdp_cmd("Runtime.evaluate", {"expression": stealth_js, "includeCommandLineAPI": True})
                    except Exception:
                        pass

                # Apply to initial page targets
                try:
                    active_targets = await driver.targets
                    if isinstance(active_targets, dict):
                        for tid, t_info in active_targets.items():
                            if getattr(t_info, 'type', '') == 'page':
                                t_obj = await driver.get_target(tid)
                                if t_obj:
                                    await configure_sd_target(t_obj)
                except Exception as e:
                    logger.warning(f"Error configuring initial SD targets: {e}")

                # Listen for any newly created tabs/windows/targets
                async def on_sd_target_created(event):
                    try:
                        t_info = event.get("targetInfo", {})
                        if t_info.get("type") == "page":
                            t_id = t_info.get("targetId")
                            if t_id:
                                t = await driver.get_target(t_id)
                                if t:
                                    await configure_sd_target(t)
                    except Exception:
                        pass

                try:
                    await driver.add_cdp_listener("Target.targetCreated", on_sd_target_created)
                    await driver.execute_cdp_cmd("Target.setDiscoverTargets", {"discover": True})
                except Exception as e:
                    logger.warning(f"Error attaching Target.targetCreated listener in SD: {e}")

                if navigate_start_url and start_url:
                    try:
                        if hasattr(driver, "get"):
                            await driver.get(start_url)
                        asyncio.create_task(self._handle_profile_auto_logins(profile, driver))
                    except Exception as nav_err:
                        logger.debug(f"[BrowserLauncher] SD start_url navigation notice: {nav_err}")

                profile["status"] = "Running"
                profile["last_launch"] = asyncio.get_running_loop().time()
                self.profile_manager.save_profile(profile)

                async def _monitor_sd_close():
                    import psutil
                    b_pid = getattr(driver, "browser_pid", None)
                    while profile_id in self.active_contexts:
                        await asyncio.sleep(1.5)
                        try:
                            if b_pid and not psutil.pid_exists(b_pid):
                                break
                        except Exception:
                            break
                    await self._handle_context_closed(profile_id)

                asyncio.create_task(_monitor_sd_close())
                self._start_continuous_cookie_sync(profile_id, driver)
                logger.info(f"Profile '{profile_id}' launched successfully via Selenium Driverless ({start_url}).")
                return True, "Profile launched successfully (Selenium Driverless).", driver

            except Exception as e:
                logger.error(f"Failed to launch profile {profile_id} via Selenium Driverless: {e}")
                profile["status"] = "Error"
                self.profile_manager.save_profile(profile)
                return False, str(e), None

        # Branch 3: Playwright Launch Path (Optional Engine – Default Chromium fallback)
        # Emits security warning since Playwright Chromium uses --no-sandbox.
        try:
            try:
                from engine.engine_security_advisor import EngineSecurityAdvisor
                EngineSecurityAdvisor.emit_startup_warnings("playwright", profile_id)
            except Exception:
                pass
            self._ensure_chromium_webrtc_preferences(user_data_dir, webrtc_mode)
            pw = await self._ensure_playwright()

            pw_kwargs: Dict[str, Any] = {
                "user_data_dir": user_data_dir,
                "headless": bool(headless),
                "user_agent": ua,
                "locale": primary_lang,
                "timezone_id": tz_id,
                "geolocation": geo_dict,
                "permissions": permissions_list,
                "args": chromium_args,
                "ignore_default_args": ["--enable-automation"],
                "proxy": proxy_dict,
                "no_viewport": True,
                "env": child_env
            }

            detected_chrome = PlatformHelper.find_chromium_binary(config.BASE_DIR)
            if detected_chrome:
                pw_kwargs["executable_path"] = detected_chrome

            if "executable_path" in pw_kwargs and pw_kwargs["executable_path"]:
                try:
                    ChromiumBinaryPatcher.patch_binary(pw_kwargs["executable_path"], backup=False)
                except Exception as patch_err:
                    logger.debug(f"[BrowserLauncher] Notice on binary patch check: {patch_err}")

            try:
                context = await pw.chromium.launch_persistent_context(**pw_kwargs)
            except Exception as pw_err:
                if "executable doesn't exist" in str(pw_err).lower() or "playwright install" in str(pw_err).lower():
                    logger.info("[BrowserLauncher] Playwright Chromium binary missing, auto-downloading...")
                    proc_inst = await asyncio.create_subprocess_exec(
                        sys.executable, "-m", "playwright", "install", "chromium",
                        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                    )
                    await proc_inst.communicate()
                    pw_kwargs.pop("executable_path", None)
                    context = await pw.chromium.launch_persistent_context(**pw_kwargs)
                else:
                    raise pw_err

            if not context:
                return False, "Failed to launch Playwright Chromium context instance.", None

            self.active_contexts[profile_id] = context
            await self._inject_cookies_for_profile(profile_id, context)

            # Inject Anti-Detect Stealth Script & In-Browser Login Assistant HUD on new documents
            stealth_js = FingerprintGenerator.generate_stealth_script(profile, target_timezone=tz_id)
            await context.add_init_script(stealth_js)
            accs = profile.get("accounts", [])
            if accs:
                from engine.account_manager import AccountManager
                hud_js = AccountManager.generate_in_browser_hud_script(accs)
                if hud_js:
                    await context.add_init_script(hud_js)

            # CDP User-Agent & Client Hints Override for OS alignment across current & newly opened tabs
            os_name = profile.get("os", "windows")
            cdp_platform = "Win32" if os_name == "windows" else ("MacIntel" if os_name == "mac" else "Linux x86_64")
            cdp_os_brand = "Windows" if os_name == "windows" else ("macOS" if os_name == "mac" else "Linux")
            
            ver_match = re.search(r"Chrome/(\d+)\.(\d+\.\d+\.\d+)", ua)
            major_ver = ver_match.group(1) if ver_match else "131"
            full_ver = f"{major_ver}.0.0.0" if ver_match else "131.0.0.0"

            async def apply_cdp_overrides(page: Page):
                try:
                    cdp = await context.new_cdp_session(page)
                    await cdp.send('Emulation.setUserAgentOverride', {
                        'userAgent': ua,
                        'acceptLanguage': accept_langs,
                        'platform': cdp_platform,
                        'userAgentMetadata': {
                            'brands': [
                                {'brand': 'Chromium', 'version': major_ver},
                                {'brand': 'Google Chrome', 'version': major_ver},
                                {'brand': 'Not-A.Brand', 'version': '99'}
                            ],
                            'fullVersionList': [
                                {'brand': 'Chromium', 'version': full_ver},
                                {'brand': 'Google Chrome', 'version': full_ver},
                                {'brand': 'Not-A.Brand', 'version': '99.0.0.0'}
                            ],
                            'fullVersion': full_ver,
                            'platform': cdp_os_brand,
                            'platformVersion': '10.0.0' if os_name == 'windows' else ('14.4.1' if os_name == 'mac' else '6.5.0'),
                            'architecture': 'x86',
                            'model': '',
                            'mobile': False,
                            'bitness': '64'
                        }
                    })
                except Exception as e:
                    logger.warning(f"Failed to set UserAgentOverride CDP on page: {e}")

            for p in context.pages:
                asyncio.create_task(apply_cdp_overrides(p))

            context.on("page", lambda p: asyncio.create_task(apply_cdp_overrides(p)))

            try:
                ctx_obj: Any = context
                pages_list = getattr(ctx_obj, "pages", [])
                p_start = pages_list[0] if pages_list else await ctx_obj.new_page()
                if navigate_start_url and start_url:
                    try:
                        await self._safe_goto(p_start, start_url)
                        asyncio.create_task(self._handle_profile_auto_logins(profile, p_start))
                    except Exception as e_nav:
                        logger.debug(f"[BrowserLauncher] Playwright Chromium startup navigation notice: {e_nav}")
                else:
                    cur_url = getattr(p_start, "url", "")
                    if cur_url and not any(cur_url.startswith(pref) for pref in ["about:", "chrome:", "edge:"]):
                        try:
                            await p_start.reload()
                        except Exception:
                            pass
            except Exception as nav_err:
                logger.warning(f"Playwright initial navigation warning: {nav_err}")

            # Update Profile Status
            profile["status"] = "Running"
            profile["last_launch"] = asyncio.get_running_loop().time()
            self.profile_manager.save_profile(profile)

            # Register close event listener to handle window closure automatically
            def on_close(ctx):
                asyncio.create_task(self._handle_context_closed(profile_id))

            context.on("close", on_close)
            self._start_continuous_cookie_sync(profile_id, context)

            logger.info(f"Profile '{profile_id}' launched successfully via Playwright.")
            return True, "Profile launched successfully (Playwright).", context

        except Exception as e:
            logger.error(f"Failed to launch browser profile {profile_id} via Playwright: {e}")
            profile["status"] = "Error"
            self.profile_manager.save_profile(profile)
            return False, str(e), None

    def _start_continuous_cookie_sync(self, profile_id: str, context: Any):
        """Spawns an async periodic background worker that continuously syncs cookies during active browsing."""
        async def _cookie_sync_loop():
            # Initial grace period: let startup navigation and initial page load settle
            await asyncio.sleep(5.0)
            while profile_id in self.active_contexts:
                try:
                    await asyncio.sleep(3.0)
                    if profile_id not in self.active_contexts:
                        break
                    await self._sync_cookies_for_profile(profile_id, context)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.debug(f"[BrowserLauncher] Continuous cookie sync note for {profile_id}: {e}")
        asyncio.create_task(_cookie_sync_loop())

    async def _handle_profile_auto_logins(self, profile: Dict[str, Any], page: Any):
        """Executes automated stealth login assistance for accounts configured with auto_login_on_launch."""
        accounts = profile.get("accounts", [])
        if not accounts or not page:
            return

        profile_id = profile.get("id", "")
        context = self.active_contexts.get(profile_id)

        from engine.account_manager import AccountManager
        for acc in accounts:
            if acc.get("auto_login_on_launch"):
                try:
                    await asyncio.sleep(1.2)
                    # Check if already authenticated before triggering login flow
                    if context and await AccountManager.is_account_authenticated(context, acc):
                        logger.info(f"[AccountManager] Session active for {acc.get('name')}. Skipping startup login automation.")
                        continue
                    success = await AccountManager.perform_account_login(page, acc)
                    if success and profile_id and context:
                        # Immediately sync cookies after login assistance
                        await asyncio.sleep(1.5)
                        await self._sync_cookies_for_profile(profile_id, context)
                except Exception as e:
                    logger.debug(f"[BrowserLauncher] Auto-login notice for {acc.get('name')}: {e}")

    async def _inject_cookies_for_profile(self, profile_id: str, context: Any) -> int:
        """Injects all valid cookies into the runtime browser context immediately upon launch before navigation."""
        from engine.cookie_manager import CookieManager
        prof_path = self.profile_manager.get_profile_path(profile_id)
        cookie_json_path = os.path.join(prof_path, "cookies.json")
        
        if not os.path.exists(cookie_json_path):
            return 0

        raw_cookies = CookieManager.import_cookies_from_file(cookie_json_path)
        if not raw_cookies:
            return 0

        # Resolve Browser to BrowserContext if needed
        if context is not None and hasattr(context, "contexts") and not hasattr(context, "add_cookies"):
            if getattr(context, "contexts"):
                context = getattr(context, "contexts")[0]
            elif hasattr(context, "new_context") and callable(getattr(context, "new_context")):
                context = await context.new_context()

        sanitized_cookies: List[Dict[str, Any]] = []
        for c in raw_cookies:
            name = str(c.get("name", "")).strip()
            value = str(c.get("value", "")).strip()
            if not name:
                continue

            domain = str(c.get("domain", "")).strip()
            path = str(c.get("path", "/") or "/").strip()
            
            sc: Dict[str, Any] = {
                "name": name,
                "value": value,
                "path": path,
            }

            if domain:
                sc["domain"] = domain
            elif "url" in c:
                sc["url"] = str(c["url"]).strip()
            else:
                continue

            exp = c.get("expires") or c.get("expiry") or c.get("expirationDate")
            if exp is not None:
                try:
                    exp_float = float(exp)
                    if exp_float > 1000000000000:
                        exp_float /= 1000.0
                    if exp_float > time.time() - 86400:
                        sc["expires"] = int(exp_float)
                except (ValueError, TypeError):
                    pass

            if "httpOnly" in c:
                sc["httpOnly"] = bool(c["httpOnly"])
            elif "httponly" in c:
                sc["httpOnly"] = bool(c["httponly"])

            if "secure" in c:
                sc["secure"] = bool(c["secure"])

            same_site = c.get("sameSite") or c.get("samesite")
            if same_site:
                ss_lower = str(same_site).lower()
                if "lax" in ss_lower:
                    sc["sameSite"] = "Lax"
                elif "strict" in ss_lower:
                    sc["sameSite"] = "Strict"
                elif "none" in ss_lower:
                    sc["sameSite"] = "None"
                    sc["secure"] = True

            sanitized_cookies.append(sc)

        if not sanitized_cookies:
            return 0

        injected_count = 0
        try:
            # 1. Playwright / Camoufox Context API
            if hasattr(context, "add_cookies") and callable(getattr(context, "add_cookies")):
                try:
                    await context.add_cookies(sanitized_cookies)
                    injected_count = len(sanitized_cookies)
                except Exception as batch_err:
                    logger.debug(f"Batch cookie injection fallback for {profile_id}: {batch_err}")
                    for single_cookie in sanitized_cookies:
                        try:
                            await context.add_cookies([single_cookie])
                            injected_count += 1
                        except Exception:
                            pass

            # 2. Nodriver / CDP Browser
            elif hasattr(context, "send") and callable(getattr(context, "send")):
                import nodriver as uc
                cdp_cookies = []
                for sc in sanitized_cookies:
                    ss_obj = None
                    if "sameSite" in sc and sc["sameSite"]:
                        ss_str = str(sc["sameSite"]).strip().lower()
                        if ss_str == "lax":
                            ss_obj = uc.cdp.network.CookieSameSite.LAX
                        elif ss_str == "strict":
                            ss_obj = uc.cdp.network.CookieSameSite.STRICT
                        elif ss_str == "none":
                            ss_obj = uc.cdp.network.CookieSameSite.NONE

                    exp_val = None
                    if "expires" in sc and sc["expires"] is not None:
                        try:
                            exp_val = uc.cdp.network.TimeSinceEpoch(float(sc["expires"]))
                        except Exception:
                            pass

                    cdp_cookies.append(uc.cdp.network.CookieParam(
                        name=sc["name"],
                        value=sc["value"],
                        domain=sc.get("domain"),
                        path=sc.get("path", "/"),
                        secure=sc.get("secure", False),
                        http_only=sc.get("httpOnly", False),
                        same_site=ss_obj,
                        expires=exp_val
                    ))
                if cdp_cookies:
                    try:
                        await context.send(uc.cdp.network.enable())
                    except Exception:
                        pass
                    await context.send(uc.cdp.network.set_cookies(cookies=cdp_cookies))
                    injected_count = len(cdp_cookies)

            # 3. Selenium Driverless
            elif hasattr(context, "execute_cdp_cmd") and callable(getattr(context, "execute_cdp_cmd")):
                try:
                    await context.execute_cdp_cmd("Network.enable", {})
                except Exception:
                    pass
                for sc in sanitized_cookies:
                    try:
                        cdp_cookie = {
                            "name": sc["name"],
                            "value": sc["value"],
                            "path": sc.get("path", "/"),
                        }
                        if sc.get("domain"):
                            cdp_cookie["domain"] = sc["domain"]
                        elif sc.get("url"):
                            cdp_cookie["url"] = sc["url"]
                        if "secure" in sc:
                            cdp_cookie["secure"] = bool(sc["secure"])
                        if "httpOnly" in sc:
                            cdp_cookie["httpOnly"] = bool(sc["httpOnly"])
                        if "sameSite" in sc and sc["sameSite"]:
                            cdp_cookie["sameSite"] = str(sc["sameSite"]).capitalize()
                        if "expires" in sc and sc["expires"] is not None:
                            cdp_cookie["expires"] = float(sc["expires"])
                        await context.execute_cdp_cmd("Network.setCookie", cdp_cookie)
                        injected_count += 1
                    except Exception as cdp_err:
                        logger.debug(f"[BrowserLauncher] Selenium driverless setCookie notice: {cdp_err}")

            if injected_count > 0:
                logger.info(f"[BrowserLauncher] Injected {injected_count} profile cookies into browser context for '{profile_id}'.")

        except Exception as e:
            logger.warning(f"[BrowserLauncher] Cookie injection notice for profile '{profile_id}': {e}")

        return injected_count

    async def _sync_cookies_for_profile(self, profile_id: str, context: Any = None):
        """Extracts live runtime cookies from context or SQLite database and saves to cookies.json."""
        from engine.cookie_manager import CookieManager
        prof_path = self.profile_manager.get_profile_path(profile_id)
        live_cookies: List[Dict[str, Any]] = []

        if context is not None:
            if hasattr(context, "contexts") and not hasattr(context, "cookies"):
                if getattr(context, "contexts"):
                    context = getattr(context, "contexts")[0]
            try:
                if hasattr(context, "cookies") and callable(getattr(context, "cookies")):
                    res = await context.cookies()
                    if isinstance(res, list):
                        live_cookies = res
                elif hasattr(context, "get_cookies") and callable(getattr(context, "get_cookies")):
                    res = await context.get_cookies()
                    if isinstance(res, list):
                        live_cookies = res
            except Exception as e:
                logger.debug(f"Could not extract live cookies from context: {e}")

        # Extract SQLite cookies from user_data DBs
        user_data_dir = self.profile_manager.get_user_data_dir(profile_id)
        sqlite_cookies = CookieManager.extract_cookies_from_user_data(user_data_dir)

        # Merge JSON, live, and SQLite cookies
        cookie_json_path = os.path.join(prof_path, "cookies.json")
        existing_json = CookieManager.import_cookies_from_file(cookie_json_path) if os.path.exists(cookie_json_path) else []

        cookie_map: Dict[str, Dict[str, Any]] = {}
        for c in existing_json + live_cookies + sqlite_cookies:
            k = f"{c.get('domain', '')}:{c.get('name', '')}"
            if k and k != ":":
                cookie_map[k] = c

        merged = list(cookie_map.values())
        if merged:
            if not hasattr(self, "_profile_cookie_sigs"):
                self._profile_cookie_sigs = {}
            items_sig = sorted([f"{c.get('domain')}:{c.get('name')}:{c.get('value')}" for c in merged])
            current_sig = f"{len(merged)}:{items_sig}"
            last_sig = self._profile_cookie_sigs.get(profile_id)
            if current_sig != last_sig:
                self._profile_cookie_sigs[profile_id] = current_sig
                CookieManager.save_cookies_to_file(merged, cookie_json_path)
                logger.info(f"Synced {len(merged)} live browsing cookies to {cookie_json_path}")

    async def _handle_context_closed(self, profile_id: str):
        """Clean up profile state when the browser context is closed."""
        context = self.active_contexts.pop(profile_id, None)
        await self._sync_cookies_for_profile(profile_id, context)
        logger.info(f"Detected window exit for profile '{profile_id}'. Cleaning up status.")

        tunnel = self.active_tunnels.pop(profile_id, None)
        if tunnel:
            try:
                await tunnel.stop()
            except Exception:
                pass

        NetworkKillSwitchManager.teardown_profile_netns(profile_id)

        sandbox = self.active_sandboxes.pop(profile_id, None)
        if sandbox:
            try:
                await sandbox.stop()
            except Exception:
                pass

        profile = self.profile_manager.load_profile(profile_id)
        if profile and profile.get("status") == "Running":
            profile["status"] = "Stopped"
            self.profile_manager.save_profile(profile)

    async def stop_profile(self, profile_id: str) -> Tuple[bool, str]:
        """Stops a running browser context and ensures process tree termination."""
        profile = self.profile_manager.load_profile(profile_id)
        context = self.active_contexts.pop(profile_id, None)
        await self._sync_cookies_for_profile(profile_id, context)
        if context:
            try:
                if hasattr(context, "close") and callable(getattr(context, "close")):
                    await context.close()
            except Exception:
                pass

        tunnel = self.active_tunnels.pop(profile_id, None)
        if tunnel:
            try:
                await tunnel.stop()
            except Exception:
                pass

        NetworkKillSwitchManager.teardown_profile_netns(profile_id)

        sandbox = self.active_sandboxes.pop(profile_id, None)
        if sandbox:
            try:
                await sandbox.stop()
            except Exception:
                pass
        
        if context:
            try:
                if hasattr(context, "stop"):
                    res = context.stop()
                    if asyncio.iscoroutine(res):
                        await res
                elif hasattr(context, "close"):
                    await context.close()
                elif hasattr(context, "quit"):
                    await context.quit()
            except Exception as e:
                logger.debug(f"Expected socket closure during quit for profile {profile_id}: {e}")

        if profile:
            debug_port = profile.get("debug_port")
            if debug_port:
                release_port(debug_port)
            profile["status"] = "Stopped"
            self.profile_manager.save_profile(profile)

        user_data_dir = self.profile_manager.get_user_data_dir(profile_id)
        self._cleanup_orphaned_profile_processes(user_data_dir)

        return True, "Profile stopped successfully."


    def _cleanup_orphaned_profile_processes(self, user_data_dir: str, engine_type: str = "chromium"):
        """Kills any orphaned Chromium/Firefox/Camoufox process using user_data_dir and cleans stale lock files."""
        if not user_data_dir or not os.path.exists(user_data_dir):
            return

        lock_names = [
            "SingletonLock", "SingletonCookie", "SingletonSocket",
            "parent.lock", ".parentlock", "lock", "lockfile", "compatibility.ini"
        ]
        for lock_name in lock_names:
            lock_path = os.path.join(user_data_dir, lock_name)
            if os.path.exists(lock_path) or os.path.islink(lock_path):
                try:
                    if os.path.isdir(lock_path):
                        shutil.rmtree(lock_path, ignore_errors=True)
                    else:
                        os.unlink(lock_path)
                except Exception:
                    pass

        try:
            import psutil
            norm_dir = os.path.normpath(user_data_dir)
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    cmd = proc.info.get('cmdline') or []
                    cmd_str = " ".join(cmd)
                    if (f"--user-data-dir={norm_dir}" in cmd_str or f"--user-data-dir={user_data_dir}" in cmd_str or
                        f"-profile {norm_dir}" in cmd_str or f"-profile {user_data_dir}" in cmd_str):
                        proc.kill()
                except Exception:
                    pass
        except Exception:
            pass

    async def stop_all_profiles(self):
        """Stops all running browser instances and shuts down Playwright engine."""
        running_ids = list(self.active_contexts.keys())
        for pid in running_ids:
            await self.stop_profile(pid)

        if self.playwright:
            try:
                await self.playwright.stop()
            except Exception as e:
                logger.debug(f"Error stopping Playwright engine: {e}")
            self.playwright = None
