import asyncio
import copy
import logging
import random
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import quote_plus, urlparse

from engine.browser import BrowserLauncher
from engine.cookie_manager import CookieManager
from engine.events import AsyncEventBus
from engine.warmup.consent_solver import SemanticBannerResolver
from engine.warmup.human_motion import BiomechanicalMotor, BiGramTypingEngine
from engine.honeypot_detector import HoneypotDetector, HoneypotScanResult
from engine.warmup.trajectory_planner import (
    WARMUP_CATEGORIES,
    PERSONA_PROFILES,
    WarmupKnowledgeStore,
    LoginAuthDetector,
    PlatformInteractionAdapters,
    SitePortalEngine,
    ContentAwareReader,
    PersonaTrajectoryEngine,
)

logger = logging.getLogger("CookieWarmupOrchestrator")


@dataclass
class WarmupConfig:
    category: str = "general"
    persona: str = "general"             # AI Persona profile key
    mode: str = "standard"               # "standard" vs "google_search_only"
    ai_model: str = "qwen2.5:1.5b"       # Local AI Micro-LLM model name
    motor_model: str = "min_jerk"        # "min_jerk" (08/2026 AI) vs "bezier"
    typing_model: str = "bigram"         # "bigram" (08/2026 AI) vs "uniform"
    content_aware_dwell: bool = True     # Dynamic WPM page analysis
    auto_evade_traps: bool = True        # Auto detect and retreat from login/auth traps
    enable_honeypot_shield: bool = True  # AI & DOM Honeypot Click-Trap Shield
    honeypot_model: str = "auto"         # AI model for ambiguous click-trap classification
    self_learning_memory: bool = True   # Self-learning trajectory persistence
    enable_verification_audit: bool = True  # Real-time fingerprint leak & diagnostic audit
    enable_captcha_solver: bool = True   # Local AI Captcha Solver (reCAPTCHA v2 / /sorry/index)
    captcha_strategy: str = "audio_first"  # "audio_first", "vision_first", "audio_only", "vision_only", "disabled"
    captcha_vision_model: str = "llava:7b"  # Vision model for image tile recognition
    max_pages: int = 5
    dwell_time: float = 8.0
    click_depth: int = 1
    concurrency: int = 2
    enable_search: bool = True
    no_google: bool = False              # Strictly forbids Google Search / domains; uses DuckDuckGo and Bing instead
    dismiss_banners: bool = True
    urls: List[str] = field(default_factory=list)
    search_queries: List[str] = field(default_factory=list)
    custom_keywords: List[str] = field(default_factory=list)  # User custom keywords for thematic red thread
    custom_websites: List[str] = field(default_factory=list)  # User custom websites to visit
    session_intent_topic: str = ""                             # Coherent topic focus ("Roter Faden")
    headless: bool = False                                     # Silent background execution / virtual display mode


class CookieWarmupRobot:
    """Advanced AI/ML background browsing robot to build authentic cookies,
    local storage, browser cache, and history for profile isolation.
    """

    def __init__(self, launcher: BrowserLauncher):
        self.launcher = launcher
        self._stop_requested: bool = False
        self.config: WarmupConfig = WarmupConfig()
        self._session_used_queries: set = set()
        self.event_bus = AsyncEventBus.get_instance()
        try:
            from engine.ai_model_manager import AIModelManager
            self.ai_manager = AIModelManager.get_instance()
        except Exception:
            self.ai_manager = None
        try:
            from engine.ai_swarm_orchestrator import AISwarmOrchestrator
            self.swarm = AISwarmOrchestrator.get_instance()
        except Exception:
            self.swarm = None

    async def _check_and_solve_captcha(self, page: Any, notify_progress: Optional[Callable] = None) -> bool:
        """Checks for Google reCAPTCHA v2 / sorry/index / Cloudflare barriers and solves them using Multi-AI Swarm."""
        if not getattr(self.config, "enable_captcha_solver", False):
            return False
        try:
            url = getattr(page, "url", "").lower()
            captcha_detect_script = """
            (() => {
                const u = (window.location.href || '').toLowerCase();
                if (u.includes('sorry/index') || u.includes('/recaptcha/') || u.includes('recaptcha.net')) return true;
                const frames = Array.from(document.querySelectorAll('iframe'));
                for (const f of frames) {
                    const s = (f.getAttribute('src') || '').toLowerCase();
                    const t = (f.getAttribute('title') || '').toLowerCase();
                    if (s.includes('recaptcha') || s.includes('challenges.cloudflare.com') || s.includes('hcaptcha') || s.includes('turnstile') || t.includes('recaptcha') || t.includes('challenge')) return true;
                }
                return !!document.querySelector('#recaptcha-anchor, .recaptcha-checkbox, div#captcha, #captcha-form, form#captcha-form, div.g-recaptcha, div.rc-anchor');
            })()
            """
            has_captcha = bool(await self._evaluate(page, captcha_detect_script))
            if not has_captcha:
                return False

            if notify_progress:
                notify_progress("⎘ Google reCAPTCHA / Challenge barrier detected! Invoking AI Captcha Solver...", 0, url, 0)

            def notify_cb(msg: str):
                if notify_progress:
                    notify_progress(msg, 0, url, 0)
                logger.info(f"[WarmupCaptcha] {msg}")

            strategy = getattr(self.config, "captcha_strategy", "audio_first")
            vision_mod = getattr(self.config, "captcha_vision_model", "llava:7b")
            ai_mod = getattr(self.config, "ai_model", None)

            # 1. Swarm Path (Auto-Ensemble: Whisper CPU -> Configured Vision Model)
            solved = False
            solve_msg = ""
            details: Dict[str, Any] = {}
            if self.swarm:
                solved, solve_msg, details = await self.swarm.solve_captcha_swarm(
                    page=page,
                    strategy=strategy,
                    configured_model=ai_mod,
                    vision_model=vision_mod,
                    notify_cb=notify_cb
                )

            # 2. Standalone Fallback
            if not solved:
                from engine.ai_captcha_solver import AICaptchaSolver
                solved, solve_msg, details = await AICaptchaSolver.solve_google_captcha(
                    page=page,
                    strategy=strategy,
                    vision_model=vision_mod,
                    notify_cb=notify_cb,
                    timeout_sec=40.0
                )

            if solved:
                logger.info(f"Warmup Captcha Solved via {details.get('method', 'AI')} ({solve_msg})")
                
                # Check for Google sorry/index continue form submit
                try:
                    submit_btn = await page.query_selector("form#captcha-form input[type='submit'], input[name='continue'], input[type='submit'], button[type='submit'], form button")
                    if submit_btn and await submit_btn.is_visible():
                        notify_cb("Submitting Google continue form...")
                        await submit_btn.click()
                except Exception:
                    pass

                await asyncio.sleep(2.0)
                return True
        except Exception as e:
            logger.debug(f"Warmup captcha solver check note: {e}")
        return False

    def _is_window_closed(self, err: Exception, page: Any = None) -> bool:
        if page and hasattr(page, "is_closed") and callable(page.is_closed):
            try:
                if page.is_closed():
                    return True
            except Exception:
                pass
        err_str = str(err).lower()
        if "execution context was destroyed" in err_str or "navigation interrupted" in err_str or "frame was detached" in err_str:
            return False
        closed_signals = [
            "target closed", "browser closed", "browser has been closed",
            "page closed", "connection closed", "target page, context or browser has been closed",
            "websocket connection closed", "session closed"
        ]
        return any(sig in err_str for sig in closed_signals)

    def request_stop(self):
        self._stop_requested = True

    async def scan_and_guard_honeypots(self, page: Any, notify_progress: Optional[Callable] = None) -> HoneypotScanResult:
        """Executes Honeypot & Click-Trap Shield scan on active page and registers traps in knowledge store."""
        if not getattr(self.config, "enable_honeypot_shield", True):
            return HoneypotScanResult()

        target_m = getattr(self.config, "ai_model", "qwen2.5:1.5b")
        def notify_shield(m: str):
            if notify_progress:
                notify_progress(m)
            logger.info(f"[HoneypotShield] {m}")

        scan_res = await HoneypotDetector.scan_page(
            page=page,
            model_name=target_m,
            evaluate_fn=self._evaluate,
            notify_cb=notify_shield
        )

        if not scan_res.is_clean and scan_res.blacklisted_hrefs:
            k_store = WarmupKnowledgeStore.get_instance()
            for trapped_url in scan_res.blacklisted_hrefs:
                k_store.record_trap(trapped_url, "AI Honeypot / Click-Trap Detected")

        return scan_res

    async def run_warmup_batch(
        self,
        profile_ids: List[str],
        config: Optional[WarmupConfig] = None,
        progress_callback: Optional[Callable[[str, str, float, str, int], None]] = None
    ) -> Dict[str, bool]:
        self._stop_requested = False
        self._session_used_queries.clear()
        cfg = copy.deepcopy(config) if config else WarmupConfig()
        self.config = cfg
        concurrency = max(1, min(10, cfg.concurrency))
        sem = asyncio.Semaphore(concurrency)
        results: Dict[str, bool] = {}

        async def worker(pid: str):
            async with sem:
                if self._stop_requested:
                    return

                def p_cb(msg: str, pct: float, current_url: str, cookie_cnt: int):
                    if progress_callback:
                        progress_callback(pid, msg, pct, current_url, cookie_cnt)

                res = await self.run_warmup(pid, config=cfg, progress_callback=p_cb)
                results[pid] = res

        tasks = [asyncio.create_task(worker(pid)) for pid in profile_ids]
        await asyncio.gather(*tasks, return_exceptions=True)
        return results

    async def bezier_mouse_move(self, page, start_x: float, start_y: float, end_x: float, end_y: float, steps: int = 15):
        await BiomechanicalMotor.move_mouse_humanoid(
            page, start_x, start_y, end_x, end_y, stop_check=lambda: self._stop_requested
        )

    async def dismiss_cookie_banners(self, page, retries: int = 4, delay: float = 0.75):
        # 1. Attach passive in-page MutationObserver & interval heartbeat
        try:
            await SemanticBannerResolver.attach_consent_autowatcher(page, self._evaluate)
        except Exception:
            pass

        # 2. Multi-stage resolution via Fast CMP Matcher, Shadow DOM, & Multi-Lingual Regex Scanner
        m_name = getattr(self.config, "ai_model", None)
        v_name = getattr(self.config, "captcha_vision_model", None)

        for i in range(retries):
            # Step A: Fast direct CMP & Shadow DOM scan across all frames
            solved = await SemanticBannerResolver.resolve_consent_banners(page, self._evaluate, model_name=m_name, vision_model=v_name)
            if solved:
                return True

            # Step B: Multi-AI Swarm Handshake if enabled
            if self.swarm and (m_name in ["swarm_auto_full", "swarm_auto", "swarm", "auto_full"] or "swarm" in str(m_name).lower()):
                try:
                    swarm_res = await self.swarm.resolve_consent_swarm(page, configured_model=m_name)
                    if swarm_res and swarm_res.get("solved"):
                        return True
                except Exception as swarm_e:
                    logger.debug(f"[Warmup] Swarm consent handshake note: {swarm_e}")

            # Step C: Micro-scroll on attempt 1 to wake up scroll-triggered CMP banners
            if i == 0:
                try:
                    await self._evaluate(page, "window.scrollBy({top: 60, behavior: 'smooth'}); setTimeout(() => window.scrollBy({top: -60, behavior: 'smooth'}), 250);")
                except Exception:
                    pass

            # Step D: Adaptive wait if a consent container is detected in DOM
            if i < retries - 1:
                try:
                    from engine.warmup.consent_solver import CHECK_CONSENT_CONTAINER_SCRIPT
                    has_container = await self._evaluate(page, CHECK_CONSENT_CONTAINER_SCRIPT)
                    effective_delay = delay * 1.5 if has_container else delay
                except Exception:
                    effective_delay = delay
                await asyncio.sleep(effective_delay)
        return False

    async def human_scroll(self, page, dwell_time: float = 8.0, persona: str = "general"):
        effective_dwell = dwell_time
        prefetch_task = None
        target_model = getattr(self.config, "ai_model", None)
        if getattr(self, "ai_manager", None):
            roles = self.ai_manager.get_hybrid_roles(target_model)
            micro_model = roles.get("micro_model", target_model or "qwen2.5:0.5b")
            if await self.ai_manager.is_engine_ready(micro_model):
                try:
                    page_info = await self._evaluate(page, "(() => ({ title: document.title || '', text: (document.body ? document.body.innerText : '').slice(0, 800) }))()")
                    if isinstance(page_info, dict):
                        persona_key = persona or getattr(self.config, "persona", "general")
                        prefetch_task = asyncio.create_task(
                            self.ai_manager.evaluate_page_dwell_time(
                                page_info.get("title", ""),
                                page_info.get("text", ""),
                                persona=persona_key,
                                model_name=micro_model
                            )
                        )

                except Exception as ai_err:
                    logger.debug(f"AI dwell evaluation prefetch note: {ai_err}")

        await ContentAwareReader.analyze_page_and_dwell(
            page, self._evaluate, base_dwell=effective_dwell, stop_check=lambda: self._stop_requested
        )

        if prefetch_task and not prefetch_task.done():
            try:
                ai_dwell = await asyncio.wait_for(prefetch_task, timeout=2.0)
                logger.info(f"AI Dynamic Page Dwell Time (Prefetched): {ai_dwell:.1f}s")
            except Exception:
                pass

    async def explore_internal_links(self, page, current_url: str, depth: int = 1) -> bool:
        if depth <= 0 or self._stop_requested:
            return False

        try:
            parsed_origin = urlparse(current_url).netloc.lower()
            if not parsed_origin:
                return False

            script = r"""
            (() => {
                const origin = window.location.hostname;
                const badPattern = /(login|signin|sign-in|signup|sign-up|register|auth|sso|checkpoint|passport|account|anmelden|registrieren|einloggen|connexion|inscription|iniciar-sesion|cart|checkout|warenkorb|feedback|about|terms|privacy|impressum|contact|kontakt|upload|more|help|faq|settings|preferences|cookie|legal|copyright|disclaimer|careers|jobs|press|sponsor|adchoices|wp-admin|wp-login|search|\/tag\/|\/author\/|category|feed)/i;
                const badTextPattern = /(log\s*in|sign\s*in|sign\s*up|register|anmelden|registrieren|feedback|upload|more|about\s*us|impressum|datenschutz|privacy|terms|cookie|cart|warenkorb|buy\s*now|checkout|kontakt|contact|support|help|faq|settings)/i;

                // 1. Prefer article & headline links
                let primaryNodes = Array.from(document.querySelectorAll('article a, main a, h1 a, h2 a, h3 a, [class*="story"] a, [class*="post"] a, [class*="article"] a, [class*="title"] a, [class*="card"] a, [class*="entry"] a, [class*="topic"] a'));
                if (primaryNodes.length < 3) {
                    primaryNodes = Array.from(document.querySelectorAll('a[href]:not(nav a):not(header a):not(footer a)'));
                }

                return primaryNodes
                    .map(a => ({
                        href: a.href,
                        text: (a.innerText || a.textContent || '').trim()
                    }))
                    .filter(item => {
                        try {
                            if (!item.text || item.text.length < 8) return false;
                            const u = new URL(item.href);
                            const pathQuery = (u.pathname + u.search).toLowerCase();
                            const txt = item.text.toLowerCase();
                            if (badPattern.test(pathQuery) || badTextPattern.test(txt)) return false;
                            if (u.protocol !== 'http:' && u.protocol !== 'https:') return false;
                            if (item.href.includes('#') || item.href.includes('javascript:')) return false;
                            return u.hostname.endsWith(origin) || origin.endsWith(u.hostname);
                        } catch(e) { return false; }
                    });
            })()
            """
            raw_links = await self._evaluate(page, script)
            if not raw_links or not isinstance(raw_links, list):
                return False

            # Run AI Honeypot Shield scan to discover and neutralize hidden click traps
            hp_res = await self.scan_and_guard_honeypots(page)
            if not hp_res.is_clean:
                raw_links = hp_res.filter_safe_links(raw_links)

            k_store = WarmupKnowledgeStore.get_instance()
            seen = set()
            link_candidates = []
            for item in raw_links:
                h = item.get("href", "")
                t = item.get("text", "")
                if not h or h in seen or h == current_url:
                    continue
                if not hp_res.is_safe_url(h):
                    continue
                if LoginAuthDetector.url_matches_auth_pattern(h) or LoginAuthDetector.link_text_matches_auth_pattern(t):
                    continue
                if k_store.is_known_trap(h):
                    continue
                seen.add(h)
                link_candidates.append(item)

            if not link_candidates:
                return False

            selected_item = None
            persona_key = getattr(self.config, "persona", "general")
            story_topic = getattr(self.config, "session_intent_topic", "General Interest")

            # 1. Try Swarm Subnavigation choice
            if self.swarm:
                try:
                    selected_item = await self.swarm.evaluate_subnavigation_choice(
                        link_candidates=link_candidates,
                        story_topic=story_topic,
                        persona_name=persona_key,
                        configured_model=getattr(self.config, "ai_model", None)
                    )
                except Exception as swarm_link_err:
                    logger.debug(f"[Warmup] Swarm link selection note: {swarm_link_err}")

            # 2. Standalone Model fallback
            if not selected_item:
                try:
                    from engine.ai_model_manager import AIModelManager
                    ai_mgr = AIModelManager.get_instance()
                    target_m = getattr(self.config, "ai_model", None)
                    if await ai_mgr.is_engine_ready(target_m):
                        selected_item = await ai_mgr.select_humanoid_next_link(
                            link_candidates,
                            persona=persona_key,
                            model_name=target_m
                        )
                except Exception as ai_err:
                    logger.debug(f"AI link selection note: {ai_err}")

            if not selected_item:
                selected_item = random.choice(link_candidates[:8])

            target_href = selected_item.get("href")
            if not target_href or not isinstance(target_href, str):
                return False

            raw_text = selected_item.get("text", "")
            link_text = raw_text[:50] if isinstance(raw_text, str) else ""
            logger.info(f"AI Editorial Article Choice [{link_text}]: {target_href}")

            logger.info(f"Sub-navigating internal content link (depth {depth}): {target_href}")
            await self._navigate(page, target_href, timeout=15000)
            await self.dismiss_cookie_banners(page)
            if getattr(self.config, "enable_captcha_solver", False):
                await self._check_and_solve_captcha(page)
            await self.human_scroll(page, dwell_time=random.uniform(4.0, 8.0))
            return True

        except Exception as e:
            if self._is_window_closed(e, page):
                self._stop_requested = True
                logger.warning(f"Browser closed during internal link exploration: {e}")
            else:
                logger.debug(f"Sub-navigation note for {current_url}: {e}")
            return False

    async def search_google_and_extract_top_results(
        self,
        page: Any,
        query: str,
        max_results: int = 5,
        notify_progress: Optional[Callable] = None
    ) -> List[Dict[str, str]]:
        """Performs an authentic humanoid search query EXCLUSIVELY on Google (google.com),
        dismisses Google consent dialogs, bypasses captchas if needed, and returns the top organic results.
        Strictly no duckduckgo, no bing, no third-party search engines.
        """
        try:
            try:
                from engine.ai_model_manager import AIModelManager
                ai_mgr = AIModelManager.get_instance()
                target_m = getattr(self.config, "ai_model", None)
                if await ai_mgr.is_engine_ready(target_m):
                    meta_script = "(() => ({ title: document.title || '', text: (document.body ? document.body.innerText : '').slice(0, 300) }))()"
                    p_info = await self._evaluate(page, meta_script)
                    if p_info and isinstance(p_info, dict) and p_info.get("title"):
                        ai_query = await ai_mgr.generate_contextual_query(
                            p_info.get("title", ""),
                            p_info.get("text", ""),
                            persona=query,
                            model_name=target_m
                        )
                        if ai_query:
                            query = ai_query
            except Exception as ai_q_err:
                logger.debug(f"AI search query generation note: {ai_q_err}")

            # STRICTLY Google only
            search_url = "https://www.google.com"
            fallback_search_url = f"https://www.google.com/search?q={quote_plus(query)}"

            logger.info(f"Navigating to Google Search ({search_url}) for query: '{query}'...")
            if notify_progress:
                notify_progress(f"Opening Google Search for: '{query}'...", 12.0, search_url, 0)

            nav_ok = await self._navigate(page, search_url, timeout=20000)
            if not nav_ok:
                logger.info(f"Initial navigation to {search_url} failed, using direct search results URL: {fallback_search_url}")
                await self._navigate(page, fallback_search_url, timeout=20000)

            # Solve Google cookie consent modal (#L2AGLb, etc.)
            await self.dismiss_cookie_banners(page)
            if getattr(self.config, "enable_captcha_solver", False):
                await self._check_and_solve_captcha(page, notify_progress)
            await asyncio.sleep(random.uniform(1.0, 2.0))

            # Humanoid typing into Google search input
            input_selector = "textarea[name='q'], input[name='q'], input[type='text'], input[type='search'], textarea[title*='Such'], input[title*='Such']"
            has_input = await self._evaluate(page, f"(() => !!document.querySelector(\"{input_selector}\"))()")
            if has_input:
                try:
                    if notify_progress:
                        notify_progress(f"Typing organic search query into Google: '{query}'", 15.0, search_url, 0)
                    await BiGramTypingEngine.type_humanoid(
                        page, input_selector, query, self._evaluate, stop_check=lambda: self._stop_requested
                    )
                    await asyncio.sleep(random.uniform(2.0, 3.5))
                except Exception as type_err:
                    logger.debug(f"Google search typing note: {type_err}")

            if getattr(self.config, "enable_captcha_solver", False):
                await self._check_and_solve_captcha(page, notify_progress)
            await self.human_scroll(page, dwell_time=3.0)

            top_script = f"""
            (() => {{
                const forbidden = [
                    'youtube.com', 'youtu.be', 'ytimg.com',
                    'google.', 'doubleclick.net', 'googleadservices.com',
                    'googlesyndication.com', 'accounts.google.com',
                    'support.google.com', 'maps.google.com', 'play.google.com',
                    'policies.google.com', 'bing.com', 'duckduckgo.com', 'yahoo.com'
                ];

                const resultContainers = document.querySelectorAll('#search, #rso, div[data-async-context], div[data-hveid], main, body');
                let links = [];
                for (const container of resultContainers) {{
                    const cLinks = Array.from(container.querySelectorAll('a[href]'));
                    if (cLinks.length > 0) {{
                        links = cLinks;
                        break;
                    }}
                }}

                const topResults = [];
                const seenHosts = new Set();

                for (const a of links) {{
                    try {{
                        let href = a.href;
                        if (!href) continue;

                        if (href.includes('/url?') && href.includes('q=')) {{
                            const uObj = new URL(href);
                            const realQ = uObj.searchParams.get('q');
                            if (realQ) href = realQ;
                        }}

                        const u = new URL(href);
                        const host = u.hostname.toLowerCase();

                        if (u.protocol !== 'http:' && u.protocol !== 'https:') continue;
                        if (forbidden.some(d => host.includes(d))) continue;

                        if (u.pathname.includes('/search') || u.pathname.includes('/preferences') || u.pathname.includes('/settings')) continue;

                        if (!seenHosts.has(host) && topResults.length < {max_results}) {{
                            seenHosts.add(host);
                            topResults.push({{
                                href: href,
                                text: (a.innerText || a.textContent || '').trim().slice(0, 100)
                            }});
                        }}
                    }} catch(e) {{}}
                }}
                return topResults;
            }})()
            """
            extracted_results = await self._evaluate(page, top_script)

            if not extracted_results or not isinstance(extracted_results, list) or len(extracted_results) == 0:
                logger.info(f"Extract returned 0 results, navigating directly to Google search fallback URL: {fallback_search_url}")
                await self._navigate(page, fallback_search_url, timeout=20000)
                await self.dismiss_cookie_banners(page)
                if getattr(self.config, "enable_captcha_solver", False):
                    await self._check_and_solve_captcha(page, notify_progress)
                await asyncio.sleep(2.0)
                extracted_results = await self._evaluate(page, top_script)

            # Filter search results through AI Honeypot Shield
            if extracted_results and isinstance(extracted_results, list):
                s_hp_res = await self.scan_and_guard_honeypots(page)
                if not s_hp_res.is_clean:
                    extracted_results = s_hp_res.filter_safe_links(extracted_results)

            return extracted_results if isinstance(extracted_results, list) else []

        except Exception as e:
            if self._is_window_closed(e, page):
                self._stop_requested = True
                logger.warning(f"Browser closed during Google search: {e}")
            else:
                logger.warning(f"Error during Google search: {e}")
            return []

    async def search_duckduckgo_and_extract_top_results(
        self,
        page: Any,
        query: str,
        max_results: int = 5,
        notify_progress: Optional[Callable] = None
    ) -> List[Dict[str, str]]:
        """Performs an authentic humanoid search query on DuckDuckGo (NoGoogle mode),
        extracts top organic results, and falls back to Bing if DuckDuckGo yields no results.
        Strictly avoids Google entirely.
        """
        try:
            search_url = "https://duckduckgo.com"
            fallback_search_url = f"https://duckduckgo.com/?q={quote_plus(query)}&ia=web"

            logger.info(f"[NoGoogle] Navigating to DuckDuckGo ({search_url}) for query: '{query}'...")
            if notify_progress:
                notify_progress(f"[NoGoogle] Opening DuckDuckGo Search: '{query}'...", 12.0, search_url, 0)

            nav_ok = await self._navigate(page, search_url, timeout=20000)
            if not nav_ok:
                logger.info(f"Initial navigation to {search_url} failed, using direct search results URL: {fallback_search_url}")
                await self._navigate(page, fallback_search_url, timeout=20000)

            await self.dismiss_cookie_banners(page)
            await asyncio.sleep(random.uniform(1.0, 2.0))

            # Humanoid typing into DuckDuckGo search input
            input_selector = "input[name='q'], input#searchbox_input, input[type='text'], input[type='search']"
            has_input = await self._evaluate(page, f"(() => !!document.querySelector(\"{input_selector}\"))()")
            if has_input:
                try:
                    if notify_progress:
                        notify_progress(f"[NoGoogle] Typing organic query into DuckDuckGo: '{query}'", 15.0, search_url, 0)
                    await BiGramTypingEngine.type_humanoid(
                        page, input_selector, query, self._evaluate, stop_check=lambda: self._stop_requested
                    )
                    await asyncio.sleep(random.uniform(0.5, 1.2))
                    # Press Enter / submit search form
                    submit_script = f"""
                    (() => {{
                        const inp = document.querySelector("{input_selector}");
                        if (inp) {{
                            inp.dispatchEvent(new KeyboardEvent('keydown', {{key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true}}));
                            inp.dispatchEvent(new KeyboardEvent('keypress', {{key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true}}));
                            inp.dispatchEvent(new KeyboardEvent('keyup', {{key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true}}));
                            if (inp.form) inp.form.submit();
                        }}
                    }})()
                    """
                    await self._evaluate(page, submit_script)
                    await asyncio.sleep(random.uniform(2.5, 4.0))
                except Exception as type_err:
                    logger.debug(f"DuckDuckGo search typing note: {type_err}")

            await self.human_scroll(page, dwell_time=3.0)

            top_script = f"""
            (() => {{
                const forbidden = [
                    'youtube.com', 'youtu.be', 'ytimg.com',
                    'google.', 'doubleclick.net', 'googleadservices.com',
                    'googlesyndication.com', 'accounts.google.com',
                    'duckduckgo.com', 'bing.com', 'yahoo.com', 'yandex.'
                ];

                const linkElements = Array.from(document.querySelectorAll(
                    "a[data-testid='result-title-a'], a.result__url, [data-layout='organic'] a[href^='http'], ol.react-results--main li a[href^='http'], article h2 a[href^='http'], .results a[href^='http']"
                ));

                const topResults = [];
                const seenHosts = new Set();

                for (const a of linkElements) {{
                    try {{
                        let href = a.href;
                        if (!href) continue;

                        // Resolve DuckDuckGo redirect uddg= parameter if present
                        if (href.includes('duckduckgo.com/l/?') && href.includes('uddg=')) {{
                            const uObj = new URL(href);
                            const realQ = uObj.searchParams.get('uddg');
                            if (realQ) href = decodeURIComponent(realQ);
                        }}

                        const u = new URL(href);
                        const host = u.hostname.toLowerCase();

                        if (u.protocol !== 'http:' && u.protocol !== 'https:') continue;
                        if (forbidden.some(d => host.includes(d))) continue;
                        if (u.pathname.includes('/search') || u.pathname.includes('/settings')) continue;

                        if (!seenHosts.has(host) && topResults.length < {max_results}) {{
                            seenHosts.add(host);
                            topResults.push({{
                                href: href,
                                text: (a.innerText || a.textContent || '').trim().slice(0, 100)
                            }});
                        }}
                    }} catch(e) {{}}
                }}
                return topResults;
            }})()
            """
            extracted_results = await self._evaluate(page, top_script)

            if not extracted_results or not isinstance(extracted_results, list) or len(extracted_results) == 0:
                logger.info(f"Extract returned 0 results, navigating directly to DuckDuckGo fallback URL: {fallback_search_url}")
                await self._navigate(page, fallback_search_url, timeout=20000)
                await self.dismiss_cookie_banners(page)
                await asyncio.sleep(2.5)
                extracted_results = await self._evaluate(page, top_script)

            # Secondary non-Google fallback: Bing
            if not extracted_results or not isinstance(extracted_results, list) or len(extracted_results) == 0:
                logger.info("[NoGoogle] DuckDuckGo empty, falling back to Bing...")
                bing_url = f"https://www.bing.com/search?q={quote_plus(query)}"
                if notify_progress:
                    notify_progress(f"[NoGoogle] Fallback to Bing Search: '{query}'...", 15.0, bing_url, 0)
                await self._navigate(page, bing_url, timeout=20000)
                await self.dismiss_cookie_banners(page)
                await asyncio.sleep(2.5)
                bing_script = f"""
                (() => {{
                    const forbidden = ['google.', 'youtube.com', 'bing.com', 'microsoft.com', 'duckduckgo.com'];
                    const links = Array.from(document.querySelectorAll('#b_results .b_algo h2 a[href], #b_results li h2 a[href]'));
                    const topResults = [];
                    const seenHosts = new Set();
                    for (const a of links) {{
                        try {{
                            const href = a.href;
                            const u = new URL(href);
                            const host = u.hostname.toLowerCase();
                            if (forbidden.some(d => host.includes(d))) continue;
                            if (!seenHosts.has(host) && topResults.length < {max_results}) {{
                                seenHosts.add(host);
                                topResults.push({{
                                    href: href,
                                    text: (a.innerText || a.textContent || '').trim().slice(0, 100)
                                }});
                            }}
                        }} catch(e) {{}}
                    }}
                    return topResults;
                }})()
                """
                extracted_results = await self._evaluate(page, bing_script)

            # Filter search results through AI Honeypot Shield
            if extracted_results and isinstance(extracted_results, list):
                s_hp_res = await self.scan_and_guard_honeypots(page)
                if not s_hp_res.is_clean:
                    extracted_results = s_hp_res.filter_safe_links(extracted_results)

            return extracted_results if isinstance(extracted_results, list) else []

        except Exception as e:
            if self._is_window_closed(e, page):
                self._stop_requested = True
                logger.warning(f"Browser closed during NoGoogle search: {e}")
            else:
                logger.warning(f"Error during NoGoogle search: {e}")
            return []

    async def perform_search_navigation(self, page, query: str, notify_progress: Optional[Callable] = None) -> bool:
        try:
            use_no_google = getattr(self.config, "no_google", False)
            if use_no_google:
                top5_results = await self.search_duckduckgo_and_extract_top_results(
                    page, query, max_results=5, notify_progress=notify_progress
                )
            else:
                top5_results = await self.search_google_and_extract_top_results(
                    page, query, max_results=5, notify_progress=notify_progress
                )
            if not top5_results:
                return False

            chosen_url = None
            k_store = WarmupKnowledgeStore.get_instance()

            if getattr(self.config, "custom_websites", None):
                custom_domains = [urlparse(w).netloc.lower() for w in self.config.custom_websites if urlparse(w).netloc]
                for item in top5_results:
                    item_host = urlparse(item["href"]).netloc.lower()
                    if any(cd in item_host or item_host in cd for cd in custom_domains):
                        chosen_url = item["href"]
                        logger.info(f"Matched Custom Website from Top 5 Search Results: {chosen_url}")
                        break

            if not chosen_url and self.swarm:
                def s_notify(m):
                    if notify_progress:
                        notify_progress(m, 22.0, "Search Ranker", 0)
                chosen_res = await self.swarm.evaluate_search_snippets(
                    top_results=top5_results,
                    story_topic=getattr(self.config, "session_intent_topic", query),
                    persona_name=getattr(self.config, "persona", "General"),
                    configured_model=getattr(self.config, "ai_model", None),
                    notify_cb=s_notify
                )
                if chosen_res:
                    chosen_url = chosen_res.get("href")

            if not chosen_url:
                ranks = list(range(len(top5_results)))
                weights = [5, 3, 2, 1, 1][:len(top5_results)]
                selected_idx = random.choices(ranks, weights=weights, k=1)[0]
                chosen_item = top5_results[selected_idx]
                chosen_url = chosen_item["href"]
                engine_name = "DuckDuckGo (NoGoogle)" if use_no_google else "Google"
                msg_txt = f"Selected Rank #{selected_idx + 1} {engine_name} Search Result: {chosen_url}"
                logger.info(msg_txt)
                if notify_progress:
                    notify_progress(msg_txt, 25.0, chosen_url, 0)

            if chosen_url:
                logger.info(f"Navigating to search result: {chosen_url}")
                await self._navigate(page, chosen_url, timeout=20000)
                await self.dismiss_cookie_banners(page)

                if PlatformInteractionAdapters.is_authority_site(chosen_url):
                    k_store.record_authority_visit(urlparse(chosen_url).netloc.lower())
                    await PlatformInteractionAdapters.interact_platform(page, chosen_url, self._evaluate, stop_check=lambda: self._stop_requested)
                else:
                    await self.human_scroll(page, dwell_time=5.0)

                if getattr(self.config, "click_depth", 0) > 0 and not self._stop_requested:
                    await self.explore_internal_links(page, chosen_url, depth=self.config.click_depth)

                return True

            return False
        except Exception as e:
            if self._is_window_closed(e, page):
                self._stop_requested = True
                logger.warning(f"Browser closed during search navigation: {e}")
            else:
                logger.warning(f"Error during search navigation: {e}")
            return False

    async def _navigate(self, page: Any, url: str, timeout: int = 20000) -> bool:
        if not page or not url:
            return False
        try:
            if hasattr(page, "goto"):
                for attempt in range(2):
                    try:
                        await page.goto(url, wait_until="domcontentloaded", timeout=timeout)
                        return True
                    except Exception as ex:
                        if self._is_window_closed(ex, page):
                            self._stop_requested = True
                            logger.warning(f"Target page or browser closed during goto to {url}.")
                            return False
                        if ("interrupted" in str(ex).lower() or "aborted" in str(ex).lower()) and attempt == 0:
                            logger.debug(f"Navigation to {url} was interrupted, retrying in 1s...")
                            await asyncio.sleep(1.0)
                            continue
                        logger.warning(f"Navigation attempt {attempt + 1} to {url} failed: {ex}")
                        if attempt == 1:
                            return False
                return False
            elif hasattr(page, "get"):
                await page.get(url)
                return True
            return False
        except Exception as e:
            if self._is_window_closed(e, page):
                self._stop_requested = True
                logger.warning(f"Target page or browser context closed during navigation to {url}.")
                return False
            logger.warning(f"Navigation error to {url}: {e}")
            return False

    async def _evaluate(self, page: Any, script: str, *args) -> Any:
        try:
            if hasattr(page, "evaluate"):
                return await page.evaluate(script, *args)
            elif hasattr(page, "evaluate_async"):
                return await page.evaluate_async(script, *args)
            elif hasattr(page, "send"):
                import nodriver as uc
                res = await page.send(uc.cdp.runtime.evaluate(expression=script, return_by_value=True))
                if res and hasattr(res, "result") and hasattr(res.result, "value"):
                    return res.result.value
                return None
        except Exception as e:
            if self._is_window_closed(e, page):
                self._stop_requested = True
            logger.debug(f"JS evaluation notice: {e}")
            return None

    async def _get_page_from_context(self, context: Any):
        if hasattr(context, "pages") and isinstance(context.pages, list):
            return context.pages[0] if context.pages else await context.new_page()
        elif hasattr(context, "main_tab"):
            return context.main_tab
        elif hasattr(context, "new_page"):
            return await context.new_page()
        elif hasattr(context, "tabs") and isinstance(context.tabs, list):
            return context.tabs[0] if context.tabs else context
        return context

    async def run_warmup(
        self,
        profile_id: str,
        config: Optional[WarmupConfig] = None,
        urls: Optional[List[str]] = None,
        max_pages: int = 5,
        progress_callback: Optional[Callable[[str, float, str, int], None]] = None
    ) -> bool:
        self._stop_requested = False
        cfg = copy.deepcopy(config) if config else WarmupConfig(max_pages=max_pages, urls=urls or [])

        def notify_progress(msg: str, percent: float, current_url: str = "", cookie_count: int = 0):
            logger.info(f"[Warmup:{profile_id}] {msg}")
            if progress_callback:
                try:
                    progress_callback(msg, percent, current_url, cookie_count)
                except Exception as cb_err:
                    logger.debug(f"Progress callback exception: {cb_err}")

            # Emit to central AsyncEventBus
            asyncio.create_task(
                self.event_bus.emit(
                    "warmup_progress",
                    profile_id=profile_id,
                    message=msg,
                    percent=percent,
                    current_url=current_url,
                    cookie_count=cookie_count
                )
            )

        # Pre-Flight Phase 1: ONNX Sentinel Tensor Consistency Audit
        profile_data = self.launcher.profile_manager.load_profile(profile_id) or {}
        profile_name = profile_data.get("name", f"Profile_{profile_id[:6]}")
        if self.swarm:
            try:
                def preflight_notify(m):
                    notify_progress(m, 2.0, "Pre-Flight", 0)
                await self.swarm.execute_warmup_preflight(profile_data, notify_cb=preflight_notify)
            except Exception as pf_err:
                logger.debug(f"[Warmup] Pre-flight audit note: {pf_err}")

        # Model readiness check
        try:
            from engine.ai_model_manager import AIModelManager
            ai_mgr = AIModelManager.get_instance()
            model_name = getattr(cfg, "ai_model", "qwen2.5:0.5b")
            if not await ai_mgr.is_ollama_running():
                notify_progress(f"Initializing local AI engine ('{model_name}')...", 3.0, "", 0)
                await ai_mgr.ensure_model_pulled(model_name)
        except Exception as ai_init_err:
            logger.debug(f"AI auto-start note: {ai_init_err}")

        # Phase 2: Intent- & Story-Synthese (Configured Strategy Model with unique query per profile)
        session_intent = ""
        if self.swarm:
            try:
                def story_notify(m):
                    notify_progress(m, 4.0, "Story Synthesizer", 0)
                story_data = await self.swarm.synthesize_warmup_story(
                    persona_key=cfg.persona,
                    custom_keywords=cfg.custom_keywords,
                    search_queries=cfg.search_queries,
                    configured_model=cfg.ai_model,
                    profile_name=profile_name,
                    profile_id=profile_id,
                    used_queries=self._session_used_queries,
                    notify_cb=story_notify
                )
                session_intent = story_data.get("primary_query", "")
            except Exception as story_err:
                logger.debug(f"[Warmup] Story synthesis note: {story_err}")

        if not session_intent:
            if cfg.custom_keywords:
                available_kw = [k for k in cfg.custom_keywords if k not in self._session_used_queries]
                session_intent = random.choice(available_kw or cfg.custom_keywords)
            elif cfg.search_queries:
                available_sq = [s for s in cfg.search_queries if s not in self._session_used_queries]
                session_intent = random.choice(available_sq or cfg.search_queries)
            else:
                persona_queries = PERSONA_PROFILES.get(cfg.persona, {}).get("queries", ["technology news 2026"])
                available_pq = [p for p in persona_queries if p not in self._session_used_queries]
                session_intent = random.choice(available_pq or persona_queries)

            self._session_used_queries.add(session_intent)

        cfg.session_intent_topic = session_intent
        logger.info(f"Warmup Session Topic Intent for profile '{profile_name}': '{session_intent}'")

        target_urls = []
        if cfg.custom_websites:
            target_urls = list(dict.fromkeys(cfg.custom_websites))
        elif cfg.urls:
            target_urls = list(dict.fromkeys(cfg.urls))
        else:
            if cfg.persona in PERSONA_PROFILES:
                target_urls = PersonaTrajectoryEngine.get_urls_for_persona(cfg.persona, cfg.max_pages)
            else:
                pool = WARMUP_CATEGORIES.get(cfg.category, WARMUP_CATEGORIES["general"])
                target_urls = random.sample(pool, min(cfg.max_pages, len(pool)))

        target_urls = target_urls[:cfg.max_pages]

        profile_dir = self.launcher.profile_manager.get_profile_path(profile_id)
        initial_metrics = CookieManager.get_profile_metrics(profile_dir)
        initial_cookies = initial_metrics["cookies"]
        initial_storage = initial_metrics["storage_items"]
        persona_name = PERSONA_PROFILES.get(cfg.persona, {}).get("name", "General")
        notify_progress(
            f"Launching profile [AI Persona: {persona_name}] (Cookies: {initial_cookies}, Storage: {initial_storage})...",
            5.0, "", initial_cookies
        )

        success, msg, context = await self.launcher.launch_profile(
            profile_id,
            headless=getattr(cfg, "headless", False),
            navigate_start_url=False
        )
        if not success or not context:
            logger.error(f"Failed to launch profile {profile_id} for warmup: {msg}")
            notify_progress(f"Launch failed: {msg}", 0.0, "", initial_cookies)
            return False

        if hasattr(context, "add_init_script"):
            try:
                from engine.warmup.consent_solver import AUTOWATCHER_SCRIPT
                await context.add_init_script(AUTOWATCHER_SCRIPT)
            except Exception as script_err:
                logger.debug(f"Init script injection note: {script_err}")

        try:
            page = await self._get_page_from_context(context)
            if hasattr(page, "add_init_script"):
                try:
                    from engine.warmup.consent_solver import AUTOWATCHER_SCRIPT
                    await page.add_init_script(AUTOWATCHER_SCRIPT)
                except Exception:
                    pass
            k_store = WarmupKnowledgeStore.get_instance()
            visited_pages = []

            # -------------------------------------------------------------
            # DEDICATED SEARCH & TOP-5 DEEP READER PIPELINE (Google or NoGoogle)
            # -------------------------------------------------------------
            if getattr(cfg, "mode", "standard") == "google_search_only" or cfg.persona == "google_search":
                search_query = cfg.session_intent_topic or PersonaTrajectoryEngine.get_search_query(cfg.persona, cfg.search_queries)
                use_no_google = getattr(cfg, "no_google", False)
                engine_title = "DuckDuckGo (NoGoogle)" if use_no_google else "Google"
                engine_base = "https://duckduckgo.com" if use_no_google else "https://www.google.com"

                notify_progress(f"{engine_title} Search & Top Deep Reader [Query: '{search_query}']", 10.0, engine_base, initial_cookies)

                max_deep_reads = min(getattr(cfg, "max_pages", 5), 5)
                if use_no_google:
                    top_results = await self.search_duckduckgo_and_extract_top_results(
                        page, search_query, max_results=max_deep_reads, notify_progress=notify_progress
                    )
                else:
                    top_results = await self.search_google_and_extract_top_results(
                        page, search_query, max_results=max_deep_reads, notify_progress=notify_progress
                    )

                if not top_results:
                    if use_no_google:
                        logger.warning("No DuckDuckGo organic search results returned, attempting direct search page extraction...")
                        fallback_url = f"https://duckduckgo.com/?q={quote_plus(search_query)}&ia=web"
                        await self._navigate(page, fallback_url, timeout=20000)
                        await self.dismiss_cookie_banners(page)
                        await asyncio.sleep(2.0)
                        top_results = await self.search_duckduckgo_and_extract_top_results(
                            page, search_query, max_results=max_deep_reads, notify_progress=notify_progress
                        )
                    else:
                        logger.warning("No Google organic search results returned, attempting direct search page extraction...")
                        fallback_url = f"https://www.google.com/search?q={quote_plus(search_query)}"
                        await self._navigate(page, fallback_url, timeout=20000)
                        await self.dismiss_cookie_banners(page)
                        await asyncio.sleep(2.0)
                        top_results = await self.search_google_and_extract_top_results(
                            page, search_query, max_results=max_deep_reads, notify_progress=notify_progress
                        )

                deep_read_targets = top_results[:max_deep_reads]
                total_steps = len(deep_read_targets) + 1
                completed_steps = 1

                for idx, res_item in enumerate(deep_read_targets):
                    if self._stop_requested:
                        notify_progress("Warmup stopped (window exit or user request).", 100.0, "", initial_cookies)
                        break

                    page_url = res_item.get("href", "")
                    link_title = res_item.get("text", "") or f"{engine_title} Search Result"
                    if not page_url:
                        continue

                    if cfg.self_learning_memory and k_store.is_known_trap(page_url):
                        logger.info(f"Skipping known Auth Trap URL: {page_url}")
                        continue

                    completed_steps += 1
                    pct = (completed_steps / total_steps) * 75.0 + 10.0
                    notify_progress(
                        f"{engine_title} Deep Reader [{idx + 1}/{len(deep_read_targets)}]: {link_title[:45]} ({page_url})",
                        pct, page_url, initial_cookies
                    )

                    try:
                        await self._navigate(page, page_url, timeout=20000)
                        if self._stop_requested:
                            break

                        if cfg.dismiss_banners:
                            await self.dismiss_cookie_banners(page)

                        if cfg.auto_evade_traps:
                            is_trap, reason, trap_type = await LoginAuthDetector.is_login_or_auth_wall(page, self._evaluate)
                            if is_trap:
                                if trap_type == "captcha_challenge" and getattr(cfg, "enable_captcha_solver", False):
                                    notify_progress(f"⎘ Captcha barrier detected on {page_url}. Solving with AI Swarm...", pct, page_url, initial_cookies)
                                    solved = await self._check_and_solve_captcha(page, notify_progress)
                                    if not solved:
                                        logger.warning(f"Captcha could not be solved on {page_url}. Evading...")
                                        k_store.record_trap(page_url, reason)
                                        notify_progress(f"Evaded Captcha Barrier: {reason}", pct, page_url, initial_cookies)
                                        await LoginAuthDetector.execute_humanoid_evasion(page, self._evaluate, stop_check=lambda: self._stop_requested)
                                        continue
                                else:
                                    logger.warning(f"Auth / Login Trap detected ('{reason}') on {page_url}! Executing evasion...")
                                    k_store.record_trap(page_url, reason)
                                    notify_progress(f"Evaded Auth Trap: {reason}", pct, page_url, initial_cookies)
                                    await LoginAuthDetector.execute_humanoid_evasion(page, self._evaluate, stop_check=lambda: self._stop_requested)
                                    continue
                        elif getattr(cfg, "enable_captcha_solver", False):
                            await self._check_and_solve_captcha(page, notify_progress)

                        if getattr(cfg, "enable_honeypot_shield", True):
                            def hp_notify(m):
                                notify_progress(m, pct, page_url, initial_cookies)
                            await self.scan_and_guard_honeypots(page, notify_progress=hp_notify)

                        if PlatformInteractionAdapters.is_authority_site(page_url):
                            k_store.record_authority_visit(urlparse(page_url).netloc.lower())
                            notify_progress(f"High-Authority Hub Interaction: {page_url}", pct, page_url, initial_cookies)
                            await PlatformInteractionAdapters.interact_platform(page, page_url, self._evaluate, stop_check=lambda: self._stop_requested)
                        else:
                            portal_handled = await SitePortalEngine.handle_portal_navigation(
                                page, page_url, self._evaluate, getattr(self, "ai_manager", None), cfg.persona, stop_check=lambda: self._stop_requested
                            )
                            if not portal_handled:
                                await self.human_scroll(page, dwell_time=cfg.dwell_time, persona=cfg.persona)

                        if cfg.click_depth > 0 and not self._stop_requested:
                            await self.explore_internal_links(page, page_url, depth=cfg.click_depth)

                        visited_pages.append(page_url)

                    except Exception as deep_err:
                        if self._is_window_closed(deep_err, page):
                            self._stop_requested = True
                            logger.warning(f"Browser closed during deep reading of {page_url}.")
                            break
                        else:
                            logger.warning(f"Note deep reading {page_url}: {deep_err}")

                    await asyncio.sleep(random.uniform(1.5, 3.0))

            # -------------------------------------------------------------
            # STANDARD WARMUP PIPELINE
            # -------------------------------------------------------------
            else:
                if getattr(cfg, "no_google", False):
                    # In NoGoogle mode, strictly purge any Google URLs from target list
                    target_urls = [u for u in target_urls if not any(g in urlparse(u).netloc.lower() for g in ["google.", "googleadservices.", "doubleclick."])]

                total_steps = len(target_urls) + (1 if cfg.enable_search else 0)
                completed_steps = 0

                if cfg.enable_search and not cfg.custom_websites and not self._stop_requested:
                    query = cfg.session_intent_topic or PersonaTrajectoryEngine.get_search_query(cfg.persona, cfg.search_queries)
                    completed_steps += 1
                    pct = (completed_steps / total_steps) * 75.0 + 10.0
                    search_engine_lbl = "DuckDuckGo (NoGoogle)" if getattr(cfg, "no_google", False) else "Search Engine"
                    notify_progress(f"Organic search ({search_engine_lbl}) [Topic: '{cfg.session_intent_topic}']: '{query}'", pct, search_engine_lbl, initial_cookies)
                    try:
                        await self.perform_search_navigation(page, query, notify_progress=notify_progress)
                    except Exception as s_err:
                        logger.debug(f"Search navigation note: {s_err}")

                for idx, page_url in enumerate(target_urls):
                    if self._stop_requested:
                        notify_progress("Warmup stopped (window exit or user request).", 100.0, "", initial_cookies)
                        break

                    if cfg.self_learning_memory and k_store.is_known_trap(page_url):
                        logger.info(f"Skipping known Auth Trap URL: {page_url}")
                        notify_progress(f"Skipped known Auth Trap: {page_url}", (idx + 1) / total_steps * 75.0 + 10.0, page_url, initial_cookies)
                        continue

                    completed_steps += 1
                    pct = (completed_steps / total_steps) * 75.0 + 10.0
                    notify_progress(f"Visiting site [{idx + 1}/{len(target_urls)}]: {page_url}", pct, page_url, initial_cookies)

                    try:
                        await self._navigate(page, page_url, timeout=20000)
                        if self._stop_requested:
                            break

                        if cfg.dismiss_banners:
                            await self.dismiss_cookie_banners(page)

                        if cfg.auto_evade_traps:
                            is_trap, reason, trap_type = await LoginAuthDetector.is_login_or_auth_wall(page, self._evaluate)
                            if is_trap:
                                if trap_type == "captcha_challenge" and getattr(cfg, "enable_captcha_solver", False):
                                    notify_progress(f"⎘ Captcha barrier detected on {page_url}. Solving with AI Swarm...", pct, page_url, initial_cookies)
                                    solved = await self._check_and_solve_captcha(page, notify_progress)
                                    if not solved:
                                        logger.warning(f"Captcha could not be solved on {page_url}. Evading...")
                                        k_store.record_trap(page_url, reason)
                                        notify_progress(f"Evaded Captcha Barrier: {reason}", pct, page_url, initial_cookies)
                                        await LoginAuthDetector.execute_humanoid_evasion(page, self._evaluate, stop_check=lambda: self._stop_requested)
                                        continue
                                else:
                                    logger.warning(f"Auth / Login Trap detected ('{reason}') on {page_url}! Executing evasion...")
                                    k_store.record_trap(page_url, reason)
                                    notify_progress(f"Evaded Auth Trap: {reason}", pct, page_url, initial_cookies)
                                    await LoginAuthDetector.execute_humanoid_evasion(page, self._evaluate, stop_check=lambda: self._stop_requested)
                                    continue
                        elif getattr(cfg, "enable_captcha_solver", False):
                            await self._check_and_solve_captcha(page, notify_progress)

                        if getattr(cfg, "enable_honeypot_shield", True):
                            def hp_notify(m):
                                notify_progress(m, pct, page_url, initial_cookies)
                            await self.scan_and_guard_honeypots(page, notify_progress=hp_notify)

                        if PlatformInteractionAdapters.is_authority_site(page_url):
                            k_store.record_authority_visit(urlparse(page_url).netloc.lower())
                            notify_progress(f"High-Authority Hub Interaction: {page_url}", pct, page_url, initial_cookies)
                            await PlatformInteractionAdapters.interact_platform(page, page_url, self._evaluate, stop_check=lambda: self._stop_requested)
                        else:
                            portal_handled = await SitePortalEngine.handle_portal_navigation(
                                page, page_url, self._evaluate, getattr(self, "ai_manager", None), cfg.persona, stop_check=lambda: self._stop_requested
                            )
                            if not portal_handled:
                                await self.human_scroll(page, dwell_time=cfg.dwell_time)

                        if cfg.click_depth > 0 and not self._stop_requested:
                            await self.explore_internal_links(page, page_url, depth=cfg.click_depth)

                        visited_pages.append(page_url)

                    except Exception as visit_err:
                        if self._is_window_closed(visit_err, page):
                            self._stop_requested = True
                            logger.warning(f"Browser closed during site visit to {page_url}.")
                            break
                        else:
                            logger.warning(f"Note visiting {page_url}: {visit_err}")

                    await asyncio.sleep(random.uniform(1.5, 3.0))

            final_metrics = CookieManager.get_profile_metrics(profile_dir)
            gained_cookies = max(0, final_metrics["cookies"] - initial_cookies)
            gained_storage = max(0, final_metrics["storage_items"] - initial_storage)

            # Phase 8: Post-Warmup Trust & Anomaly Audit
            trust_score_val = 88.0
            if self.swarm:
                try:
                    def post_audit_notify(m):
                        notify_progress(m, 95.0, "Post-Audit", final_metrics["cookies"])
                    trust_score_val, trust_details = await self.swarm.audit_post_warmup(
                        profile_data=profile_data,
                        page=page,
                        context=context,
                        initial_cookies=initial_cookies,
                        final_cookies=final_metrics["cookies"],
                        notify_cb=post_audit_notify
                    )
                    profile_data["trust_score"] = trust_score_val
                    profile_data["trust_details"] = trust_details
                    self.launcher.profile_manager.save_profile(profile_data)
                except Exception as post_audit_err:
                    logger.debug(f"[Warmup] Post-audit note: {post_audit_err}")
            else:
                try:
                    from engine.trust_score_evaluator import ProfileTrustEvaluator
                    trust_score, trust_details = await ProfileTrustEvaluator.evaluate_profile_trust(
                        profile_data=profile_data,
                        page=page,
                        context=context
                    )
                    profile_data["trust_score"] = trust_score
                    profile_data["trust_details"] = trust_details
                    self.launcher.profile_manager.save_profile(profile_data)
                    trust_score_val = trust_score
                except Exception as trust_err:
                    logger.debug(f"Trust Score evaluation note: {trust_err}")

            for visited in (visited_pages or target_urls):
                k_store.record_visit_success(visited, gained_cookies)

            notify_progress(
                f"Completed! Gained +{gained_cookies} cookies, +{gained_storage} storage items (Total: {final_metrics['cookies']} cookies, Trust Score: {trust_score_val}%).",
                100.0, "Done", final_metrics["cookies"]
            )
            logger.info(f"Cookie Warmup finished for profile '{profile_id}' (+{gained_cookies} cookies, +{gained_storage} storage items, Trust Score: {trust_score_val}%).")
            return True

        except Exception as e:
            if any(term in str(e).lower() for term in ["closed", "target", "destroyed", "context"]):
                logger.warning(f"Browser window exit detected for profile {profile_id}. Clean exit.")
            else:
                logger.warning(f"Error during Cookie Warmup execution for {profile_id}: {e}")
            notify_progress("Warmup finished.", 100.0, "", initial_cookies)
            return True
        finally:
            try:
                await self.launcher.stop_profile(profile_id)
            except Exception:
                pass
