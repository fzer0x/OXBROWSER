import os
import math
import random
import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple, Callable

import numpy as np

logger = logging.getLogger("KeystrokeDynamics")

try:
    import onnxruntime as ort
    _ORT_AVAILABLE = True
except ImportError:
    _ORT_AVAILABLE = False


class KeystrokeDynamicsEngine:
    """
    Sub-millisecond Biomechanical Keystroke Dynamics Engine for 0xBrowser.
    Simulates authentic human typing biomechanics:
    - Down-to-Up Dwell Time (Hold Time per Key)
    - Up-to-Down Flight Time (Inter-key travel latency based on physical keyboard layout)
    - Shift / Modifier hesitations and capital letter cognitive latency
    - Lognormal and Gaussian biological tremor
    - Authentic adjacent-key mistyping with realistic recognition & Backspace correction
    Uses ONNX Biometry Regressor (Tier 0 CPU) with seamless analytical fallback.
    """

    _instance: Optional['KeystrokeDynamicsEngine'] = None

    # Standard QWERTY/QWERTZ physical matrix coordinates (row, column)
    KEYBOARD_MATRIX: Dict[str, Tuple[float, float]] = {
        '1': (0.0, 0.0), '2': (0.0, 1.0), '3': (0.0, 2.0), '4': (0.0, 3.0), '5': (0.0, 4.0),
        '6': (0.0, 5.0), '7': (0.0, 6.0), '8': (0.0, 7.0), '9': (0.0, 8.0), '0': (0.0, 9.0),
        'q': (1.0, 0.5), 'w': (1.0, 1.5), 'e': (1.0, 2.5), 'r': (1.0, 3.5), 't': (1.0, 4.5),
        'z': (1.0, 5.5), 'y': (1.0, 5.5), 'u': (1.0, 6.5), 'i': (1.0, 7.5), 'o': (1.0, 8.5), 'p': (1.0, 9.5),
        'a': (2.0, 0.8), 's': (2.0, 1.8), 'd': (2.0, 2.8), 'f': (2.0, 3.8), 'g': (2.0, 4.8),
        'h': (2.0, 5.8), 'j': (2.0, 6.8), 'k': (2.0, 7.8), 'l': (2.0, 8.8),
        'x': (3.0, 1.2), 'c': (3.0, 2.2), 'v': (3.0, 3.2), 'b': (3.0, 4.2),
        'n': (3.0, 5.2), 'm': (3.0, 6.2), ' ': (4.0, 4.5)
    }

    ADJACENT_KEYS: Dict[str, List[str]] = {
        'a': ['q', 'w', 's', 'y', 'z'], 'b': ['v', 'g', 'h', 'n', ' '],
        'c': ['x', 'd', 'f', 'v', ' '], 'd': ['s', 'e', 'r', 'f', 'c', 'x'],
        'e': ['w', '3', '4', 'r', 'd', 's'], 'f': ['d', 'r', 't', 'g', 'v', 'c'],
        'g': ['f', 't', 'z', 'y', 'h', 'b', 'v'], 'h': ['g', 'z', 'y', 'u', 'j', 'n', 'b'],
        'i': ['u', '8', '9', 'o', 'k', 'j'], 'j': ['h', 'u', 'i', 'k', 'm', 'n'],
        'k': ['j', 'i', 'o', 'l', 'm'], 'l': ['k', 'o', 'p'],
        'm': ['n', 'j', 'k'], 'n': ['b', 'h', 'j', 'm'],
        'o': ['i', '9', '0', 'p', 'l', 'k'], 'p': ['o', '0'],
        'q': ['1', '2', 'w', 'a'], 'r': ['e', '4', '5', 't', 'f', 'd'],
        's': ['a', 'w', 'e', 'd', 'x'], 't': ['r', '5', '6', 'z', 'y', 'g', 'f'],
        'u': ['z', 'y', '7', '8', 'i', 'j', 'h'], 'v': ['c', 'f', 'g', 'b', ' '],
        'w': ['q', '2', '3', 'e', 's', 'a'], 'x': ['y', 'z', 's', 'd', 'c'],
        'y': ['t', '6', '7', 'u', 'h', 'g'], 'z': ['t', '6', '7', 'u', 'h', 'g'],
        ' ': ['c', 'v', 'b', 'n', 'm']
    }

    def __init__(self, model_path: Optional[str] = None):
        if not model_path:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            model_path = os.path.join(base_dir, "models", "keystroke_dynamics_v1.onnx")

        self.model_path = model_path
        self._session: Optional[Any] = None
        self._load_onnx_model()

    @classmethod
    def get_instance(cls) -> 'KeystrokeDynamicsEngine':
        if cls._instance is None:
            cls._instance = KeystrokeDynamicsEngine()
        return cls._instance

    def _load_onnx_model(self):
        if _ORT_AVAILABLE and os.path.exists(self.model_path) and os.path.getsize(self.model_path) > 500:
            try:
                opts = ort.SessionOptions()
                opts.intra_op_num_threads = 1
                opts.inter_op_num_threads = 1
                self._session = ort.InferenceSession(self.model_path, sess_options=opts, providers=["CPUExecutionProvider"])
                logger.info(f"KeystrokeDynamics ONNX session initialized from {self.model_path}")
            except Exception as e:
                logger.warning(f"Failed to load Keystroke ONNX session: {e}. Using biological analytical engine.")
                self._session = None
        else:
            self._session = None

    def calculate_key_distance(self, char1: str, char2: str) -> float:
        """Returns Euclidean distance on physical keyboard layout."""
        c1 = char1.lower()
        c2 = char2.lower()
        pos1 = self.KEYBOARD_MATRIX.get(c1)
        pos2 = self.KEYBOARD_MATRIX.get(c2)
        if pos1 and pos2:
            return math.hypot(pos1[0] - pos2[0], pos1[1] - pos2[1])
        return 2.5

    def predict_timings(
        self,
        prev_char: str,
        current_char: str,
        speed_preset: str = "balanced",
        fatigue_factor: float = 0.0
    ) -> Tuple[float, float]:
        """
        Calculates (dwell_time_s, flight_time_s) for the current keystroke.
        - dwell_time_s: keydown to keyup hold time
        - flight_time_s: keyup to next keydown transit time
        """
        dist = self.calculate_key_distance(prev_char, current_char)
        is_upper = current_char.isupper() or current_char in "!@#$%^&*()_+{}|:\"<>?~"
        is_space = current_char == ' '
        is_punct = current_char in ".,;:-_/'\"!?()[]"

        speed_multipliers = {
            "fast": 0.72,
            "balanced": 1.0,
            "careful": 1.45,
            "relaxed": 1.25
        }
        speed_scale = speed_multipliers.get(speed_preset.lower(), 1.0)

        # 1. Try ONNX model inference if available
        if self._session:
            try:
                feat = np.array([[
                    dist,
                    1.0 if is_upper else 0.0,
                    1.0 if is_space else 0.0,
                    1.0 if is_punct else 0.0,
                    speed_scale,
                    fatigue_factor
                ]], dtype=np.float32)

                inp_name = self._session.get_inputs()[0].name
                preds = self._session.run(None, {inp_name: feat})[0][0]
                dwell_ms = float(preds[0])
                flight_ms = float(preds[1])

                # Add natural micro-jitter
                dwell_ms += random.gauss(0, 4.0)
                flight_ms += random.gauss(0, 8.0)

                dwell_s = max(0.035, min(0.180, dwell_ms / 1000.0))
                flight_s = max(0.020, min(0.450, flight_ms / 1000.0))
                return dwell_s, flight_s
            except Exception as e:
                logger.debug(f"ONNX Keystroke inference note: {e}")

        # 2. High-fidelity Biological Analytical Fallback (Log-Normal Distribution)
        # Baseline human dwell time is ~60-95ms
        base_dwell_mu = 0.068 * speed_scale
        if is_upper:
            base_dwell_mu += 0.022  # Shift-key hold overhead
        if is_space:
            base_dwell_mu += 0.015  # Thumb press is slightly more deliberate

        dwell_s = random.lognormvariate(math.log(base_dwell_mu), 0.25)
        dwell_s = max(0.038, min(0.160, dwell_s))

        # Baseline flight time scales with key distance and punctuation hesitation
        base_flight_mu = (0.075 + dist * 0.018) * speed_scale
        if is_upper:
            base_flight_mu += 0.080  # Cognitive preparation for capital letters
        if is_punct:
            base_flight_mu += 0.095  # Punctuation hesitation
        if is_space:
            base_flight_mu += 0.040  # Word boundary pause

        # Add fatigue drift
        base_flight_mu += fatigue_factor * 0.025

        flight_s = random.lognormvariate(math.log(base_flight_mu), 0.32)
        flight_s = max(0.025, min(0.550, flight_s))

        return dwell_s, flight_s

    async def type_with_biometrics(
        self,
        page: Any,
        selector: Optional[str],
        text: str,
        speed_preset: str = "balanced",
        error_rate: float = 0.035,
        press_enter: bool = False,
        stop_check: Optional[Callable[[], bool]] = None
    ) -> bool:
        """
        Executes authentic humanoid typing on a Playwright / Camoufox page element:
        - Fires discrete `keyboard.down()` -> sleep(dwell) -> `keyboard.up()` events.
        - Emulates human key travel latency with inter-key flight times.
        - Synthesizes realistic adjacent-key typos with Backspace corrections.
        """
        if not page or not text:
            return False

        try:
            # Click into element to focus if selector provided
            if selector and hasattr(page, "click"):
                try:
                    await page.click(selector, timeout=2500)
                except Exception:
                    pass

            prev_char = 'e'
            fatigue = 0.0

            for i, char in enumerate(text):
                if stop_check and stop_check():
                    logger.info("[KeystrokeDynamics] Typing stopped via stop_check.")
                    break

                fatigue = min(1.0, float(i) / max(1.0, float(len(text))))

                # Natural Human Typo & Correction routine
                if random.random() < error_rate and char.lower() in self.ADJACENT_KEYS:
                    typo_char = random.choice(self.ADJACENT_KEYS[char.lower()])
                    # Type wrong key
                    t_dwell, t_flight = self.predict_timings(prev_char, typo_char, speed_preset, fatigue)
                    await self._dispatch_discrete_key(page, typo_char, t_dwell)
                    # Notice error hesitation (140 - 320ms)
                    await asyncio.sleep(random.uniform(0.14, 0.32))
                    # Press Backspace
                    b_dwell, _ = self.predict_timings(typo_char, "Backspace", speed_preset, fatigue)
                    await self._dispatch_discrete_key(page, "Backspace", b_dwell)
                    # Recovery hesitation before resuming
                    await asyncio.sleep(random.uniform(0.08, 0.18))
                    prev_char = typo_char

                # Actual target keystroke
                dwell_s, flight_s = self.predict_timings(prev_char, char, speed_preset, fatigue)
                await self._dispatch_discrete_key(page, char, dwell_s)
                await asyncio.sleep(flight_s)
                prev_char = char

            if press_enter:
                await asyncio.sleep(random.uniform(0.20, 0.50))
                await self._dispatch_discrete_key(page, "Enter", random.uniform(0.06, 0.11))

            return True
        except Exception as e:
            logger.error(f"[KeystrokeDynamics] Error typing text: {e}")
            return False

    @staticmethod
    async def _dispatch_discrete_key(page: Any, key: str, dwell_s: float):
        """Dispatches realistic keydown -> hold -> keyup events."""
        kb = getattr(page, "keyboard", None)
        if kb and hasattr(kb, "down") and hasattr(kb, "up"):
            await kb.down(key)
            await asyncio.sleep(dwell_s)
            await kb.up(key)
        elif hasattr(page, "type"):
            await page.type("", key, delay=int(dwell_s * 1000))
