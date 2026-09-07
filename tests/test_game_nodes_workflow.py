import unittest
import asyncio
from engine.workflow_engine import (
    WorkflowDAG, WorkflowNode, WorkflowEdge, NodeType,
    WorkflowDAGRunner, WorkflowExecutionState
)


class TestGameNodesWorkflow(unittest.IsolatedAsyncioTestCase):

    async def test_chess_solver_dag_execution(self):
        dag = WorkflowDAG(name="Chess Test DAG")
        n1 = WorkflowNode(id="n1", node_type=NodeType.START, title="Start")
        # Mate in 1 FEN
        n2 = WorkflowNode(
            id="n2",
            node_type=NodeType.CHESS_SOLVER,
            title="Chess Move",
            params={
                "fen": "rnbqkbnr/ppppp2p/5p2/6p1/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 3",
                "depth": 3,
                "auto_move": False,
                "save_to_var": "best_move"
            }
        )
        n3 = WorkflowNode(id="n3", node_type=NodeType.TERMINATE, title="Finish", params={"status": "success"})

        dag.nodes = {"n1": n1, "n2": n2, "n3": n3}
        dag.entry_node_id = "n1"
        dag.add_edge("n1", "n2")
        dag.add_edge("n2", "n3", source_port="out")

        runner = WorkflowDAGRunner(dag)
        success = await runner.execute()

        self.assertTrue(success)
        self.assertEqual(runner.state, WorkflowExecutionState.COMPLETED)
        move_str = runner.variables.get("best_move", "")
        self.assertTrue(isinstance(move_str, str) and len(move_str) >= 4)

    async def test_super_grandmaster_godmode_chess_solver(self):
        from engine.game_solvers.chess_solver import ChessSolver, ChessEngineType
        solver = ChessSolver()

        # 1. Test Opening Book Resolution (Start pos -> 1.e4)
        start_fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -"
        res_book = await solver.solve_best_move_ai(start_fen, engine_type=ChessEngineType.SUPER_GRANDMASTER_GODMODE)
        self.assertEqual(res_book.uci_move, "e2e4")
        self.assertIn("Grandmaster Book", res_book.engine_name)

        # 2. Test Deep Calculation on Tactical/Mate Position
        tactical_fen = "rnbqkbnr/ppppp2p/5p2/6p1/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 3"
        res_tac = await solver.solve_best_move_ai(tactical_fen, engine_type=ChessEngineType.SUPER_GRANDMASTER_GODMODE, depth=16)
        self.assertEqual(res_tac.uci_move, "d1h5")  # Queen to h5 checkmate (Fool's mate)
        self.assertTrue(res_tac.is_mate or "Stockfish" in res_tac.engine_name)

    def test_chess_anti_ban_engine(self):
        from engine.game_solvers.chess_solver import ChessAntiBanEngine
        # Test human thinking delay calculations
        delay_book = ChessAntiBanEngine.calculate_human_thinking_delay("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -", is_book=True, target_elo=2400)
        self.assertGreaterEqual(delay_book, 0.4)
        self.assertLessEqual(delay_book, 4.0)

        delay_sharp = ChessAntiBanEngine.calculate_human_thinking_delay("r1bqk2r/pp2bppp/2n1pn2/2pp4/3P4/2N1PN2/PPP1BPPP/R1BQ1RK1 w kq -", eval_cp=10, target_elo=2400)
        self.assertGreaterEqual(delay_sharp, 0.5)

        # Test Bézier curve generation
        start_pt = (100.0, 100.0)
        end_pt = (400.0, 300.0)
        curve_pts = ChessAntiBanEngine.generate_bezier_points(start_pt, end_pt, num_steps=16)
        self.assertGreater(len(curve_pts), 10)
        self.assertAlmostEqual(curve_pts[-1][0], end_pt[0], delta=5.0)
        self.assertAlmostEqual(curve_pts[-1][1], end_pt[1], delta=5.0)

    async def test_poker_solver_dag_execution_and_branching(self):
        dag = WorkflowDAG(name="Poker Test DAG")
        n1 = WorkflowNode(id="n1", node_type=NodeType.START, title="Start")
        # Royal flush made hand
        n2 = WorkflowNode(
            id="n2",
            node_type=NodeType.POKER_SOLVER,
            title="Poker GTO",
            params={
                "my_cards": ["Ah", "Kh"],
                "community_cards": ["Qh", "Jh", "10h"],
                "pot_size": 50.0,
                "current_bet_to_call": 10.0,
                "strategy": "gto_balanced",
                "auto_click_action": False,
                "save_to_var": "my_poker_decision"
            }
        )
        n_raise = WorkflowNode(id="n_raise", node_type=NodeType.TERMINATE, title="Hand Raised", params={"status": "success"})
        n_fold = WorkflowNode(id="n_fold", node_type=NodeType.TERMINATE, title="Hand Folded", params={"status": "failed"})

        dag.nodes = {"n1": n1, "n2": n2, "n_raise": n_raise, "n_fold": n_fold}
        dag.entry_node_id = "n1"
        dag.add_edge("n1", "n2")
        dag.add_edge("n2", "n_raise", source_port="raise")
        dag.add_edge("n2", "n_raise", source_port="call")
        dag.add_edge("n2", "n_fold", source_port="fold")

        runner = WorkflowDAGRunner(dag)
        success = await runner.execute()

        self.assertTrue(success)
        self.assertEqual(runner.state, WorkflowExecutionState.COMPLETED)
        self.assertIn(runner.variables.get("my_poker_decision"), ["raise", "all_in", "call", "bet"])


    def test_lichess_dom_and_flipped_fen_generation(self):
        from engine.game_solvers.chess_solver import ChessSolver
        # Standard starting position grid (64 squares)
        grid = [
            'r', 'n', 'b', 'q', 'k', 'b', 'n', 'r',
            'p', 'p', 'p', 'p', 'p', 'p', 'p', 'p',
            None, None, None, None, None, None, None, None,
            None, None, None, None, None, None, None, None,
            None, None, None, None, None, None, None, None,
            None, None, None, None, None, None, None, None,
            'P', 'P', 'P', 'P', 'P', 'P', 'P', 'P',
            'R', 'N', 'B', 'Q', 'K', 'B', 'N', 'R'
        ]
        fen = ChessSolver.grid_to_fen(grid, active_color='w')
        self.assertEqual(fen, "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1")

        # Verify JS extraction script contains Lichess Chessground translate regex and flipped handling
        js = ChessSolver.get_dom_extraction_script()
        self.assertIn("cg-board", js)
        self.assertIn("orientation-black", js)
        self.assertIn("translate", js)


if __name__ == "__main__":
    unittest.main()
