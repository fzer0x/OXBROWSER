"""
chess_antidetect.py
===================
Statistical anti-detection layer for the SoxBot chess solver.

Implements:
  PositionDifficultyAnalyzer  – difficulty score per position (0.0-1.0)
  PlayerBaseline              – rolling session model of "normal" play
  HumanizedTimingEngine       – difficulty-correlated, fatigue-aware think times
  EloThrottleController       – probabilistic move selection to match target Elo
  AntiDetectChessSession      – main orchestrator (one instance per game)

Counteracts all 16 detection vectors described in the spec:
  Timing analysis, engine correlation, difficulty-weighted accuracy,
  CPL tracking, player baseline deviation, performance rating spikes,
  opening/endgame weighting, humanizer detection, and multi-game analysis.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import random
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("ChessAntiDetect")


# ---------------------------------------------------------------------------
# Constants & Elo → CPL calibration table
# ---------------------------------------------------------------------------

# Empirically calibrated: (avg_cpl, std_cpl) per Elo band (from Lichess data)
ELO_CPL_TABLE: Dict[int, Tuple[float, float]] = {
    800:  (120.0, 55.0),
    1000: ( 90.0, 45.0),
    1200: ( 65.0, 38.0),
    1400: ( 48.0, 30.0),
    1600: ( 35.0, 24.0),
    1800: ( 24.0, 18.0),
    2000: ( 16.0, 12.0),
    2200: ( 10.0,  8.0),
    2400: (  6.0,  5.0),
    2600: (  3.5,  3.0),
}

# Phase move weights (counteracts opening/endgame pattern detection)
PHASE_WEIGHTS = {
    "opening":    0.20,
    "middlegame": 0.75,
    "endgame":    1.00,
}


def _elo_to_cpl(target_elo: int) -> Tuple[float, float]:
    """Interpolates avg_cpl and std_cpl for any Elo in [800, 2600]."""
    keys = sorted(ELO_CPL_TABLE.keys())
    if target_elo <= keys[0]:
        return ELO_CPL_TABLE[keys[0]]
    if target_elo >= keys[-1]:
        return ELO_CPL_TABLE[keys[-1]]
    for i in range(len(keys) - 1):
        lo, hi = keys[i], keys[i + 1]
        if lo <= target_elo <= hi:
            t = (target_elo - lo) / (hi - lo)
            avg_lo, std_lo = ELO_CPL_TABLE[lo]
            avg_hi, std_hi = ELO_CPL_TABLE[hi]
            return (avg_lo + t * (avg_hi - avg_lo), std_lo + t * (std_hi - std_lo))
    return ELO_CPL_TABLE[keys[-1]]


def _game_phase(move_number: int) -> str:
    if move_number <= 12:
        return "opening"
    elif move_number <= 30:
        return "middlegame"
    return "endgame"


def _re_first(pattern: str, text: str) -> Optional[str]:
    m = re.search(pattern, text)
    return m.group(1) if m else None


# ---------------------------------------------------------------------------
# PositionDifficultyAnalyzer
# ---------------------------------------------------------------------------

@dataclass
class DifficultyResult:
    score: float           # 0.0 (trivial) → 1.0 (extremely hard)
    eval_gap_cp: int       # centipawn gap between engine top-1 and top-2
    top_moves: List[str]   # UCI moves from multipv (best first)
    top_evals: List[int]   # corresponding evals (relative, centipawns)
    candidate_count: int   # legal move count
    is_tactical: bool      # large eval swing possible


class PositionDifficultyAnalyzer:
    """
    Scores a position's difficulty using Stockfish MultiPV 3.

    The key insight: easy positions have one obviously best move (large gap
    between top-1 and top-2 eval). Hard positions have several near-equal
    candidates — exactly where engine assistance is most detectable.
    """

    def __init__(self, stockfish_path: Optional[str] = None):
        self.stockfish_path = stockfish_path

    def analyze(
        self,
        fen: str,
        candidate_uci_moves: List[str],
        depth: int = 12,
        timeout_ms: int = 1500,
    ) -> DifficultyResult:
        """Synchronous difficulty analysis."""
        if self.stockfish_path:
            try:
                result = self._stockfish_multipv(fen, depth=depth, timeout_ms=timeout_ms)
                if result:
                    return result
            except Exception as e:
                logger.debug(f"[DifficultyAnalyzer] Stockfish multipv error: {e}")
        return self._heuristic_difficulty(fen, candidate_uci_moves)

    async def analyze_async(
        self,
        fen: str,
        candidate_uci_moves: List[str],
        depth: int = 12,
        timeout_ms: int = 1500,
    ) -> DifficultyResult:
        """Async wrapper — runs Stockfish in executor thread."""
        return await asyncio.to_thread(
            self.analyze, fen, candidate_uci_moves, depth, timeout_ms
        )

    def _stockfish_multipv(self, fen: str, depth: int, timeout_ms: int) -> Optional[DifficultyResult]:
        """Runs Stockfish with MultiPV 3 and extracts eval gap."""
        if not self.stockfish_path:
            return None
        sf_bin: str = self.stockfish_path
        from engine.platform_helper import PlatformHelper
        proc = subprocess.Popen(
            [sf_bin],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            creationflags=PlatformHelper.get_subprocess_creation_flags()
        )
        try:
            uci_init = (
                "uci\n"
                "setoption name MultiPV value 3\n"
                "setoption name Threads value 1\n"
                "setoption name Hash value 64\n"
                "isready\n"
                f"position fen {fen}\n"
                f"go depth {depth}\n"
            )
            if proc.stdin:
                proc.stdin.write(uci_init)
                proc.stdin.flush()

            multipv_data: Dict[int, Dict] = {}
            deadline = time.time() + (timeout_ms / 1000.0) + 3.0

            while time.time() < deadline:
                line = (proc.stdout.readline() if proc.stdout else "").strip()
                if not line:
                    continue
                if line.startswith("info") and "multipv" in line and " pv " in line:
                    mp = _re_first(r"multipv (\d+)", line)
                    pv = _re_first(r" pv (\S+)", line)
                    cp = _re_first(r"score cp (-?\d+)", line)
                    mt = _re_first(r"score mate (-?\d+)", line)
                    if mp and pv:
                        idx = int(mp)
                        ev = int(cp) if cp is not None else (30000 if mt and int(mt) > 0 else -30000)
                        multipv_data[idx] = {"move": pv, "eval": ev}
                if line.startswith("bestmove"):
                    break

            if not multipv_data:
                return None

            sorted_keys = sorted(multipv_data.keys())
            top_moves = [multipv_data[k]["move"] for k in sorted_keys if "move" in multipv_data[k]]
            top_evals = [multipv_data[k]["eval"] for k in sorted_keys if "eval" in multipv_data[k]]

            if not top_evals:
                return None

            eval_gap = abs(top_evals[0] - top_evals[1]) if len(top_evals) >= 2 else 300
            is_tactical = eval_gap > 150 or abs(top_evals[0]) > 200

            # Narrow gap → harder; 0cp gap → 1.0, 300cp+ gap → 0.0
            gap_score   = max(0.0, 1.0 - eval_gap / 300.0)
            count_score = min(1.0, len(top_moves) / 30.0)
            difficulty  = max(0.0, min(1.0, 0.65 * gap_score + 0.35 * count_score))

            return DifficultyResult(
                score=round(difficulty, 3),
                eval_gap_cp=eval_gap,
                top_moves=top_moves,
                top_evals=top_evals,
                candidate_count=len(top_moves),
                is_tactical=is_tactical,
            )
        finally:
            try:
                proc.terminate()
            except Exception:
                pass

    def _heuristic_difficulty(self, fen: str, candidate_uci_moves: List[str]) -> DifficultyResult:
        piece_count = sum(1 for c in fen.split()[0] if c.isalpha())
        endgame_bonus = max(0.0, (16 - piece_count) / 16.0) * 0.3
        count_score   = min(1.0, len(candidate_uci_moves) / 30.0) * 0.4
        difficulty    = max(0.0, min(1.0, 0.3 + endgame_bonus + count_score))
        return DifficultyResult(
            score=round(difficulty, 3),
            eval_gap_cp=100,
            top_moves=candidate_uci_moves[:3] if candidate_uci_moves else [],
            top_evals=[0],
            candidate_count=len(candidate_uci_moves),
            is_tactical=False,
        )


# ---------------------------------------------------------------------------
# PlayerBaseline
# ---------------------------------------------------------------------------

@dataclass
class MoveRecord:
    move_number: int
    fen: str
    played_move: str
    engine_top1: str
    cpl: int
    difficulty: float
    think_seconds: float
    phase: str
    is_engine_top1: bool
    is_engine_top3: bool


class PlayerBaseline:
    """
    Rolling per-session model of "normal" play statistics.

    Tracks CPL, blunder rate, engine correlation, timing distributions
    bucketed by difficulty, and estimated performance rating.
    Exposes deviation_score() to flag if the current game is anomalous.
    """

    def __init__(self, profile_path: Optional[str] = None, window: int = 80):
        self.profile_path = profile_path
        self.window = window
        self.moves: List[MoveRecord] = []
        self._game_cpls: List[float] = []
        self._game_ratings: List[float] = []

        self._baseline: Dict = {
            "avg_cpl": 65.0,
            "cpl_variance": 38.0 ** 2,
            "blunder_rate": 0.08,
            "engine_top1_rate": 0.40,
            "engine_top3_rate": 0.70,
            "avg_think_easy": 1.5,
            "avg_think_hard": 6.0,
            "std_think_easy": 0.6,
            "std_think_hard": 2.5,
            "games_sampled": 0,
        }
        self._load_baseline()

    def _load_baseline(self):
        if not self.profile_path:
            return
        p = Path(self.profile_path) / "chess_baseline.json"
        if p.exists():
            try:
                with open(p) as f:
                    self._baseline.update(json.load(f))
                logger.debug(f"[PlayerBaseline] Loaded baseline from {p}")
            except Exception as e:
                logger.debug(f"[PlayerBaseline] Could not load baseline: {e}")

    def save_baseline(self):
        if not self.profile_path:
            return
        p = Path(self.profile_path) / "chess_baseline.json"
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w") as f:
                json.dump(self._baseline, f, indent=2)
        except Exception as e:
            logger.debug(f"[PlayerBaseline] Could not save baseline: {e}")

    def record_move(self, record: MoveRecord):
        self.moves.append(record)
        if len(self.moves) > self.window:
            self.moves.pop(0)

    def finish_game(self, game_avg_cpl: float, performance_rating: float):
        self._game_cpls.append(game_avg_cpl)
        self._game_ratings.append(performance_rating)
        alpha = 0.15
        n = self._baseline["games_sampled"]
        if n >= 3:
            self._baseline["avg_cpl"] = (1 - alpha) * self._baseline["avg_cpl"] + alpha * game_avg_cpl
        self._baseline["games_sampled"] = n + 1
        self.save_baseline()

    @property
    def current_avg_cpl(self) -> float:
        if not self.moves:
            return self._baseline["avg_cpl"]
        return sum(m.cpl for m in self.moves) / len(self.moves)

    @property
    def current_blunder_rate(self) -> float:
        if not self.moves:
            return self._baseline["blunder_rate"]
        return sum(1 for m in self.moves if m.cpl > 100) / len(self.moves)

    @property
    def current_engine_top1_rate(self) -> float:
        if not self.moves:
            return self._baseline["engine_top1_rate"]
        return sum(1 for m in self.moves if m.is_engine_top1) / len(self.moves)

    @property
    def current_engine_top3_rate(self) -> float:
        if not self.moves:
            return self._baseline["engine_top3_rate"]
        return sum(1 for m in self.moves if m.is_engine_top3) / len(self.moves)

    def avg_think_for_difficulty(self, difficulty: float) -> float:
        bucket = [m for m in self.moves if abs(m.difficulty - difficulty) < 0.25]
        if len(bucket) < 3:
            easy_t = self._baseline["avg_think_easy"]
            hard_t = self._baseline["avg_think_hard"]
            return easy_t + difficulty * (hard_t - easy_t)
        return sum(m.think_seconds for m in bucket) / len(bucket)

    def deviation_score(self) -> float:
        """Returns 0.0-1.0; values > 0.6 indicate suspicious play vs. baseline."""
        if len(self.moves) < 8:
            return 0.0
        baseline_cpl  = self._baseline["avg_cpl"]
        cpl_dev   = max(0.0, (baseline_cpl - self.current_avg_cpl) / baseline_cpl)
        baseline_top1 = self._baseline["engine_top1_rate"]
        top1_dev  = max(0.0, (self.current_engine_top1_rate - baseline_top1) / max(0.01, 1.0 - baseline_top1))
        blunder_dev = max(0.0, (self._baseline["blunder_rate"] - self.current_blunder_rate) / max(0.01, self._baseline["blunder_rate"]))
        score = 0.40 * cpl_dev + 0.40 * top1_dev + 0.20 * blunder_dev
        return round(min(1.0, score), 3)

    def to_dict(self) -> Dict:
        return {
            "moves_recorded": len(self.moves),
            "current_avg_cpl": round(self.current_avg_cpl, 1),
            "current_blunder_rate": round(self.current_blunder_rate, 3),
            "current_engine_top1_rate": round(self.current_engine_top1_rate, 3),
            "deviation_score": self.deviation_score(),
            "baseline": self._baseline,
        }


# ---------------------------------------------------------------------------
# HumanizedTimingEngine
# ---------------------------------------------------------------------------

class HumanizedTimingEngine:
    """
    Difficulty-correlated, fatigue-aware thinking time generator.

    Counteracts:
    - Constant-timing detection (std_dev always scales with difficulty)
    - Time-vs-difficulty correlation analysis
    - Humanizer detection (not a fixed jitter offset on engine time)
    - Clock urgency modelling
    """

    _PRESETS: Dict[str, Tuple[float, float, float, float]] = {
        # (mean_easy, mean_hard, std_easy, std_hard) in seconds
        "bullet":    (0.40,  2.5,  0.15, 0.50),
        "fast":      (0.55,  3.0,  0.18, 0.60),
        "blitz":     (1.00,  8.0,  0.40, 1.80),
        "speed":     (1.20,  9.0,  0.50, 2.00),
        "rapid":     (2.50, 18.0,  0.80, 4.00),
        "classical": (4.00, 35.0,  1.20, 7.00),
        "balanced":  (1.50, 10.0,  0.50, 2.50),
    }

    def __init__(self, speed_preset: str = "blitz", target_elo: int = 1500):
        self.speed_preset = speed_preset.lower()
        self.target_elo = target_elo
        preset = self._PRESETS.get(self.speed_preset, self._PRESETS["blitz"])
        self._mean_easy, self._mean_hard, self._std_easy, self._std_hard = preset

    def think_time(
        self,
        difficulty: float,
        move_number: int = 1,
        clock_remaining_s: float = 300.0,
        is_book: bool = False,
        is_recapture: bool = False,
        is_forced: bool = False,
    ) -> float:
        """Returns a realistic think time in seconds."""

        # --- Special fast-cases ------------------------------------------
        if is_forced:
            return max(0.3, round(random.gauss(0.5, 0.12), 2))

        if is_recapture and move_number > 5:
            return max(0.25, round(random.gauss(0.55, 0.18), 2))

        if is_book or move_number <= 3:
            return max(0.4, round(random.gauss(0.85, 0.25), 2))

        # --- Difficulty-interpolated base time ---------------------------
        mean_t = self._mean_easy + difficulty * (self._mean_hard - self._mean_easy)
        std_t  = self._std_easy  + difficulty * (self._std_hard  - self._std_easy)

        # --- Session fatigue: slight drift upward as move count grows ----
        fatigue_factor = 1.0 + min(0.25, move_number * 0.004)
        mean_t *= fatigue_factor

        # --- Clock urgency -----------------------------------------------
        if clock_remaining_s < 30.0:
            urgency = max(0.2, clock_remaining_s / 30.0)
            mean_t *= urgency
            std_t  *= urgency
        elif clock_remaining_s < 90.0:
            urgency = 0.6 + (clock_remaining_s - 30.0) / 150.0
            mean_t *= urgency

        # --- Elo modifier ------------------------------------------------
        if self.target_elo < 1400:
            mean_t += random.uniform(0.3, 1.0)
        elif self.target_elo > 2200:
            mean_t *= 0.85

        # --- Sample from Gaussian ----------------------------------------
        t = max(0.25, random.gauss(mean_t, std_t))

        # --- Think-and-change pattern (15% on hard positions) ------------
        # Simulate: consider a move, reconsider, pause again
        if difficulty > 0.65 and random.random() < 0.15:
            t += random.uniform(1.2, 3.5)

        return round(t, 2)

    @staticmethod
    def pre_move_hover_delay() -> float:
        """Delay between thinking ending and mouse starting to move."""
        return round(random.gauss(0.12, 0.04), 3)

    @staticmethod
    def post_move_pause() -> float:
        """Tiny pause after releasing the piece (motor delay)."""
        return round(random.uniform(0.02, 0.08), 3)


# ---------------------------------------------------------------------------
# EloThrottleController
# ---------------------------------------------------------------------------

class EloThrottleController:
    """
    Controls engine strength to match a target Elo rating.

    Samples from the top-N engine candidates weighted to produce the CPL
    distribution of a real player at target_elo.

    Counteracts:
    - Suspiciously high engine correlation
    - Hard-position accuracy anomalies
    - Performance rating spikes
    - Perfect endgame play on low-rated accounts
    """

    def __init__(
        self,
        target_elo: int = 1500,
        opening_strength: float = 1.0,
        endgame_strength: float = 0.85,
    ):
        self.target_elo = target_elo
        self.opening_strength = opening_strength
        self.endgame_strength = endgame_strength
        self._avg_cpl_target, self._cpl_std_target = _elo_to_cpl(target_elo)
        self._move_cpls: List[int] = []

    def select_move(
        self,
        top_moves: List[str],
        top_evals: List[int],
        difficulty: DifficultyResult,
        move_number: int,
        legal_moves: List[str],
        baseline: Optional[PlayerBaseline] = None,
    ) -> Tuple[str, int]:
        """Returns (chosen_uci_move, actual_cpl)."""
        if not top_moves or not legal_moves:
            return (legal_moves[0] if legal_moves else ""), 0

        candidates = [(m, e) for m, e in zip(top_moves, top_evals) if m in legal_moves]
        if not candidates:
            candidates = [(top_moves[0], top_evals[0])]

        phase = _game_phase(move_number)
        phase_weight = PHASE_WEIGHTS[phase]

        # Opening: prefer engine top-1 (opening theory is expected)
        if phase == "opening" or move_number <= 6:
            if random.random() < self.opening_strength:
                self._move_cpls.append(0)
                return candidates[0][0], 0

        # Sample a target CPL for this move from calibrated distribution
        target_cpl = abs(random.gauss(
            self._avg_cpl_target * difficulty.score * phase_weight,
            self._cpl_std_target,
        ))

        # Find candidate whose CPL from top-1 best matches target_cpl
        best_eval = top_evals[0] if top_evals else 0
        chosen_idx = 0
        best_delta = float("inf")
        for i, (move, ev) in enumerate(candidates):
            cpl = abs(best_eval - ev)
            delta = abs(cpl - target_cpl)
            if delta < best_delta:
                best_delta = delta
                chosen_idx = i

        chosen_move, chosen_eval = candidates[chosen_idx]
        actual_cpl = abs(best_eval - chosen_eval)

        # Safety: never deliberately blunder when ahead
        if actual_cpl > 200 and best_eval > -100:
            chosen_move, chosen_eval = candidates[0]
            actual_cpl = 0

        # Deviation guard: if session stats are already suspicious, force top-1
        if baseline and baseline.deviation_score() > 0.55:
            logger.debug("[EloThrottle] High deviation score → forcing engine top-1")
            chosen_move, chosen_eval = candidates[0]
            actual_cpl = 0

        self._move_cpls.append(actual_cpl)
        return chosen_move, actual_cpl

    @property
    def session_avg_cpl(self) -> float:
        if not self._move_cpls:
            return 0.0
        return sum(self._move_cpls) / len(self._move_cpls)

    def estimate_performance_rating(self, session_avg_cpl: Optional[float] = None) -> float:
        """Inverse-maps CPL to Elo via the calibration table."""
        cpl = session_avg_cpl if session_avg_cpl is not None else self.session_avg_cpl
        keys = sorted(ELO_CPL_TABLE.keys())
        for i in range(len(keys) - 1, -1, -1):
            avg, _ = ELO_CPL_TABLE[keys[i]]
            if cpl <= avg:
                return float(keys[i])
        return float(keys[0])

    def to_dict(self) -> Dict:
        return {
            "target_elo": self.target_elo,
            "avg_cpl_target": round(self._avg_cpl_target, 1),
            "session_avg_cpl": round(self.session_avg_cpl, 1),
            "estimated_performance_rating": round(self.estimate_performance_rating(), 0),
            "moves_sampled": len(self._move_cpls),
        }


# ---------------------------------------------------------------------------
# AntiDetectChessSession
# ---------------------------------------------------------------------------

class AntiDetectChessSession:
    """
    Main orchestrator for a single chess game session.

    Usage::

        session = AntiDetectChessSession(
            stockfish_path="/usr/bin/stockfish",
            target_elo=1500,
            speed_preset="blitz",
            profile_path="/path/to/profiles/account-id",
        )

        # Before every move:
        move, think_secs, diff = await session.get_move(
            fen=current_fen,
            top_moves=engine_top3_moves,
            top_evals=engine_top3_evals,
            legal_moves=all_legal_uci,
            clock_remaining_s=180.0,
        )
        await asyncio.sleep(think_secs)
        # play move ...

        # At game end:
        session.finish_game()
    """

    def __init__(
        self,
        stockfish_path: Optional[str] = None,
        target_elo: int = 1500,
        speed_preset: str = "blitz",
        profile_path: Optional[str] = None,
        difficulty_depth: int = 12,
        difficulty_timeout_ms: int = 1200,
    ):
        self.stockfish_path = stockfish_path
        self.target_elo = target_elo
        self.speed_preset = speed_preset
        self.profile_path = profile_path
        self._move_number = 0
        self._session_cpls: List[int] = []

        self.difficulty_analyzer = PositionDifficultyAnalyzer(stockfish_path=stockfish_path)
        self.baseline = PlayerBaseline(profile_path=profile_path)
        self.timing_engine = HumanizedTimingEngine(speed_preset=speed_preset, target_elo=target_elo)
        self.throttle = EloThrottleController(target_elo=target_elo)

    async def get_move(
        self,
        fen: str,
        top_moves: List[str],
        top_evals: List[int],
        legal_moves: List[str],
        clock_remaining_s: float = 300.0,
        is_book: bool = False,
        is_recapture: bool = False,
    ) -> Tuple[str, float, DifficultyResult]:
        """
        Select the best-fit move and compute the humanized think time.

        Returns:
            (chosen_uci_move, think_seconds, difficulty_result)
        """
        self._move_number += 1

        # 1. Score position difficulty
        if is_book:
            difficulty = DifficultyResult(
                score=0.05, eval_gap_cp=300,
                top_moves=top_moves, top_evals=top_evals,
                candidate_count=len(legal_moves), is_tactical=False,
            )
        else:
            difficulty = await self.difficulty_analyzer.analyze_async(
                fen, legal_moves,
                depth=12, timeout_ms=1200,
            )

        # 2. Select move via Elo throttle
        is_forced = len(legal_moves) == 1
        chosen_move, actual_cpl = self.throttle.select_move(
            top_moves=top_moves,
            top_evals=top_evals,
            difficulty=difficulty,
            move_number=self._move_number,
            legal_moves=legal_moves,
            baseline=self.baseline,
        )
        self._session_cpls.append(actual_cpl)

        # 3. Compute think time
        think_secs = self.timing_engine.think_time(
            difficulty=difficulty.score,
            move_number=self._move_number,
            clock_remaining_s=clock_remaining_s,
            is_book=is_book,
            is_recapture=is_recapture,
            is_forced=is_forced,
        )

        # 4. Record move in baseline
        engine_top1 = top_moves[0] if top_moves else chosen_move
        engine_top3 = set(top_moves[:3])
        self.baseline.record_move(MoveRecord(
            move_number=self._move_number,
            fen=fen,
            played_move=chosen_move,
            engine_top1=engine_top1,
            cpl=actual_cpl,
            difficulty=difficulty.score,
            think_seconds=think_secs,
            phase=_game_phase(self._move_number),
            is_engine_top1=(chosen_move == engine_top1),
            is_engine_top3=(chosen_move in engine_top3),
        ))

        logger.info(
            f"[AntiDetect] Move {self._move_number}: {chosen_move} | "
            f"difficulty={difficulty.score:.2f} eval_gap={difficulty.eval_gap_cp}cp "
            f"CPL={actual_cpl} think={think_secs:.2f}s "
            f"deviation={self.baseline.deviation_score():.2f}"
        )

        return chosen_move, think_secs, difficulty

    def finish_game(self):
        """Call at game end to update the persistent baseline."""
        if not self._session_cpls:
            return
        avg_cpl = sum(self._session_cpls) / len(self._session_cpls)
        perf_rating = self.throttle.estimate_performance_rating(avg_cpl)
        self.baseline.finish_game(avg_cpl, perf_rating)
        logger.info(
            f"[AntiDetect] Game finished: avg_cpl={avg_cpl:.1f} "
            f"estimated_perf_rating={perf_rating:.0f} "
            f"deviation_score={self.baseline.deviation_score():.2f}"
        )

    def status(self) -> Dict:
        return {
            "move_number": self._move_number,
            "throttle": self.throttle.to_dict(),
            "baseline": self.baseline.to_dict(),
            "speed_preset": self.speed_preset,
            "target_elo": self.target_elo,
        }
