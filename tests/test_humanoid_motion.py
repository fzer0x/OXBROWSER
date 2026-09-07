import os
import sys
import math

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.warmup.stochastic_motion import (
    OrnsteinUhlenbeckTremor,
    HumanoidTrajectoryGenerator,
    CurvedScrollGenerator
)


def test_ornstein_uhlenbeck_tremor():
    tremor = OrnsteinUhlenbeckTremor(theta=0.15, sigma=0.5)
    samples_x = []
    samples_y = []
    for _ in range(100):
        tx, ty = tremor.step(dt=0.016)
        samples_x.append(tx)
        samples_y.append(ty)

    assert len(samples_x) == 100
    assert any(abs(x) > 0.001 for x in samples_x)
    print(f" OU Tremor generated {len(samples_x)} samples successfully.")


def test_stochastic_path_generation():
    start = (150.0, 200.0)
    end = (800.0, 600.0)
    duration = 0.85

    path = HumanoidTrajectoryGenerator.generate_stochastic_path(start, end, duration, target_size=50.0)
    assert len(path) >= 15

    for x, y, dt in path:
        assert isinstance(x, float)
        assert isinstance(y, float)
        assert dt > 0.001

    # Check total movement progression
    start_point = path[0]
    end_point = path[-1]
    dist_to_target = math.hypot(end_point[0] - end[0], end_point[1] - end[1])
    assert dist_to_target < 15.0  # Finished within target button bounds
    print(f" Stochastic Path generated {len(path)} waypoints (Final accuracy delta: {dist_to_target:.2f}px).")


def test_curved_scroll_generator():
    burst = CurvedScrollGenerator.generate_scroll_burst(total_pixels=450, duration=0.6)
    assert len(burst) >= 8
    total_scrolled = sum(px for px, _ in burst)
    print(f" Curved Scroll burst generated {len(burst)} steps (Total scrolled: {total_scrolled}px).")
    assert abs(total_scrolled) > 100


if __name__ == "__main__":
    test_ornstein_uhlenbeck_tremor()
    test_stochastic_path_generation()
    test_curved_scroll_generator()
    print("ALL PHASE 3 HUMAN MOTION TESTS PASSED! ⫸")
