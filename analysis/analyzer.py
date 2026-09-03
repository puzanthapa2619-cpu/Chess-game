"""Post-game analyzer using Stockfish (or fallback) to classify each move.

Move categories mirror chess.com terminology:
  brilliant, great, best, excellent, good, book, inaccuracy,
  mistake, blunder, missed_win, missed_mate
"""
import chess

from utils.logger import get_logger
from game.opening_book import identify_opening

log = get_logger("analyzer")


# Category thresholds in centipawn-loss (from opponent's POV of best move).
def _classify(cp_loss: int, was_only_move: bool, was_book: bool,
              missed_mate: bool, missed_win: bool, played_best: bool,
              is_brilliant: bool) -> str:
    if was_book:
        return "book"
    if is_brilliant:
        return "brilliant"
    if missed_mate:
        return "missed_mate"
    if missed_win:
        return "missed_win"
    if played_best:
        return "best"
    if cp_loss < 10:
        return "great"
    if cp_loss < 25:
        return "excellent"
    if cp_loss < 60:
        return "good"
    if cp_loss < 120:
        return "inaccuracy"
    if cp_loss < 250:
        return "mistake"
    return "blunder"


def accuracy_from_cpl(avg_cpl: float) -> float:
    """Chess.com-style accuracy formula (approximation)."""
    import math
    x = max(0, avg_cpl)
    # Empirical mapping
    acc = 103.1668 * math.exp(-0.04354 * x) - 3.1669
    return max(0.0, min(100.0, acc))


class GameAnalyzer:
    def __init__(self, engine_manager, time_per_move: float = 0.25):
        self.engine = engine_manager
        self.time = time_per_move

    def analyze(self, moves_uci, progress_callback=None):
        """Analyse a list of UCI move strings played from the starting pos.

        Returns a big dict with per-move classifications, accuracies, and
        summary counts.
        """
        board = chess.Board()
        evaluations = []       # per-ply eval from white's POV, in cp
        classifications = []   # per-ply {move, san, classification, cp_loss, ...}
        cpl_white, cpl_black = [], []
        counts = {k: 0 for k in ("brilliant", "great", "best", "excellent",
                                  "good", "book", "inaccuracy", "mistake",
                                  "blunder", "missed_win", "missed_mate")}

        # Book cutoff: first 10 plies count as "book" if match a known opening
        sans_played = []
        tmp = chess.Board()
        for u in moves_uci:
            try:
                m = chess.Move.from_uci(u)
                sans_played.append(tmp.san(m))
                tmp.push(m)
            except Exception:
                sans_played.append("")
        opening = identify_opening(sans_played)

        for i, uci in enumerate(moves_uci):
            try:
                move = chess.Move.from_uci(uci)
            except Exception:
                continue
            if move not in board.legal_moves:
                continue

            # Best move & eval BEFORE the played move
            best_info = self.engine.analyse_move(board, time_limit=self.time)
            best_move = best_info[0]["move"] if best_info else None
            best_cp = best_info[0]["score_cp"] if best_info else 0  # from side to move

            # Eval AFTER the played move (from opponent's POV -> negate)
            board.push(move)
            after = self.engine.analyse_move(board, time_limit=self.time)
            after_cp_from_opp = after[0]["score_cp"] if after else 0
            after_cp_from_mover = -after_cp_from_opp
            board.pop()

            # cp_loss: how much worse the played move is vs. best
            cp_loss = max(0, best_cp - after_cp_from_mover)

            was_book = i < 10 and opening != "Unknown Opening"
            played_best = (best_move is not None and move == best_move)
            missed_mate = best_cp >= 90000 and after_cp_from_mover < 5000
            missed_win = (best_cp >= 300 and after_cp_from_mover < 100
                          and not missed_mate)
            # Brilliant heuristic: sacrifices material while remaining best
            is_brilliant = False
            if played_best and board.is_capture(move) is False:
                # Piece put en prise but still best -> brilliant
                board.push(move)
                attackers = board.attackers(not board.turn, move.to_square)
                defenders = board.attackers(board.turn, move.to_square)
                board.pop()
                mover_piece = board.piece_at(move.from_square)
                if (mover_piece and mover_piece.piece_type in
                        (chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT)
                        and len(attackers) > len(defenders)
                        and best_cp > 100):
                    is_brilliant = True

            cls = _classify(cp_loss, False, was_book,
                            missed_mate, missed_win, played_best, is_brilliant)
            counts[cls] += 1

            side = "white" if board.turn == chess.WHITE else "black"
            (cpl_white if side == "white" else cpl_black).append(cp_loss)

            san = board.san(move)
            board.push(move)
            # Evaluation from white's POV for the eval graph
            eval_white = after_cp_from_opp if board.turn == chess.WHITE else -after_cp_from_opp
            evaluations.append(eval_white)
            classifications.append({
                "ply": i + 1,
                "san": san,
                "uci": uci,
                "classification": cls,
                "cp_loss": cp_loss,
                "best_move": best_move.uci() if best_move else None,
                "side": side,
                "eval_white": eval_white,
            })

            if progress_callback:
                progress_callback(i + 1, len(moves_uci))

        avg_w = sum(cpl_white) / len(cpl_white) if cpl_white else 0
        avg_b = sum(cpl_black) / len(cpl_black) if cpl_black else 0

        return {
            "accuracy_white":    round(accuracy_from_cpl(avg_w), 2),
            "accuracy_black":    round(accuracy_from_cpl(avg_b), 2),
            "avg_cp_loss_white": round(avg_w, 1),
            "avg_cp_loss_black": round(avg_b, 1),
            **counts,
            "evaluation_json":     evaluations,
            "classification_json": classifications,
            "opening":             opening,
        }
