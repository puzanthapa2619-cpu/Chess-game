"""In-game screen: board + sidebar with clocks, buttons, chat, move list."""
import pygame
import chess
import time
import threading
import os
import random

from ui.base_screen import Screen
from ui.widgets import Button, ScrollList, TextInput
from game.board_view import BoardView, PIECE_CODE
from game.timer import ChessTimer
from game.elo import update_ratings
from game.opening_book import identify_opening
from analysis.export import export_pgn
from database.db import Database


PROMO_ORDER = [chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT]
PROMO_LETTER = {chess.QUEEN: "Q", chess.ROOK: "R",
                chess.BISHOP: "B", chess.KNIGHT: "N"}


class PromotionDialog:
    def __init__(self, color, to_square, board_view):
        self.color = color
        self.to_sq = to_square
        self.bv = board_view
        self.result = None
        x, y = board_view.square_to_xy(to_square)
        row = 0 if not board_view.flip() and chess.square_rank(to_square) == 7 else \
              0 if board_view.flip() and chess.square_rank(to_square) == 0 else 4
        # Stack downward from top; if promoting from black (rank 0), stack down.
        self.rect = pygame.Rect(x, y if row == 0 else y - 3 * board_view.sq_size,
                                board_view.sq_size, 4 * board_view.sq_size)

    def draw(self, surf, assets, theme, piece_theme):
        pygame.draw.rect(surf, (250, 250, 250), self.rect, border_radius=6)
        pygame.draw.rect(surf, (30, 30, 30), self.rect, width=2, border_radius=6)
        prefix = "w" if self.color else "b"
        mouse = pygame.mouse.get_pos()
        for i, pt in enumerate(PROMO_ORDER):
            cell = pygame.Rect(self.rect.x, self.rect.y + i * self.bv.sq_size,
                               self.bv.sq_size, self.bv.sq_size)
            if cell.collidepoint(mouse):
                pygame.draw.rect(surf, (230, 230, 200), cell, border_radius=4)
            img = assets.get_piece(piece_theme, prefix + PROMO_LETTER[pt],
                                   self.bv.sq_size)
            if img:
                surf.blit(img, cell)

    def handle(self, e):
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            for i, pt in enumerate(PROMO_ORDER):
                cell = pygame.Rect(self.rect.x, self.rect.y + i * self.bv.sq_size,
                                   self.bv.sq_size, self.bv.sq_size)
                if cell.collidepoint(e.pos):
                    self.result = pt
                    return True
        return False


class GameScreen(Screen):
    """Handles offline games (AI, guest, hot-seat) and online games."""

    def __init__(self, app):
        super().__init__(app)
        self.db = Database()
        self.board = chess.Board()
        self.view: BoardView = None
        self.timer: ChessTimer = None
        self.mode = "ai"          # ai | offline | guest | online
        self.online_client = None
        self.ai_color = chess.BLACK
        self.ai_thinking = False
        self.ai_result = None
        self.ai_thread = None
        self.pending_promo = None
        self.promo_dialog = None
        self.move_sans = []
        self.match_id = None
        self.game_over_reason = None
        self.game_over_winner = None
        self.captured_white = []   # black pieces captured by white
        self.captured_black = []
        self.chat_messages = []
        self.draw_offer_from_opponent = False
        self.tournament_ctx = None
        self.tournament_status_msg = ""
        self._pending_tournament_transition = None
        self._pending_tournament_champion = None
        self._pending_draw_replay = None

        # Widgets
        self.resign_btn = Button((0,0,110,36), "Resign", self._resign)
        self.draw_btn   = Button((0,0,110,36), "Draw",   self._offer_draw)
        self.undo_btn   = Button((0,0,110,36), "Undo",   self._undo)
        self.hint_btn   = Button((0,0,110,36), "Hint",   self._hint)
        self.flip_btn   = Button((0,0,110,36), "Flip",   self._flip)
        self.exit_btn   = Button((0,0,110,36), "Menu",   self._exit)
        self.newgame_btn= Button((0,0,140,40), "New Game",
                                 self._new_game, primary=True)
        self.analyze_btn= Button((0,0,140,40), "Analyze",
                                 self._analyze, primary=True)
        self.pgn_btn    = Button((0,0,140,36), "Export PGN", self._export_pgn)
        self.rematch_btn = Button((0,0,110,36), "Rematch", self._rematch)
        self.accept_draw_btn = Button((0,0,110,32), "Accept", self._accept_draw, primary=True)
        self.decline_draw_btn = Button((0,0,110,32), "Decline", self._decline_draw)

        self.chat_input = TextInput((0,0,240,32), "Type message...",
                                    on_submit=self._send_chat)
        self.chat_send  = Button((0,0,60,32), "Send", self._send_chat)

        self.move_list = ScrollList((0,0,240,200), 22, [],
                                     self._render_move_row)

    # ---------- lifecycle ----------
    def on_enter(self, mode="ai", online_client=None, tournament_ctx=None, **ctx):
        self.mode = mode
        self.online_client = online_client
        self.tournament_ctx = tournament_ctx
        self.tournament_status_msg = ""
        self._pending_tournament_transition = None
        self._pending_tournament_champion = None
        self._pending_draw_replay = None
        self.board = chess.Board()
        self.move_sans = []
        self.captured_white = []
        self.captured_black = []
        self.chat_messages = []
        self.game_over_reason = None
        self.game_over_winner = None
        self.ai_result = None
        self.ai_thinking = False
        self.pending_promo = None
        self.promo_dialog = None
        self.draw_offer_from_opponent = False

        # Setup board view - rect computed in _layout
        self.view = BoardView(self.board, self.app.assets, self.app.settings,
                              pygame.Rect(0, 0, 800, 800))
        self._layout()

        # Timer
        tc = (tournament_ctx or {}).get("time_control") or self.app.settings.get("time_control", "10+0")
        try:
            mins, inc = tc.split("+")
            self.timer = ChessTimer(float(mins), float(inc))
        except Exception:
            self.timer = ChessTimer(10, 0)
        if mode != "online":
            self.timer.start()
        else:
            # Online games must run the clock too — the room is only entered
            # once both players are already present, so it's safe to start
            # immediately.
            self.timer.start()

        # AI color: random unless specified
        self.ai_color = chess.BLACK if random.random() < 0.5 else chess.WHITE
        if mode == "ai" and self.ai_color == chess.WHITE:
            self.app.settings.set("flip_board", True)
        else:
            self.app.settings.set("flip_board", False)
        if mode == "local":
            self.app.settings.set("flip_board", False)  # White moves first

        # If online: register message handler
        if mode == "online" and self.online_client is not None:
            self.online_client.on_message = self._on_online_msg

    def on_exit(self):
        if self.online_client:
            self.online_client.on_message = None
        # Terminate AI thread on exit
        self.ai_thinking = False

    def on_resize(self):
        self._layout()

    def _layout(self):
        w, h = self.app.screen.get_size()
        top_bar = 60
        board_area_h = h - top_bar - 20
        sidebar_w = 320
        board_area_w = w - sidebar_w - 20
        board_size = min(board_area_w, board_area_h)
        board_size = (board_size // 8) * 8
        bx = 10
        by = top_bar + (board_area_h - board_size) // 2
        rect = pygame.Rect(bx, by, board_size, board_size)
        if self.view:
            self.view.set_rect(rect)

        # Sidebar buttons
        sx = bx + board_size + 20
        # Top bar buttons
        self.exit_btn.rect.topleft   = (10, 12)
        self.flip_btn.rect.topleft   = (130, 12)
        self.hint_btn.rect.topleft   = (250, 12)
        self.undo_btn.rect.topleft   = (370, 12)
        self.draw_btn.rect.topleft   = (490, 12)
        self.resign_btn.rect.topleft = (610, 12)

        # Sidebar layout
        y = top_bar + 20
        self.newgame_btn.rect.topleft = (sx, y); y += 48
        self.analyze_btn.rect.topleft = (sx, y); y += 48
        self.pgn_btn.rect.topleft     = (sx, y); y += 48
        self.rematch_btn.rect.topleft = (sx, y); y += 48
        # Draw offer buttons (hidden unless offer active)
        self.accept_draw_btn.rect.topleft = (sx, y)
        self.decline_draw_btn.rect.topleft = (sx + 120, y); y += 40

        # Move list panel
        list_h = h - y - 130
        self.move_list.rect = pygame.Rect(sx, y, 240, list_h)
        # Chat
        self.chat_input.rect.topleft = (sx, self.move_list.rect.bottom + 12)
        self.chat_send.rect.topleft  = (sx + 250, self.move_list.rect.bottom + 12)

        base = [self.exit_btn, self.flip_btn, self.hint_btn, self.undo_btn,
                self.draw_btn, self.resign_btn,
                self.move_list]
        if self.tournament_ctx:
            # Bracket auto-advances; no manual rematch/new game here.
            base += [self.analyze_btn, self.pgn_btn]
        else:
            base += [self.newgame_btn, self.analyze_btn, self.pgn_btn, self.rematch_btn]
        if self.mode == "online":
            base += [self.chat_input, self.chat_send]
        if self.draw_offer_from_opponent:
            base += [self.accept_draw_btn, self.decline_draw_btn]
        self.widgets = base

    # ---------- callbacks ----------
    def _resign(self):
        if self.game_over_reason: return
        if self.mode == "online" and self.online_client:
            self.online_client.resign()
            return
        winner = "black" if self.board.turn == chess.WHITE else "white"
        self._end_game("resignation", winner)

    def _offer_draw(self):
        if self.game_over_reason: return
        if self.mode == "online" and self.online_client:
            self.online_client.offer_draw()
        else:
            # In offline modes, just accept immediately
            self._end_game("agreement", "draw")

    def _accept_draw(self):
        if self.mode == "online" and self.online_client:
            self.online_client.accept_draw()
        self.draw_offer_from_opponent = False
        self._layout()

    def _decline_draw(self):
        if self.mode == "online" and self.online_client:
            self.online_client.decline_draw()
        self.draw_offer_from_opponent = False
        self._layout()

    def _undo(self):
        if self.mode == "online":
            return  # not allowed online
        if self.game_over_reason:
            return
        if not self.board.move_stack:
            return
        # If vs AI, undo two plies so it's still the player's turn
        n = 2 if (self.mode == "ai" and len(self.board.move_stack) >= 2) else 1
        for _ in range(n):
            if self.board.move_stack:
                self.view.undo()
                if self.move_sans:
                    self.move_sans.pop()
        # Rebuild captured lists
        self._recompute_captured()
        self._refresh_move_list()

    def _flip(self):
        cur = self.app.settings.get_bool("flip_board")
        self.app.settings.set("flip_board", not cur)

    def _hint(self):
        if not self.app.settings.get_bool("hint_enabled"): return
        if self.game_over_reason: return
        threading.Thread(target=self._do_hint, daemon=True).start()

    def _do_hint(self):
        move = self.app.engine.play(self.board.copy(),
                                    difficulty="Expert")
        if move:
            self.view.show_hint(move)

    def _exit(self):
        if self.mode == "online" and self.online_client:
            try: self.online_client.close()
            except Exception: pass
        self.app.goto("home")

    def _new_game(self):
        self.on_enter(mode=self.mode, online_client=self.online_client)

    def _rematch(self):
        if self.mode == "online" and self.online_client:
            self.online_client.rematch()
        else:
            self._new_game()

    def _analyze(self):
        if not self.move_sans:
            return
        moves_uci = [m.uci() for m in self.board.move_stack]
        self.app.goto("analysis",
                      moves_uci=moves_uci,
                      white=self._white_name(),
                      black=self._black_name(),
                      result=self.board.result() if self.game_over_reason else "*",
                      match_id=self.match_id)

    def _export_pgn(self):
        if not self.board.move_stack:
            return
        os.makedirs("exports", exist_ok=True)
        path = os.path.join("exports",
                            f"game_{int(time.time())}.pgn")
        moves_uci = [m.uci() for m in self.board.move_stack]
        sans_all = []
        b = chess.Board()
        for m in self.board.move_stack:
            sans_all.append(b.san(m)); b.push(m)
        opening = identify_opening(sans_all)
        export_pgn(path, moves_uci, self._white_name(), self._black_name(),
                   self.board.result() if self.game_over_reason else "*",
                   opening=opening)
        self.app.toast(f"PGN exported to {path}")

    def _send_chat(self):
        text = self.chat_input.text.strip()
        if not text: return
        if self.mode == "online" and self.online_client:
            self.online_client.send_chat(text)
            self.chat_messages.append(("You", text))
        self.chat_input.text = ""

    # ---------- names ----------
    def _white_name(self):
        if self.mode == "ai":
            return self.app.current_user.get("username", "Player") \
                if self.ai_color == chess.BLACK else "Stockfish"
        if self.mode == "online":
            return self.app.online_white_name or "White"
        return self.app.current_user.get("username", "Player") \
            if self.app.current_user else "Player"

    def _black_name(self):
        if self.mode == "ai":
            return "Stockfish" if self.ai_color == chess.BLACK \
                else self.app.current_user.get("username", "Player")
        if self.mode == "online":
            return self.app.online_black_name or "Black"
        if self.mode == "local":
            return "Player 2"
        return "Opponent"

    # ---------- move handling ----------
    def _attempt_move(self, from_sq, to_sq):
        piece = self.board.piece_at(from_sq)
        if piece and piece.piece_type == chess.PAWN:
            rank = chess.square_rank(to_sq)
            if (piece.color and rank == 7) or (not piece.color and rank == 0):
                if any(m.promotion for m in self.board.legal_moves
                       if m.from_square == from_sq and m.to_square == to_sq):
                    if self.app.settings.get_bool("auto_promote_queen"):
                        return self._push(chess.Move(from_sq, to_sq,
                                                     promotion=chess.QUEEN))
                    self.pending_promo = (from_sq, to_sq)
                    self.promo_dialog = PromotionDialog(piece.color, to_sq,
                                                        self.view)
                    return True
        # Find move
        candidates = [m for m in self.board.legal_moves
                      if m.from_square == from_sq and m.to_square == to_sq]
        if not candidates: return False
        return self._push(candidates[0])

    def _push(self, move: chess.Move):
        captured = self.board.piece_at(move.to_square)
        if self.board.is_en_passant(move):
            ep = chess.square(chess.square_file(move.to_square),
                              chess.square_rank(move.from_square))
            captured = self.board.piece_at(ep)
        mover_color = self.board.turn
        is_castle = (self.board.piece_at(move.from_square).piece_type == chess.KING
                     and abs(chess.square_file(move.from_square) -
                             chess.square_file(move.to_square)) == 2)
        san_before = self.board.san(move)
        ok, san = self.view.push_move(move, animate=True)
        if not ok: return False
        self.move_sans.append(san_before)
        if captured:
            code = PIECE_CODE[(captured.piece_type, captured.color)]
            (self.captured_white if mover_color else self.captured_black).append(code)
        # Sound
        if self.board.is_checkmate():
            self.app.sounds.play("checkmate", 0.8)
        elif self.board.is_check():
            self.app.sounds.play("check", 0.7)
        elif move.promotion:
            self.app.sounds.play("promotion", 0.6)
        elif is_castle:
            self.app.sounds.play("castle", 0.6)
        elif captured:
            self.app.sounds.play("capture", 0.6)
        else:
            self.app.sounds.play("move", 0.6)
        # Switch timer
        if self.timer:
            self.timer.switch()
        self._refresh_move_list()

        # Local hot-seat: flip the board so it faces whoever moves next.
        if self.mode == "local":
            self.app.settings.set("flip_board", self.board.turn == chess.BLACK)

        # Online: send to opponent
        if self.mode == "online" and self.online_client and mover_color == self._my_color():
            self.online_client.send_move(move.uci(),
                clock={"white": self.timer.white_time,
                       "black": self.timer.black_time})

        # Check for end
        if self.board.is_game_over():
            self._auto_end()
        return True

    def _my_color(self):
        if self.mode == "ai":
            return not self.ai_color
        if self.mode == "online":
            return self.app.online_my_color
        return self.board.turn  # hot-seat

    def _recompute_captured(self):
        self.captured_white = []
        self.captured_black = []
        b = chess.Board()
        for m in self.board.move_stack:
            captured = b.piece_at(m.to_square)
            if b.is_en_passant(m):
                ep = chess.square(chess.square_file(m.to_square),
                                  chess.square_rank(m.from_square))
                captured = b.piece_at(ep)
            mover = b.turn
            b.push(m)
            if captured:
                code = PIECE_CODE[(captured.piece_type, captured.color)]
                (self.captured_white if mover else self.captured_black).append(code)

    def _refresh_move_list(self):
        pairs = []
        for i in range(0, len(self.move_sans), 2):
            wm = self.move_sans[i]
            bm = self.move_sans[i+1] if i+1 < len(self.move_sans) else ""
            pairs.append((i // 2 + 1, wm, bm))
        self.move_list.set_items(pairs)

    def _render_move_row(self, surf, row_rect, i, item, theme, assets):
        n, wm, bm = item
        f = assets.get_font(13)
        c = theme.c
        surf.blit(f.render(f"{n:>3}.", True, c["text_dim"]),
                  (row_rect.x + 8, row_rect.y + 4))
        surf.blit(f.render(wm, True, c["text"]),
                  (row_rect.x + 45, row_rect.y + 4))
        surf.blit(f.render(bm, True, c["text"]),
                  (row_rect.x + 130, row_rect.y + 4))

    # ---------- AI ----------
    def _maybe_start_ai(self):
        if self.mode != "ai": return
        if self.game_over_reason or self.ai_thinking: return
        if self.view.is_animating() or self.pending_promo: return
        if self.board.turn != self.ai_color: return
        self.ai_thinking = True
        self.ai_result = None
        diff = self.app.settings.get("ai_difficulty", "Normal")
        elo = self.app.settings.get_int("ai_elo", 1500)
        board_copy = self.board.copy()

        def worker():
            move = self.app.engine.play(board_copy, difficulty=diff, custom_elo=elo)
            self.ai_result = move
            self.ai_thinking = False

        self.ai_thread = threading.Thread(target=worker, daemon=True)
        self.ai_thread.start()

    def _apply_ai_result(self):
        if self.ai_result is None: return
        m = self.ai_result
        self.ai_result = None
        if m in self.board.legal_moves:
            self._push(m)

    # ---------- online messages ----------
    def _on_online_msg(self, msg):
        t = msg.get("type")
        if t == "move":
            try:
                m = chess.Move.from_uci(msg.get("uci", ""))
                if m in self.board.legal_moves and self.board.turn != self._my_color():
                    self._push(m)
                    clock = msg.get("clock")
                    if clock and self.timer:
                        self.timer.white_time = float(clock.get("white", self.timer.white_time))
                        self.timer.black_time = float(clock.get("black", self.timer.black_time))
                        self.timer._last = time.time()
            except Exception:
                pass
        elif t == "chat":
            self.chat_messages.append((msg.get("from", "?"), msg.get("text", "")))
        elif t == "draw_offer":
            self.draw_offer_from_opponent = True
            self._layout()
        elif t == "draw_declined":
            self.app.toast("Draw offer declined.")
        elif t == "game_over":
            self._end_game(msg.get("reason", "-"), msg.get("winner", "draw"))
        elif t == "opponent_disconnected":
            self.app.toast("Opponent disconnected.")
        elif t == "tournament_match_start":
            # Next round begins — flag it, actual transition happens on the
            # main thread in update() so we never touch screens from here.
            me = (self.app.current_user or {}).get("username", "Guest")
            self.app.online_white_name = msg.get("white", "White")
            self.app.online_black_name = msg.get("black", "Black")
            self.app.online_my_color = (msg.get("color") == "white")
            self._pending_tournament_transition = msg
        elif t == "tournament_draw_replay":
            self._pending_draw_replay = msg
        elif t == "tournament_eliminated":
            rn = msg.get("round_name", "")
            self.tournament_status_msg = f"Eliminated in the {rn}. Watching for the final result..."
        elif t == "tournament_champion":
            self._pending_tournament_champion = msg

    # ---------- game end ----------
    def _auto_end(self):
        b = self.board
        if b.is_checkmate():
            winner = "black" if b.turn else "white"
            self._end_game("checkmate", winner)
        elif b.is_stalemate():
            self._end_game("stalemate", "draw")
        elif b.is_insufficient_material():
            self._end_game("insufficient material", "draw")
        elif b.is_seventyfive_moves():
            self._end_game("75-move rule", "draw")
        elif b.is_fivefold_repetition():
            self._end_game("fivefold repetition", "draw")

    def _end_game(self, reason, winner):
        if self.game_over_reason:
            return
        self.game_over_reason = reason
        self.game_over_winner = winner
        if self.timer:
            self.timer.stop()
        result = "1-0" if winner == "white" else "0-1" if winner == "black" else "1/2-1/2"
        if winner == "draw":
            self.app.sounds.play("checkmate", 0.5)
        else:
            my_col = self._my_color()
            i_won = (winner == "white" and my_col == chess.WHITE) or \
                    (winner == "black" and my_col == chess.BLACK)
            self.app.sounds.play("victory" if i_won else "defeat", 0.8)

        # Save match if not guest
        self._save_match(result)

    def _save_match(self, result):
        try:
            user = self.app.current_user
            if not user or user.get("id", 0) == 0:
                return   # guest / no persistence

            # Compute PGN
            moves_uci = [m.uci() for m in self.board.move_stack]
            sans = []
            b = chess.Board()
            for m in self.board.move_stack:
                sans.append(b.san(m)); b.push(m)
            opening = identify_opening(sans)

            os.makedirs("exports", exist_ok=True)
            pgn_path = os.path.join("exports", f"match_{int(time.time())}.pgn")
            export_pgn(pgn_path, moves_uci, self._white_name(), self._black_name(),
                       result, opening=opening)
            with open(pgn_path, encoding="utf-8") as f:
                pgn_text = f.read()

            # Determine white/black user ids
            white_id = user["id"] if self._my_color() == chess.WHITE else None
            black_id = user["id"] if self._my_color() == chess.BLACK else None

            # Elo update (only for AI or online with rated opponent -> we treat AI as fixed rating)
            wr_before = user["rating"] if self._my_color() == chess.WHITE else 1500
            br_before = user["rating"] if self._my_color() == chess.BLACK else 1500
            wr_after, br_after, dw, db = update_ratings(wr_before, br_before, result)
            if self._my_color() == chess.WHITE:
                new_rating = wr_after; delta = dw
            else:
                new_rating = br_after; delta = db

            self.match_id = self.db.create_match(
                white_id=white_id, black_id=black_id,
                white_name=self._white_name(), black_name=self._black_name(),
                result=result, termination=self.game_over_reason,
                time_control=self.app.settings.get("time_control", "10+0"),
                mode=self.mode, pgn=pgn_text, final_fen=self.board.fen(),
                opening=opening,
                duration_sec=int(getattr(self, "_start_time", time.time()) -
                                 time.time()) * -1 if hasattr(self, "_start_time") else 0,
                white_rating_before=wr_before, black_rating_before=br_before,
                white_rating_after=wr_after, black_rating_after=br_after,
            )
            # Moves
            board2 = chess.Board()
            for i, m in enumerate(self.board.move_stack):
                self.db.add_move(self.match_id, i + 1, board2.san(m), m.uci(),
                                 board2.fen())
                board2.push(m)
            # Update user stats
            wins = user["wins"] + (1 if (result == "1-0" and self._my_color() == chess.WHITE)
                                       or (result == "0-1" and self._my_color() == chess.BLACK)
                                    else 0)
            losses = user["losses"] + (1 if (result == "0-1" and self._my_color() == chess.WHITE)
                                          or (result == "1-0" and self._my_color() == chess.BLACK)
                                       else 0)
            draws = user["draws"] + (1 if result == "1/2-1/2" else 0)
            games = user["games_played"] + 1
            self.db.update_user_stats(user["id"], wins, losses, draws,
                                      new_rating, user.get("accuracy", 0.0),
                                      games, peak_rating=new_rating)
            self.db.add_rating_point(user["id"], new_rating, delta, self.match_id)
            # Refresh in-memory user
            row = self.db.user_by_id(user["id"])
            if row:
                d = dict(row)
                d.pop("password_hash", None); d.pop("verify_code", None)
                self.app.current_user = d
            # Achievements
            self._check_achievements(wins, games)
        except Exception as e:
            from utils.logger import get_logger
            get_logger("game").error("Save match failed: %s", e)

    def _check_achievements(self, wins, games):
        uid = self.app.current_user["id"]
        if games == 1:
            self.db.award_achievement(uid, "FIRST_GAME", "First Steps",
                                      "Play your first ranked game.")
        if wins == 1:
            self.db.award_achievement(uid, "FIRST_WIN", "First Victory",
                                      "Win your first game.")
        if wins == 10:
            self.db.award_achievement(uid, "TEN_WINS", "Rising Star",
                                      "Win 10 games.")
        if games == 50:
            self.db.award_achievement(uid, "FIFTY_GAMES", "Dedicated",
                                      "Play 50 games.")

    # ---------- events ----------
    def on_event(self, event) -> bool:
        # Promotion dialog first
        if self.promo_dialog:
            if self.promo_dialog.handle(event):
                if self.promo_dialog.result:
                    fr, to = self.pending_promo
                    self._push(chess.Move(fr, to, promotion=self.promo_dialog.result))
                    self.pending_promo = None
                    self.promo_dialog = None
            return True

        if super().on_event(event):
            return True

        # Only allow board input for my color
        allow = True
        if self.game_over_reason: allow = False
        elif self.mode == "ai" and self.board.turn == self.ai_color: allow = False
        elif self.mode == "online" and self.board.turn != self._my_color(): allow = False

        if not allow: return False

        if event.type == pygame.MOUSEBUTTONDOWN:
            r = self.view.handle_mousedown(event.pos, event.button)
            if r and r[0] == "move":
                self._attempt_move(r[1], r[2])
        elif event.type == pygame.MOUSEMOTION:
            self.view.handle_mousemove(event.pos)
        elif event.type == pygame.MOUSEBUTTONUP:
            r = self.view.handle_mouseup(event.pos, event.button)
            if r and r[0] == "move":
                self._attempt_move(r[1], r[2])
        return False

    def update(self, dt):
        # Tournament transitions must happen on the main thread only.
        if self._pending_tournament_transition is not None:
            msg = self._pending_tournament_transition
            self._pending_tournament_transition = None
            client = self.online_client
            self.online_client = None  # re-attached by on_enter
            self.app.goto("game", mode="online", online_client=client,
                          tournament_ctx={
                              "tournament_code": msg.get("tournament_code"),
                              "round_name": msg.get("round_name"),
                              "match_index": msg.get("match_index"),
                              "matches_in_round": msg.get("matches_in_round"),
                              "time_control": msg.get("time_control", "5+0"),
                          })
            return
        if self._pending_tournament_champion is not None:
            msg = self._pending_tournament_champion
            self._pending_tournament_champion = None
            client = self.online_client
            self.online_client = None
            try:
                if client: client.close()
            except Exception:
                pass
            self.app.goto("tournament_result", result=msg)
            return
        if self._pending_draw_replay is not None:
            msg = self._pending_draw_replay
            self._pending_draw_replay = None
            self._apply_draw_replay(msg)

        # Update clocks
        if self.timer and not self.game_over_reason:
            flagged = self.timer.flagged()
            if flagged == "white":
                self._end_game("timeout", "black")
            elif flagged == "black":
                self._end_game("timeout", "white")
        # AI
        if self.ai_result is not None and not self.view.is_animating():
            self._apply_ai_result()
        self._maybe_start_ai()

    def _apply_draw_replay(self, msg):
        """Knockout draw tie-break: server resets the board with colors
        swapped rather than eliminating no one."""
        self.board = chess.Board()
        self.move_sans = []
        self.captured_white = []
        self.captured_black = []
        self.game_over_reason = None
        self.game_over_winner = None
        self.pending_promo = None
        self.promo_dialog = None
        self.view = BoardView(self.board, self.app.assets, self.app.settings,
                              self.view.rect)
        me = (self.app.current_user or {}).get("username", "Guest")
        self.app.online_white_name = msg.get("white", "White")
        self.app.online_black_name = msg.get("black", "Black")
        self.app.online_my_color = (msg.get("white") == me)
        tc = (self.tournament_ctx or {}).get("time_control") or "5+0"
        try:
            mins, inc = tc.split("+")
            self.timer = ChessTimer(float(mins), float(inc))
        except Exception:
            self.timer = ChessTimer(5, 0)
        self.timer.start()
        self.app.settings.set("flip_board", not self.app.online_my_color)
        self.app.toast("Draw — sudden-death replay with colors swapped!")

    # ---------- draw ----------
    def draw(self, surf):
        c = self.app.theme.c
        surf.fill(c["bg"])
        # Top bar
        pygame.draw.rect(surf, c["panel"], (0, 0, surf.get_width(), 60))
        pygame.draw.line(surf, c["border"], (0, 60), (surf.get_width(), 60), 1)

        # Board
        if self.view:
            self.view.draw(surf)

        # Sidebar
        w, h = surf.get_size()
        sx = self.newgame_btn.rect.x
        sw = w - sx - 20
        pygame.draw.rect(surf, c["panel"],
                         (sx - 12, 68, sw + 24, h - 78), border_radius=10)
        pygame.draw.rect(surf, c["border"],
                         (sx - 12, 68, sw + 24, h - 78), width=1, border_radius=10)

        # Clocks (above the sidebar)
        self._draw_clocks(surf, sx, sw)

        # Captured pieces above/below the board? Show in sidebar.
        self._draw_captured(surf, sx, sw)

        # Widgets (buttons, move list, chat)
        super().draw(surf)

        # Status / winner banner
        self._draw_status(surf, sx, sw)

        # Chat log for online mode
        if self.mode == "online":
            self._draw_chat(surf, sx, sw)

        # Promotion popup on top
        if self.promo_dialog and self.view:
            self.promo_dialog.draw(surf, self.app.assets, self.app.theme,
                                   self.app.settings.get("piece_theme"))

        # Game over overlay
        if self.game_over_reason:
            self._draw_game_over(surf)

    def _draw_clocks(self, surf, sx, sw):
        if not self.timer: return
        c = self.app.theme.c
        font = self.app.assets.get_font(28, bold=True)
        small = self.app.assets.get_font(12)
        # Top clock = opponent, bottom clock = you (from your POV)
        top_time = self.timer.black_time if self._my_color() == chess.WHITE else self.timer.white_time
        bot_time = self.timer.white_time if self._my_color() == chess.WHITE else self.timer.black_time
        top_active = (self.timer.turn == chess.WHITE and self._my_color() == chess.BLACK) or \
                     (self.timer.turn == chess.BLACK and self._my_color() == chess.WHITE)
        # Layout - top clock in top bar, bottom clock also in top bar right of buttons
        top_rect = pygame.Rect(sx + 130, 12, 110, 36)
        bot_rect = pygame.Rect(sx, 12, 120, 36)
        for rect, t, active in ((top_rect, top_time, top_active),
                                (bot_rect, bot_time, not top_active)):
            col = c["accent"] if active else c["chip"]
            pygame.draw.rect(surf, col, rect, border_radius=6)
            text_col = (255, 255, 255) if active else c["text"]
            t_render = font.render(self.timer.format(t), True, text_col)
            surf.blit(t_render, t_render.get_rect(center=rect.center))

    def _draw_captured(self, surf, sx, sw):
        c = self.app.theme.c
        piece_theme = self.app.settings.get("piece_theme")
        piece_size = 22
        # White captures (black pieces captured) shown near white player
        # Below the sidebar buttons area, above move list
        y_bot_area = self.move_list.rect.y - 60
        # Opponent's captures on top
        opp_caps = self.captured_black if self._my_color() == chess.WHITE else self.captured_white
        my_caps  = self.captured_white if self._my_color() == chess.WHITE else self.captured_black
        # Draw two rows of captured piece thumbnails
        for row, caps, y in ((0, opp_caps, self.newgame_btn.rect.y - 30),
                              (1, my_caps, y_bot_area)):
            for i, code in enumerate(caps[:12]):
                img = self.app.assets.get_piece(piece_theme, code, piece_size)
                if img:
                    surf.blit(img, (sx + i * (piece_size - 4), y))

    def _draw_status(self, surf, sx, sw):
        c = self.app.theme.c
        f = self.app.assets.get_font(14, bold=True)
        if self.mode == "online" and self.online_client:
            surf.blit(f.render(f"Ping: {self.online_client.ping_ms} ms", True, c["text_dim"]),
                      (sx, 6))
        if self.tournament_ctx:
            rn = self.tournament_ctx.get("round_name", "")
            mi = self.tournament_ctx.get("match_index")
            mt = self.tournament_ctx.get("matches_in_round")
            label = f"Tournament — {rn}" + (f" (match {mi}/{mt})" if mi and mt else "")
            fb = self.app.assets.get_font(15, bold=True)
            t = fb.render(label, True, c["accent"])
            surf.blit(t, (surf.get_width() // 2 - t.get_width() // 2, 18))

    def _draw_chat(self, surf, sx, sw):
        c = self.app.theme.c
        area = pygame.Rect(sx, self.chat_input.rect.bottom + 8, 320,
                           surf.get_height() - self.chat_input.rect.bottom - 20)
        pygame.draw.rect(surf, c["bg_alt"], area, border_radius=6)
        pygame.draw.rect(surf, c["border"], area, width=1, border_radius=6)
        f = self.app.assets.get_font(12)
        y = area.y + 6
        for who, msg in self.chat_messages[-8:]:
            line = f"{who}: {msg}"
            t = f.render(line[:44], True, c["text"])
            surf.blit(t, (area.x + 6, y))
            y += 16

    def _draw_game_over(self, surf):
        c = self.app.theme.c
        overlay = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 130))
        surf.blit(overlay, (0, 0))
        # Card
        w, h = surf.get_size()
        card = pygame.Rect(w // 2 - 220, h // 2 - 130, 440, 260)
        pygame.draw.rect(surf, c["panel"], card, border_radius=12)
        pygame.draw.rect(surf, c["border"], card, width=1, border_radius=12)
        title_font = self.app.assets.get_font(34, bold=True)
        sub_font = self.app.assets.get_font(18)
        title = "Draw" if self.game_over_winner == "draw" else \
                f"{self.game_over_winner.capitalize()} wins"
        t = title_font.render(title, True, c["accent"])
        surf.blit(t, (card.centerx - t.get_width() // 2, card.y + 30))
        s = sub_font.render(f"by {self.game_over_reason}", True, c["text_dim"])
        surf.blit(s, (card.centerx - s.get_width() // 2, card.y + 80))
        # Reuse existing buttons drawn by widget list; hint text:
        if self.tournament_ctx:
            hint_text = (self.tournament_status_msg or
                         "Waiting for the tournament to continue...")
        else:
            hint_text = "Click 'New Game', 'Analyze', or 'Export PGN' →"
        h = self.app.assets.get_font(13).render(hint_text, True, c["text_dim"])
        surf.blit(h, (card.centerx - h.get_width() // 2, card.bottom - 30))
