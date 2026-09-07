import unittest
import asyncio
from engine.game_solvers.chess_solver import PureChessBoard, ChessSolver, ChessMoveResult, ChessPlatform


class TestChessSolver(unittest.TestCase):

    def test_board_initialization_and_fen(self):
        start_fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        board = PureChessBoard(start_fen)
        self.assertEqual(board.get_fen(), start_fen)
        self.assertEqual(board.active_color, 'w')
        self.assertEqual(len(board.board), 64)
        self.assertEqual(board.board[0], 'r')
        self.assertEqual(board.board[63], 'R')

    def test_legal_moves_from_start_position(self):
        start_fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        board = PureChessBoard(start_fen)
        moves = board.generate_legal_moves()
        # From starting position, White has 16 pawn moves (8 single, 8 double) + 4 knight moves = 20 moves
        self.assertEqual(len(moves), 20)

    def test_san_to_uci_conversion(self):
        start_fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        board = PureChessBoard(start_fen)
        
        # Test SAN "e4" -> "e2e4"
        self.assertEqual(board.san_to_uci("e4"), "e2e4")
        # Test SAN "Nf3" -> "g1f3"
        self.assertEqual(board.san_to_uci("Nf3"), "g1f3")
        # Test direct UCI "b1c3"
        self.assertEqual(board.san_to_uci("b1c3"), "b1c3")

    def test_solver_detects_fool_mate_in_one(self):
        # Position where White has mate in 1: Queen to h5#
        fen = "rnbqkbnr/ppppp2p/5p2/6p1/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 3"
        solver = ChessSolver()
        res = solver.solve_best_move(fen, depth=3)
        self.assertIsInstance(res, ChessMoveResult)
        self.assertEqual(res.from_square, "d1")
        self.assertEqual(res.to_square, "h5")
        self.assertEqual(res.uci_move, "d1h5")

    def test_dom_grid_to_fen(self):
        grid: list[str | None] = [None] * 64
        grid[0] = 'r'
        grid[4] = 'k'
        grid[7] = 'r'
        grid[56] = 'R'
        grid[60] = 'K'
        grid[63] = 'R'
        fen = ChessSolver.grid_to_fen(grid, active_color='w')
        self.assertTrue(fen.startswith("r3k2r/8/8/8/8/8/8/R3K2R"))
        self.assertIn("w KQkq - 0 1", fen)

    def test_depth_configuration_up_to_50(self):
        solver = ChessSolver()
        fen = "rnbqkbnr/ppppp2p/5p2/6p1/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 3"
        res = solver.solve_best_move(fen, depth=50)
        self.assertIsInstance(res, ChessMoveResult)
        self.assertEqual(res.uci_move, "d1h5")

    def test_ai_solver_ensemble_execution(self):
        async def _run():
            solver = ChessSolver()
            fen = "rnbqkbnr/ppppp2p/5p2/6p1/4P3/8/PPPP1PPP/RNBQKBNR w KQkq - 0 3"
            res = await solver.solve_best_move_ai(fen, engine_type="ai_hybrid_ensemble", depth=3)
            self.assertIsInstance(res, ChessMoveResult)
            self.assertTrue(len(res.uci_move) >= 4)
            self.assertIsNotNone(res.engine_name)
        asyncio.run(_run())


if __name__ == "__main__":
    unittest.main()
