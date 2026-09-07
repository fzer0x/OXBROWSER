import asyncio
import math
import random
import time
import logging
from typing import List, Tuple, Optional, Callable, Any

logger = logging.getLogger("HumanMotion")


def get_lognormal_delay(mean: float = 1.8, sigma: float = 0.55, min_val: float = 0.3, max_val: float = 14.0) -> float:
    """Computes non-deterministic log-normal cognitive delay to match human reaction distributions."""
    try:
        val = random.lognormvariate(math.log(max(0.1, mean)), sigma)
        return max(min_val, min(val, max_val))
    except Exception as e:
        logger.debug(f"Delay calculation fallback: {e}")
        return random.uniform(min_val, min(min_val * 3, max_val))


class BiomechanicalMotor:
    """Simulates biomechanical motor dynamics for human mouse movement.
    Uses 5th-order minimum jerk trajectory polynomials combined with Fitts's Law duration,
    physiological micro-tremor, and 30% proprioceptive overshoot + sub-movement correction.
    """

    @staticmethod
    def calculate_fitts_duration(distance: float, target_width: float = 40.0) -> float:
        """Fitts's Law model: T = a + b * log2(1 + D / W) with Lognormal velocity scaling."""
        if distance <= 0:
            return 0.1
        a = 0.14  # Reaction & initiation overhead (sec)
        b = 0.17  # Motor scaling factor
        index_of_difficulty = math.log2(1.0 + max(distance, 1.0) / max(target_width, 5.0))
        duration = a + b * index_of_difficulty
        # Log-normal human speed variation (realistic fat-tail distribution)
        duration *= random.lognormvariate(0.0, 0.18)
        return max(0.14, min(duration, 2.8))

    @staticmethod
    def generate_min_jerk_path(
        start: Tuple[float, float],
        end: Tuple[float, float],
        duration: float,
        num_points: int = 25
    ) -> List[Tuple[float, float]]:
        """Generates a minimum-jerk trajectory curve with Bezier arc curvature, tremor, and optional overshoot correction."""
        x0, y0 = start
        x1, y1 = end
        dx = x1 - x0
        dy = y1 - y0
        dist = math.hypot(dx, dy)

        if dist < 2.0:
            return [start, end]

        # 30% chance of human physical overshoot past target
        target_x, target_y = end
        overshot = False
        if dist > 80.0 and random.random() < 0.30:
            overshot = True
            overshoot_dist = random.uniform(6.0, 18.0)
            target_x = x1 + (dx / dist) * overshoot_dist + random.uniform(-4, 4)
            target_y = y1 + (dy / dist) * overshoot_dist + random.uniform(-4, 4)

        # Dynamic control points for natural arm arc
        arc_scale = random.uniform(-0.18, 0.18) * dist
        perp_x = -dy / dist * arc_scale
        perp_y = dx / dist * arc_scale

        ctrl_x1 = x0 + dx * 0.3 + perp_x
        ctrl_y1 = y0 + dy * 0.3 + perp_y
        ctrl_x2 = x0 + dx * 0.7 + perp_x * 0.5
        ctrl_y2 = y0 + dy * 0.7 + perp_y * 0.5

        path = []
        beta_power = random.betavariate(2.2, 5.0) if hasattr(random, "betavariate") else 0.35
        for i in range(num_points + 1):
            t = i / float(num_points)
            min_jerk_s = 10.0 * (t ** 3) - 15.0 * (t ** 4) + 6.0 * (t ** 5)
            beta_s = math.pow(t, beta_power) if t > 0 else 0.0
            s = min_jerk_s * 0.80 + beta_s * 0.20

            bx = (1 - s)**3 * x0 + 3 * (1 - s)**2 * s * ctrl_x1 + 3 * (1 - s) * (s**2) * ctrl_x2 + (s**3) * target_x
            by = (1 - s)**3 * y0 + 3 * (1 - s)**2 * s * ctrl_y1 + 3 * (1 - s) * (s**2) * ctrl_y2 + (s**3) * target_y

            # Tremor superposition
            tremor_freq1 = 9.5
            tremor_freq2 = 13.5
            elapsed = t * duration
            tremor_x = math.sin(elapsed * tremor_freq1 * 2 * math.pi) * 0.75 + random.gauss(0, 0.25)
            tremor_y = math.cos(elapsed * tremor_freq2 * 2 * math.pi) * 0.75 + random.gauss(0, 0.25)

            dampening = 1.0 - (t ** 2)
            final_x = bx + tremor_x * dampening
            final_y = by + tremor_y * dampening
            path.append((final_x, final_y))

        # Append sub-movement correction if overshoot occurred
        if overshot:
            sub_steps = random.randint(3, 6)
            for k in range(1, sub_steps + 1):
                st = k / float(sub_steps)
                cx = target_x + (x1 - target_x) * st + random.gauss(0, 0.4)
                cy = target_y + (y1 - target_y) * st + random.gauss(0, 0.4)
                path.append((cx, cy))

        return path

    @classmethod
    async def move_mouse_humanoid(
        cls,
        page: Any,
        start_x: float,
        start_y: float,
        end_x: float,
        end_y: float,
        target_width: float = 40.0,
        speed_mult: float = 1.0,
        stop_check: Optional[Callable[[], bool]] = None
    ):
        """Executes smooth biomechanical movement on page object with non-deterministic step timing."""
        try:
            dx = end_x - start_x
            dy = end_y - start_y
            dist = math.hypot(dx, dy)
            if dist < 3.0:
                return

            duration = cls.calculate_fitts_duration(dist, target_width) / max(0.1, speed_mult)
            
            # Use Phase 3 Stochastic Trajectory Generator
            from engine.warmup.stochastic_motion import HumanoidTrajectoryGenerator
            stochastic_path = HumanoidTrajectoryGenerator.generate_stochastic_path(
                (start_x, start_y), (end_x, end_y), duration, target_size=target_width
            )

            for px, py, seg_dt in stochastic_path:
                if stop_check and stop_check():
                    break

                if hasattr(page, "mouse") and hasattr(page.mouse, "move"):
                    await page.mouse.move(px, py)

                await asyncio.sleep(seg_dt)

        except Exception as e:
            logger.debug(f"Biomechanical motor move note: {e}")

    @classmethod
    async def humanoid_idle_sleep(
        cls,
        page: Any,
        duration: float,
        cur_x: float,
        cur_y: float,
        stop_check: Optional[Callable[[], bool]] = None
    ) -> Tuple[float, float]:
        """Multi-mode non-deterministic human idle engine.
        Humans don't drift constantly: they switch dynamically between:
        - 40% Complete Static Hand Rest (Mouse is completely still while reading)
        - 35% Active Neuromuscular Micro-Drift (Breathing & micro-tremors)
        - 15% Nervous Jitter / Micro-twitch
        - 10% Small Cursor Relocation (Shifting hand comfort position by 5-25px)
        """
        if duration <= 0.05:
            return cur_x, cur_y

        start_time = time.time()
        last_x, last_y = cur_x, cur_y
        t_start = random.uniform(0, 100)

        while (time.time() - start_time) < duration:
            if stop_check and stop_check():
                break

            idle_mode = random.choices(
                ["static_rest", "micro_drift", "jitter", "relocate", "reading_sweep", "curiosity_wander"],
                weights=[0.25, 0.25, 0.15, 0.10, 0.15, 0.10],
                k=1
            )[0]

            mode_duration = min(duration - (time.time() - start_time), random.uniform(0.3, 1.4))
            if mode_duration <= 0.02:
                break

            mode_start = time.time()

            if idle_mode == "static_rest":
                await asyncio.sleep(mode_duration)

            elif idle_mode == "reading_sweep":
                # Horizontal cognitive reading saccade
                sweep_dx = random.uniform(35, 110) * random.choice([1, 1, -0.5])
                sweep_dy = random.uniform(-6, 10)
                tx = max(80.0, min(880.0, last_x + sweep_dx))
                ty = max(80.0, min(650.0, last_y + sweep_dy))
                await cls.move_mouse_humanoid(page, last_x, last_y, tx, ty, target_width=35.0, speed_mult=1.4, stop_check=stop_check)
                last_x, last_y = tx, ty
                await asyncio.sleep(random.uniform(0.08, 0.20))

            elif idle_mode == "curiosity_wander":
                tx = max(80.0, min(880.0, last_x + random.uniform(-60, 60)))
                ty = max(80.0, min(650.0, last_y + random.uniform(-45, 45)))
                await cls.move_mouse_humanoid(page, last_x, last_y, tx, ty, target_width=45.0, speed_mult=1.2, stop_check=stop_check)
                last_x, last_y = tx, ty
                await asyncio.sleep(random.uniform(0.10, 0.25))

            elif idle_mode == "micro_drift":
                while (time.time() - mode_start) < mode_duration:
                    if stop_check and stop_check():
                        break
                    elapsed = (time.time() - start_time) + t_start
                    drift_x = math.sin(elapsed * 0.25 * 2 * math.pi) * 1.2 + math.sin(elapsed * 10.5 * 2 * math.pi) * 0.5 + random.gauss(0, 0.25)
                    drift_y = math.cos(elapsed * 0.25 * 2 * math.pi) * 1.2 + math.cos(elapsed * 12.0 * 2 * math.pi) * 0.5 + random.gauss(0, 0.25)
                    target_x = max(10.0, last_x + drift_x)
                    target_y = max(10.0, last_y + drift_y)
                    if hasattr(page, "mouse") and hasattr(page.mouse, "move"):
                        try:
                            await page.mouse.move(target_x, target_y)
                        except Exception:
                            pass
                    last_x, last_y = target_x, target_y
                    await asyncio.sleep(random.uniform(0.03, 0.07))

            elif idle_mode == "jitter":
                twitch_x = last_x + random.uniform(-3.5, 3.5)
                twitch_y = last_y + random.uniform(-3.5, 3.5)
                if hasattr(page, "mouse") and hasattr(page.mouse, "move"):
                    try:
                        await page.mouse.move(twitch_x, twitch_y)
                    except Exception:
                        pass
                last_x, last_y = twitch_x, twitch_y
                await asyncio.sleep(mode_duration)

            elif idle_mode == "relocate":
                reloc_x = max(10.0, last_x + random.uniform(-25, 25))
                reloc_y = max(10.0, last_y + random.uniform(-20, 20))
                await cls.move_mouse_humanoid(page, last_x, last_y, reloc_x, reloc_y, target_width=30.0, speed_mult=1.4, stop_check=stop_check)
                last_x, last_y = reloc_x, reloc_y
                await asyncio.sleep(mode_duration * 0.4)

        return last_x, last_y


class CognitiveGazeTracker:
    """Asynchronous background worker that produces continuous, unique, natural mouse movements
    while AI models (LLMs, VLMs, Whisper STT) are thinking, loading, or evaluating."""

    def __init__(self, page: Any, initial_pos: Optional[Tuple[float, float]] = None):
        self.page = page
        self.current_pos = initial_pos or (random.uniform(250, 650), random.uniform(200, 500))
        self._stop_event = asyncio.Event()
        self._task: Optional[asyncio.Task] = None

    async def __aenter__(self):
        self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()

    def start(self):
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> Tuple[float, float]:
        self._stop_event.set()
        if self._task and not self._task.done():
            try:
                await asyncio.wait_for(self._task, timeout=0.4)
            except Exception:
                pass
        return self.current_pos

    async def _run_loop(self):
        cur_x, cur_y = self.current_pos
        while not self._stop_event.is_set():
            try:
                behavior = random.choices(
                    ["reading_sweep", "curiosity_wander", "micro_drift", "hesitant_hover", "small_relocate", "static_rest"],
                    weights=[0.25, 0.22, 0.20, 0.15, 0.10, 0.08],
                    k=1
                )[0]

                if behavior == "reading_sweep":
                    sweep_len = random.uniform(40, 130) * random.choice([1, 1, -0.6])
                    target_x = max(100.0, min(850.0, cur_x + sweep_len))
                    target_y = max(100.0, min(600.0, cur_y + random.uniform(-8, 12)))
                    await BiomechanicalMotor.move_mouse_humanoid(self.page, cur_x, cur_y, target_x, target_y, target_width=35.0, speed_mult=1.3, stop_check=lambda: self._stop_event.is_set())
                    cur_x, cur_y = target_x, target_y
                    await asyncio.sleep(random.uniform(0.10, 0.25))

                elif behavior == "curiosity_wander":
                    target_x = max(100.0, min(850.0, cur_x + random.uniform(-80, 80)))
                    target_y = max(100.0, min(580.0, cur_y + random.uniform(-55, 55)))
                    await BiomechanicalMotor.move_mouse_humanoid(self.page, cur_x, cur_y, target_x, target_y, target_width=45.0, speed_mult=1.2, stop_check=lambda: self._stop_event.is_set())
                    cur_x, cur_y = target_x, target_y
                    await asyncio.sleep(random.uniform(0.12, 0.28))

                elif behavior == "micro_drift":
                    cur_x, cur_y = await BiomechanicalMotor.humanoid_idle_sleep(self.page, random.uniform(0.25, 0.55), cur_x, cur_y, stop_check=lambda: self._stop_event.is_set())

                elif behavior == "hesitant_hover":
                    twitch_x = max(50.0, min(900.0, cur_x + random.uniform(-4, 4)))
                    twitch_y = max(50.0, min(650.0, cur_y + random.uniform(-4, 4)))
                    if hasattr(self.page, "mouse") and hasattr(self.page.mouse, "move"):
                        try:
                            await self.page.mouse.move(twitch_x, twitch_y)
                        except Exception:
                            pass
                    cur_x, cur_y = twitch_x, twitch_y
                    await asyncio.sleep(random.uniform(0.15, 0.35))

                elif behavior == "small_relocate":
                    target_x = max(120.0, min(800.0, cur_x + random.uniform(-45, 45)))
                    target_y = max(100.0, min(550.0, cur_y + random.uniform(-35, 35)))
                    await BiomechanicalMotor.move_mouse_humanoid(self.page, cur_x, cur_y, target_x, target_y, target_width=30.0, speed_mult=1.5, stop_check=lambda: self._stop_event.is_set())
                    cur_x, cur_y = target_x, target_y

                else:
                    await asyncio.sleep(random.uniform(0.12, 0.25))

                self.current_pos = (cur_x, cur_y)
            except Exception:
                await asyncio.sleep(0.2)


class BiGramTypingEngine:
    """Simulates realistic human typing based on QWERTY key spatial distance,
    shift hesitations, bi-gram timings, and occasional mistypes with backspace correction.
    """

    KEYBOARD_LAYOUT = {
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
        'l': ['k', 'o', 'p', 'k'], 'm': ['n', 'j', 'k'], 'n': ['b', 'h', 'j', 'm'],
        'o': ['i', '9', '0', 'p', 'l', 'k'], 'p': ['o', '0', '-', 'l'],
        'q': ['1', '2', 'w', 'a'], 'r': ['e', '4', '5', 't', 'f', 'd'],
        's': ['a', 'w', 'e', 'd', 'x', 'z'], 't': ['r', '5', '6', 'y', 'g', 'f'],
        'u': ['y', '7', '8', 'i', 'j', 'h'], 'v': ['c', 'f', 'g', 'b'],
        'w': ['q', '2', '3', 'e', 's', 'a'], 'x': ['z', 's', 'd', 'c'],
        'y': ['t', '6', '7', 'u', 'h', 'g'], 'z': ['a', 's', 'x']
    }

    @classmethod
    def get_key_distance(cls, char1: str, char2: str) -> float:
        c1 = char1.lower()
        c2 = char2.lower()
        if c1 in cls.KEYBOARD_LAYOUT and c2 in cls.KEYBOARD_LAYOUT:
            r1, col1 = cls.KEYBOARD_LAYOUT[c1]
            r2, col2 = cls.KEYBOARD_LAYOUT[c2]
            return math.hypot(r1 - r2, col1 - col2)
        return 2.5

    @classmethod
    async def type_humanoid(
        cls,
        page: Any,
        selector: str,
        text: str,
        evaluate_fn: Callable,
        stop_check: Optional[Callable[[], bool]] = None,
        press_enter: bool = True
    ):
        """Types text with bi-gram delays, shift hesitations, and realistic mistype correction."""
        try:
            # Delegate to KeystrokeDynamicsEngine if available
            try:
                from engine.keystroke_dynamics import KeystrokeDynamicsEngine
                kde = KeystrokeDynamicsEngine.get_instance()
                success = await kde.type_with_biometrics(
                    page=page,
                    selector=selector,
                    text=text,
                    speed_preset="balanced",
                    press_enter=press_enter,
                    stop_check=stop_check
                )
                if success:
                    return
            except Exception as e:
                logger.debug(f"KeystrokeDynamics delegation fallback: {e}")

            if hasattr(page, "click"):
                try:
                    await page.click(selector, timeout=2000)
                except Exception as e:
                    logger.debug(f"Type humanoid initial click note: {e}")

            prev_char = 'e'
            for idx, char in enumerate(text):
                if stop_check and stop_check():
                    break

                # 5% chance of human mistype with realistic error-recognition & Backspace correction
                if random.random() < 0.05 and char.lower() in cls.ADJACENT_KEYS:
                    wrong_char = random.choice(cls.ADJACENT_KEYS[char.lower()])
                    await cls._dispatch_char(page, selector, wrong_char, evaluate_fn)
                    await asyncio.sleep(random.uniform(0.12, 0.28))
                    await cls._press_key(page, selector, "Backspace", evaluate_fn)
                    await asyncio.sleep(random.uniform(0.08, 0.16))

                dist = cls.get_key_distance(prev_char, char)
                base_delay = get_lognormal_delay(mean=0.09, sigma=0.45, min_val=0.04, max_val=0.35) + dist * 0.012

                if char.isupper() or char in "!@#$%^&*()_+{}|:\"<>?":
                    base_delay += get_lognormal_delay(mean=0.15, sigma=0.4, min_val=0.08, max_val=0.32)

                if char in " ,.?!":
                    base_delay += get_lognormal_delay(mean=0.16, sigma=0.5, min_val=0.06, max_val=0.40)

                if random.random() < 0.15:
                    base_delay += random.uniform(0.20, 0.55)

                await cls._dispatch_char(page, selector, char, evaluate_fn)
                await asyncio.sleep(base_delay)
                prev_char = char

            if press_enter:
                await asyncio.sleep(get_lognormal_delay(mean=0.35, sigma=0.4, min_val=0.15, max_val=0.75))
                await cls._press_key(page, selector, "Enter", evaluate_fn)

        except Exception as e:
            logger.debug(f"BiGram typing note: {e}")

    @staticmethod
    async def _dispatch_char(page: Any, selector: str, char: str, evaluate_fn: Callable):
        if hasattr(page, "keyboard") and hasattr(page.keyboard, "type"):
            await page.keyboard.type(char)
        elif hasattr(page, "type"):
            await page.type(selector, char)
        else:
            js = f"""
            (() => {{
                const el = document.querySelector("{selector}");
                if (el) {{
                    el.value += "{char}";
                    el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                }}
            }})()
            """
            await evaluate_fn(page, js)

    @staticmethod
    async def _press_key(page: Any, selector: str, key_name: str, evaluate_fn: Callable):
        if hasattr(page, "keyboard") and hasattr(page.keyboard, "press"):
            await page.keyboard.press(key_name)
        elif hasattr(page, "press"):
            await page.press(selector, key_name)
        else:
            js = f"""
            (() => {{
                const el = document.querySelector("{selector}");
                if (el) {{
                    if ("{key_name}" === "Backspace" && el.value.length > 0) {{
                        el.value = el.value.slice(0, -1);
                    }}
                    el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    el.dispatchEvent(new KeyboardEvent('keydown', {{ key: '{key_name}', bubbles: true }}));
                }}
            }})()
            """
            await evaluate_fn(page, js)
