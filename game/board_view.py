"""Chess board rendering, animations, and interaction.

Draws the board, pieces, highlights, legal-move indicators, animations
(slide, capture, promotion, check, checkmate) and handles drag-and-drop.
"""
import time
import math
import pygame
import chess

SEL_GLOW      = (255, 235, 80, 220)
LAST_MOVE     = (247, 236, 91, 130)
LEGAL_DOT     = (30, 30, 30, 90)
LEGAL_RING    = (30, 30, 30, 150)
HINT_COLOR    = (60, 180, 240, 180)
CHECK_RED     = (235, 40, 40)
COORD_LIGHT   = (245, 235, 210)
COORD_DARK    = (110, 80, 50)

PIECE_CODE = {
    (chess.PAWN, True):  "wP", (chess.PAWN, False):  "bP",
    (chess.KNIGHT, True):"wN", (chess.KNIGHT, False):"bN",
    (chess.BISHOP, True):"wB", (chess.BISHOP, False):"bB",
    (chess.ROOK, True):  "wR", (chess.ROOK, False):  "bR",
    (chess.QUEEN, True): "wQ", (chess.QUEEN, False): "bQ",
    (chess.KING, True):  "wK", (chess.KING, False):  "bK",
}


def _ease_out_cubic(t: float) -> float:
    return 1 - (1 - t) ** 3


class MoveAnimation:
    """Slide + capture + castling animation payload."""

    def __init__(self, piece_code, from_xy, to_xy, duration=0.22,
                 captured_code=None, captured_xy=None):
        self.piece_code = piece_code
        self.from_xy = from_xy
        self.to_xy = to_xy
        self.duration = duration
        self.start = time.time()
        self.captured_code = captured_code
        self.captured_xy = captured_xy or to_xy
        self.done = False

    def current_pos(self):
        t = (time.time() - self.start) / self.duration
        if t >= 1.0:
            self.done = True
            return self.to_xy
        e = _ease_out_cubic(t)
        return (self.from_xy[0] + (self.to_xy[0] - self.from_xy[0]) * e,
                self.from_xy[1] + (self.to_xy[1] - self.from_xy[1]) * e)

    def capture_progress(self):
        return min(1.0, (time.time() - self.start) / (self.duration * 0.8))


class BoardView:
    """Renders and interacts with a chess board."""

    def __init__(self, board: chess.Board, assets, settings, rect: pygame.Rect):
        self.board = board
        self.assets = assets
        self.settings = settings
        self.rect = rect
        self.sq_size = rect.width // 8

        self.selected_sq = None
        self.legal_targets = set()
        self.dragging = False
        self.drag_from = None
        self.drag_piece_code = None
        self.drag_pos = (0, 0)

        self.last_move = None
        self.animations = []
        self.hidden_sqs = set()
        self.check_pulse_start = None
        self.checkmate_time = None
        self.promo_effect_start = None
        self.promo_effect_sq = None

        self.hint_move = None   # arrow to draw for a hint
        self.interactive = True # False for review / spectator

    # ---------- layout ----------
    def set_rect(self, rect):
        self.rect = rect
        self.sq_size = rect.width // 8

    def flip(self):
        return self.settings.get_bool("flip_board")

    def square_to_xy(self, sq):
        file = chess.square_file(sq)
        rank = chess.square_rank(sq)
        if self.flip():
            col, row = 7 - file, rank
        else:
            col, row = file, 7 - rank
        return (self.rect.x + col * self.sq_size,
                self.rect.y + row * self.sq_size)

    def xy_to_square(self, x, y):
        if not self.rect.collidepoint(x, y):
            return None
        col = (x - self.rect.x) // self.sq_size
        row = (y - self.rect.y) // self.sq_size
        if not (0 <= col < 8 and 0 <= row < 8):
            return None
        if self.flip():
            file, rank = 7 - col, row
        else:
            file, rank = col, 7 - row
        return chess.square(int(file), int(rank))

    # ---------- selection ----------
    def select_square(self, sq):
        if sq is not None:
            p = self.board.piece_at(sq)
            if p and p.color == self.board.turn:
                self.selected_sq = sq
                self.legal_targets = {m.to_square for m in self.board.legal_moves
                                      if m.from_square == sq}
                return
        self.selected_sq = None
        self.legal_targets = set()

    # ---------- moves ----------
    def push_move(self, move: chess.Move, animate: bool = True):
        """Play a fully-legal move with animation."""
        piece = self.board.piece_at(move.from_square)
        if piece is None:
            return False, None
        captured = self.board.piece_at(move.to_square)
        is_ep = self.board.is_en_passant(move)
        if is_ep:
            ep_sq = chess.square(chess.square_file(move.to_square),
                                 chess.square_rank(move.from_square))
            captured = self.board.piece_at(ep_sq)

        pcode = PIECE_CODE[(piece.piece_type, piece.color)]
        if move.promotion:
            pcode = PIECE_CODE[(move.promotion, piece.color)]
        ccode = PIECE_CODE[(captured.piece_type, captured.color)] if captured else None

        from_xy = self.square_to_xy(move.from_square)
        to_xy = self.square_to_xy(move.to_square)

        # Detect castling BEFORE pushing
        is_castling = (piece.piece_type == chess.KING and
                       abs(chess.square_file(move.from_square) -
                           chess.square_file(move.to_square)) == 2)

        san = self.board.san(move)
        self.board.push(move)
        self.last_move = move

        if move.promotion:
            self.promo_effect_start = time.time()
            self.promo_effect_sq = move.to_square

        if animate and self.settings.get_bool("animate"):
            speed = self.settings.get("animation_speed", "normal")
            dur = {"slow": 0.35, "normal": 0.22, "fast": 0.12}.get(speed, 0.22)
            self.hidden_sqs.add(move.to_square)
            self.animations.append(
                MoveAnimation(pcode, from_xy, to_xy, duration=dur,
                              captured_code=ccode, captured_xy=to_xy))
            if is_castling:
                rank = chess.square_rank(move.from_square)
                if chess.square_file(move.to_square) == 6:
                    rook_from = chess.square(7, rank); rook_to = chess.square(5, rank)
                else:
                    rook_from = chess.square(0, rank); rook_to = chess.square(3, rank)
                rcode = "wR" if piece.color else "bR"
                self.hidden_sqs.add(rook_to)
                self.animations.append(
                    MoveAnimation(rcode, self.square_to_xy(rook_from),
                                  self.square_to_xy(rook_to), duration=dur))

        if self.board.is_checkmate():
            self.checkmate_time = time.time()
        elif self.board.is_check():
            self.check_pulse_start = time.time()
        else:
            self.check_pulse_start = None

        self.selected_sq = None
        self.legal_targets = set()
        return True, san

    def is_animating(self):
        return len(self.animations) > 0

    def undo(self):
        if not self.board.move_stack:
            return
        self.board.pop()
        self.last_move = self.board.peek() if self.board.move_stack else None
        self.animations.clear()
        self.hidden_sqs.clear()
        self.selected_sq = None
        self.legal_targets = set()
        if self.board.is_check():
            self.check_pulse_start = time.time()
        else:
            self.check_pulse_start = None
        self.checkmate_time = None

    def show_hint(self, move):
        self.hint_move = move

    def clear_hint(self):
        self.hint_move = None

    # ---------- drawing ----------
    def _draw_squares(self, surf):
        theme = self.settings.get("board_theme", "green")
        light, dark = self.assets.get_board_tiles(theme, self.sq_size)
        for sq in chess.SQUARES:
            x, y = self.square_to_xy(sq)
            f, r = chess.square_file(sq), chess.square_rank(sq)
            surf.blit(light if (f + r) % 2 == 1 else dark, (x, y))

    def _draw_highlights(self, surf):
        if self.last_move and self.settings.get_bool("highlight_last"):
            for sq in (self.last_move.from_square, self.last_move.to_square):
                x, y = self.square_to_xy(sq)
                s = pygame.Surface((self.sq_size, self.sq_size), pygame.SRCALPHA)
                s.fill(LAST_MOVE); surf.blit(s, (x, y))

        if self.board.is_check() and not self.board.is_checkmate():
            ksq = self.board.king(self.board.turn)
            if ksq is not None:
                x, y = self.square_to_xy(ksq)
                t = 0.5 + 0.5 * math.sin(time.time() * 6)
                s = pygame.Surface((self.sq_size, self.sq_size), pygame.SRCALPHA)
                center = (self.sq_size // 2, self.sq_size // 2)
                for r in range(self.sq_size // 2, 0, -4):
                    a = int(60 * (1 - r / (self.sq_size / 2)) * (0.6 + 0.4 * t))
                    pygame.draw.circle(s, (*CHECK_RED, a), center, r)
                surf.blit(s, (x, y))

        if self.board.is_checkmate() and self.checkmate_time:
            ksq = self.board.king(self.board.turn)
            if ksq is not None:
                x, y = self.square_to_xy(ksq)
                t = time.time() - self.checkmate_time
                a = int(120 + 100 * abs(math.sin(t * 3)))
                s = pygame.Surface((self.sq_size, self.sq_size), pygame.SRCALPHA)
                s.fill((200, 0, 0, min(220, a)))
                surf.blit(s, (x, y))

        if self.selected_sq is not None:
            x, y = self.square_to_xy(self.selected_sq)
            s = pygame.Surface((self.sq_size, self.sq_size), pygame.SRCALPHA)
            for i in range(4, 0, -1):
                pygame.draw.rect(s, (255, 255, 120, 40),
                                 (i, i, self.sq_size - i*2, self.sq_size - i*2),
                                 width=2, border_radius=4)
            pygame.draw.rect(s, SEL_GLOW, s.get_rect(), width=3, border_radius=4)
            surf.blit(s, (x, y))

        if self.settings.get_bool("show_legal") and self.selected_sq is not None:
            for tgt in self.legal_targets:
                x, y = self.square_to_xy(tgt)
                s = pygame.Surface((self.sq_size, self.sq_size), pygame.SRCALPHA)
                center = (self.sq_size // 2, self.sq_size // 2)
                if self.board.piece_at(tgt) is not None:
                    pygame.draw.circle(s, LEGAL_RING, center,
                                       self.sq_size // 2 - 3, width=5)
                else:
                    pygame.draw.circle(s, LEGAL_DOT, center, self.sq_size // 7)
                surf.blit(s, (x, y))

    def _draw_hint(self, surf):
        if not self.hint_move:
            return
        fx = self.square_to_xy(self.hint_move.from_square)
        tx = self.square_to_xy(self.hint_move.to_square)
        cx1 = fx[0] + self.sq_size // 2
        cy1 = fx[1] + self.sq_size // 2
        cx2 = tx[0] + self.sq_size // 2
        cy2 = tx[1] + self.sq_size // 2
        # Draw thick semi-transparent arrow
        overlay = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        pygame.draw.line(overlay, HINT_COLOR, (cx1, cy1), (cx2, cy2),
                         max(6, self.sq_size // 10))
        # Arrowhead
        angle = math.atan2(cy2 - cy1, cx2 - cx1)
        head = self.sq_size // 4
        for ao in (2.6, -2.6):
            ex = cx2 - head * math.cos(angle + ao)
            ey = cy2 - head * math.sin(angle + ao)
            pygame.draw.line(overlay, HINT_COLOR, (cx2, cy2), (ex, ey),
                             max(6, self.sq_size // 10))
        surf.blit(overlay, (0, 0))

    def _draw_pieces(self, surf):
        theme = self.settings.get("piece_theme", "classic")
        for sq in chess.SQUARES:
            p = self.board.piece_at(sq)
            if not p:
                continue
            if self.dragging and sq == self.drag_from:
                continue
            if sq in self.hidden_sqs and self.animations:
                continue
            code = PIECE_CODE[(p.piece_type, p.color)]
            img = self.assets.get_piece(theme, code, self.sq_size)
            if img:
                surf.blit(img, self.square_to_xy(sq))

    def _draw_animations(self, surf):
        theme = self.settings.get("piece_theme", "classic")
        alive = []
        for a in self.animations:
            pos = a.current_pos()
            if a.captured_code:
                cp = a.capture_progress()
                sc = 1.0 - cp
                if sc > 0:
                    orig = self.assets.get_piece(theme, a.captured_code, self.sq_size)
                    if orig:
                        sz = max(1, int(self.sq_size * sc))
                        img = pygame.transform.smoothscale(orig, (sz, sz))
                        img.set_alpha(int(255 * (1 - cp)))
                        ox, oy = a.captured_xy
                        surf.blit(img, (ox + (self.sq_size - sz) // 2,
                                         oy + (self.sq_size - sz) // 2))
            img = self.assets.get_piece(theme, a.piece_code, self.sq_size)
            if img:
                surf.blit(img, pos)
            if not a.done:
                alive.append(a)
        if not alive:
            self.hidden_sqs.clear()
        self.animations = alive

    def _draw_promo(self, surf):
        if self.promo_effect_start is None:
            return
        t = time.time() - self.promo_effect_start
        if t > 0.6:
            self.promo_effect_start = None
            self.promo_effect_sq = None
            return
        x, y = self.square_to_xy(self.promo_effect_sq)
        s = pygame.Surface((self.sq_size, self.sq_size), pygame.SRCALPHA)
        center = (self.sq_size // 2, self.sq_size // 2)
        p = t / 0.6
        r = int(self.sq_size * (0.2 + 0.4 * p))
        a = int(220 * (1 - p))
        pygame.draw.circle(s, (255, 215, 0, a), center, r, width=4)
        pygame.draw.circle(s, (255, 240, 150, a // 2), center, r // 2)
        surf.blit(s, (x, y))

    def _draw_drag(self, surf):
        if not self.dragging or not self.drag_piece_code:
            return
        theme = self.settings.get("piece_theme", "classic")
        hover = self.xy_to_square(*self.drag_pos)
        if hover is not None:
            x, y = self.square_to_xy(hover)
            s = pygame.Surface((self.sq_size, self.sq_size), pygame.SRCALPHA)
            pygame.draw.rect(s, (255, 255, 255, 60), s.get_rect(), border_radius=4)
            surf.blit(s, (x, y))
        img = self.assets.get_piece(theme, self.drag_piece_code, int(self.sq_size * 1.05))
        if img:
            rect = img.get_rect(center=self.drag_pos)
            surf.blit(img, rect.topleft)

    def _draw_coords(self, surf):
        if not self.settings.get_bool("show_coords"):
            return
        font = self.assets.get_font(max(11, self.sq_size // 7), bold=True)
        for i in range(8):
            file = chr(ord('a') + (7 - i if self.flip() else i))
            rank = str(i + 1 if self.flip() else 8 - i)
            # Files
            bx = self.rect.x + i * self.sq_size
            color = COORD_DARK if (i + 7) % 2 == 0 else COORD_LIGHT
            t = font.render(file, True, color)
            surf.blit(t, (bx + self.sq_size - t.get_width() - 3,
                          self.rect.y + 8 * self.sq_size - t.get_height() - 2))
            # Ranks
            color = COORD_DARK if i % 2 == 0 else COORD_LIGHT
            t = font.render(rank, True, color)
            surf.blit(t, (self.rect.x + 3, self.rect.y + i * self.sq_size + 2))

    def draw(self, surf):
        self._draw_squares(surf)
        self._draw_highlights(surf)
        self._draw_hint(surf)
        self._draw_pieces(surf)
        self._draw_animations(surf)
        self._draw_promo(surf)
        self._draw_drag(surf)
        self._draw_coords(surf)

    # ---------- input ----------
    def handle_mousedown(self, pos, button):
        if not self.interactive or button != 1:
            return None
        sq = self.xy_to_square(*pos)
        if sq is None:
            return None
        if self.selected_sq is not None and sq in self.legal_targets:
            return ("move", self.selected_sq, sq)
        p = self.board.piece_at(sq)
        if p and p.color == self.board.turn:
            self.select_square(sq)
            self.dragging = True
            self.drag_from = sq
            self.drag_piece_code = PIECE_CODE[(p.piece_type, p.color)]
            self.drag_pos = pos
        else:
            self.select_square(None)
        return None

    def handle_mousemove(self, pos):
        if self.dragging:
            self.drag_pos = pos

    def handle_mouseup(self, pos, button):
        if button != 1:
            return None
        result = None
        if self.dragging:
            drop_sq = self.xy_to_square(*pos)
            if drop_sq is not None and drop_sq != self.drag_from \
                    and drop_sq in self.legal_targets:
                result = ("move", self.drag_from, drop_sq)
        self.dragging = False
        self.drag_from = None
        self.drag_piece_code = None
        return result
