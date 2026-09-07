import asyncio
import json
import logging
import math
import os
import random
import re
import time
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import urlparse

from engine.warmup.human_motion import BiomechanicalMotor, BiGramTypingEngine, get_lognormal_delay
from engine.warmup.consent_solver import SemanticBannerResolver

logger = logging.getLogger("TrajectoryPlanner")

# ============================================================================
# BEHAVIORAL DATASTRUCTURES & PRESETS
# ============================================================================

WARMUP_CATEGORIES: Dict[str, List[str]] = {
    "general": [
        "https://www.wikipedia.org", "https://www.bbc.com", "https://www.reuters.com",
        "https://www.nationalgeographic.com", "https://www.smithsonianmag.com", "https://www.theguardian.com",
        "https://www.nytimes.com", "https://www.scientificamerican.com", "https://www.wired.com",
        "https://www.theverge.com", "https://www.bloomberg.com", "https://www.economist.com",
        "https://www.time.com", "https://www.vox.com", "https://www.theatlantic.com",
        "https://www.newyorker.com", "https://www.npr.org", "https://www.usatoday.com",
        "https://www.dw.com", "https://www.spiegel.de", "https://www.lemonde.fr"
    ],
    "news": [
        "https://www.bbc.com/news", "https://www.reuters.com", "https://www.cnn.com",
        "https://www.nytimes.com", "https://www.theguardian.com/world", "https://www.aljazeera.com",
        "https://www.bloomberg.com/news", "https://www.apnews.com", "https://www.cnbc.com",
        "https://www.france24.com/en", "https://www.independent.co.uk", "https://www.wsj.com",
        "https://www.euronews.com", "https://www.dw.com/en", "https://www.forbes.com"
    ],
    "tech": [
        "https://techcrunch.com", "https://www.theverge.com", "https://arstechnica.com",
        "https://news.ycombinator.com", "https://github.com", "https://stackoverflow.com",
        "https://dev.to", "https://www.producthunt.com", "https://pypi.org",
        "https://www.wired.com/category/gear", "https://www.engadget.com", "https://www.tomshardware.com",
        "https://www.anandtech.com", "https://www.macrumors.com", "https://9to5mac.com",
        "https://slashdot.org", "https://lobste.rs", "https://www.bleepingcomputer.com"
    ],
    "science": [
        "https://www.nature.com", "https://www.science.org", "https://www.sciencedaily.com",
        "https://www.quantamagazine.org", "https://www.space.com", "https://www.phys.org",
        "https://www.newscientist.com", "https://www.scientificamerican.com", "https://www.livescience.com",
        "https://earthsky.org", "https://www.astronomy.com", "https://phys.org/physics-news"
    ],
    "ecommerce": [
        "https://www.amazon.com", "https://www.ebay.com", "https://www.etsy.com",
        "https://www.bestbuy.com", "https://www.target.com", "https://www.walmart.com",
        "https://www.aliexpress.com", "https://www.newegg.com", "https://www.bhphotovideo.com",
        "https://www.ikea.com", "https://www.wayfair.com", "https://www.homedepot.com"
    ],
    "social": [
        "https://www.reddit.com", "https://news.ycombinator.com", "https://medium.com",
        "https://www.quora.com", "https://www.pinterest.com", "https://www.linkedin.com",
        "https://dev.to", "https://www.behance.net", "https://dribbble.com", "https://www.goodreads.com"
    ],
    "travel": [
        "https://www.lonelyplanet.com", "https://www.tripadvisor.com", "https://www.nationalgeographic.com/travel",
        "https://www.cntraveler.com", "https://www.travelandleisure.com", "https://www.atlasobscura.com",
        "https://www.nomadicmatt.com", "https://www.roughguides.com", "https://www.timeout.com"
    ],
    "food": [
        "https://www.allrecipes.com", "https://www.seriouseats.com", "https://www.bonappetit.com",
        "https://www.epicurious.com", "https://www.foodandwine.com", "https://www.tasteofhome.com",
        "https://cooking.nytimes.com", "https://www.delish.com", "https://www.simplyrecipes.com"
    ],
    "design": [
        "https://www.archdaily.com", "https://www.dezeen.com", "https://www.designboom.com",
        "https://www.smashingmagazine.com", "https://sidebar.io", "https://www.awwwards.com",
        "https://www.creativebloq.com", "https://abduzeedo.com", "https://www.wallpaper.com"
    ],
    "gaming": [
        "https://www.ign.com", "https://www.gamespot.com", "https://www.pcgamer.com",
        "https://www.eurogamer.net", "https://www.polygon.com", "https://kotaku.com",
        "https://www.rockpapershotgun.com", "https://www.destructoid.com"
    ],
    "fingerprint": [
        "https://www.browserscan.net", "https://browserleaks.com", "https://dnsleaktest.com",
        "https://iphey.com", "https://bot.sannysoft.com", "https://amiunique.org",
        "https://pixelscan.net", "https://coveryourtracks.eff.org", "https://whoer.net",
        "https://abrahamjuliot.github.io/creepjs/"
    ]
}

DEFAULT_WARMUP_URLS = WARMUP_CATEGORIES["general"]

DEFAULT_SEARCH_QUERIES = [
    "latest space exploration discoveries 2026",
    "best mechanical keyboards for software engineers",
    "modern clean energy transitions and solar efficiency",
    "python async performance optimization guide",
    "top sustainable architecture design trends",
    "best travel destinations off the beaten path",
    "healthy Mediterranean dinner recipes and meal prep",
    "open source micro LLM development benchmarks",
    "modern web UI typography and minimalist design inspiration",
    "deep sea marine biology new species catalog",
    "quantum computing hardware breakthroughs 2026",
    "ergonomic workspace setups for remote programmers",
    "organic gardening tips for beginners",
    "history of ancient civilisations archaeological findings",
    "rust embedded systems memory safety best practices",
    "best noise canceling headphones studio review",
    "high altitude mountain trekking packing checklist",
    "modern sourdough bread baking science and fermentation",
    "electric vehicle solid state battery advancements",
    "astronomy telescope guide for stargazing",
    "minimalist home office desk accessories",
    "urban vertical farming sustainable agriculture",
    "modern cyber threat intelligence and cryptography trends",
    "classical music history and symphonic analysis",
    "cloud infrastructure scaling patterns kubernetes"
]

PERSONA_PROFILES: Dict[str, Dict[str, Any]] = {
    "general": {
        "name": "General Consumer",
        "categories": ["general", "news", "science", "travel", "food", "design"],
        "queries": DEFAULT_SEARCH_QUERIES,
        "wpm_target": 220,
        "internal_click_prob": 0.65,
    },
    "tech": {
        "name": "Tech Enthusiast & Developer",
        "categories": ["tech", "science", "news"],
        "queries": [
            "python async performance optimization",
            "rust vs c++ embedded benchmarks 2026",
            "open source micro LLM quantization guide",
            "kubernetes architecture updates",
            "frontend frameworks comparison 2026",
            "cloud native computing foundation landscape",
            "cybersecurity vulnerability disclosure guide"
        ],
        "wpm_target": 260,
        "internal_click_prob": 0.80,
    },
    "ecommerce": {
        "name": "E-Commerce Buyer",
        "categories": ["ecommerce", "tech", "design"],
        "queries": [
            "best noise canceling headphones studio review",
            "ergonomic desk setup ideas for home office",
            "wireless mechanical keyboards deals 2026",
            "smart home automation hub comparison",
            "lightweight water resistant travel backpacks"
        ],
        "wpm_target": 200,
        "internal_click_prob": 0.75,
    },
    "news": {
        "name": "News & Media Reader",
        "categories": ["news", "general", "science"],
        "queries": [
            "breaking global economic news today",
            "renewable energy policy and solar developments",
            "space exploration telescope discoveries 2026",
            "tech industry quarterly earnings report"
        ],
        "wpm_target": 240,
        "internal_click_prob": 0.70,
    },
    "social": {
        "name": "Community & Social Explorer",
        "categories": ["social", "tech", "design"],
        "queries": [
            "top discussion topics on hacker news",
            "creative architecture and minimalist interior trends",
            "open source development community showcases",
            "best independent software engineering publications"
        ],
        "wpm_target": 210,
        "internal_click_prob": 0.85,
    },
    "fingerprint": {
        "name": "Browser Fingerprint & Privacy Auditor",
        "categories": ["fingerprint", "tech"],
        "queries": [
            "browser fingerprint test online",
            "dns leak test check",
            "webgl canvas fingerprint test",
            "bot sannysoft detection check",
            "antidetect browser privacy score"
        ],
        "wpm_target": 200,
        "internal_click_prob": 0.50,
    },
    "google_search": {
        "name": "Google Search & Top-5 Deep Reader",
        "categories": ["general", "tech", "news", "science"],
        "queries": DEFAULT_SEARCH_QUERIES,
        "wpm_target": 230,
        "internal_click_prob": 0.75,
    }
}


class WarmupKnowledgeStore:
    """Self-Learning Knowledge Base & Reinforcement Store.
    Persists trajectory experiences, trap counts, domain scores, and high-yield paths
    to avoid repeating auth trap mistakes across profile warmup sessions.
    """
    _instance: Optional['WarmupKnowledgeStore'] = None

    def __init__(self, data_path: Optional[str] = None):
        if not data_path:
            try:
                import config
                data_path = os.path.join(config.SESSIONS_DIR, "warmup_knowledge.json")
            except Exception:
                data_path = os.path.join(os.path.expanduser("~"), ".soxbot_warmup_knowledge.json")
        self.data_path = data_path
        self.learned_traps: Dict[str, Dict[str, Any]] = {}
        self.domain_stats: Dict[str, Dict[str, Any]] = {}
        self.audit_reports: Dict[str, Dict[str, Any]] = {}
        self.traps_avoided_count: int = 0
        self._load_store()

    @classmethod
    def get_instance(cls) -> 'WarmupKnowledgeStore':
        if cls._instance is None:
            cls._instance = WarmupKnowledgeStore()
        return cls._instance

    def _load_store(self):
        try:
            if os.path.exists(self.data_path):
                with open(self.data_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.learned_traps = data.get("learned_traps", {})
                    self.domain_stats = data.get("domain_stats", {})
                    self.audit_reports = data.get("audit_reports", {})
                    self.traps_avoided_count = data.get("traps_avoided_count", 0)
        except Exception as e:
            logger.debug(f"WarmupKnowledgeStore load notice: {e}")

    def save_store(self):
        try:
            os.makedirs(os.path.dirname(self.data_path), exist_ok=True)
            with open(self.data_path, "w", encoding="utf-8") as f:
                json.dump({
                    "learned_traps": self.learned_traps,
                    "domain_stats": self.domain_stats,
                    "audit_reports": self.audit_reports,
                    "traps_avoided_count": self.traps_avoided_count
                }, f, indent=2)
        except Exception as e:
            logger.debug(f"WarmupKnowledgeStore save notice: {e}")

    def record_trap(self, url: str, reason: str):
        parsed = urlparse(url)
        netloc = parsed.netloc.lower()
        clean_url = f"{parsed.scheme}://{netloc}{parsed.path}" if parsed.scheme else url
        
        self.learned_traps[clean_url] = {
            "reason": reason,
            "timestamp": time.time(),
            "hits": self.learned_traps.get(clean_url, {}).get("hits", 0) + 1
        }
        self.traps_avoided_count += 1

        if netloc:
            st = self.domain_stats.setdefault(netloc, {"visits": 0, "traps": 0, "cookies_gained": 0, "score": 1.0})
            st["traps"] += 1
            st["score"] = max(0.0, (st["cookies_gained"] + 1) / (st["visits"] + st["traps"] * 3.0))

        self.save_store()

    def record_authority_visit(self, domain: str):
        st = self.domain_stats.setdefault(domain, {"visits": 0, "traps": 0, "cookies_gained": 0, "authority": True, "score": 1.5})
        st["visits"] += 1
        st["authority"] = True
        self.save_store()

    def record_visit_success(self, url: str, cookies_gained: int):
        netloc = urlparse(url).netloc.lower()
        if netloc:
            st = self.domain_stats.setdefault(netloc, {"visits": 0, "traps": 0, "cookies_gained": 0, "score": 1.0})
            st["visits"] += 1
            st["cookies_gained"] += max(0, cookies_gained)
            st["score"] = max(0.1, (st["cookies_gained"] + 1) / (st["visits"] + st["traps"] * 3.0))
            self.save_store()

    def is_known_trap(self, url: str) -> bool:
        parsed = urlparse(url)
        netloc = parsed.netloc.lower()
        clean_url = f"{parsed.scheme}://{netloc}{parsed.path}" if parsed.scheme else url
        if clean_url in self.learned_traps:
            return True
        if netloc in self.domain_stats:
            st = self.domain_stats[netloc]
            if st["traps"] >= 3 and st["traps"] > st["visits"]:
                return True
        return False

    def get_domain_score(self, domain: str) -> float:
        d = domain.lower()
        if d in self.domain_stats:
            return float(self.domain_stats[d].get("score", 1.0))
        return 1.0

    def record_audit_finding(self, url: str, score: int, alerts: List[str]):
        netloc = urlparse(url).netloc.lower()
        if netloc:
            self.audit_reports[netloc] = {
                "url": url,
                "score": score,
                "alerts": alerts,
                "timestamp": time.time()
            }
            self.save_store()

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_learned_domains": len(self.domain_stats),
            "total_traps_recorded": len(self.learned_traps),
            "total_traps_avoided": self.traps_avoided_count,
            "total_audits_logged": len(self.audit_reports)
        }


IS_AUTH_TRAP_SCRIPT = """
(() => {
    // 1. CAPTCHA / Cloudflare / Google sorry/index Challenge detection (TOP PRIORITY)
    const url = (window.location.href || '').toLowerCase();
    if (url.includes('sorry/index') || url.includes('/recaptcha/') || url.includes('recaptcha.net')) {
        return { is_trap: true, reason: 'Google reCAPTCHA / Sorry Barrier detected', trap_type: 'captcha_challenge' };
    }

    const iframes = Array.from(document.querySelectorAll('iframe'));
    for (const frame of iframes) {
        const src = (frame.getAttribute('src') || '').toLowerCase();
        const title = (frame.getAttribute('title') || '').toLowerCase();
        if (src.includes('challenges.cloudflare.com') || src.includes('recaptcha') || src.includes('hcaptcha') || src.includes('turnstile') || title.includes('recaptcha') || title.includes('challenge')) {
            return { is_trap: true, reason: 'Cloudflare / CAPTCHA challenge barrier detected', trap_type: 'captcha_challenge' };
        }
    }

    const hasCaptchaDom = !!document.querySelector('#recaptcha-anchor, .recaptcha-checkbox, div#captcha, #captcha-form, form#captcha-form, div.g-recaptcha');
    if (hasCaptchaDom) {
        return { is_trap: true, reason: 'reCAPTCHA DOM element detected', trap_type: 'captcha_challenge' };
    }

    // Helper: ignore elements located inside cookie consent banners
    function isInsideConsent(el) {
        let p = el;
        while (p && p !== document.body && p !== document.documentElement) {
            const cls = (p.getAttribute ? (p.getAttribute('class') || '') : '').toLowerCase();
            const id = (p.id || '').toLowerCase();
            if (id.includes('cookie') || id.includes('consent') || id.includes('privacy') || id.includes('cmp') ||
                id.includes('usercentrics') || id.includes('onetrust') || id.includes('didomi') || id.includes('cookiebot') ||
                cls.includes('cookie') || cls.includes('consent') || cls.includes('privacy') || cls.includes('cmp') ||
                cls.includes('usercentrics') || cls.includes('onetrust') || cls.includes('didomi') || cls.includes('cookiebot')) {
                return true;
            }
            p = p.parentElement;
        }
        return false;
    }

    // 2. Password input detection
    const passInputs = Array.from(document.querySelectorAll('input[type="password"], input[name*="pass"], input[id*="pass"], input[autocomplete="current-password"], input[autocomplete="new-password"]'));
    const visiblePassInputs = passInputs.filter(el => {
        if (isInsideConsent(el)) return false;
        const style = window.getComputedStyle(el);
        const rect = el.getBoundingClientRect();
        return style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0;
    });
    if (visiblePassInputs.length > 0) {
        return { is_trap: true, reason: 'Visible password input field detected', trap_type: 'password_field' };
    }

    // 3. Auth Form ID / Class / Action detection
    const forms = Array.from(document.querySelectorAll('form'));
    for (const f of forms) {
        if (isInsideConsent(f)) continue;
        const act = (f.getAttribute('action') || '').toLowerCase();
        const id = (f.id || '').toLowerCase();
        const cls = (f.className || '').toString().toLowerCase();
        if (act.includes('login') || act.includes('signin') || act.includes('auth') || act.includes('sso') || act.includes('checkpoint') ||
            id.includes('login') || id.includes('signin') || id.includes('auth') ||
            cls.includes('login') || cls.includes('signin') || cls.includes('auth-modal')) {
            const inputs = f.querySelectorAll('input[type="text"], input[type="email"], input[type="password"]');
            if (inputs.length > 0) {
                return { is_trap: true, reason: `Authentication form detected (${id || cls || act})`, trap_type: 'auth_form' };
            }
        }
    }

    // 4. Page Title & Main Heading Multi-lingual Text Inspection
    const pageTitle = (document.title || '').trim().toLowerCase();
    const headings = Array.from(document.querySelectorAll('h1, h2')).filter(h => !isInsideConsent(h)).map(h => (h.innerText || h.textContent || '').trim().toLowerCase());
    const authKeywords = [
        'log in', 'login', 'sign in', 'signin', 'sign up', 'signup',
        'anmelden', 'einloggen', 'registrieren',
        'se connecter', 'connexion', 'iniciar sesión', 'accedi',
        'account verification', 'security check', 'enter password',
        'passwort eingeben', 'verify your identity', 'cloudflare turnstile', 'just a moment...'
    ];

    for (const kw of authKeywords) {
        if (pageTitle.includes(kw)) {
            return { is_trap: true, reason: `Auth title indicator detected ('${kw}')`, trap_type: 'auth_title' };
        }
        for (const h of headings) {
            if (h.length < 50 && h.includes(kw)) {
                return { is_trap: true, reason: `Auth heading indicator detected ('${kw}')`, trap_type: 'auth_heading' };
            }
        }
    }

    // 5. OAuth & Social Sign-In Buttons
    const oauthBtns = Array.from(document.querySelectorAll('button, a, div[role="button"]')).filter(el => {
        if (isInsideConsent(el)) return false;
        const txt = (el.innerText || el.textContent || '').toLowerCase();
        return (txt.includes('sign in with') || txt.includes('log in with') || txt.includes('mit google anmelden') || txt.includes('mit apple anmelden') || txt.includes('continue with google') || txt.includes('continue with apple'));
    });
    if (oauthBtns.length > 0) {
        return { is_trap: true, reason: 'Social OAuth sign-in portal detected', trap_type: 'oauth_portal' };
    }

    return { is_trap: false, reason: '', trap_type: 'none' };
})()
"""


class LoginAuthDetector:
    """Multi-lingual Login & Auth Trap Detector & Humanoid Evasion Engine."""

    AUTH_URL_REGEX = re.compile(
        r"/(?:login|logging|signin|sign-in|signup|sign-up|register|registration|auth|authentication|sso|oauth|checkpoint|passport|account|myaccount|user/login|users/sign_in|session|sessions|anmelden|registrieren|einloggen|connexion|inscription|iniciar-sesion|registro|accedi|entrar|cadastrar|cart|checkout|basket|warenkorb|subscribe|membership|paywall|verify|challenge|identity)\b",
        re.IGNORECASE
    )

    AUTH_TEXT_REGEX = re.compile(
        r"\b(?:log\s*in|sign\s*in|sign\s*up|register|create\s*account|my\s*account|anmelden|registrieren|einloggen|konto\s*erstellen|se\s*connecter|s'inscrire|créer\s*un\s*compte|iniciar\s*sesión|registrarse|crear\s*cuenta|accedi|registrati|crea\s*account|enter\s*password|passwort\s*eingeben|mot\s*de\s*passe|subscriber\s*only|subscribe\s*now)\b",
        re.IGNORECASE
    )

    @classmethod
    def url_matches_auth_pattern(cls, url: str) -> bool:
        if not url:
            return False
        try:
            parsed = urlparse(url)
            path_query = (parsed.path + "?" + parsed.query).lower()
            return bool(cls.AUTH_URL_REGEX.search(path_query))
        except Exception:
            return False

    @classmethod
    def link_text_matches_auth_pattern(cls, text: str) -> bool:
        if not text:
            return False
        return bool(cls.AUTH_TEXT_REGEX.search(text))

    @classmethod
    async def is_login_or_auth_wall(cls, page: Any, evaluate_fn: Callable) -> Tuple[bool, str, str]:
        try:
            res = await evaluate_fn(page, IS_AUTH_TRAP_SCRIPT)
            if res and isinstance(res, dict) and res.get("is_trap"):
                return True, str(res.get("reason", "Auth trap")), str(res.get("trap_type", "unknown"))
            return False, "", "none"
        except Exception as e:
            logger.debug(f"LoginAuthDetector scan notice: {e}")
            return False, "", "none"

    @classmethod
    async def execute_humanoid_evasion(
        cls,
        page: Any,
        evaluate_fn: Callable,
        stop_check: Optional[Callable[[], bool]] = None
    ) -> bool:
        try:
            logger.info("Executing Humanoid Evasion Retreat: Realized auth trap / wrong page...")
            await asyncio.sleep(random.uniform(0.35, 0.65))
            if stop_check and stop_check():
                return False

            cur_x = random.randint(300, 600)
            cur_y = random.randint(300, 600)
            back_btn_x = random.randint(35, 65)
            back_btn_y = random.randint(35, 55)

            await BiomechanicalMotor.move_mouse_humanoid(
                page, cur_x, cur_y, back_btn_x, back_btn_y, target_width=30.0, stop_check=stop_check
            )
            await asyncio.sleep(random.uniform(0.25, 0.45))

            if hasattr(page, "go_back"):
                try:
                    await page.go_back(wait_until="domcontentloaded", timeout=8000)
                    logger.info("Humanoid Evasion successful: Executed page.go_back().")
                    return True
                except Exception:
                    pass

            await evaluate_fn(page, "(() => window.history.back())()")
            await asyncio.sleep(random.uniform(0.8, 1.5))
            logger.info("Humanoid Evasion fallback: Triggered window.history.back().")
            return True
        except Exception as e:
            logger.debug(f"Humanoid evasion note: {e}")
            return False


class BrowserVerificationSuite:
    """Active Real-Time Fingerprint & Leak Audit Engine."""

    VERIFICATION_DOMAINS = [
        "browserscan.net", "browserleaks.com", "dnsleaktest.com",
        "iphey.com", "sannysoft.com", "amiunique.org",
        "pixelscan.net", "eff.org", "whoer.net", "github.io/creepjs"
    ]

    @classmethod
    def is_verification_site(cls, url: str) -> bool:
        if not url:
            return False
        u = url.lower()
        return any(domain in u for domain in cls.VERIFICATION_DOMAINS)


class SitePortalEngine:
    """Site Portal & AI Copilot Interaction Engine for Bing and Google."""

    @classmethod
    async def handle_portal_navigation(
        cls,
        page: Any,
        url: str,
        evaluate_fn: Callable,
        ai_manager: Any,
        persona: str,
        stop_check: Optional[Callable[[], bool]] = None
    ) -> bool:
        if not url:
            return False
        try:
            await SemanticBannerResolver.resolve_consent_banners(page, evaluate_fn)
        except Exception:
            pass
        netloc = urlparse(url).netloc.lower()
        if "bing.com" in netloc:
            return await cls._handle_bing_portal(page, evaluate_fn, ai_manager, persona, stop_check)
        elif "google.com" in netloc:
            return await cls._handle_google_portal(page, evaluate_fn, ai_manager, persona, stop_check)
        return False

    @classmethod
    async def _handle_bing_portal(
        cls,
        page: Any,
        evaluate_fn: Callable,
        ai_manager: Any,
        persona: str,
        stop_check: Optional[Callable[[], bool]] = None
    ) -> bool:
        choice = random.choices(["trending_news", "copilot", "search"], weights=[0.60, 0.25, 0.15], k=1)[0]
        logger.info(f"Bing Portal Strategy Choice: '{choice}'")

        if choice == "trending_news":
            try:
                await evaluate_fn(page, "window.scrollBy({top: 380, behavior: 'smooth'});")
                await asyncio.sleep(random.uniform(0.8, 1.5))

                stories_script = """
                (() => {
                    const bad = /(video|watch|youtube|vimeo|tiktok|shorts|privacy|terms|login|signin|cart|checkout)/i;
                    const selectors = [
                        'a[href*="msn.com"]', 'a[href*="news"]', '#hp_news a', '#trending_topics a',
                        '.nws_card a', '.news-card a', '#headline a', 'a.title', '[data-module="news"] a',
                        'div[class*="news"] a', 'div[class*="story"] a', 'div[class*="article"] a', 'a.hp_sw_a'
                    ];
                    const elements = Array.from(document.querySelectorAll(selectors.join(',')));
                    const candidates = [];
                    for (const el of elements) {
                        const href = el.href || '';
                        const text = (el.innerText || el.textContent || '').trim();
                        const rect = el.getBoundingClientRect();
                        if (href && text.length > 8 && rect.width > 20 && rect.height > 15 && rect.top > 0 && rect.top < (window.innerHeight + 200)) {
                            if (!bad.test(href) && !bad.test(text)) {
                                candidates.push({
                                    href: href,
                                    text: text.slice(0, 50),
                                    x: rect.left + rect.width / 2.0,
                                    y: rect.top + rect.height / 2.0,
                                    w: rect.width
                                });
                            }
                        }
                    }
                    return candidates;
                })()
                """
                stories = await evaluate_fn(page, stories_script)
                if stories and isinstance(stories, list) and len(stories) > 0:
                    chosen = random.choice(stories[:6])
                    cx, cy = chosen["x"], chosen["y"]
                    title = chosen.get("text", "")
                    logger.info(f"Found Bing News Card ['{title}']. Navigating...")

                    await BiomechanicalMotor.move_mouse_humanoid(page, 300, 300, cx, cy, target_width=chosen.get("w", 50.0), stop_check=stop_check)
                    await BiomechanicalMotor.humanoid_idle_sleep(page, random.uniform(0.4, 0.8), cx, cy, stop_check=stop_check)

                    if hasattr(page, "mouse") and hasattr(page.mouse, "click"):
                        await page.mouse.click(cx, cy)
                        await asyncio.sleep(3.0)
                        await SemanticBannerResolver.resolve_consent_banners(page, evaluate_fn)
                        await ContentAwareReader.analyze_page_and_dwell(page, evaluate_fn, base_dwell=12.0, stop_check=stop_check)
                        return True
            except Exception as e:
                logger.debug(f"Bing news card note: {e}")

        elif choice == "copilot" and ai_manager:
            try:
                copilot_script = """
                (() => {
                    const btns = Array.from(document.querySelectorAll('a[href*="copilot"], #b_copilot, [aria-label*="Copilot"], button[title*="Copilot"], .copilot-button'));
                    for (const b of btns) {
                        const rect = b.getBoundingClientRect();
                        if (rect.width > 0 && rect.height > 0) {
                            return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2, width: rect.width };
                        }
                    }
                    return null;
                })()
                """
                box = await evaluate_fn(page, copilot_script)
                if box and isinstance(box, dict) and box.get("x", 0) > 0:
                    cx, cy = box["x"], box["y"]
                    await BiomechanicalMotor.move_mouse_humanoid(page, 200, 200, cx, cy, target_width=box.get("width", 40.0), stop_check=stop_check)
                    await BiomechanicalMotor.humanoid_idle_sleep(page, 0.3, cx, cy, stop_check=stop_check)
                    if hasattr(page, "mouse") and hasattr(page.mouse, "click"):
                        await page.mouse.click(cx, cy)
                        await asyncio.sleep(2.0)

                        question = await ai_manager.generate_copilot_prompt(persona)
                        logger.info(f"Asking Copilot question: '{question}'")
                        chat_selector = "textarea, input[type='text'], #searchbox"
                        await BiGramTypingEngine.type_humanoid(page, chat_selector, question, evaluate_fn, stop_check=stop_check)
                        await asyncio.sleep(4.0)
                        await ContentAwareReader.analyze_page_and_dwell(page, evaluate_fn, base_dwell=7.0, stop_check=stop_check)
                        return True
            except Exception as e:
                logger.debug(f"Bing Copilot interaction note: {e}")

        return False

    @classmethod
    async def _handle_google_portal(
        cls,
        page: Any,
        evaluate_fn: Callable,
        ai_manager: Any,
        persona: str,
        stop_check: Optional[Callable[[], bool]] = None
    ) -> bool:
        try:
            if random.random() < 0.35:
                news_script = """
                (() => {
                    const links = Array.from(document.querySelectorAll('a[href*="news.google.com"], a[aria-label*="News"]'));
                    return links.map(a => a.href).filter(h => h && h.length > 5);
                })()
                """
                n_links = await evaluate_fn(page, news_script)
                if n_links and isinstance(n_links, list) and len(n_links) > 0:
                    target_url = random.choice(n_links)
                    logger.info(f"Navigating Google News portal: {target_url}")
                    await page.goto(target_url, wait_until="domcontentloaded", timeout=15000)
                    await SemanticBannerResolver.resolve_consent_banners(page, evaluate_fn)
                    await ContentAwareReader.analyze_page_and_dwell(page, evaluate_fn, base_dwell=7.0, stop_check=stop_check)
                    return True
        except Exception as e:
            logger.debug(f"Google portal note: {e}")
        return False


class PlatformInteractionAdapters:
    """High-Authority Site Platform Adapters (Reddit, Wikipedia, GitHub, StackOverflow)."""

    AUTHORITY_DOMAINS = [
        "reddit.com", "stackoverflow.com", "wikipedia.org", "github.com",
        "medium.com", "ycombinator.com", "quora.com", "pypi.org",
        "nytimes.com", "theverge.com", "techcrunch.com", "bbc.com"
    ]

    @classmethod
    def is_authority_site(cls, url: str) -> bool:
        if not url:
            return False
        netloc = urlparse(url).netloc.lower()
        return any(domain in netloc for domain in cls.AUTHORITY_DOMAINS)

    @classmethod
    async def interact_platform(
        cls,
        page: Any,
        url: str,
        evaluate_fn: Callable,
        stop_check: Optional[Callable[[], bool]] = None
    ) -> bool:
        if not url:
            return False
        netloc = urlparse(url).netloc.lower()

        try:
            if "reddit.com" in netloc:
                return await cls._interact_reddit(page, evaluate_fn, stop_check)
            elif "wikipedia.org" in netloc:
                return await cls._interact_wikipedia(page, evaluate_fn, stop_check)
            elif "github.com" in netloc:
                return await cls._interact_github(page, evaluate_fn, stop_check)
            elif "stackoverflow.com" in netloc:
                return await cls._interact_stackoverflow(page, evaluate_fn, stop_check)
        except Exception as e:
            logger.debug(f"Platform adapter note ({netloc}): {e}")

        return False

    @classmethod
    async def _interact_reddit(cls, page: Any, evaluate_fn: Callable, stop_check: Optional[Callable[[], bool]] = None) -> bool:
        logger.info("Executing Reddit High-Authority Interaction Adapter...")
        reddit_script = """
        (() => {
            const comments = Array.from(document.querySelectorAll('shrule-post, [data-testid="post-container"], p, div[slot="comment"]'));
            if (comments.length === 0) return null;
            const el = comments[Math.floor(Math.random() * comments.length)];
            const rect = el.getBoundingClientRect();
            return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2, width: rect.width };
        })()
        """
        box = await evaluate_fn(page, reddit_script)
        if box and isinstance(box, dict) and box.get("x", 0) > 0:
            cx, cy = box["x"], box["y"]
            await BiomechanicalMotor.move_mouse_humanoid(page, 200, 200, cx, cy, target_width=box.get("width", 60.0), stop_check=stop_check)
            await BiomechanicalMotor.humanoid_idle_sleep(page, get_lognormal_delay(mean=2.5, sigma=0.5), cx, cy, stop_check=stop_check)

        if random.random() < 0.35:
            sub_link_script = """
            (() => {
                const links = Array.from(document.querySelectorAll('a[href*="/r/"]')).filter(a => (a.innerText || '').startsWith('r/'));
                if (links.length === 0) return null;
                const link = links[Math.floor(Math.random() * links.length)];
                return { href: link.href };
            })()
            """
            s_link = await evaluate_fn(page, sub_link_script)
            if s_link and isinstance(s_link, dict) and s_link.get("href"):
                await page.goto(s_link["href"], wait_until="domcontentloaded", timeout=15000)
                await ContentAwareReader.analyze_page_and_dwell(page, evaluate_fn, base_dwell=6.0, stop_check=stop_check)
                return True
        return True

    @classmethod
    async def _interact_wikipedia(cls, page: Any, evaluate_fn: Callable, stop_check: Optional[Callable[[], bool]] = None) -> bool:
        logger.info("Executing Wikipedia High-Authority Interaction Adapter...")
        wiki_script = """
        (() => {
            const links = Array.from(document.querySelectorAll('#mw-content-text a[href^="/wiki/"]')).filter(a => !a.href.includes(':'));
            if (links.length === 0) return null;
            const link = links[Math.floor(Math.random() * links.length)];
            const rect = link.getBoundingClientRect();
            return { href: link.href, x: rect.left + rect.width / 2, y: rect.top + rect.height / 2, w: rect.width };
        })()
        """
        w_item = await evaluate_fn(page, wiki_script)
        if w_item and isinstance(w_item, dict) and w_item.get("x", 0) > 0:
            cx, cy = w_item["x"], w_item["y"]
            await BiomechanicalMotor.move_mouse_humanoid(page, 200, 200, cx, cy, target_width=w_item.get("w", 40.0), stop_check=stop_check)
            await BiomechanicalMotor.humanoid_idle_sleep(page, 0.8, cx, cy, stop_check=stop_check)

            if random.random() < 0.60 and w_item.get("href"):
                await page.goto(w_item["href"], wait_until="domcontentloaded", timeout=15000)
                await ContentAwareReader.analyze_page_and_dwell(page, evaluate_fn, base_dwell=7.0, stop_check=stop_check)
                return True
        return True

    @classmethod
    async def _interact_github(cls, page: Any, evaluate_fn: Callable, stop_check: Optional[Callable[[], bool]] = None) -> bool:
        logger.info("Executing GitHub High-Authority Interaction Adapter...")
        file_script = """
        (() => {
            const files = Array.from(document.querySelectorAll('a.Link--primary, [data-pjax="#repo-content-pjax-container"]'));
            if (files.length === 0) return null;
            const f = files[Math.floor(Math.random() * files.length)];
            return { href: f.href };
        })()
        """
        f_item = await evaluate_fn(page, file_script)
        if f_item and isinstance(f_item, dict) and f_item.get("href"):
            await page.goto(f_item["href"], wait_until="domcontentloaded", timeout=15000)
            await ContentAwareReader.analyze_page_and_dwell(page, evaluate_fn, base_dwell=6.0, stop_check=stop_check)
            return True
        return True

    @classmethod
    async def _interact_stackoverflow(cls, page: Any, evaluate_fn: Callable, stop_check: Optional[Callable[[], bool]] = None) -> bool:
        logger.info("Executing StackOverflow High-Authority Interaction Adapter...")
        so_script = """
        (() => {
            const codes = Array.from(document.querySelectorAll('pre code, .answercell'));
            if (codes.length === 0) return null;
            const c = codes[0];
            const rect = c.getBoundingClientRect();
            return { x: rect.left + 20, y: rect.top + 15, w: rect.width - 40 };
        })()
        """
        code_box = await evaluate_fn(page, so_script)
        if code_box and isinstance(code_box, dict) and code_box.get("w", 0) > 40:
            sx, sy = code_box["x"], code_box["y"]
            ex = sx + min(code_box["w"], 220.0)
            if hasattr(page, "mouse") and hasattr(page.mouse, "down"):
                try:
                    await page.mouse.move(sx, sy)
                    await page.mouse.down()
                    await BiomechanicalMotor.move_mouse_humanoid(page, sx, sy, ex, sy, stop_check=stop_check)
                    await asyncio.sleep(0.8)
                    await page.mouse.up()
                    await page.mouse.click(ex + 10.0, sy)
                except Exception:
                    pass
        return True


class ContentAwareReader:
    """Simulates humanoid visual reading behavior, dynamic WPM-based dwell time,
    micro-drifts, mouse hovering over interesting media, and smooth variable scrolling.
    """

    @classmethod
    async def analyze_page_and_dwell(
        cls,
        page: Any,
        evaluate_fn: Callable,
        base_dwell: float = 8.0,
        wpm_target: int = 220,
        stop_check: Optional[Callable[[], bool]] = None
    ):
        try:
            analysis_script = """
            (() => {
                const text = document.body ? (document.body.innerText || '') : '';
                const words = text.split(/\\s+/).filter(w => w.length > 0).length;
                const images = document.querySelectorAll('img').length;
                const innerHeight = window.innerHeight || 800;
                const scrollHeight = document.documentElement.scrollHeight || 2000;
                return { words, images, innerHeight, scrollHeight };
            })()
            """
            meta = await evaluate_fn(page, analysis_script)
            words = meta.get("words", 300) if isinstance(meta, dict) else 300
            images = meta.get("images", 5) if isinstance(meta, dict) else 5
            vh = meta.get("innerHeight", 800) if isinstance(meta, dict) else 800

            computed_dwell = (words / (wpm_target / 60.0)) + (images * 0.5)
            dwell_time = max(base_dwell * 0.6, min(computed_dwell, base_dwell * 2.2))

            # Initial check & In-page MutationObserver for delayed popups (5-15s)
            try:
                await SemanticBannerResolver.attach_consent_autowatcher(page, evaluate_fn)
                await SemanticBannerResolver.resolve_consent_banners(page, evaluate_fn)
            except Exception:
                pass

            start_time = time.time()
            last_banner_check = time.time()
            cur_x, cur_y = random.randint(150, 450), random.randint(150, 450)

            while (time.time() - start_time) < dwell_time and not (stop_check and stop_check()):
                # Non-intrusive periodic check for delayed cookie banners (every ~2.0s)
                if (time.time() - last_banner_check) > 2.0:
                    last_banner_check = time.time()
                    try:
                        await SemanticBannerResolver.resolve_consent_banners(page, evaluate_fn)
                    except Exception:
                        pass
                action = random.choices(
                    ["micro_scan", "skimming_scroll", "cognitive_pause", "curiosity_hover", "back_scroll"],
                    weights=[0.35, 0.25, 0.20, 0.12, 0.08],
                    k=1
                )[0]

                if action == "micro_scan":
                    scroll_delta = random.randint(90, 240)
                    await evaluate_fn(page, f"window.scrollBy({{top: {scroll_delta}, behavior: 'smooth'}});")
                    target_x = random.randint(180, 750)
                    target_y = random.randint(200, min(vh - 80, 680))
                    await BiomechanicalMotor.move_mouse_humanoid(page, cur_x, cur_y, target_x, target_y, target_width=50.0, stop_check=stop_check)
                    cur_x, cur_y = await BiomechanicalMotor.humanoid_idle_sleep(page, get_lognormal_delay(mean=2.2, sigma=0.5), target_x, target_y, stop_check=stop_check)

                elif action == "skimming_scroll":
                    scroll_delta = random.randint(380, 780)
                    await evaluate_fn(page, f"window.scrollBy({{top: {scroll_delta}, behavior: 'smooth'}});")
                    target_x = random.randint(100, 300)
                    target_y = random.randint(150, min(vh - 100, 600))
                    await BiomechanicalMotor.move_mouse_humanoid(page, cur_x, cur_y, target_x, target_y, stop_check=stop_check)
                    cur_x, cur_y = await BiomechanicalMotor.humanoid_idle_sleep(page, get_lognormal_delay(mean=1.2, sigma=0.4), target_x, target_y, stop_check=stop_check)

                elif action == "cognitive_pause":
                    pause_time = get_lognormal_delay(mean=4.8, sigma=0.55, min_val=3.0, max_val=11.0)
                    cur_x, cur_y = await BiomechanicalMotor.humanoid_idle_sleep(page, pause_time, cur_x, cur_y, stop_check=stop_check)

                elif action == "curiosity_hover":
                    hover_script = """
                    (() => {
                        const els = Array.from(document.querySelectorAll('h1, h2, h3, img, a')).filter(e => {
                            const rect = e.getBoundingClientRect();
                            return rect.width > 30 && rect.height > 20 && rect.top > 50 && rect.top < (window.innerHeight - 50);
                        });
                        if (els.length === 0) return null;
                        const el = els[Math.floor(Math.random() * els.length)];
                        const r = el.getBoundingClientRect();
                        return { x: r.left + r.width / 2, y: r.top + r.height / 2, w: r.width };
                    })()
                    """
                    box = await evaluate_fn(page, hover_script)
                    if box and isinstance(box, dict) and box.get("x", 0) > 0:
                        hx, hy = box["x"], box["y"]
                        await BiomechanicalMotor.move_mouse_humanoid(page, cur_x, cur_y, hx, hy, target_width=box.get("w", 40.0), stop_check=stop_check)
                        cur_x, cur_y = await BiomechanicalMotor.humanoid_idle_sleep(page, random.uniform(0.35, 0.85), hx, hy, stop_check=stop_check)

                elif action == "back_scroll":
                    up_delta = random.randint(-350, -140)
                    await evaluate_fn(page, f"window.scrollBy({{top: {up_delta}, behavior: 'smooth'}});")
                    cur_x, cur_y = await BiomechanicalMotor.humanoid_idle_sleep(page, get_lognormal_delay(mean=1.8, sigma=0.45), cur_x, cur_y, stop_check=stop_check)

            await evaluate_fn(page, "window.scrollTo({top: 0, behavior: 'smooth'});")
            await BiomechanicalMotor.humanoid_idle_sleep(page, random.uniform(0.5, 1.2), cur_x, cur_y, stop_check=stop_check)

        except Exception as e:
            logger.debug(f"Content-aware reader note: {e}")


class PersonaTrajectoryEngine:
    """Generates authentic search intent and navigation trajectories tailored to specific AI personas."""

    @classmethod
    def get_urls_for_persona(cls, persona_key: str, max_pages: int) -> List[str]:
        p = PERSONA_PROFILES.get(persona_key, PERSONA_PROFILES["general"])
        pool: List[str] = []
        for cat in p["categories"]:
            if cat in WARMUP_CATEGORIES:
                pool.extend(WARMUP_CATEGORIES[cat])

        unique_pool = list(dict.fromkeys(pool))
        if len(unique_pool) >= max_pages:
            return random.sample(unique_pool, max_pages)
        return unique_pool

    @classmethod
    def get_search_query(cls, persona_key: str, custom_queries: Optional[List[str]] = None) -> str:
        if custom_queries:
            return random.choice(custom_queries)
        p = PERSONA_PROFILES.get(persona_key, PERSONA_PROFILES["general"])
        return random.choice(p["queries"])
