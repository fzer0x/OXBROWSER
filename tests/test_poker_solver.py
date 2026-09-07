import unittest
from engine.game_solvers.poker_evaluator import PokerCard, PokerHandEvaluator, HandRank
from engine.game_solvers.poker_solver import PokerSolver, PokerGameState, PokerAction, PokerStrategy


class TestPokerSolver(unittest.TestCase):

    def test_poker_card_parsing(self):
        c1 = PokerCard.from_str("Ah")
        self.assertEqual(c1.rank, 14)
        self.assertEqual(c1.suit, "h")

        c2 = PokerCard.from_str("10s")
        self.assertEqual(c2.rank, 10)
        self.assertEqual(c2.suit, "s")

        c3 = PokerCard.from_str("Td")
        self.assertEqual(c3.rank, 10)
        self.assertEqual(c3.suit, "d")

    def test_hand_rankings_hierarchy(self):
        # Royal Flush vs Four of a Kind
        royal_flush = [PokerCard.from_str(c) for c in ["Ah", "Kh", "Qh", "Jh", "10h"]]
        quads = [PokerCard.from_str(c) for c in ["Ks", "Kh", "Kd", "Kc", "2h"]]
        
        r_rf, _ = PokerHandEvaluator.evaluate_5cards(royal_flush)
        r_quads, _ = PokerHandEvaluator.evaluate_5cards(quads)

        self.assertEqual(r_rf, HandRank.ROYAL_FLUSH)
        self.assertEqual(r_quads, HandRank.FOUR_OF_A_KIND)
        self.assertTrue(r_rf > r_quads)

        # Full House vs Flush
        full_house = [PokerCard.from_str(c) for c in ["8s", "8h", "8d", "2c", "2h"]]
        flush = [PokerCard.from_str(c) for c in ["As", "Js", "8s", "6s", "2s"]]

        r_fh, _ = PokerHandEvaluator.evaluate_5cards(full_house)
        r_fl, _ = PokerHandEvaluator.evaluate_5cards(flush)

        self.assertEqual(r_fh, HandRank.FULL_HOUSE)
        self.assertEqual(r_fl, HandRank.FLUSH)
        self.assertTrue(r_fh > r_fl)

    def test_monte_carlo_pocket_aces_equity(self):
        # Pocket Aces (AA) should have ~85% equity heads-up pre-flop against random hand
        res = PokerHandEvaluator.calculate_equity_monte_carlo(
            my_hole_cards=["Ah", "As"],
            community_cards=[],
            num_opponents=1,
            iterations=1500
        )
        self.assertGreaterEqual(res["equity"], 0.78)
        self.assertLessEqual(res["equity"], 0.92)

    def test_poker_solver_monster_hand_raise_allin(self):
        # Nut Straight on River
        solver = PokerSolver(strategy=PokerStrategy.GTO_BALANCED)
        state = PokerGameState(
            my_cards=["Ah", "Kd"],
            community_cards=["Qh", "Js", "10c", "2d", "3h"],
            pot_size=100.0,
            current_bet_to_call=20.0,
            my_stack=150.0,
            num_opponents=1
        )
        decision = solver.decide_action(state, iterations=1000)
        self.assertIn(decision.action, [PokerAction.RAISE, PokerAction.ALL_IN])
        self.assertGreater(decision.equity, 0.90)
        self.assertGreater(decision.expected_value, 0.0)

    def test_poker_solver_trash_hand_fold(self):
        # 7-2 offsuit facing big raise on Ace-high board
        solver = PokerSolver(strategy=PokerStrategy.TIGHT_AGGRESSIVE)
        state = PokerGameState(
            my_cards=["7h", "2c"],
            community_cards=["Ah", "Kd", "Qs"],
            pot_size=50.0,
            current_bet_to_call=40.0,
            my_stack=200.0,
            num_opponents=2
        )
        decision = solver.decide_action(state, iterations=1000)
        self.assertEqual(decision.action, PokerAction.FOLD)
        self.assertLess(decision.equity, 0.15)

    def test_preflop_ak_and_pairs_open_raising_multiway(self):
        # Ace-King (AK) with 4 opponents in unopened pot -> Must BET/Open-Raise
        solver = PokerSolver(strategy=PokerStrategy.AI_ALL_MODELS_HYBRID)
        state_ak = PokerGameState(
            my_cards=["Ah", "Kd"],
            community_cards=[],
            pot_size=20.0,
            current_bet_to_call=0.0,
            my_stack=200.0,
            num_opponents=4
        )
        decision_ak = solver.decide_action(state_ak, iterations=500)
        self.assertEqual(decision_ak.action, PokerAction.BET)
        self.assertGreaterEqual(decision_ak.bet_amount, 5.0)

        # Pocket Aces (AA) facing a bet with 4 opponents -> Must RAISE / 3-Bet
        state_aa = PokerGameState(
            my_cards=["As", "Ah"],
            community_cards=[],
            pot_size=30.0,
            current_bet_to_call=10.0,
            my_stack=200.0,
            num_opponents=4
        )
        decision_aa = solver.decide_action(state_aa, iterations=500)
        self.assertIn(decision_aa.action, [PokerAction.RAISE, PokerAction.ALL_IN])
        self.assertGreaterEqual(decision_aa.bet_amount, 25.0)

    def test_custom_hybrid_swarm_poker_decision(self):
        import asyncio
        solver = PokerSolver(strategy=PokerStrategy.AI_ALL_MODELS_HYBRID)
        state = PokerGameState(
            my_cards=["Kh", "Kd"],
            community_cards=["Js", "10d", "4c"],
            pot_size=120.0,
            current_bet_to_call=0.0,
            my_stack=300.0,
            num_opponents=2
        )
        # Test passing custom hybrid swarm identifier
        decision = asyncio.run(solver.decide_with_ai_ensemble(state, strategy=PokerStrategy.AI_ALL_MODELS_HYBRID, ai_model="swarm_full_master", iterations=1000))
        self.assertIn(decision.action, [PokerAction.CHECK, PokerAction.BET, PokerAction.RAISE])
        self.assertGreater(decision.equity, 0.65)
        self.assertTrue(len(decision.reasoning) > 0)

    def test_dict_and_symbol_cards_evaluation(self):
        solver = PokerSolver()
        # Test cards passed as dicts (as in workflow node params)
        state = PokerGameState(
            my_cards=["Jc", "7h"],
            community_cards=[{"card_type": "high_card", "value": "Q"}, {"card_type": "high_card", "value": "8"}],
            pot_size=10.5,
            current_bet_to_call=0.0,
            num_opponents=4
        )
        decision = solver.decide_action(state, strategy=PokerStrategy.TIGHT_AGGRESSIVE, iterations=500)
        self.assertIsNotNone(decision)
        self.assertIn(decision.action, [PokerAction.CHECK, PokerAction.BET, PokerAction.FOLD])

    def test_nested_dict_and_container_cards_evaluation(self):
        solver = PokerSolver()
        # Test exact nested dict payload from Loop iteration 10
        raw_board = [{'card_1': {'rank': 'A', 'suit': 'spades'}, 'card_2': {'rank': 'Q', 'suit': 'hearts'}}, {'card_3': {'rank': '4', 'suit': 'diamonds'}}]
        extracted_board = [str(c) for c in PokerCard.extract_cards(raw_board)]
        self.assertEqual(len(extracted_board), 3)
        self.assertIn("As", extracted_board)
        self.assertIn("Qh", extracted_board)
        self.assertIn("4d", extracted_board)

        state = PokerGameState(
            my_cards=[str(c) for c in PokerCard.extract_cards([8, 8])],
            community_cards=extracted_board,
            pot_size=10.5,
            current_bet_to_call=0.0,
            num_opponents=4
        )
        decision = solver.decide_action(state, strategy=PokerStrategy.TIGHT_AGGRESSIVE, iterations=500)
        self.assertIsNotNone(decision)
        self.assertIn(decision.action, [PokerAction.CHECK, PokerAction.BET, PokerAction.FOLD])

    def test_poker_anti_ban_engine(self):
        from engine.game_solvers.poker_solver import PokerAntiBanEngine
        # Preflop fold delay
        delay_fold = PokerAntiBanEngine.calculate_human_thinking_delay(PokerAction.FOLD, community_cards_count=0)
        self.assertGreaterEqual(delay_fold, 0.4)
        self.assertLessEqual(delay_fold, 3.0)

        # High-Stakes All-In river delay
        delay_allin = PokerAntiBanEngine.calculate_human_thinking_delay(PokerAction.ALL_IN, community_cards_count=5)
        self.assertGreaterEqual(delay_allin, 2.5)

        # Bézier curves
        start_pt = (200.0, 500.0)
        end_pt = (800.0, 900.0)
        curve = PokerAntiBanEngine.generate_bezier_points(start_pt, end_pt, num_steps=15)
        self.assertGreater(len(curve), 10)
        self.assertAlmostEqual(curve[-1][0], end_pt[0], delta=5.0)
        self.assertAlmostEqual(curve[-1][1], end_pt[1], delta=5.0)

    def test_poker_ml_memory_manager(self):
        import os
        import tempfile
        from engine.game_solvers.poker_ml_memory import PokerMLMemoryManager
        
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
            tmp_path = tmp.name

        try:
            mem = PokerMLMemoryManager(storage_path=tmp_path)
            
            # 1. Test button geometry calibration
            mem.update_button_coordinates("https://play.playwsop.com/table1", 1920, 1080, "fold", 1344.0, 982.0, 80.0, 40.0)
            coords = mem.get_button_coordinates("https://play.playwsop.com/table1", 1920, 1080, "fold")
            self.assertIsNotNone(coords)
            x, y, w, h = coords
            self.assertAlmostEqual(x, 1344.0, delta=10.0)
            self.assertAlmostEqual(y, 982.0, delta=10.0)

            # Test responsive viewport scaling (e.g. 1280x720)
            scaled_coords = mem.get_button_coordinates("https://play.playwsop.com/table1", 1280, 720, "fold")
            self.assertIsNotNone(scaled_coords)
            sx, sy, _, _ = scaled_coords
            self.assertAlmostEqual(sx, (1344.0 / 1920.0) * 1280.0, delta=10.0)

            # 2. Test technique outcome recording and reinforcement
            mem.record_technique_outcome("flop_cbet_value", "win", 45.0, ev=3.2)
            mem.record_technique_outcome("flop_cbet_value", "win", 30.0, ev=2.8)
            stats = mem.get_learning_stats_summary()
            self.assertIn("flop_cbet_value", stats["techniques"])
            self.assertGreater(stats["techniques"]["flop_cbet_value"]["win_rate"], 0.70)
            
            multiplier = mem.get_technique_aggression_multiplier("flop_cbet_value")
            self.assertGreater(multiplier, 1.0)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


if __name__ == "__main__":
    unittest.main()
