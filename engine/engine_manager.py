"""Stockfish engine wrapper with graceful fallback to built-in AI.

Auto-detects Stockfish on PATH or in engine/stockfish/. If none is found,
falls back to a pure-Python negamax + alpha-beta engine so the app always
has an AI opponent.
"""
import os
import shutil
import threading
from typing import Optional

import chess
import chess.engine

from utils.paths import ENGINE_DIR
from utils.logger import get_logger
from settings.settings_manager import AI_DIFFICULTIES

log = get_logger("engine")


def find_stockfish(custom_path: str = "") -> Optional[str]:
    """Locate a Stockfish binary. Returns absolute path or None."""
    candidates = []
    if custom_path:
        candidates.append(custom_path)
    # Local engine dir
    for name in ("stockfish", "stockfish.exe"):
        candidates.append(os.path.join(ENGINE_DIR, name))
    # PATH
    for name in ("stockfish", "stockfish.exe"):
        p = shutil.which(name)
        if p:
            candidates.append(p)
    for c in candidates:
        if c and os.path.isfile(c) and os.access(c, os.X_OK):
            return c
    return None


# ---------- fallback engine ----------
_PIECE_VAL = {chess.PAWN: 100, chess.KNIGHT: 320, chess.BISHOP: 330,
              chess.ROOK: 500, chess.QUEEN: 900, chess.KING: 20000}

_PST_PAWN = [
     0,0,0,0,0,0,0,0, 5,10,10,-20,-20,10,10,5,
     5,-5,-10,0,0,-10,-5,5, 0,0,0,20,20,0,0,0,
     5,5,10,25,25,10,5,5, 10,10,20,30,30,20,10,10,
     50,50,50,50,50,50,50,50, 0,0,0,0,0,0,0,0]
_PST_KNIGHT = [-50,-40,-30,-30,-30,-30,-40,-50, -40,-20,0,5,5,0,-20,-40,
    -30,5,10,15,15,10,5,-30, -30,0,15,20,20,15,0,-30,
    -30,5,15,20,20,15,5,-30, -30,0,10,15,15,10,0,-30,
    -40,-20,0,0,0,0,-20,-40, -50,-40,-30,-30,-30,-30,-40,-50]
_PST_BISHOP = [-20,-10,-10,-10,-10,-10,-10,-20, -10,5,0,0,0,0,5,-10,
    -10,10,10,10,10,10,10,-10, -10,0,10,10,10,10,0,-10,
    -10,5,5,10,10,5,5,-10, -10,0,5,10,10,5,0,-10,
    -10,0,0,0,0,0,0,-10, -20,-10,-10,-10,-10,-10,-10,-20]
_PST_ROOK = [0,0,5,10,10,5,0,0, -5,0,0,0,0,0,0,-5,
    -5,0,0,0,0,0,0,-5, -5,0,0,0,0,0,0,-5, -5,0,0,0,0,0,0,-5,
    -5,0,0,0,0,0,0,-5, 5,10,10,10,10,10,10,5, 0,0,0,0,0,0,0,0]
_PST_QUEEN = [-20,-10,-10,-5,-5,-10,-10,-20, -10,0,5,0,0,0,0,-10,
    -10,5,5,5,5,5,0,-10, 0,0,5,5,5,5,0,-5,
    -5,0,5,5,5,5,0,-5, -10,0,5,5,5,5,0,-10,
    -10,0,0,0,0,0,0,-10, -20,-10,-10,-5,-5,-10,-10,-20]
_PST_KING = [20,30,10,0,0,10,30,20, 20,20,0,0,0,0,20,20,
    -10,-20,-20,-20,-20,-20,-20,-10, -20,-30,-30,-40,-40,-30,-30,-20,
    -30,-40,-40,-50,-50,-40,-40,-30, -30,-40,-40,-50,-50,-40,-40,-30,
    -30,-40,-40,-50,-50,-40,-40,-30, -30,-40,-40,-50,-50,-40,-40,-30]
_PSTS = {chess.PAWN:_PST_PAWN, chess.KNIGHT:_PST_KNIGHT, chess.BISHOP:_PST_BISHOP,
         chess.ROOK:_PST_ROOK, chess.QUEEN:_PST_QUEEN, chess.KING:_PST_KING}


def _evaluate(b: chess.Board) -> int:
    if b.is_checkmate():
        return -99999 if b.turn else 99999
    if b.is_stalemate() or b.is_insufficient_material():
        return 0
    s = 0
    for sq, p in b.piece_map().items():
        v = _PIECE_VAL[p.piece_type]
        t = _PSTS[p.piece_type][sq if p.color else chess.square_mirror(sq)]
        s += (v + t) if p.color == chess.WHITE else -(v + t)
    return s if b.turn == chess.WHITE else -s


def _negamax(b, d, a, be):
    if d == 0 or b.is_game_over():
        return _evaluate(b)
    best = -1_000_000
    moves = list(b.legal_moves)
    moves.sort(key=lambda m: 1 if b.is_capture(m) else 0, reverse=True)
    for m in moves:
        b.push(m)
        v = -_negamax(b, d-1, -be, -a)
        b.pop()
        if v > best: best = v
        if best > a: a = best
        if a >= be: break
    return best


def _fallback_move(board: chess.Board, depth: int = 2) -> Optional[chess.Move]:
    best, best_v = None, -1_000_000
    a, be = -1_000_000, 1_000_000
    moves = list(board.legal_moves)
    if not moves:
        return None
    moves.sort(key=lambda m: 1 if board.is_capture(m) else 0, reverse=True)
    for m in moves:
        board.push(m)
        v = -_negamax(board, depth-1, -be, -a)
        board.pop()
        if v > best_v:
            best_v = v; best = m
        if v > a: a = v
    return best


class EngineManager:
    """High-level engine facade used by the game controller."""

    def __init__(self, stockfish_path: str = ""):
        self._lock = threading.Lock()
        self._engine: Optional[chess.engine.SimpleEngine] = None
        self._path = find_stockfish(stockfish_path)
        if self._path:
            try:
                self._engine = chess.engine.SimpleEngine.popen_uci(self._path)
                log.info("Stockfish loaded from %s", self._path)
            except Exception as e:
                log.error("Failed to start Stockfish: %s", e)
                self._engine = None

    @property
    def has_stockfish(self) -> bool:
        return self._engine is not None

    def close(self):
        with self._lock:
            if self._engine:
                try:
                    self._engine.quit()
                except Exception:
                    pass
                self._engine = None

    def _apply_difficulty(self, difficulty: str, custom_elo: Optional[int] = None):
        if not self._engine:
            return
        cfg = AI_DIFFICULTIES.get(difficulty, AI_DIFFICULTIES["Normal"]).copy()
        if difficulty == "Custom" and custom_elo:
            cfg["elo"] = int(custom_elo)
        try:
            opts = {}
            # UCI_LimitStrength + UCI_Elo restrict strength
            opts["Skill Level"] = cfg["skill"]
            opts["UCI_LimitStrength"] = True
            opts["UCI_Elo"] = max(1320, min(3190, cfg["elo"]))
            self._engine.configure(opts)
        except Exception as e:
            log.warning("Engine configure failed: %s", e)

    def play(self, board: chess.Board, difficulty: str = "Normal",
             custom_elo: Optional[int] = None) -> Optional[chess.Move]:
        """Return the engine's chosen move for board (does not push)."""
        cfg = AI_DIFFICULTIES.get(difficulty, AI_DIFFICULTIES["Normal"])
        with self._lock:
            if self._engine:
                try:
                    self._apply_difficulty(difficulty, custom_elo)
                    limit = chess.engine.Limit(time=cfg["time"], depth=cfg["depth"])
                    result = self._engine.play(board, limit)
                    return result.move
                except Exception as e:
                    log.error("Engine play failed, falling back: %s", e)
        # Fallback
        return _fallback_move(board.copy(), depth=min(3, cfg["depth"]))

    def analyse_move(self, board: chess.Board, time_limit: float = 0.3,
                     multipv: int = 1):
        """Return a list of {move, score_cp, pv} for the position.

        Uses Stockfish when available, otherwise a shallow fallback.
        """
        with self._lock:
            if self._engine:
                try:
                    info = self._engine.analyse(board,
                                                chess.engine.Limit(time=time_limit),
                                                multipv=multipv)
                    if not isinstance(info, list):
                        info = [info]
                    out = []
                    for it in info:
                        score = it.get("score")
                        cp = 0
                        if score is not None:
                            pov = score.pov(board.turn)
                            if pov.is_mate():
                                cp = 100000 if pov.mate() > 0 else -100000
                            else:
                                cp = pov.score(mate_score=100000) or 0
                        pv = it.get("pv", [])
                        out.append({"move": pv[0] if pv else None,
                                    "score_cp": cp, "pv": pv})
                    return out
                except Exception as e:
                    log.error("Engine analyse failed: %s", e)
        m = _fallback_move(board.copy(), depth=2)
        return [{"move": m, "score_cp": _evaluate(board), "pv": [m] if m else []}]
