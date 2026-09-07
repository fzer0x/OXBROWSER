import os
import re
import json
import math
import random
import asyncio
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple, Union

from .poker_evaluator import PokerCard, PokerHandEvaluator, HandRank

logger = logging.getLogger("PokerSolver")


class PokerAction(str, Enum):
    FOLD = "fold"
    CHECK = "check"
    CALL = "call"
    BET = "bet"
    RAISE = "raise"
    ALL_IN = "all_in"


class PokerAntiBanEngine:
    """
    State-of-the-Art Anti-Ban & Stealth Humanization Engine for Poker Solvers.
    Simulates human reaction time, Gaussian street-by-street thinking distributions,
    pot-odds deliberation latency, click jitter, and cubic Bézier cursor trajectories.
    """

    @staticmethod
    def calculate_human_thinking_delay(
        action: PokerAction,
        community_cards_count: int = 0,
        pot_size: float = 20.0,
        current_bet_to_call: float = 0.0,
        equity: float = 0.5,
        speed_preset: str = "balanced"
    ) -> float:
        """
        Calculates realistic human reaction & deliberation time in seconds.
        """
        if community_cards_count == 0:
            street = "preflop"
        elif community_cards_count == 3:
            street = "flop"
        elif community_cards_count == 4:
            street = "turn"
        else:
            street = "river"

        preset = (speed_preset or "balanced").lower()

        # 1. Fast / Obvious Pre-Flop Folds
        if action == PokerAction.FOLD and street == "preflop":
            base = random.uniform(0.6, 1.5)
            if preset in ["fast", "blitz", "speed"]:
                base *= 0.7
            return max(0.4, round(base + random.gauss(0, 0.15), 2))

        # 2. Standard Checks / Small Calls
        if action in [PokerAction.CHECK, PokerAction.CALL] and current_bet_to_call <= 0.0:
            base = random.uniform(1.1, 2.4)
            if street in ["turn", "river"]:
                base += random.uniform(0.5, 1.2)
            if preset in ["fast", "blitz", "speed"]:
                base *= 0.75
            return max(0.5, round(base + random.gauss(0, 0.25), 2))

        # 3. Critical Calling Decisions under Pressure (Facing Bet)
        if action == PokerAction.CALL and current_bet_to_call > 0.0:
            pot_odds_ratio = current_bet_to_call / max(1.0, pot_size + current_bet_to_call)
            deliberation = 2.4 + (pot_odds_ratio * 3.5)
            if street in ["turn", "river"]:
                deliberation += 1.2
            if preset in ["fast", "blitz", "speed"]:
                deliberation *= 0.7
            elif preset in ["deep", "deep_thinking"]:
                deliberation *= 1.3
            return max(0.8, round(deliberation + random.gauss(0, 0.45), 2))

        # 4. Bet / Raise / All-In Sizing Calculations
        if action in [PokerAction.BET, PokerAction.RAISE, PokerAction.ALL_IN]:
            if action == PokerAction.ALL_IN:
                base = random.uniform(4.5, 8.5)
            else:
                base = random.uniform(2.2, 5.0)
            if street in ["turn", "river"]:
                base += 1.0
            if preset in ["fast", "blitz", "speed"]:
                base *= 0.7
            return max(0.9, round(base + random.gauss(0, 0.5), 2))

        return max(0.5, round(random.uniform(1.2, 2.8) + random.gauss(0, 0.3), 2))

    @staticmethod
    def generate_bezier_points(
        p0: Tuple[float, float],
        p3: Tuple[float, float],
        num_steps: int = 15
    ) -> List[Tuple[float, float]]:
        """
        Generates smooth cubic Bézier trajectory with human acceleration and ease-out.
        """
        x0, y0 = p0
        x3, y3 = p3
        dx = x3 - x0
        dy = y3 - y0
        dist = math.hypot(dx, dy)

        if dist < 1.0:
            return [p3]

        nx = -dy / dist
        ny = dx / dist

        arc = random.uniform(-0.25, 0.25) * min(dist, 160.0)
        p1 = (
            x0 + dx * random.uniform(0.2, 0.4) + nx * arc + random.gauss(0, 2.0),
            y0 + dy * random.uniform(0.2, 0.4) + ny * arc + random.gauss(0, 2.0)
        )
        p2 = (
            x0 + dx * random.uniform(0.6, 0.8) + nx * (arc * 0.7) + random.gauss(0, 2.0),
            y0 + dy * random.uniform(0.6, 0.8) + ny * (arc * 0.7) + random.gauss(0, 2.0)
        )

        points = []
        for i in range(1, num_steps + 1):
            t_linear = i / float(num_steps)
            t = 3 * (t_linear ** 2) - 2 * (t_linear ** 3)

            omt = 1.0 - t
            bx = (omt ** 3) * x0 + 3 * (omt ** 2) * t * p1[0] + 3 * omt * (t ** 2) * p2[0] + (t ** 3) * x3
            by = (omt ** 3) * y0 + 3 * (omt ** 2) * t * p1[1] + 3 * omt * (t ** 2) * p2[1] + (t ** 3) * y3
            points.append((bx, by))

        if random.random() < 0.35 and dist > 35:
            points.insert(-1, (x3 + random.uniform(-3.0, 3.0), y3 + random.uniform(-3.0, 3.0)))

        return points


class PokerStrategy(str, Enum):
    AI_ALL_MODELS_HYBRID = "ai_all_models_hybrid"
    AI_DEEPSEEK_REASONING = "ai_deepseek_reasoning"
    AI_VISION_VLM = "ai_vision_vlm"
    AI_ADAPTIVE = "ai_adaptive"
    GTO_BALANCED = "gto_balanced"
    TIGHT_AGGRESSIVE = "tight_aggressive"
    LOOSE_AGGRESSIVE = "loose_aggressive"


@dataclass
class PokerGameState:
    my_cards: List[str]                             # e.g. ["Ah", "Kd"]
    community_cards: List[str] = field(default_factory=list) # e.g. ["Qs", "Jd", "10c"]
    pot_size: float = 0.0                          # Current pot in chips/cents
    current_bet_to_call: float = 0.0               # Amount required to call
    my_stack: float = 100.0                        # My remaining chip stack
    position: str = "button"                       # "button", "cutoff", "small_blind", "big_blind", "early", "middle"
    num_opponents: int = 1                         # Number of active players in hand
    big_blind_size: float = 2.0                    # Reference big blind size


@dataclass
class PokerDecisionResult:
    action: PokerAction
    bet_amount: float
    equity: float
    pot_odds: float
    expected_value: float
    current_hand_rank: Optional[str] = None
    reasoning: str = ""
    confidence: float = 0.95


class PokerSolver:
    """
    Autonomous Texas Hold'em Game Theory & Mathematical Decision Engine.
    Combines Multimodal Vision AI, DeepSeek-R1 CoT Reasoning, Monte Carlo Equity Simulation,
    Pot-Odds EV Calculation, and GTO Aggressive Heuristics.
    """

    def __init__(self, strategy: PokerStrategy = PokerStrategy.AI_ALL_MODELS_HYBRID):
        self.strategy = strategy

    @staticmethod
    def classify_preflop_tier(hole_cards: List[str]) -> Tuple[int, str]:
        """
        Classifies 2 hole cards into GTO Hand Strength Tiers (1 = Monster/Premium to 5 = Trash).
        Returns (tier_number, hand_description).
        """
        if not hole_cards or len(hole_cards) < 2:
            return 5, "Unknown"
        c1 = PokerCard.from_str(hole_cards[0])
        c2 = PokerCard.from_str(hole_cards[1])
        r1, r2 = max(c1.rank, c2.rank), min(c1.rank, c2.rank)
        is_suited = (c1.suit.lower() == c2.suit.lower())
        is_pair = (r1 == r2)

        def r_to_c(r: int) -> str:
            m = {14: 'A', 13: 'K', 12: 'Q', 11: 'J', 10: 'T'}
            return m.get(r, str(r))

        # Tier 1: Monster Hands (AA, KK, QQ, AKs, AKo)
        if is_pair and r1 >= 12:
            return 1, f"Pocket {r_to_c(r1)}'s (Premium Monster)"
        if r1 == 14 and r2 == 13:
            return 1, f"Ace-King {'Suited' if is_suited else 'Offsuit'} (Big Slick)"

        # Tier 2: Very Strong Hands (JJ, TT, 99, AQs, AQo, AJs, KQs)
        if is_pair and r1 >= 9:
            return 2, f"Pocket {r_to_c(r1)}'s (Strong Pair)"
        if r1 == 14 and r2 == 12:
            return 2, f"Ace-Queen {'Suited' if is_suited else 'Offsuit'}"
        if r1 == 14 and r2 == 11 and is_suited:
            return 2, "Ace-Jack Suited"
        if r1 == 13 and r2 == 12 and is_suited:
            return 2, "King-Queen Suited"

        # Tier 3: Solid Playable Hands (88, 77, 66, ATs, ATo, KJs, KQo, QJs, JTs)
        if is_pair and r1 >= 6:
            return 3, f"Pocket {r_to_c(r1)}'s (Middle Pair)"
        if r1 == 14 and r2 >= 10:
            return 3, f"Ace-{r_to_c(r2)} {'Suited' if is_suited else 'Offsuit'}"
        if r1 == 13 and r2 >= 11:
            return 3, f"King-{r_to_c(r2)} {'Suited' if is_suited else 'Offsuit'}"
        if r1 == 12 and r2 == 11:
            return 3, f"Queen-Jack {'Suited' if is_suited else 'Offsuit'}"
        if r1 == 11 and r2 == 10:
            return 3, f"Jack-Ten {'Suited' if is_suited else 'Offsuit'}"

        # Tier 4: Speculative / Positional Hands (55-22, Suited Connectors, Suited Aces)
        if is_pair:
            return 4, f"Pocket {r_to_c(r1)}'s (Small Pair)"
        if is_suited and (r1 == 14 or (r1 - r2 == 1 and r2 >= 5)):
            return 4, f"Suited Connector / Speculative Ace ({r_to_c(r1)}{r_to_c(r2)}s)"

        return 5, f"Unconnected High-Card ({r_to_c(r1)}{r_to_c(r2)})"

    def decide_action(
        self,
        state: PokerGameState,
        strategy: Optional[PokerStrategy] = None,
        iterations: int = 3000
    ) -> PokerDecisionResult:
        """
        Calculates mathematical Hand Equity and chooses the optimal GTO action.
        Properly raises, bets, 3-bets, and calls across all table sizes.
        """
        strat = strategy or self.strategy
        if not state.my_cards or len(state.my_cards) < 2:
            return PokerDecisionResult(
                action=PokerAction.CHECK if state.current_bet_to_call <= 0.0 else PokerAction.FOLD,
                bet_amount=0.0,
                equity=0.0,
                pot_odds=0.0,
                expected_value=0.0,
                reasoning="No valid hole cards detected."
            )

        # 1. Calculate Hand Equity via Fast Monte Carlo (capped at 800 iterations for sub-20ms real-time responsiveness)
        sim_n = min(800, max(200, iterations))
        eq_res = PokerHandEvaluator.calculate_equity_monte_carlo(
            my_hole_cards=state.my_cards[:2],
            community_cards=state.community_cards,
            num_opponents=max(1, state.num_opponents),
            iterations=sim_n
        )
        equity = eq_res["equity"]

        # Current made hand ranking
        all_known = [PokerCard.from_str(c) for c in (state.my_cards[:2] + state.community_cards)]
        current_hand_label = "Pre-Flop (Unmade)"
        rank = None
        if len(all_known) >= 5:
            rank, _ = PokerHandEvaluator.evaluate_7cards(all_known)
            current_hand_label = rank.label

        # 2. Multi-Way Relative Equity Analysis
        num_players = max(2, state.num_opponents + 1)
        fair_share_equity = 1.0 / float(num_players)
        rel_advantage = equity / fair_share_equity if fair_share_equity > 0 else 1.0

        # Pot Odds & EV
        call_amt = max(0.0, state.current_bet_to_call)
        pot = max(0.0, state.pot_size)
        total_pot_after_call = pot + call_amt
        pot_odds = (call_amt / total_pot_after_call) if total_pot_after_call > 0 and call_amt > 0 else 0.0
        expected_value = (equity * total_pot_after_call) - call_amt

        # Classify Street and Pre-flop Strength
        street = "preflop" if len(state.community_cards) == 0 else ("flop" if len(state.community_cards) == 3 else ("turn" if len(state.community_cards) == 4 else "river"))
        preflop_tier, preflop_desc = self.classify_preflop_tier(state.my_cards)

        action = PokerAction.CHECK if call_amt <= 0.0 else PokerAction.FOLD
        bet_size = 0.0
        reason = ""

        # --- A. PRE-FLOP DECISION MATRIX ---
        if street == "preflop":
            if preflop_tier == 1: # AA, KK, QQ, AK
                if call_amt <= 0.0:
                    action = PokerAction.BET
                    bet_size = min(state.my_stack, max(state.big_blind_size * 3.5, round(pot * 0.75, 1)))
                    reason = f"Monster Hand: {preflop_desc} ({round(equity*100, 1)}% Eq, {round(rel_advantage*100)}% of fair share). Open-Raising for value."
                else:
                    if state.my_stack <= call_amt * 3.0:
                        action = PokerAction.ALL_IN
                        bet_size = state.my_stack
                        reason = f"Monster Hand: {preflop_desc} ({round(equity*100, 1)}% Eq). Jamming All-In."
                    else:
                        action = PokerAction.RAISE
                        bet_size = min(state.my_stack, max(call_amt * 3.0, round(pot * 0.85, 1)))
                        reason = f"Monster Hand: {preflop_desc} ({round(equity*100, 1)}% Eq). 3-Bet Re-Raising for value."

            elif preflop_tier == 2: # JJ, TT, 99, AQ, AJs, KQs
                if call_amt <= 0.0:
                    action = PokerAction.BET
                    bet_size = min(state.my_stack, max(state.big_blind_size * 3.0, round(pot * 0.66, 1)))
                    reason = f"Strong Premium: {preflop_desc} ({round(equity*100, 1)}% Eq). Open-Raising 3x BB."
                else:
                    if call_amt <= state.big_blind_size * 4.0:
                        action = PokerAction.RAISE if (strat in [PokerStrategy.LOOSE_AGGRESSIVE, PokerStrategy.AI_ALL_MODELS_HYBRID] and random.random() < 0.65) else PokerAction.CALL
                        bet_size = min(state.my_stack, call_amt * 2.5 if action == PokerAction.RAISE else call_amt)
                        reason = f"Very Strong Hand: {preflop_desc} ({round(equity*100, 1)}% Eq). {'3-Bet Raising' if action == PokerAction.RAISE else 'Calling in position'}."
                    else:
                        action = PokerAction.CALL
                        bet_size = min(state.my_stack, call_amt)
                        reason = f"Strong Hand: {preflop_desc}. Calling bet ({round(equity*100, 1)}% Eq)."

            elif preflop_tier == 3: # 88-66, AT+, KJ+, QJ, JT
                if call_amt <= 0.0:
                    action = PokerAction.BET if random.random() < 0.70 else PokerAction.CHECK
                    bet_size = min(state.my_stack, max(state.big_blind_size * 2.5, round(pot * 0.5, 1))) if action == PokerAction.BET else 0.0
                    reason = f"Solid Hand: {preflop_desc} ({round(equity*100, 1)}% Eq). {'Opening pot' if action == PokerAction.BET else 'Checking'}."
                else:
                    if expected_value > 0 or equity >= pot_odds:
                        action = PokerAction.CALL
                        bet_size = min(state.my_stack, call_amt)
                        reason = f"Playable Hand: {preflop_desc}. Profitable call (EV +{round(expected_value, 2)})."
                    else:
                        action = PokerAction.FOLD
                        bet_size = 0.0
                        reason = f"Fold: {preflop_desc} facing large bet without odds."

            elif preflop_tier == 4: # Small pairs, Suited connectors
                if call_amt <= 0.0:
                    action = PokerAction.BET if (strat in [PokerStrategy.LOOSE_AGGRESSIVE, PokerStrategy.AI_ALL_MODELS_HYBRID] and random.random() < 0.45) else PokerAction.CHECK
                    bet_size = min(state.my_stack, max(state.big_blind_size * 2.2, round(pot * 0.4, 1))) if action == PokerAction.BET else 0.0
                    reason = f"Speculative Hand: {preflop_desc} ({round(equity*100, 1)}% Eq)."
                else:
                    if call_amt <= state.big_blind_size * 2.0 and total_pot_after_call >= call_amt * 4.0:
                        action = PokerAction.CALL
                        bet_size = min(state.my_stack, call_amt)
                        reason = f"Implied Odds Call: {preflop_desc} hunting sets/draws."
                    else:
                        action = PokerAction.FOLD
                        reason = f"Fold: {preflop_desc} lacking implied odds."

            else: # Tier 5 Trash
                if call_amt <= 0.0:
                    action = PokerAction.CHECK
                    reason = f"Trash Hand ({preflop_desc}). Checking for free card."
                else:
                    action = PokerAction.FOLD
                    reason = f"Fold: Unfavorable trash hand ({preflop_desc}) vs bet."

        # --- B. POST-FLOP DECISION MATRIX (Flop / Turn / River) ---
        else:
            if call_amt <= 0.0: # Free check or open bet
                if rel_advantage >= 1.55 or (all_known and rank and rank >= HandRank.TWO_PAIR):
                    # Monster Made Hand: Heavy Value Bet (66% - 85% Pot)
                    action = PokerAction.BET
                    bet_size = min(state.my_stack, max(state.big_blind_size, round(pot * 0.70, 1)))
                    reason = f"Strong Value Made Hand: {current_hand_label} ({round(equity*100, 1)}% Eq, Rel-Adv {round(rel_advantage, 2)}x). Value betting 70% pot."
                elif rel_advantage >= 1.20 or (all_known and rank and rank == HandRank.ONE_PAIR):
                    # Medium Value / Top Pair / Flop C-Bet (45% - 55% Pot)
                    action = PokerAction.BET
                    bet_size = min(state.my_stack, max(state.big_blind_size, round(pot * 0.50, 1)))
                    reason = f"Continuation / Value Bet: {current_hand_label} ({round(equity*100, 1)}% Eq). Betting 50% pot."
                elif rel_advantage >= 1.05 and (strat in [PokerStrategy.LOOSE_AGGRESSIVE, PokerStrategy.AI_ALL_MODELS_HYBRID] or street == "flop"):
                    # Light Probe / Semi-Bluff C-Bet (33% Pot)
                    action = PokerAction.BET
                    bet_size = min(state.my_stack, max(state.big_blind_size, round(pot * 0.33, 1)))
                    reason = f"Probe / Semi-Bluff C-Bet ({round(equity*100, 1)}% Eq, {street.capitalize()})."
                else:
                    action = PokerAction.CHECK
                    reason = f"Checking behind for pot control / showdown ({current_hand_label}, {round(equity*100, 1)}% Eq)."

            else: # Facing Bet / Raise Post-flop
                if rel_advantage >= 1.80 or (all_known and rank and rank >= HandRank.THREE_OF_A_KIND):
                    # Dominant Made Hand: Raise / 3-Bet / All-In
                    if state.my_stack <= call_amt * 2.5:
                        action = PokerAction.ALL_IN
                        bet_size = state.my_stack
                        reason = f"Dominant Monster: {current_hand_label} ({round(equity*100, 1)}% Eq). Shoving All-In."
                    else:
                        action = PokerAction.RAISE
                        bet_size = min(state.my_stack, max(call_amt * 2.8, round(pot * 0.80, 1)))
                        reason = f"Dominant Made Hand: {current_hand_label} ({round(equity*100, 1)}% Eq). Raising for value."
                elif rel_advantage >= 1.35 or expected_value > 0 or equity >= pot_odds:
                    # Profitable Call
                    action = PokerAction.CALL
                    bet_size = min(state.my_stack, call_amt)
                    reason = f"Profitable Call ({current_hand_label}, Eq {round(equity*100, 1)}% >= Odds {round(pot_odds*100, 1)}%, EV +{round(expected_value, 2)})."
                elif (strat in [PokerStrategy.LOOSE_AGGRESSIVE, PokerStrategy.AI_ALL_MODELS_HYBRID]) and street == "flop" and equity >= fair_share_equity * 1.1:
                    # Float / Semi-Bluff Raise
                    action = PokerAction.RAISE
                    bet_size = min(state.my_stack, call_amt * 2.2)
                    reason = f"Semi-Bluff Float with draw potential on {street.capitalize()} ({round(equity*100, 1)}% Eq)."
                else:
                    action = PokerAction.FOLD
                    reason = f"Fold: {current_hand_label} (Eq {round(equity*100, 1)}% < Odds {round(pot_odds*100, 1)}%, EV {round(expected_value, 2)})."

        return PokerDecisionResult(
            action=action,
            bet_amount=bet_size,
            equity=equity,
            pot_odds=pot_odds,
            expected_value=round(expected_value, 2),
            current_hand_rank=current_hand_label,
            reasoning=reason,
            confidence=0.94
        )

    async def decide_with_ai_ensemble(
        self,
        state: PokerGameState,
        page: Optional[Any] = None,
        strategy: Optional[PokerStrategy] = None,
        ai_model: Optional[str] = "auto",
        iterations: int = 3000
    ) -> PokerDecisionResult:
        """
        Omniscient AI All-Models Hybrid Decision Engine:
        1. Resolves Hybrid Swarm / Custom Group roles (Vision, Reasoning, Strategy).
        2. Multimodal Vision VLM perceives live table screenshot & DOM.
        3. Monte Carlo Engine simulates thousands of hand combinations to compute exact mathematical Equity & Pot Odds.
        4. Strategic Reasoning Model (DeepSeek-R1 / Qwen2.5 / Gemini / Swarm) analyzes ranges, board texture, and GTO equilibrium.
        5. Applies Grandmaster Aggression Guard to prevent under-betting on monster hands.
        """
        strat = strategy or self.strategy

        # 0. Resolve Hybrid Swarm Roles and Multi-Task Configuration
        target_vision_model = "qwen2.5vl:3b"
        target_reasoning_model = ai_model or "auto"
        swarm_display_name = ai_model or "AI Ensemble"
        custom_system_prompt = None
        custom_vision_prompt = None
        sim_iterations = iterations
        try:
            from engine.ai_model_manager import AIModelManager
            ai_mgr = AIModelManager.get_instance()
            if ai_model:
                roles = ai_mgr.get_hybrid_roles(ai_model)
                target_vision_model = roles.get("vision_model") or roles.get("heavy_vision_model") or target_vision_model
                r_cand = roles.get("reasoning_model") or roles.get("strategy_model") or roles.get("text_model")
                if r_cand:
                    target_reasoning_model = r_cand

                from engine.ai_hybrid_groups_manager import AIHybridGroupsManager
                hg_mgr = AIHybridGroupsManager.get_instance()
                grp = hg_mgr.get_group(ai_model)
                if grp:
                    swarm_display_name = grp.get("name", ai_model)
                    poker_task = hg_mgr.get_group_task_config(ai_model, "poker")
                    if poker_task:
                        if poker_task.get("vision_ocr_role") and roles.get(poker_task["vision_ocr_role"]):
                            target_vision_model = roles[poker_task["vision_ocr_role"]]
                        if poker_task.get("reasoning_role") and roles.get(poker_task["reasoning_role"]):
                            target_reasoning_model = roles[poker_task["reasoning_role"]]
                        custom_system_prompt = poker_task.get("custom_gto_prompt")
                        custom_vision_prompt = poker_task.get("custom_vision_prompt")
                        if poker_task.get("equity_eval_iterations"):
                            try:
                                sim_iterations = int(poker_task["equity_eval_iterations"])
                            except Exception:
                                pass
        except Exception:
            pass

        # 1. State Refinement via Vision / DOM if page is active and cards need extraction
        if page and (not state.my_cards or len(state.my_cards) < 2):
            try:
                extracted = await PokerSolver.extract_state_from_page(page, vision_model=target_vision_model, custom_prompt=custom_vision_prompt)
                if extracted and len(extracted.my_cards) >= 2:
                    state.my_cards = extracted.my_cards
                    if extracted.community_cards:
                        state.community_cards = extracted.community_cards
                    if extracted.pot_size > 0:
                        state.pot_size = extracted.pot_size
                    if extracted.current_bet_to_call > 0:
                        state.current_bet_to_call = extracted.current_bet_to_call
            except Exception as ex_ext:
                logger.warning(f"AI Vision state extraction warning: {ex_ext}")

        # 2. Mathematical GTO Baseline Calculation
        base_decision = self.decide_action(state, strategy=strat, iterations=sim_iterations)
        if not state.my_cards or len(state.my_cards) < 2:
            return base_decision

        # 3. DeepSeek-R1 / Hybrid Swarm Strategic Reasoning
        try:
            from engine.ai_model_manager import AIModelManager
            ai_mgr = AIModelManager.get_instance()

            target_model = target_reasoning_model
            if target_model in ["auto", "default", "50/50_smart_hybrid", "ai_hybrid_ensemble"]:
                installed = ai_mgr.get_installed_model_ids_sync()
                if any("deepseek-r1" in m for m in installed):
                    target_model = next(m for m in installed if "deepseek-r1" in m)
                elif any("qwen2.5:7b" in m or "qwen2.5:3b" in m or "qwen2.5:1.5b" in m for m in installed):
                    target_model = next(m for m in installed if "qwen2.5" in m)
                else:
                    target_model = "auto"

            street = "Pre-Flop" if len(state.community_cards) == 0 else ("Flop" if len(state.community_cards) == 3 else ("Turn" if len(state.community_cards) == 4 else "River"))
            pre_tier, _ = self.classify_preflop_tier(state.my_cards)

            system_prompt = custom_system_prompt or (
                "You are an elite Texas Hold'em Poker AI Grandmaster and Game Theory Optimal (GTO) Solver. "
                "You play aggressively: Open-Raise and 3-Bet with Tier-1 and Tier-2 hands (AA, KK, QQ, AK, AQ, High Pairs), "
                "value bet made hands, and C-bet in position. Never passivity-check monster hands. "
                "Output ONLY a valid JSON object matching the required schema without any markdown wrapping or preamble."
            )

            prompt = (
                f"### LIVE POKER TABLE SITUATION ({street}):\n"
                f"- Hero Hole Cards: {state.my_cards} (GTO Tier: {pre_tier})\n"
                f"- Community Board: {state.community_cards if state.community_cards else 'None (Pre-Flop)'}\n"
                f"- Made Hand Rank: {base_decision.current_hand_rank}\n"
                f"- Mathematical Equity: {round(base_decision.equity * 100, 1)}%\n"
                f"- Recommended GTO Action: {base_decision.action.value.upper()} (Sizing: {base_decision.bet_amount})\n"
                f"- Current Pot: {state.pot_size} chips | Bet to Call: {state.current_bet_to_call} chips\n"
                f"- Pot Odds: {round(base_decision.pot_odds * 100, 1)}% | Expected Value (EV): {base_decision.expected_value}\n"
                f"- Table Position: {state.position} | Active Opponents: {state.num_opponents}\n\n"
                "### TASK:\n"
                "Confirm or refine the optimal GTO action ('fold', 'check', 'call', 'bet', 'raise', 'all_in') and exact sizing.\n"
                "Return ONLY valid JSON:\n"
                "{\n"
                f'  "action": "{base_decision.action.value}",\n'
                f'  "bet_amount": {base_decision.bet_amount},\n'
                '  "reasoning": "<1-sentence Grandmaster rationale explaining why this action maximizes EV>",\n'
                '  "confidence": 0.95\n'
                "}"
            )

            raw_ai = await ai_mgr.generate_response(
                prompt=prompt,
                system_prompt=system_prompt,
                model_name=target_model,
                json_mode=True,
                operation="AI Poker Grandmaster Reasoning"
            )

            if raw_ai:
                m = re.search(r"\{.*\}", raw_ai, re.DOTALL)
                if m:
                    data = json.loads(m.group(0))
                    raw_act = (data.get("action") or "").strip().lower()
                    act_map = {
                        "fold": PokerAction.FOLD,
                        "check": PokerAction.CHECK,
                        "call": PokerAction.CALL,
                        "bet": PokerAction.BET,
                        "raise": PokerAction.RAISE,
                        "all_in": PokerAction.ALL_IN,
                        "allin": PokerAction.ALL_IN
                    }
                    if raw_act in act_map:
                        parsed_act = act_map[raw_act]

                        # Grandmaster Aggression Guard: If base mathematical GTO says BET/RAISE with monster hand, do NOT allow AI to weakly check
                        if base_decision.action in [PokerAction.BET, PokerAction.RAISE, PokerAction.ALL_IN] and pre_tier in [1, 2]:
                            parsed_act = base_decision.action
                            parsed_amt = base_decision.bet_amount
                        else:
                            if state.current_bet_to_call <= 0.0 and parsed_act == PokerAction.FOLD:
                                parsed_act = PokerAction.CHECK
                            parsed_amt = float(data.get("bet_amount", base_decision.bet_amount))
                            parsed_amt = min(state.my_stack, max(0.0, parsed_amt))

                        ai_reason = (data.get("reasoning") or "").strip() or base_decision.reasoning
                        conf = float(data.get("confidence", 0.95))

                        return PokerDecisionResult(
                            action=parsed_act,
                            bet_amount=round(parsed_amt, 1),
                            equity=base_decision.equity,
                            pot_odds=base_decision.pot_odds,
                            expected_value=base_decision.expected_value,
                            current_hand_rank=base_decision.current_hand_rank,
                            reasoning=f"🧠 [{target_model.upper()}] {ai_reason}",
                            confidence=conf
                        )
        except Exception as ex_ai:
            logger.warning(f"AI Poker reasoning fallback to GTO: {ex_ai}")

        return base_decision

    @staticmethod
    def get_dom_extraction_script() -> str:
        """
        JavaScript payload to inject into browser page to automatically parse
        cards, pot, action buttons, and current bets from HTML5 / Web Poker clients.
        """
        return """
        (() => {
            let myCards = [];
            let commCards = [];
            let potSize = 0.0;
            let betToCall = 0.0;
            let visibleActions = [];

            // Helper to clean card notation (e.g. '10h', 'As', 'Kd')
            const normalizeCard = (str) => {
                if (!str) return null;
                const m = str.trim().toLowerCase().match(/([2-9tjqka]|10)([hdcs])/i);
                if (m) return (m[1] === 't' ? '10' : m[1].toUpperCase()) + m[2].toLowerCase();
                return null;
            };

            // 1. Comprehensive DOM Card Element Search
            const cardSelectors = [
                '[class*="card"]', '[class*="Card"]', '[data-card]', '[data-rank]',
                '.playing-card', '.table-player-cards .card', '.community-cards .card',
                'img[src*="card"]', 'img[alt*="card"]', 'svg[class*="card"]'
            ];
            
            const cardElements = document.querySelectorAll(cardSelectors.join(', '));
            cardElements.forEach(el => {
                let cardVal = null;
                // Check class name
                const cls = (el.className || '').toString();
                const mCls = cls.match(/(?:card[-_]?)([2-9tjqka]|10)([hdcs])/i);
                if (mCls) cardVal = normalizeCard(mCls[1] + mCls[2]);

                // Check dataset
                if (!cardVal && el.dataset) {
                    if (el.dataset.card) cardVal = normalizeCard(el.dataset.card);
                    else if (el.dataset.rank && el.dataset.suit) cardVal = normalizeCard(el.dataset.rank + el.dataset.suit);
                }

                // Check alt or src
                if (!cardVal && el.tagName === 'IMG') {
                    const src = el.src || el.alt || '';
                    const mSrc = src.match(/([2-9tjqka]|10)_?(?:of_)?([hdcs]|hearts|diamonds|clubs|spades)/i);
                    if (mSrc) {
                        const s = mSrc[2][0].toLowerCase();
                        cardVal = normalizeCard(mSrc[1] + s);
                    }
                }

                if (cardVal) {
                    const isHero = el.closest('.my-hand, .hero, .user-cards, [id*="hero"], [id*="my_hand"], .table-player-you, .player-self, .bottom-player');
                    if (isHero) {
                        if (!myCards.includes(cardVal)) myCards.push(cardVal);
                    } else {
                        if (!commCards.includes(cardVal) && !myCards.includes(cardVal)) commCards.push(cardVal);
                    }
                }
            });

            // 2. Action Buttons & Turn Detection
            const btnSelectors = [
                'button:has-text("Check")', 'button:has-text("Call")', 'button:has-text("Fold")',
                'button:has-text("Raise")', 'button:has-text("Bet")', 'button:has-text("All-In")',
                '[data-action]', '.action-button', '.btn-action', '.btn-check', '.btn-call',
                '.btn-fold', '.btn-raise', '.action-btn', '.check-button', '.call-button'
            ];
            
            const allBtns = document.querySelectorAll('button, .action-button, [data-action], .btn-action');
            allBtns.forEach(b => {
                const txt = (b.innerText || b.getAttribute('data-action') || b.className || '').toLowerCase();
                if (b.offsetParent !== null) { // visible
                    if (txt.includes('fold')) visibleActions.push('fold');
                    if (txt.includes('check')) visibleActions.push('check');
                    if (txt.includes('call')) visibleActions.push('call');
                    if (txt.includes('raise') || txt.includes('bet')) visibleActions.push('raise');
                    if (txt.includes('all-in') || txt.includes('all in')) visibleActions.push('all_in');
                }
            });

            // 3. Pot Text Parsing
            const potEls = document.querySelectorAll('[class*="pot"], [id*="pot"], .table-pot, .pot-size');
            potEls.forEach(el => {
                const txt = el.innerText || '';
                const numMatch = txt.replace(/[,]/g, '').match(/\\$?(\\d+(?:\\.\\d+)?)/);
                if (numMatch && !potSize) {
                    potSize = parseFloat(numMatch[1]);
                }
            });

            // 4. Canvas dimensions if present
            const canvasEl = document.querySelector('canvas');
            const canvasRect = canvasEl ? canvasEl.getBoundingClientRect() : null;

            return {
                my_cards: myCards,
                community_cards: commCards,
                pot_size: potSize || 20.0,
                current_bet_to_call: betToCall,
                visible_actions: visibleActions,
                is_my_turn: visibleActions.length > 0,
                has_canvas: canvasEl !== null,
                canvas_rect: canvasRect ? { x: canvasRect.x, y: canvasRect.y, width: canvasRect.width, height: canvasRect.height } : null
            };
        })();
        """

    @staticmethod
    async def extract_state_from_page(page: Any, vision_model: Optional[str] = None, custom_prompt: Optional[str] = None) -> Optional[PokerGameState]:
        """
        Extracts live Poker Game State from active page using DOM parsing and Vision AI fallback.
        """
        if not page:
            return None

        try:
            # 1. Try DOM parsing
            dom_res = await page.evaluate(PokerSolver.get_dom_extraction_script())
            if dom_res and len(dom_res.get("my_cards", [])) >= 2:
                return PokerGameState(
                    my_cards=dom_res["my_cards"],
                    community_cards=dom_res.get("community_cards", []),
                    pot_size=float(dom_res.get("pot_size", 20.0)),
                    current_bet_to_call=float(dom_res.get("current_bet_to_call", 0.0))
                )

            # 2. If canvas/empty DOM, use Vision VLM to extract cards and pot from screenshot
            if hasattr(page, "screenshot"):
                from engine.ai_model_manager import AIModelManager
                ai_mgr = AIModelManager.get_instance()
                screenshot_bytes = await page.screenshot()

                prompt = custom_prompt or (
                    "You are a professional Poker Assistant. Analyze this live poker table screenshot:\n"
                    "1. Find hero's 2 hole cards at the bottom of the table (e.g. ['Ah', 'Kd'] or ['10s', '8c']).\n"
                    "2. Find community cards in the center of table (flop, turn, river).\n"
                    "3. Read total pot size (number) and current bet to call.\n"
                    "4. Check if action buttons (Fold, Check, Call, Raise) are currently visible and active.\n\n"
                    "Output ONLY valid JSON:\n"
                    "{\n"
                    '  "my_cards": ["Ah", "Kd"],\n'
                    '  "community_cards": [],\n'
                    '  "pot_size": 20.0,\n'
                    '  "current_bet_to_call": 0.0,\n'
                    '  "is_my_turn": true\n'
                    "}"
                )

                raw_json = await ai_mgr.generate_vision_response(
                    prompt=prompt,
                    image_data=screenshot_bytes,
                    model_name=vision_model or "qwen2.5vl:3b",
                    operation="AI Poker Vision OCR"
                )

                if raw_json:
                    import json
                    m = re.search(r"\{.*\}", raw_json, re.DOTALL)
                    if m:
                        try:
                            data = json.loads(m.group(0))
                            hole = data.get("my_cards", [])
                            if len(hole) >= 2:
                                return PokerGameState(
                                    my_cards=hole,
                                    community_cards=data.get("community_cards", []),
                                    pot_size=float(data.get("pot_size", 20.0)),
                                    current_bet_to_call=float(data.get("current_bet_to_call", 0.0))
                                )
                        except Exception:
                            pass

                    # Fallback Regex card matcher (e.g. ['Ah', 'Kd'] or Ah Kd in text)
                    card_pat = re.compile(r"\b(10|[2-9TJQKA])[shdc]\b", re.IGNORECASE)
                    found_cards = card_pat.findall(raw_json)
                    if len(found_cards) >= 2:
                        return PokerGameState(
                            my_cards=found_cards[:2],
                            community_cards=found_cards[2:7],
                            pot_size=20.0,
                            current_bet_to_call=0.0
                        )
        except Exception as ex:
            logger.warning(f"Poker state extraction note: {ex}")

        return None

    @staticmethod
    async def execute_action_on_page(
        page: Any,
        action: PokerAction,
        bet_amount: float = 0.0,
        anti_ban: bool = True,
        human_delay: bool = True,
        speed_preset: str = "balanced",
        community_cards_count: int = 0,
        pot_size: float = 20.0,
        current_bet_to_call: float = 0.0,
        equity: float = 0.5
    ) -> bool:
        """
        Executes poker action (Fold, Check, Call, Bet, Raise, All-In) on the browser page
        using humanized Bézier mouse trajectories, Gaussian thinking delay, and button jitter
        to prevent platform bot detection.
        """
        if not page:
            return False

        action_name = action.value.lower()
        success = False

        try:
            # 1. Humanized Deliberation & Thinking Delay (Anti-Ban)
            if anti_ban and human_delay:
                thinking_time = PokerAntiBanEngine.calculate_human_thinking_delay(
                    action=action,
                    community_cards_count=community_cards_count,
                    pot_size=pot_size,
                    current_bet_to_call=current_bet_to_call,
                    equity=equity,
                    speed_preset=speed_preset
                )
                logger.info(f"[PokerAntiBan] Humanized thinking delay: {thinking_time:.2f}s (Action: {action.value.upper()}, Speed: {speed_preset})")
                await asyncio.sleep(thinking_time)

            # 2. Tier 0: Check ML Memory Learned Button Geometry
            from engine.game_solvers.poker_ml_memory import PokerMLMemoryManager
            ml_mem = PokerMLMemoryManager.get_instance()
            page_url = getattr(page, "url", "") or ""
            viewport_size = getattr(page, "viewport_size", None) or {"width": 1280, "height": 720}
            vw = float(viewport_size.get("width", 1280))
            vh = float(viewport_size.get("height", 720))

            cached_coords = ml_mem.get_button_coordinates(page_url, vw, vh, action.value)
            if cached_coords and hasattr(page, "mouse"):
                cx, cy, cw, ch = cached_coords
                jitter_x = max(-0.30, min(0.30, random.gauss(0, 0.12))) if anti_ban else 0.0
                jitter_y = max(-0.30, min(0.30, random.gauss(0, 0.12))) if anti_ban else 0.0
                target_x = cx + jitter_x * (cw / 2.0)
                target_y = cy + jitter_y * (ch / 2.0)

                if anti_ban:
                    start_x = target_x + random.uniform(-100, 100)
                    start_y = target_y + random.uniform(40, 150)
                    curve_pts = PokerAntiBanEngine.generate_bezier_points((start_x, start_y), (target_x, target_y), num_steps=14)
                    for pt_x, pt_y in curve_pts:
                        await page.mouse.move(pt_x, pt_y)
                        await asyncio.sleep(random.uniform(0.008, 0.015))
                    await page.mouse.down()
                    await asyncio.sleep(random.uniform(0.04, 0.08))
                    await page.mouse.up()
                else:
                    await page.mouse.click(target_x, target_y)
                success = True
                logger.info(f"[PokerMLMemory] Executed action [{action.value.upper()}] via learned memory geometry ({target_x:.1f}, {target_y:.1f})")

            # 3. Tier 1: Targeted DOM button clicks with Human Bézier Movement & Calibration
            if not success:
                sel_list = []
                if action == PokerAction.FOLD:
                    sel_list = ["button:has-text('Fold')", "[data-action='fold']", ".btn-fold", ".fold-button", "[class*='fold']"]
                elif action == PokerAction.CHECK:
                    sel_list = ["button:has-text('Check')", "[data-action='check']", ".btn-check", ".check-button", "[class*='check']"]
                elif action == PokerAction.CALL:
                    sel_list = ["button:has-text('Call')", "[data-action='call']", ".btn-call", ".call-button", "[class*='call']"]
                elif action in [PokerAction.RAISE, PokerAction.BET]:
                    sel_list = ["button:has-text('Raise')", "button:has-text('Bet')", "[data-action='raise']", ".btn-raise", ".raise-button", "[class*='raise']", "[class*='bet']"]
                elif action == PokerAction.ALL_IN:
                    sel_list = ["button:has-text('All-In')", "button:has-text('All in')", "[data-action='allin']", ".btn-allin", "[class*='allin']"]

                for sel in sel_list:
                    btn = await page.query_selector(sel)
                    if btn:
                        is_visible = await btn.is_visible()
                        if is_visible:
                            box = await btn.bounding_box()
                            if box and hasattr(page, "mouse"):
                                jitter_x = max(-0.35, min(0.35, random.gauss(0, 0.15))) if anti_ban else 0.0
                                jitter_y = max(-0.35, min(0.35, random.gauss(0, 0.15))) if anti_ban else 0.0
                                target_x = box["x"] + box["width"] * (0.5 + jitter_x)
                                target_y = box["y"] + box["height"] * (0.5 + jitter_y)

                                # Learn / calibrate coordinates to ML memory file
                                ml_mem.update_button_coordinates(page_url, vw, vh, action.value, target_x, target_y, box["width"], box["height"])

                                if anti_ban:
                                    start_x = target_x + random.uniform(-150, 150)
                                    start_y = target_y + random.uniform(50, 200)
                                    curve_pts = PokerAntiBanEngine.generate_bezier_points((start_x, start_y), (target_x, target_y), num_steps=random.randint(12, 18))
                                    for pt_x, pt_y in curve_pts:
                                        await page.mouse.move(pt_x, pt_y)
                                        await asyncio.sleep(random.uniform(0.008, 0.016))

                                    await page.mouse.down()
                                    await asyncio.sleep(random.uniform(0.04, 0.08))
                                    await page.mouse.up()
                                else:
                                    await page.mouse.click(target_x, target_y)
                            else:
                                await btn.click()
                            success = True
                            break

            # 4. Tier 2: Canvas Geometry Click (for PlayWSOP, Zynga, Canvas clients) & Calibration
            if not success:
                canvas_info = await page.evaluate("""() => {
                    const c = document.querySelector('canvas');
                    if (!c) return null;
                    const r = c.getBoundingClientRect();
                    return { x: r.x, y: r.y, width: r.width, height: r.height };
                }""")

                if canvas_info and canvas_info.get("width", 0) > 100:
                    cx = float(canvas_info["x"])
                    cy = float(canvas_info["y"])
                    cw = float(canvas_info["width"])
                    ch = float(canvas_info["height"])

                    target_x, target_y = 0.0, cy + (ch * 0.91)
                    if action == PokerAction.FOLD:
                        target_x = cx + (cw * 0.70)
                    elif action in [PokerAction.CHECK, PokerAction.CALL]:
                        target_x = cx + (cw * 0.81)
                    else: # RAISE / BET / ALL-IN
                        target_x = cx + (cw * 0.92)

                    # Learn canvas coordinates to memory
                    ml_mem.update_button_coordinates(page_url, vw, vh, action.value, target_x, target_y, 85.0, 42.0)

                    if hasattr(page, "mouse"):
                        if anti_ban:
                            start_x = target_x + random.uniform(-100, 100)
                            start_y = target_y + random.uniform(40, 150)
                            curve_pts = PokerAntiBanEngine.generate_bezier_points((start_x, start_y), (target_x, target_y), num_steps=14)
                            for pt_x, pt_y in curve_pts:
                                await page.mouse.move(pt_x, pt_y)
                                await asyncio.sleep(random.uniform(0.008, 0.015))
                            await page.mouse.down()
                            await asyncio.sleep(random.uniform(0.04, 0.08))
                            await page.mouse.up()
                        else:
                            await page.mouse.click(target_x, target_y)
                        success = True

            # 5. Tier 3: Universal Poker Keyboard Hotkeys (if click didn't trigger)
            if not success and hasattr(page, "keyboard"):
                if action == PokerAction.FOLD:
                    await page.keyboard.press("f")
                    await page.keyboard.press("1")
                elif action in [PokerAction.CHECK, PokerAction.CALL]:
                    await page.keyboard.press("c")
                    await page.keyboard.press("Space")
                    await page.keyboard.press("2")
                elif action in [PokerAction.RAISE, PokerAction.BET, PokerAction.ALL_IN]:
                    await page.keyboard.press("r")
                    await page.keyboard.press("3")
                    await page.keyboard.press("Enter")

            return True
        except Exception as ex:
            logger.warning(f"Error executing poker action on page: {ex}")
            return False
