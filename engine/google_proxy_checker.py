import os
import shutil
import tempfile
import asyncio
import random
import logging
import math
import time
from typing import Dict, Any, Tuple, Optional, List, Callable

from camoufox.async_api import AsyncCamoufox
from engine.ai_model_manager import AIModelManager
from engine.honeypot_detector import HoneypotDetector, HoneypotScanResult

logger = logging.getLogger("GoogleProxyChecker")

# Comprehensive high-entropy topic & persona matrix for AI generation
AI_TOPICS = [
    "Science, Astronomy & Physics",
    "Python, Linux & Web Engineering",
    "Gourmet Cooking, Baking & Recipes",
    "Alpine Hiking, Trekking & Travel Destinations",
    "Home Automation, DIY & Gardening",
    "Fitness, Strength Training & Nutrition",
    "Ancient History, Archaeology & Civilization",
    "Wildlife, Marine Biology & Nature",
    "Quantum Computing & Artificial Intelligence",
    "Automotive Repair & Electric Vehicles",
    "Daily Life, Productivity & Personal Growth"
]

AI_PERSONAS = [
    "curious student looking for an explanation",
    "software engineer searching for technical documentation",
    "home chef searching for an authentic recipe",
    "outdoor traveler planning an excursion",
    "hobbyist looking for troubleshooting advice",
    "science enthusiast searching for recent discoveries",
    "daily life user searching for practical recommendations"
]

# Curated High-Quality Multilingual Fallback Query Pool (100+ queries)
FALLBACK_QUERIES = [
    # Science & Tech
    "what is the fastest animal in the world",
    "latest space exploration discoveries 2026",
    "best practices for python async programming",
    "how do solar panels generate electricity",
    "difference between machine learning and deep learning",
    "how does a quantum computer work simple",
    "what causes the northern lights aurora",
    "why is the sky blue science explanation",
    "how do lithium ion batteries store energy",
    "james webb telescope latest high resolution images",
    "how do black holes warp space and time",
    "what is the difference between ram and vram",
    "how do fiber optic cables transmit data",
    "why do magnets attract and repel metals",
    "what is the speed of light in water",
    
    # Cooking & Recipes
    "how to make homemade pizza dough easy",
    "healthy quick dinner recipes under 20 minutes",
    "how to brew pour over coffee at home",
    "authentic italian carbonara recipe without cream",
    "secret to making crispy french fries in oven",
    "how to bake sourdough bread for beginners",
    "best spices for roasted vegetables",
    "how to make creamy mushroom risotto step by step",
    "difference between baking soda and baking powder",
    "how to sear a ribeye steak in cast iron",
    "homemade guacamole recipe with fresh lime",
    
    # Travel & Outdoors
    "top travel destinations in europe 2026",
    "how to train for a half marathon beginner",
    "best day hiking trails in the black forest",
    "what to pack for a week in iceland in summer",
    "top scenic train routes in switzerland",
    "how to set up a tent in windy conditions",
    "best lightweight backpacking gear for beginners",
    "national parks in north america to visit in spring",
    
    # Daily Life & Home
    "easy houseplants that require low light",
    "best books on productivity and habit building",
    "benefits of regular strength training",
    "how to remove stubborn coffee stains from carpet",
    "effective morning routine for high focus",
    "how to sharpen kitchen knives with a whetstone",
    "how to improve indoor air quality naturally",
    "energy saving tips for home heating in winter",
    "how to properly organize a home workspace",
    
    # German authentic queries
    "wetterbericht für die nächsten 7 tage",
    "schnelle gesunde rezepte für das abendessen",
    "beste wanderrouten im schwarzwald für anfänger",
    "unterschied zwischen oled und qled fernsehern",
    "wie pflegt man monstera zimmerpflanzen richtig",
    "tipps für besseren schlaf und regeneration",
    "sauerteigbrot backen anleitung für einsteiger",
    "strom sparen im haushalt einfache tipps",
    "beste sehenswürdigkeiten in wien an einem wochenende",
    "wie funktioniert eine wärmepumpe im altbau",
    "gute bücher über psychologie und gewohnheiten"
]

QWERTY_KEYBOARD = {
    'q': (0, 0), 'w': (0, 1), 'e': (0, 2), 'r': (0, 3), 't': (0, 4), 'y': (0, 5), 'u': (0, 6), 'i': (0, 7), 'o': (0, 8), 'p': (0, 9),
    'a': (1, 0), 's': (1, 1), 'd': (1, 2), 'f': (1, 3), 'g': (1, 4), 'h': (1, 5), 'j': (1, 6), 'k': (1, 7), 'l': (1, 8),
    'z': (2, 0), 'x': (2, 1), 'c': (2, 2), 'v': (2, 3), 'b': (2, 4), 'n': (2, 5), 'm': (2, 6)
}

ADJACENT_KEYS = {
    'a': ['s', 'q', 'w', 'z'], 'b': ['v', 'g', 'h', 'n'], 'c': ['x', 'd', 'f', 'v'],
    'd': ['s', 'e', 'r', 'f', 'c', 'x'], 'e': ['w', '3', '4', 'r', 'd', 's'],
    'f': ['d', 'r', 't', 'g', 'v', 'c'], 'g': ['f', 't', 'y', 'h', 'b', 'v'],
    'h': ['g', 'y', 'u', 'j', 'n', 'b'], 'i': ['u', '8', '9', 'o', 'k', 'j'],
    'j': ['h', 'u', 'i', 'k', 'm', 'n'], 'k': ['j', 'i', 'o', 'l', 'm'],
    'l': ['k', 'o', 'p'], 'm': ['n', 'j', 'k'], 'n': ['b', 'h', 'j', 'm'],
    'o': ['i', '9', '0', 'p', 'l', 'k'], 'p': ['o', '0', 'l'],
    'q': ['1', '2', 'w', 'a'], 'r': ['e', '4', '5', 't', 'f', 'd'],
    's': ['a', 'w', 'e', 'd', 'x', 'z'], 't': ['r', '5', '6', 'y', 'g', 'f'],
    'u': ['y', '7', '8', 'i', 'j', 'h'], 'v': ['c', 'f', 'g', 'b'],
    'w': ['q', '2', '3', 'e', 's', 'a'], 'x': ['z', 's', 'd', 'c'],
    'y': ['t', '6', '7', 'u', 'h', 'g'], 'z': ['a', 's', 'x']
}


class OrnsteinUhlenbeckTremor:
    """Simulates physiological neuromuscular micro-tremor using a mean-reverting OU stochastic process."""

    def __init__(self, theta: float = 0.20, sigma: float = 0.55):
        self.theta = theta
        self.sigma = sigma
        self.state_x = 0.0
        self.state_y = 0.0

    def step(self, dt: float = 0.016) -> Tuple[float, float]:
        dx = -self.theta * self.state_x * dt + self.sigma * math.sqrt(dt) * random.gauss(0, 1)
        dy = -self.theta * self.state_y * dt + self.sigma * math.sqrt(dt) * random.gauss(0, 1)
        self.state_x += dx
        self.state_y += dy
        return self.state_x, self.state_y


class HumanoidSessionProfile:
    """Session-specific typing and motor dynamics model for natural human simulation."""

    def __init__(self):
        # 1. Biomechanical session characteristics
        self.handedness = random.choice(["right", "right", "right", "left"])  # 75% right-handed
        self.profile_type = random.choice(["fast", "moderate", "deliberate"])
        
        self.tremor_sigma = random.uniform(0.35, 0.80)
        self.tremor_theta = random.uniform(0.16, 0.24)
        self.fitts_a = random.uniform(0.12, 0.18)
        self.fitts_b = random.uniform(0.14, 0.22)
        self.overshoot_rate = random.uniform(0.22, 0.38)
        
        # Virtual cursor position within initial viewport
        self.cursor_x = random.uniform(150, 750)
        self.cursor_y = random.uniform(80, 420)

        # 2. Keystroke dynamics per personality
        if self.profile_type == "fast":
            self.char_delay_mean = random.uniform(0.030, 0.055)  # 30-55ms
            self.mistype_chance = 0.03
            self.word_pause_range = (0.08, 0.18)
            self.click_hold = random.uniform(0.045, 0.085)
            self.pre_submit_pause = random.uniform(0.35, 0.70)
        elif self.profile_type == "moderate":
            self.char_delay_mean = random.uniform(0.060, 0.095)  # 60-95ms
            self.mistype_chance = 0.06
            self.word_pause_range = (0.14, 0.32)
            self.click_hold = random.uniform(0.065, 0.125)
            self.pre_submit_pause = random.uniform(0.60, 1.20)
        else:  # deliberate
            self.char_delay_mean = random.uniform(0.100, 0.160)  # 100-160ms
            self.mistype_chance = 0.08
            self.word_pause_range = (0.25, 0.50)
            self.click_hold = random.uniform(0.085, 0.165)
            self.pre_submit_pause = random.uniform(0.90, 1.80)

    def get_char_delay(self, char1: str, char2: str) -> float:
        """Calculates variable log-normal inter-key delay based on physical QWERTY distance."""
        dist = 2.0
        c1, c2 = char1.lower(), char2.lower()
        if c1 in QWERTY_KEYBOARD and c2 in QWERTY_KEYBOARD:
            r1, col1 = QWERTY_KEYBOARD[c1]
            r2, col2 = QWERTY_KEYBOARD[c2]
            dist = math.hypot(r1 - r2, col1 - col2)

        base = random.lognormvariate(math.log(self.char_delay_mean), 0.35)
        delay = base + dist * 0.008

        if char2.isupper() or char2 in "?!@#$%^&*()_+:\"":
            delay += random.uniform(0.08, 0.20)  # Shift-key hesitation

        return max(0.015, min(delay, 0.45))

    def generate_human_path(
        self,
        start: Tuple[float, float],
        end: Tuple[float, float],
        target_size: float = 40.0
    ) -> List[Tuple[float, float, float]]:
        """
        Generates a 5th-order minimum jerk trajectory with asymmetric Bézier curvature,
        session-specific handedness bias, Ornstein-Uhlenbeck neuromuscular tremor, and overshoot sub-movement.
        """
        x0, y0 = start
        x1, y1 = end
        dx = x1 - x0
        dy = y1 - y0
        dist = math.hypot(dx, dy)

        if dist < 2.0:
            return [(x0, y0, 0.01), (x1, y1, 0.02)]

        # Fitts's Law duration scaled by session motor traits
        index_of_difficulty = math.log2(1.0 + max(dist, 1.0) / max(target_size, 5.0))
        duration = (self.fitts_a + self.fitts_b * index_of_difficulty) * random.lognormvariate(0.0, 0.16)
        duration = max(0.18, min(duration, 2.2))

        num_points = max(16, min(75, int(dist / 9.0)))
        dt_base = duration / float(num_points)

        # Realistic overshoot for distances > 60px
        target_x, target_y = end
        has_overshoot = False
        if dist > 60.0 and random.random() < self.overshoot_rate:
            has_overshoot = True
            overshoot_mag = random.uniform(0.03, 0.10) * dist
            target_x = x1 + (dx / dist) * overshoot_mag + random.gauss(0, 2.5)
            target_y = y1 + (dy / dist) * overshoot_mag + random.gauss(0, 2.5)

        # Handedness bias + dynamic wrist/elbow arc curvature
        handedness_bias = 0.07 if self.handedness == "right" else -0.07
        arc_intensity = (handedness_bias + random.uniform(-0.16, 0.16)) * dist
        perp_x = -dy / dist * arc_intensity
        perp_y = dx / dist * arc_intensity

        ctrl_x1 = x0 + dx * 0.25 + perp_x
        ctrl_y1 = y0 + dy * 0.25 + perp_y
        ctrl_x2 = x0 + dx * 0.70 + perp_x * 0.6
        ctrl_y2 = y0 + dy * 0.70 + perp_y * 0.6

        tremor_gen = OrnsteinUhlenbeckTremor(theta=self.tremor_theta, sigma=self.tremor_sigma)
        path: List[Tuple[float, float, float]] = []

        for i in range(num_points + 1):
            t = i / float(num_points)
            
            # 5th-order minimum jerk polynomial (human bell-curve velocity)
            min_jerk = 10.0 * (t ** 3) - 15.0 * (t ** 4) + 6.0 * (t ** 5)
            
            # Cubic Bézier interpolation
            bx = (1 - min_jerk)**3 * x0 + 3 * (1 - min_jerk)**2 * min_jerk * ctrl_x1 + 3 * (1 - min_jerk) * (min_jerk**2) * ctrl_x2 + (min_jerk**3) * target_x
            by = (1 - min_jerk)**3 * y0 + 3 * (1 - min_jerk)**2 * min_jerk * ctrl_y1 + 3 * (1 - min_jerk) * (min_jerk**2) * ctrl_y2 + (min_jerk**3) * target_y

            # Neuromuscular Tremor
            tx, ty = tremor_gen.step(dt=dt_base)
            dampening = 1.0 - (t ** 2) * 0.75
            final_x = bx + tx * dampening
            final_y = by + ty * dampening

            seg_dt = dt_base * random.lognormvariate(0.0, 0.14)
            path.append((final_x, final_y, max(0.003, seg_dt)))

        # Corrective sub-movements if overshot
        if has_overshoot:
            correct_steps = random.randint(4, 7)
            last_x, last_y, _ = path[-1]
            sub_duration = random.uniform(0.08, 0.18)
            sub_dt = sub_duration / float(correct_steps)
            for k in range(1, correct_steps + 1):
                st = k / float(correct_steps)
                cx = last_x + (x1 - last_x) * st + random.gauss(0, 0.4)
                cy = last_y + (y1 - last_y) * st + random.gauss(0, 0.4)
                path.append((cx, cy, max(0.003, sub_dt * random.uniform(0.8, 1.2))))

        return path

    async def move_mouse_humanoid(self, page: Any, target_x: float, target_y: float, target_size: float = 40.0):
        """Moves cursor to target coordinates using smooth biomechanical curve path."""
        if not hasattr(page, "mouse"):
            return

        start = (self.cursor_x, self.cursor_y)
        end = (target_x, target_y)
        path = self.generate_human_path(start, end, target_size=target_size)

        for px, py, seg_dt in path:
            try:
                await page.mouse.move(px, py)
            except Exception:
                pass
            await asyncio.sleep(seg_dt)

        self.cursor_x, self.cursor_y = target_x, target_y

    async def type_into_input(self, page: Any, text: str):
        """Simulates human typing with spatial bi-gram timings and realistic mistype recovery."""
        prev_char = 'e'
        for i, char in enumerate(text):
            # Realistic mistype simulation
            if random.random() < self.mistype_chance and char.lower() in ADJACENT_KEYS:
                wrong_char = random.choice(ADJACENT_KEYS[char.lower()])
                await page.keyboard.type(wrong_char, delay=int(self.char_delay_mean * 1000))
                # Error detection hesitation
                await asyncio.sleep(random.uniform(0.12, 0.28))
                await page.keyboard.press("Backspace")
                await asyncio.sleep(random.uniform(0.06, 0.15))

            delay_sec = self.get_char_delay(prev_char, char)
            await page.keyboard.type(char, delay=int(delay_sec * 1000))
            prev_char = char

            # Word boundary micro-pause (thinking space)
            if char == ' ':
                await asyncio.sleep(random.uniform(*self.word_pause_range))

    async def human_click(self, page: Any, element: Any):
        """Moves mouse naturally to element with biomechanical trajectories and executes click."""
        try:
            box = await element.bounding_box()
            if box:
                # Add random offset from exact center to avoid robotic accuracy
                target_x = box["x"] + box["width"] * random.uniform(0.28, 0.72)
                target_y = box["y"] + box["height"] * random.uniform(0.28, 0.72)
                target_w = max(box["width"], 20.0)

                # Biomechanical mouse movement
                await self.move_mouse_humanoid(page, target_x, target_y, target_size=target_w)
                
                # Pre-click hover hesitation
                await asyncio.sleep(random.uniform(0.08, 0.22))
                
                if hasattr(page, "mouse"):
                    await page.mouse.down()
                    await asyncio.sleep(self.click_hold)
                    await page.mouse.up()
                    await asyncio.sleep(random.uniform(0.05, 0.12))
                    return
        except Exception:
            pass

        # Fallback click
        await element.click()

    async def human_idle(self, page: Any, duration_sec: float):
        """Simulates natural human hand rest, micro-drifts, tremors, and gaze movement during pauses."""
        if not hasattr(page, "mouse") or duration_sec <= 0.05:
            await asyncio.sleep(duration_sec)
            return

        from engine.warmup.human_motion import BiomechanicalMotor
        try:
            nx, ny = await BiomechanicalMotor.humanoid_idle_sleep(page, duration_sec, self.cursor_x, self.cursor_y)
            self.cursor_x, self.cursor_y = nx, ny
        except Exception:
            await asyncio.sleep(duration_sec)



class GoogleProxyChecker:
    """AI-Assisted Google Proxy Validator with High-Entropy Queries and Session Motor Dynamics."""

    @staticmethod
    async def generate_test_query(model_name: Optional[str] = None) -> str:
        """Generates an authentic, high-entropy search question using local AI model or diverse fallback queries."""
        try:
            ai_mgr = AIModelManager.get_instance()
            if await ai_mgr.is_engine_ready(model_name):

                topic = random.choice(AI_TOPICS)
                persona = random.choice(AI_PERSONAS)
                
                prompt = (
                    f"You are a {persona}. "
                    f"Topic interest: {topic}. "
                    "Generate a single, natural, realistic 3-7 word search query or question you would type into Google search. "
                    "Output ONLY the plain search query string, without quotes, formatting, numbers, or introductory text."
                )
                target_model = model_name if (model_name and model_name != "auto") else None
                
                res = await asyncio.wait_for(
                    ai_mgr.generate_response(
                        prompt,
                        system_prompt="You generate natural short realistic human search engine queries with high topic diversity. Output ONLY the query string.",
                        model_name=target_model
                    ),
                    timeout=8.0
                )
                query = AIModelManager.sanitize_search_query(res)

                if 3 <= len(query) < 95 and not query.lower().startswith("here is") and not query.lower().startswith("output"):
                    logger.info(f"[GoogleProxyChecker] HQ AI generated query: '{query}' [Topic: {topic}] (model={target_model or 'default'})")
                    return query
        except Exception as e:
            logger.debug(f"[GoogleProxyChecker] AI query generation fallback ({e})")

        chosen = random.choice(FALLBACK_QUERIES)
        logger.info(f"[GoogleProxyChecker] Using organic test query: '{chosen}'")
        return chosen

    @classmethod
    def _build_camoufox_proxy_config(cls, proxy_cfg: Dict[str, Any]) -> Optional[Dict[str, str]]:
        """Formats proxy configuration for Playwright/Camoufox."""
        if not proxy_cfg.get("enabled", True) and "enabled" in proxy_cfg:
            return None
        
        host = str(proxy_cfg.get("host", "")).strip()
        port = int(proxy_cfg.get("port", 8080))
        if not host:
            return None

        p_type = str(proxy_cfg.get("type", "http")).lower()
        if p_type in ["socks5", "socks5h"]:
            scheme = "socks5"
        elif p_type in ["https", "ssl"]:
            scheme = "https"
        else:
            scheme = "http"

        user = str(proxy_cfg.get("username", "")).strip()
        pwd = str(proxy_cfg.get("password", "")).strip()

        proxy_dict: Dict[str, str] = {
            "server": f"{scheme}://{host}:{port}"
        }
        if user:
            proxy_dict["username"] = user
        if pwd:
            proxy_dict["password"] = pwd

        return proxy_dict

    @classmethod
    async def check_proxy_with_google(
        cls,
        proxy_cfg: Dict[str, Any],
        headless: bool = True,
        model_name: Optional[str] = None,
        profile_data: Optional[Dict[str, Any]] = None,
        timeout_sec: float = 25.0,
        captcha_strategy: str = "audio_first",
        vision_model: Optional[str] = None,
        enable_honeypot_shield: bool = True,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Validates proxy against Google Search using Camoufox and an AI search query with unique session typing dynamics.
        
        Returns:
            (is_google_proxy: bool, status_message: str, details: Dict[str, Any])
        """
        start_time = time.time()
        host = proxy_cfg.get("host", "Unknown")
        port = proxy_cfg.get("port", 8080)

        # Measure or retrieve Quick Test network latency (round-trip/handshake) rather than total browser lifecycle duration
        quick_latency = proxy_cfg.get("latency_ms", -1)
        if quick_latency is None or quick_latency <= 0:
            from engine.proxy_checker import ProxyChecker
            try:
                ok, _, q_lat = await ProxyChecker.check_proxy(proxy_cfg)
                if ok and q_lat > 0:
                    quick_latency = q_lat
            except Exception:
                pass

        if quick_latency is None or quick_latency <= 0:
            try:
                t_sock = time.time()
                conn = asyncio.open_connection(str(proxy_cfg.get("host")), int(proxy_cfg.get("port", 8080)))
                r, w = await asyncio.wait_for(conn, timeout=3.0)
                w.close()
                await w.wait_closed()
                quick_latency = round((time.time() - t_sock) * 1000, 2)
            except Exception:
                quick_latency = 120.0
        
        # Instantiate session-specific typing profile
        human_session = HumanoidSessionProfile()

        def notify(msg: str):
            logger.info(f"[GoogleProxyChecker {host}:{port}] {msg}")
            if progress_callback:
                progress_callback(msg)

        proxy_dict = cls._build_camoufox_proxy_config(proxy_cfg)
        if not proxy_dict:
            return False, "Invalid Proxy Config", {"error": "Missing host or port", "latency_ms": quick_latency}

        temp_dir = tempfile.mkdtemp(prefix=f"soxbot_camoufox_google_{host}_{port}_")
        test_query = await cls.generate_test_query(model_name=model_name)
        notify(f"Starting test with query: '{test_query}' [Speed: {human_session.profile_type}, Quick Latency: {quick_latency}ms]...")

        # Setup OS, Screen and Locale
        target_os = "windows"
        target_locale = "de-DE"
        screen_obj = None

        if profile_data:
            target_os = profile_data.get("os", "windows").lower()
            target_locale = profile_data.get("primary_language", profile_data.get("locale", "en-US"))
            res_str = profile_data.get("screen_resolution", "1920x1080")
            try:
                w_res, h_res = map(int, res_str.split("x"))
                from browserforge.fingerprints import Screen
                screen_obj = Screen(min_width=w_res, max_width=w_res, min_height=h_res, max_height=h_res)
            except Exception:
                pass

        # Setup LocalProxyTunnel if proxy auth or custom TLS JA3 preset is required
        tunnel = None
        effective_proxy_dict = proxy_dict
        user_auth = str(proxy_cfg.get("username", "")).strip()
        pwd_auth = str(proxy_cfg.get("password", "")).strip()
        tls_preset = proxy_cfg.get("tls_ja3_preset", "auto")

        if user_auth or pwd_auth or (tls_preset and tls_preset != "auto"):
            try:
                from engine.proxy_tunnel import LocalProxyTunnel
                tunnel = LocalProxyTunnel(
                    upstream_host=str(host).strip(),
                    upstream_port=int(port),
                    username=user_auth,
                    password=pwd_auth,
                    proxy_type=str(proxy_cfg.get("type", "http")).lower(),
                    max_concurrency=64,
                    burst_protection=True,
                    burst_stagger_ms=15.0,
                    tls_preset="firefox_130_linux" if target_os == "linux" else ("firefox_130_win11" if target_os == "windows" else "auto"),
                    target_os=target_os
                )
                tunnel_port = await tunnel.start()
                effective_proxy_dict = {"server": f"http://127.0.0.1:{tunnel_port}"}
                notify(f"Local Proxy Tunnel active on 127.0.0.1:{tunnel_port} (Firefox JA4 impersonation).")
            except Exception as tun_err:
                logger.warning(f"[GoogleProxyChecker] Could not initialize LocalProxyTunnel ({tun_err}), falling back to direct proxy config.")

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
            "network.proxy.socks_remote_dns": True,
            "network.trr.mode": 5,
            "browser.startup.page": 0,
            "browser.startup.homepage": "about:blank",
            "startup.homepage_welcome_url": "about:blank",
            "startup.homepage_override_url": "about:blank",
            "media.peerconnection.enabled": True,
            "media.peerconnection.ice.proxy_only": True,
            "media.peerconnection.ice.proxy_only_if_behind_proxy": True,
            "media.peerconnection.ice.obfuscate_host_addresses": True,
            "media.peerconnection.use_document_iceservers": False,
            "media.ffmpeg.vaapi.enabled": False,
            "media.rdd-ffmpeg.enabled": True,
            "media.fragmented-mp4.ffmpeg.enabled": True,
            "media.mediasource.enabled": True,
            "media.mediasource.mp4.enabled": True,
            "media.mediasource.vp9.enabled": True,
            "media.autoplay.default": 0,
            "media.autoplay.allow-muted": True,
            "media.autoplay.blocking_policy": 0,
        }

        # Write clean startup user.js to profile temp dir
        try:
            user_js_path = os.path.join(temp_dir, "user.js")
            ujs_lines = [
                'user_pref("browser.startup.page", 0);\n',
                'user_pref("browser.startup.homepage", "about:blank");\n',
                'user_pref("startup.homepage_welcome_url", "about:blank");\n',
                'user_pref("startup.homepage_override_url", "about:blank");\n',
                'user_pref("network.proxy.socks_remote_dns", true);\n',
                'user_pref("network.dns.disablePrefetch", true);\n',
                'user_pref("media.peerconnection.ice.proxy_only", true);\n',
            ]
            with open(user_js_path, "w", encoding="utf-8") as f_ujs:
                f_ujs.writelines(ujs_lines)
        except Exception:
            pass

        camou_config: Dict[str, Any] = {
            "mediaDevices:enabled": True,
            "mediaDevices:micros": 1,
            "mediaDevices:webcams": 1,
            "mediaDevices:speakers": 0,
        }
        if host and str(host).strip() not in ["127.0.0.1", "localhost", "0.0.0.0"]:
            camou_config["webrtc:ipv4"] = str(host).strip()
            ff_prefs["network.dns.disableIPv6"] = True

        camoufox_kwargs: Dict[str, Any] = {
            "user_data_dir": temp_dir,
            "persistent_context": True,
            "headless": "virtual" if headless else False,
            "os": target_os,
            "locale": target_locale,
            "proxy": effective_proxy_dict,
            "ignore_https_errors": True,
            "firefox_user_prefs": ff_prefs,
            "config": camou_config,
            "i_know_what_im_doing": True
        }
        try:
            import geoip2  # noqa: F401
            camoufox_kwargs["geoip"] = True
        except ImportError:
            pass

        # Locate Camoufox Binary and expose H.264 codecs
        try:
            from engine.browser import BrowserLauncher
            c_bin = BrowserLauncher._find_camoufox_binary()
            if c_bin:
                camoufox_kwargs["executable_path"] = c_bin
                BrowserLauncher._ensure_camoufox_h264_codecs(os.path.dirname(c_bin))
        except Exception:
            pass

        if screen_obj:
            camoufox_kwargs["screen"] = screen_obj

        # Ensure native display is restored if running non-headless after virtual display
        sys_display = os.environ.get("ORIGINAL_DISPLAY") or os.environ.get("DISPLAY")
        if not os.environ.get("ORIGINAL_DISPLAY") and sys_display:
            os.environ["ORIGINAL_DISPLAY"] = sys_display

        if not headless and os.environ.get("ORIGINAL_DISPLAY"):
            os.environ["DISPLAY"] = os.environ["ORIGINAL_DISPLAY"]

        try:
            notify(f"Launching Camoufox (headless={headless}, os={target_os}, typist={human_session.profile_type})...")
            async with AsyncCamoufox(**camoufox_kwargs) as context:
                # Inject Stealth Script and Anti-Detect layer
                try:
                    from engine.fingerprint import FingerprintGenerator
                    dummy_prof = profile_data or {"os": target_os, "language": target_locale}
                    stealth_js = FingerprintGenerator.generate_stealth_script(dummy_prof)
                    if hasattr(context, "add_init_script"):
                        await context.add_init_script(stealth_js)
                except Exception as s_err:
                    logger.debug(f"[GoogleProxyChecker] Stealth init script note: {s_err}")

                pages = getattr(context, "pages", [])
                page = pages[0] if pages else await context.new_page()

                notify("Navigating to https://www.google.com...")
                try:
                    await page.goto(
                        "https://www.google.com",
                        wait_until="domcontentloaded",
                        timeout=int(timeout_sec * 1000)
                    )
                except Exception as nav_err:
                    latency = round((time.time() - start_time) * 1000, 2)
                    notify(f"Connection failed: {nav_err}")
                    if tunnel:
                        try:
                            await tunnel.stop()
                        except Exception:
                            pass
                    return False, "Connection Failed / Timeout", {
                        "error": str(nav_err),
                        "latency_ms": quick_latency,
                        "total_duration_ms": latency,
                        "query": test_query
                    }

                await asyncio.sleep(random.uniform(0.8, 1.5))

                # AI Honeypot & Click-Trap Shield Pre-Scan on Google entry page
                hp_scan = HoneypotScanResult()
                if enable_honeypot_shield:
                    hp_scan = await HoneypotDetector.scan_page(page, model_name=model_name, notify_cb=notify)

                # Progressive mounting loop: Wait for consent, captcha, or search input (up to 12s)
                search_input = None
                mount_start = time.time()
                while time.time() - mount_start < 12.0:
                    current_url = page.url.lower()

                    # 1. Check for immediate captcha
                    has_landing_captcha = (
                        "sorry/index" in current_url or
                        "recaptcha" in current_url or
                        bool(await page.query_selector("iframe[src*='recaptcha'], iframe[src*='enterprise'], div#captcha, #captcha-form, form#captcha-form"))
                    )

                    if has_landing_captcha:
                        notify("Google triggered CAPTCHA on entry (/sorry/index). Triggering Local AI Captcha Solver...")
                        if captcha_strategy in ["swarm_auto", "swarm", "auto_full", "auto_ensemble"]:
                            from engine.ai_swarm_orchestrator import AISwarmOrchestrator
                            solved, solve_msg, solve_details = await AISwarmOrchestrator.get_instance().solve_captcha_swarm(
                                page=page,
                                strategy=captcha_strategy,
                                notify_cb=notify
                            )
                        else:
                            from engine.ai_captcha_solver import AICaptchaSolver
                            solved, solve_msg, solve_details = await AICaptchaSolver.solve_google_captcha(
                                page=page,
                                strategy=captcha_strategy,
                                vision_model=vision_model,
                                human_session=human_session,
                                notify_cb=notify,
                                timeout_sec=timeout_sec
                            )
                        if not solved:
                            latency = round((time.time() - start_time) * 1000, 2)
                            notify(f"Entry CAPTCHA solving failed ({solve_msg}).")
                            return False, f"Google Captcha Blocked ({solve_msg})", {
                                "captcha": True,
                                "url": page.url,
                                "latency_ms": quick_latency,
                                "total_duration_ms": latency,
                                "query": test_query,
                                "solve_error": solve_msg
                            }
                        else:
                            notify(f"Entry CAPTCHA resolved via {solve_details.get('method', 'AI')}! Waiting for search interface...")
                            await human_session.human_idle(page, random.uniform(2.0, 3.0))

                    # 2. Check and dismiss Cookie Consent Banner
                    consent_selectors = [
                        "button#L2AGYb",
                        "button:has-text('Alle akzeptieren')",
                        "button:has-text('Accept all')",
                        "button:has-text('Ich stimme zu')",
                        "button:has-text('Tout accepter')",
                        "button:has-text('Aceptar todo')",
                        "button:has-text('Accetta tutto')",
                        "button:has-text('I agree')",
                        "form[action*='consent'] button"
                    ]
                    for sel in consent_selectors:
                        try:
                            if not hp_scan.is_safe_element(selector=sel):
                                continue
                            btn = await page.query_selector(sel)
                            if btn and await btn.is_visible():
                                notify(f"Dismissing Google consent modal via '{sel}'...")
                                await human_session.human_click(page, btn)
                                await human_session.human_idle(page, random.uniform(1.2, 2.0))
                                break
                        except Exception:
                            pass

                    # 3. Check for Search Input
                    search_selectors = [
                        "textarea[name='q']",
                        "input[name='q']",
                        "textarea[title='Suche']",
                        "textarea[title='Search']",
                        "input[type='search']",
                        "input[type='text']"
                    ]
                    for s_sel in search_selectors:
                        cand = await page.query_selector(s_sel)
                        if cand and await cand.is_visible():
                            search_input = cand
                            break

                    if search_input:
                        break

                    await human_session.human_idle(page, 0.8)

                if not search_input:
                    notify("Could not find Google search input bar after mounting wait.")
                    return False, "Search Bar Not Found / Slow Page", {"url": page.url, "query": test_query}

                notify(f"Typing AI query '{test_query}' with {human_session.profile_type} typing dynamics...")
                await human_session.human_click(page, search_input)
                await human_session.human_idle(page, random.uniform(0.35, 0.70))

                # Human-like bi-gram typing with typos and variable speeds
                await human_session.type_into_input(page, test_query)
                
                # Natural cognitive pre-submit hesitation with idle gaze movements
                await human_session.human_idle(page, human_session.pre_submit_pause)

                # Submit query (either by pressing Enter or clicking search button)
                if random.random() < 0.80:
                    notify("Submitting search query via Enter key...")
                    await page.keyboard.press("Enter")
                else:
                    notify("Submitting search query via Google Search button...")
                    submit_btn = await page.query_selector("input[name='btnK'], button[type='submit']")
                    if submit_btn and await submit_btn.is_visible():
                        await human_session.human_click(page, submit_btn)
                    else:
                        await page.keyboard.press("Enter")

                # Wait for search results or captcha response with natural hand rest / drift
                await human_session.human_idle(page, random.uniform(2.5, 3.5))

                final_url = page.url.lower()
                latency = round((time.time() - start_time) * 1000, 2)

                # 1. Check for Captcha / Bot Interception after search submit (Up to 2 consecutive barriers)
                was_ai_unlocked = False
                for barrier_round in range(1, 3):
                    final_url = page.url.lower()
                    is_captcha = (
                        "sorry/index" in final_url or
                        "recaptcha" in final_url or
                        bool(await page.query_selector("iframe[src*='recaptcha'], div#captcha, #captcha-form, form#captcha-form"))
                    )

                    if not is_captcha:
                        break

                    round_suffix = f" (Barrier #{barrier_round})" if barrier_round > 1 else ""
                    notify(f"Google triggered CAPTCHA verification on query submit{round_suffix}. Invoking Local AI Captcha Solver...")
                    if captcha_strategy in ["swarm_auto", "swarm", "auto_full", "auto_ensemble"]:
                        from engine.ai_swarm_orchestrator import AISwarmOrchestrator
                        solved, solve_msg, solve_details = await AISwarmOrchestrator.get_instance().solve_captcha_swarm(
                            page=page,
                            strategy=captcha_strategy,
                            notify_cb=notify
                        )
                    else:
                        from engine.ai_captcha_solver import AICaptchaSolver
                        solved, solve_msg, solve_details = await AICaptchaSolver.solve_google_captcha(
                            page=page,
                            strategy=captcha_strategy,
                            vision_model=vision_model,
                            human_session=human_session,
                            notify_cb=notify,
                            timeout_sec=timeout_sec
                        )
                    if solved:
                        was_ai_unlocked = True
                        notify(f"Post-submit CAPTCHA{round_suffix} successfully unlocked via {solve_details.get('method', 'AI')}!")
                        await human_session.human_idle(page, random.uniform(1.5, 2.5))

                        # If on /sorry/index form, click form submit/continue button if present
                        submit_btn = await page.query_selector("form#captcha-form input[type='submit'], input[name='continue'], input[type='submit'], button[type='submit'], form button, form input[type='submit']")
                        if submit_btn and await submit_btn.is_visible():
                            notify("Submitting Google continue form...")
                            await human_session.human_click(page, submit_btn)
                            await human_session.human_idle(page, random.uniform(2.0, 3.0))
                        elif "sorry/index" not in page.url.lower() and "search?q=" not in page.url.lower():
                            # Trigger Enter to submit search if on home search box
                            try:
                                search_box = await page.query_selector("textarea[name='q'], input[name='q']")
                                if search_box and await search_box.is_visible():
                                    await page.keyboard.press("Enter")
                                    await human_session.human_idle(page, random.uniform(2.0, 3.0))
                            except Exception:
                                pass

                    else:
                        notify(f"Post-submit CAPTCHA{round_suffix} solving failed ({solve_msg}).")
                        return False, f"Google Captcha Blocked ({solve_msg})", {
                            "captcha": True,
                            "url": page.url,
                            "latency_ms": quick_latency,
                            "total_duration_ms": latency,
                            "query": test_query,
                            "solve_error": solve_msg
                        }

                # 2. Check for organic Google Search Results with polling
                result_elements = None
                for _ in range(8):
                    final_url = page.url.lower()
                    result_elements = await page.query_selector(
                        "#search, #rso, div.g, div.MjjYud, div[data-sokoban-container], div#result-stats, #center_col"
                    )
                    if result_elements or "search?q=" in final_url:
                        break
                    await asyncio.sleep(0.5)

                # Honeypot scan on search results page
                post_hp_scan = HoneypotScanResult()
                if enable_honeypot_shield and (result_elements or "search?q=" in page.url.lower()):
                    post_hp_scan = await HoneypotDetector.scan_page(page, model_name=model_name, notify_cb=notify)

                if result_elements or "search?q=" in final_url:
                    # Capture session cookies for reuse
                    cookies_list = []
                    try:
                        if hasattr(page, "context") and hasattr(page.context, "cookies"):
                            cookies_list = await page.context.cookies()
                        elif hasattr(context, "cookies") and callable(getattr(context, "cookies")):
                            cookies_list = await context.cookies()
                        elif hasattr(context, "contexts") and context.contexts:
                            cookies_list = await context.contexts[0].cookies()
                    except Exception:
                        pass

                    status_label = "Google Verified (AI-Unlocked)" if was_ai_unlocked else "Google Verified (Clean No-Captcha)"
                    notify(f"SUCCESS: Organic Google search results received (Quick Latency: {quick_latency}ms, Total: {latency}ms)! Declaring as {status_label}.")
                    return True, status_label, {
                        "captcha": False,
                        "ai_unlocked": was_ai_unlocked,
                        "url": page.url,
                        "latency_ms": quick_latency,
                        "total_duration_ms": latency,
                        "query": test_query,
                        "honeypot_shield_clean": hp_scan.is_clean and post_hp_scan.is_clean,
                        "cookies": cookies_list
                    }

                notify(f"Search results could not be confirmed (URL: {page.url}).")
                return False, "Unconfirmed Results", {
                    "captcha": False,
                    "url": page.url,
                    "latency_ms": quick_latency,
                    "total_duration_ms": latency,
                    "query": test_query
                }

        except Exception as e:
            latency = round((time.time() - start_time) * 1000, 2)
            notify(f"Exception during Google check: {e}")
            return False, f"Check Error: {str(e)[:40]}", {
                "error": str(e),
                "latency_ms": quick_latency,
                "total_duration_ms": latency,
                "query": test_query
            }

        finally:
            if tunnel:
                try:
                    await tunnel.stop()
                except Exception:
                    pass
            if os.environ.get("ORIGINAL_DISPLAY"):
                os.environ["DISPLAY"] = os.environ["ORIGINAL_DISPLAY"]
            shutil.rmtree(temp_dir, ignore_errors=True)

    @classmethod
    async def check_proxies_batch(
        cls,
        proxies: List[Dict[str, Any]],
        max_concurrency: int = 2,
        headless: bool = True,
        model_name: Optional[str] = None,
        profile_data: Optional[Dict[str, Any]] = None,
        profile_pool: Optional[List[Dict[str, Any]]] = None,
        timeout_sec: float = 25.0,
        captcha_strategy: str = "audio_first",
        vision_model: Optional[str] = None,
        enable_honeypot_shield: bool = True,
        cancel_event: Optional[asyncio.Event] = None,
        on_proxy_complete: Optional[Callable[[Dict[str, Any], bool, str, Dict[str, Any]], None]] = None,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> List[Tuple[Dict[str, Any], bool, str, Dict[str, Any]]]:
        """
        Runs concurrent AI Google checks across a list of proxies with multi-profile rotation and cancellation support.
        """
        sem = asyncio.Semaphore(max(1, max_concurrency))
        total = len(proxies)
        completed_count = 0
        results: List[Tuple[Dict[str, Any], bool, str, Dict[str, Any]]] = []

        pool = profile_pool or ([profile_data] if profile_data else None)

        async def _check_single(idx: int, p: Dict[str, Any]):
            nonlocal completed_count
            if cancel_event and cancel_event.is_set():
                return
            
            assigned_profile = None
            if pool and len(pool) > 0:
                assigned_profile = pool[idx % len(pool)]

            async with sem:
                if cancel_event and cancel_event.is_set():
                    return
                success, msg, details = await cls.check_proxy_with_google(
                    p,
                    headless=headless,
                    model_name=model_name,
                    profile_data=assigned_profile,
                    timeout_sec=timeout_sec,
                    captcha_strategy=captcha_strategy,
                    vision_model=vision_model,
                    enable_honeypot_shield=enable_honeypot_shield
                )
                completed_count += 1
                if progress_callback:
                    progress_callback(completed_count, total, f"{p.get('host')}:{p.get('port')} -> {msg}")
                if on_proxy_complete:
                    on_proxy_complete(p, success, msg, details)
                results.append((p, success, msg, details))

        tasks = [_check_single(i, p) for i, p in enumerate(proxies)]
        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            logger.info("[GoogleProxyChecker] Batch check cancelled by user.")
        return results
