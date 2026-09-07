import os
import re
import time
import json
import math
import logging
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger("PokerMLMemory")

MEMORY_FILE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "storage", "poker_memory.json")


class PokerMLMemoryManager:
    """
    Machine Learning Memory & Spatial Calibration Engine for Poker Solvers.
    Stores and adapts:
    1. Exact pixel geometry and normalized relative coordinates of action buttons per table/client.
    2. Experience Replay & Reinforcement Learning Metrics for Poker Techniques (C-Bets, 3-Bets, Semi-Bluffs, Value Jams).
    3. Adaptive decision weighting based on historic win rates and EV yield.
    """

    _instance: Optional['PokerMLMemoryManager'] = None

    def __init__(self, storage_path: str = MEMORY_FILE_PATH):
        self.storage_path = storage_path
        self.memory: Dict[str, Any] = self._load_memory()

    @classmethod
    def get_instance(cls) -> 'PokerMLMemoryManager':
        if cls._instance is None:
            cls._instance = PokerMLMemoryManager()
        return cls._instance

    def _default_memory(self) -> Dict[str, Any]:
        return {
            "version": "2.0",
            "button_layouts": {
                "generic_canvas": {
                    "viewport": {"width": 1280, "height": 720},
                    "buttons": {
                        "fold": {"rel_x": 0.70, "rel_y": 0.91, "width": 85, "height": 42, "confidence": 0.92, "hits": 10},
                        "check": {"rel_x": 0.81, "rel_y": 0.91, "width": 85, "height": 42, "confidence": 0.92, "hits": 10},
                        "call": {"rel_x": 0.81, "rel_y": 0.91, "width": 85, "height": 42, "confidence": 0.92, "hits": 10},
                        "raise": {"rel_x": 0.92, "rel_y": 0.91, "width": 85, "height": 42, "confidence": 0.92, "hits": 10},
                        "bet": {"rel_x": 0.92, "rel_y": 0.91, "width": 85, "height": 42, "confidence": 0.92, "hits": 10},
                        "all_in": {"rel_x": 0.92, "rel_y": 0.84, "width": 80, "height": 38, "confidence": 0.88, "hits": 5}
                    },
                    "last_updated": time.time()
                }
            },
            "technique_experience": {
                "preflop_monster_raise": {"attempts": 15, "successes": 13, "chips_won": 340.0, "win_rate": 0.867, "avg_ev": 8.5},
                "flop_cbet_value": {"attempts": 22, "successes": 17, "chips_won": 215.0, "win_rate": 0.773, "avg_ev": 4.2},
                "flop_semi_bluff": {"attempts": 10, "successes": 6, "chips_won": 85.0, "win_rate": 0.600, "avg_ev": 2.0},
                "turn_second_barrel": {"attempts": 8, "successes": 6, "chips_won": 160.0, "win_rate": 0.750, "avg_ev": 5.1},
                "river_value_bet": {"attempts": 14, "successes": 12, "chips_won": 410.0, "win_rate": 0.857, "avg_ev": 11.2},
                "pot_control_check": {"attempts": 20, "successes": 14, "chips_won": 65.0, "win_rate": 0.700, "avg_ev": 1.1}
            },
            "hand_history_log": []
        }

    def _load_memory(self) -> Dict[str, Any]:
        if os.path.exists(self.storage_path) and os.path.getsize(self.storage_path) > 0:
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict) and "button_layouts" in data:
                        return data
            except Exception as e:
                logger.debug(f"[PokerMLMemory] Re-initializing memory file: {e}")
        
        default_mem = self._default_memory()
        self._save_memory(default_mem)
        return default_mem

    def _save_memory(self, data: Optional[Dict[str, Any]] = None) -> None:
        if data is not None:
            self.memory = data
        try:
            os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(self.memory, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"[PokerMLMemory] Failed to save memory file: {e}")

    def _clean_table_key(self, page_url_or_domain: str) -> str:
        if not page_url_or_domain:
            return "generic_canvas"
        u = page_url_or_domain.lower()
        if "playwsop" in u or "wsop" in u:
            return "playwsop"
        elif "zynga" in u:
            return "zynga_poker"
        elif "pokerstars" in u:
            return "pokerstars"
        elif "ggpoker" in u or "natural8" in u:
            return "ggpoker"
        elif "coinpoker" in u:
            return "coinpoker"
        elif "replaypoker" in u:
            return "replaypoker"
        elif "clubgg" in u:
            return "clubgg"
        
        # Extract host or clean key
        clean = re.sub(r"https?://", "", u).split("/")[0].replace(":", "_")
        return clean or "generic_canvas"

    # --- 1. SPATIAL BUTTON GEOMETRY MEMORY ---

    def get_button_coordinates(
        self,
        page_url: str,
        viewport_w: float,
        viewport_h: float,
        action_name: str
    ) -> Optional[Tuple[float, float, float, float]]:
        """
        Retrieves learned pixel bounding box (center_x, center_y, width, height)
        for an action button calibrated to the current viewport resolution.
        """
        key = self._clean_table_key(page_url)
        layouts = self.memory.get("button_layouts", {})
        
        table_layout = layouts.get(key) or layouts.get("generic_canvas")
        if not table_layout:
            return None

        btn_data = table_layout.get("buttons", {}).get(action_name.lower())
        if not btn_data:
            return None

        rel_x = float(btn_data.get("rel_x", 0.8))
        rel_y = float(btn_data.get("rel_y", 0.9))
        btn_w = float(btn_data.get("width", 80.0))
        btn_h = float(btn_data.get("height", 40.0))

        # Denormalize to live viewport pixel coordinates
        actual_x = rel_x * viewport_w
        actual_y = rel_y * viewport_h

        return actual_x, actual_y, btn_w, btn_h

    def update_button_coordinates(
        self,
        page_url: str,
        viewport_w: float,
        viewport_h: float,
        action_name: str,
        abs_x: float,
        abs_y: float,
        width: float,
        height: float
    ) -> None:
        """
        Learns / updates the spatial geometry of a poker button using Exponential Moving Average (EMA)
        smoothing to adjust for responsive viewport layouts.
        """
        if viewport_w <= 0 or viewport_h <= 0:
            return

        key = self._clean_table_key(page_url)
        if "button_layouts" not in self.memory:
            self.memory["button_layouts"] = {}

        if key not in self.memory["button_layouts"]:
            self.memory["button_layouts"][key] = {
                "viewport": {"width": viewport_w, "height": viewport_h},
                "buttons": {},
                "last_updated": time.time()
            }

        table_layout = self.memory["button_layouts"][key]
        table_layout["viewport"] = {"width": viewport_w, "height": viewport_h}
        table_layout["last_updated"] = time.time()

        new_rel_x = abs_x / viewport_w
        new_rel_y = abs_y / viewport_h

        act_key = action_name.lower()
        existing = table_layout["buttons"].get(act_key)

        if existing:
            # EMA Smoothing (alpha = 0.35)
            alpha = 0.35
            smoothed_x = (1 - alpha) * existing["rel_x"] + alpha * new_rel_x
            smoothed_y = (1 - alpha) * existing["rel_y"] + alpha * new_rel_y
            hits = existing.get("hits", 1) + 1
            conf = min(0.99, existing.get("confidence", 0.8) + 0.02)

            table_layout["buttons"][act_key] = {
                "rel_x": round(smoothed_x, 4),
                "rel_y": round(smoothed_y, 4),
                "width": round(width, 1),
                "height": round(height, 1),
                "confidence": round(conf, 2),
                "hits": hits
            }
        else:
            table_layout["buttons"][act_key] = {
                "rel_x": round(new_rel_x, 4),
                "rel_y": round(new_rel_y, 4),
                "width": round(width, 1),
                "height": round(height, 1),
                "confidence": 0.85,
                "hits": 1
            }

        self._save_memory()
        logger.info(f"[PokerMLMemory] Calibrated '{act_key}' for table '{key}' -> rel=({new_rel_x:.3f}, {new_rel_y:.3f})")

    # --- 2. TECHNIQUE & REINFORCEMENT LEARNING EXPERIENCE ---

    def record_technique_outcome(
        self,
        technique: str,
        outcome: str,
        profit: float,
        ev: float = 0.0,
        hand_details: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Records the real-world outcome of a poker technique (e.g. 'cbet_flop', 'preflop_3bet')
        and updates the dynamic win rate and expected value model.
        """
        if "technique_experience" not in self.memory:
            self.memory["technique_experience"] = {}

        t_data = self.memory["technique_experience"].setdefault(technique, {
            "attempts": 0,
            "successes": 0,
            "chips_won": 0.0,
            "win_rate": 0.5,
            "avg_ev": 0.0
        })

        t_data["attempts"] += 1
        is_success = (outcome.lower() in ["win", "success", "fold_forced", "pot_won"] or profit > 0.0)
        if is_success:
            t_data["successes"] += 1

        t_data["chips_won"] = round(t_data.get("chips_won", 0.0) + profit, 1)
        t_data["win_rate"] = round(t_data["successes"] / float(t_data["attempts"]), 3)
        t_data["avg_ev"] = round((t_data.get("avg_ev", 0.0) * (t_data["attempts"] - 1) + ev) / float(t_data["attempts"]), 2)

        # Log to recent history (keep max 100 entries)
        if "hand_history_log" not in self.memory:
            self.memory["hand_history_log"] = []

        log_entry = {
            "timestamp": time.time(),
            "technique": technique,
            "outcome": outcome,
            "profit": profit,
            "ev": ev,
            "details": hand_details or {}
        }
        self.memory["hand_history_log"].append(log_entry)
        if len(self.memory["hand_history_log"]) > 100:
            self.memory["hand_history_log"] = self.memory["hand_history_log"][-100:]

        self._save_memory()
        logger.info(f"[PokerMLMemory] Recorded technique '{technique}' outcome={outcome} (Profit: {profit:+.1f}, Win-Rate: {t_data['win_rate']*100:.1f}%)")

    def get_technique_aggression_multiplier(self, technique: str) -> float:
        """
        Calculates an adaptive multiplier (0.80 to 1.30) based on historical success rate.
        If a technique is consistently profitable, the solver uses it with higher confidence.
        """
        t_data = self.memory.get("technique_experience", {}).get(technique)
        if not t_data or t_data.get("attempts", 0) < 3:
            return 1.0

        wr = float(t_data.get("win_rate", 0.5))
        # Scale between 0.80 (low win rate) and 1.30 (high win rate > 75%)
        mult = 0.80 + (wr * 0.50)
        return max(0.80, min(1.30, round(mult, 2)))

    def get_learning_stats_summary(self) -> Dict[str, Any]:
        """Returns structured summary of learned layouts and technique metrics."""
        return {
            "total_tables_learned": len(self.memory.get("button_layouts", {})),
            "techniques": self.memory.get("technique_experience", {}),
            "recent_hands_logged": len(self.memory.get("hand_history_log", []))
        }
