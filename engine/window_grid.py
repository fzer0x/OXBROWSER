import math
from typing import List, Tuple


class WindowGridCalculator:
    """Calculates non-overlapping auto-tiling grid positions (x, y, width, height) for multi-browser launches."""

    @staticmethod
    def calculate_grid_positions(
        count: int,
        screen_w: int = 1920,
        screen_h: int = 1080,
        taskbar_h: int = 40
    ) -> List[Tuple[int, int, int, int]]:
        """
        Returns a list of (pos_x, pos_y, width, height) tuples for positioning N windows side-by-side.
        """
        if count <= 0:
            return []

        usable_h = max(400, screen_h - taskbar_h)

        if count == 1:
            return [(0, 0, screen_w, usable_h)]
        elif count == 2:
            w = screen_w // 2
            return [
                (0, 0, w, usable_h),
                (w, 0, w, usable_h)
            ]

        # Calculate optimal number of columns and rows
        cols = math.ceil(math.sqrt(count))
        rows = math.ceil(count / cols)

        win_w = max(360, screen_w // cols)
        win_h = max(300, usable_h // rows)

        positions = []
        for idx in range(count):
            r = idx // cols
            c = idx % cols
            x = c * win_w
            y = r * win_h
            positions.append((x, y, win_w, win_h))

        return positions
