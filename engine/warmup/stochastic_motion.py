"""
Advanced Stochastic & Diffusion-like Biomechanical Motion Controller.
Implements Ornstein-Uhlenbeck physical tremor dynamics, non-linear velocity profiles,
sub-goal target overshooting, and natural inertial scrolling to defeat reCAPTCHA v3 & Cloudflare Turnstile.
"""

import math
import random
import logging
from typing import List, Tuple, Optional

logger = logging.getLogger("StochasticMotion")


class OrnsteinUhlenbeckTremor:
    """Simulates physiological neuromuscular micro-tremor using a mean-reverting Ornstein-Uhlenbeck stochastic process."""

    def __init__(self, theta: float = 0.15, mu: float = 0.0, sigma: float = 0.45):
        self.theta = theta  # Rate of mean reversion (muscle elasticity)
        self.mu = mu        # Long-term mean (center of resting position)
        self.sigma = sigma  # Volatility / tremor magnitude
        self.state_x = mu
        self.state_y = mu

    def step(self, dt: float = 0.016) -> Tuple[float, float]:
        dx = self.theta * (self.mu - self.state_x) * dt + self.sigma * math.sqrt(dt) * random.gauss(0, 1)
        dy = self.theta * (self.mu - self.state_y) * dt + self.sigma * math.sqrt(dt) * random.gauss(0, 1)
        self.state_x += dx
        self.state_y += dy
        return self.state_x, self.state_y


class HumanoidTrajectoryGenerator:
    """Generates stochastic, high-entropy human mouse trajectories."""

    @staticmethod
    def generate_stochastic_path(
        start: Tuple[float, float],
        end: Tuple[float, float],
        duration: float,
        target_size: float = 40.0,
        num_points: Optional[int] = None
    ) -> List[Tuple[float, float, float]]:
        """
        Returns list of (x, y, t_delta) points representing natural human acceleration,
        curved arc deflection, and stochastic micro-tremor.
        """
        x0, y0 = start
        x1, y1 = end
        dx = x1 - x0
        dy = y1 - y0
        dist = math.hypot(dx, dy)

        if dist < 2.0:
            return [(x0, y0, 0.01), (x1, y1, duration)]

        if num_points is None:
            num_points = max(16, min(65, int(dist / 10.0)))

        # 1. Check for realistic human overshoot (35% probability for long distances)
        target_x, target_y = end
        has_overshoot = False
        if dist > 70.0 and random.random() < 0.35:
            has_overshoot = True
            overshoot_factor = random.uniform(0.04, 0.12)
            target_x = x1 + (dx / dist) * (dist * overshoot_factor) + random.gauss(0, 3.0)
            target_y = y1 + (dy / dist) * (dist * overshoot_factor) + random.gauss(0, 3.0)

        # 2. Asymmetric Bézier control points (natural wrist/elbow arc)
        arc_intensity = random.uniform(-0.22, 0.22) * dist
        perp_x = -dy / dist * arc_intensity
        perp_y = dx / dist * arc_intensity

        ctrl_x1 = x0 + dx * 0.25 + perp_x
        ctrl_y1 = y0 + dy * 0.25 + perp_y
        ctrl_x2 = x0 + dx * 0.70 + perp_x * 0.6
        ctrl_y2 = y0 + dy * 0.70 + perp_y * 0.6

        tremor_gen = OrnsteinUhlenbeckTremor(theta=0.20, sigma=0.55)
        path = []
        dt_base = duration / float(num_points)

        for i in range(num_points + 1):
            t = i / float(num_points)
            
            # Non-linear bell curve velocity profile (Fitts' Law motor planning)
            # Starts slow, accelerates in middle, decelerates near target
            min_jerk = 10.0 * (t ** 3) - 15.0 * (t ** 4) + 6.0 * (t ** 5)
            
            # Bézier interpolation
            bx = (1 - min_jerk)**3 * x0 + 3 * (1 - min_jerk)**2 * min_jerk * ctrl_x1 + 3 * (1 - min_jerk) * (min_jerk**2) * ctrl_x2 + (min_jerk**3) * target_x
            by = (1 - min_jerk)**3 * y0 + 3 * (1 - min_jerk)**2 * min_jerk * ctrl_y1 + 3 * (1 - min_jerk) * (min_jerk**2) * ctrl_y2 + (min_jerk**3) * target_y

            # Superimpose OU Tremor
            tx, ty = tremor_gen.step(dt=dt_base)
            dampening = 1.0 - (t ** 2) * 0.75
            final_x = bx + tx * dampening
            final_y = by + ty * dampening

            # Non-deterministic timing delta per segment
            seg_dt = dt_base * random.lognormvariate(0.0, 0.15)
            path.append((final_x, final_y, max(0.003, seg_dt)))

        # 3. Sub-movement correction steps if overshoot occurred
        if has_overshoot:
            correct_steps = random.randint(4, 7)
            last_x, last_y, _ = path[-1]
            for k in range(1, correct_steps + 1):
                st = k / float(correct_steps)
                cx = last_x + (x1 - last_x) * st + random.gauss(0, 0.5)
                cy = last_y + (y1 - last_y) * st + random.gauss(0, 0.5)
                path.append((cx, cy, dt_base * 0.8))

        return path


class CurvedScrollGenerator:
    """Generates momentum-based natural scroll bursts with acceleration, deceleration, and micro-pauses."""

    @staticmethod
    def generate_scroll_burst(total_pixels: int, duration: float = 0.8) -> List[Tuple[int, float]]:
        """Generates list of (pixel_delta, delay_sec) steps for smooth inertial scrolling."""
        steps = max(8, min(24, int(abs(total_pixels) / 25)))
        results = []
        sign = 1 if total_pixels >= 0 else -1
        abs_px = abs(total_pixels)
        dt = duration / float(steps)

        for i in range(1, steps + 1):
            t = i / float(steps)
            # Quadratic ease-out velocity profile
            velocity = math.sin(t * math.pi)
            step_px = int((abs_px / steps) * (0.4 + 1.2 * velocity))
            if step_px > 0:
                results.append((step_px * sign, max(0.01, dt * random.uniform(0.8, 1.2))))

        return results
