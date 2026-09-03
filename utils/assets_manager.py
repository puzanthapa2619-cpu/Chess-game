"""Asset loading / scaling / caching for pieces, boards, sounds, icons."""
import os
import pygame

from utils.paths import PIECES, BOARDS, SOUNDS, ICONS, IMAGES, FONTS
from utils.logger import get_logger

log = get_logger("assets")

PIECE_CODES = ["wK","wQ","wR","wB","wN","wP","bK","bQ","bR","bB","bN","bP"]


def list_piece_themes():
    if not os.path.isdir(PIECES):
        return []
    return sorted(d for d in os.listdir(PIECES)
                  if os.path.isdir(os.path.join(PIECES, d)))


def list_board_themes():
    if not os.path.isdir(BOARDS):
        return []
    return sorted(d for d in os.listdir(BOARDS)
                  if os.path.isdir(os.path.join(BOARDS, d)))


class AssetManager:
    def __init__(self):
        self._orig_pieces = {}
        self._scaled_pieces = {}
        self._orig_boards = {}
        self._scaled_boards = {}
        self._sounds = {}
        self._icons = {}
        self._fonts = {}

    # ---------- pieces ----------
    def _load_theme(self, theme):
        if theme in self._orig_pieces:
            return
        d = os.path.join(PIECES, theme)
        pieces = {}
        for code in PIECE_CODES:
            for ext in (".png", ".svg"):
                p = os.path.join(d, code + ext)
                if os.path.exists(p):
                    try:
                        pieces[code] = pygame.image.load(p).convert_alpha()
                    except Exception as e:
                        log.error("Failed loading %s: %s", p, e)
                    break
        self._orig_pieces[theme] = pieces

    def get_piece(self, theme, code, size):
        key = (theme, size)
        if key not in self._scaled_pieces:
            self._load_theme(theme)
            scaled = {}
            for c, surf in self._orig_pieces[theme].items():
                scaled[c] = pygame.transform.smoothscale(surf, (size, size))
            self._scaled_pieces[key] = scaled
        return self._scaled_pieces[key].get(code)

    # ---------- boards ----------
    def _load_board(self, theme):
        if theme in self._orig_boards:
            return
        d = os.path.join(BOARDS, theme)
        try:
            l = pygame.image.load(os.path.join(d, "light.png")).convert()
            k = pygame.image.load(os.path.join(d, "dark.png")).convert()
            self._orig_boards[theme] = (l, k)
        except Exception as e:
            log.error("Failed loading board %s: %s", theme, e)
            surf = pygame.Surface((256, 256))
            surf.fill((200, 200, 200))
            self._orig_boards[theme] = (surf, surf)

    def get_board_tiles(self, theme, sq_size):
        key = (theme, sq_size)
        if key not in self._scaled_boards:
            self._load_board(theme)
            l, d = self._orig_boards[theme]
            self._scaled_boards[key] = (
                pygame.transform.smoothscale(l, (sq_size, sq_size)),
                pygame.transform.smoothscale(d, (sq_size, sq_size)),
            )
        return self._scaled_boards[key]

    def invalidate_size(self):
        self._scaled_pieces.clear()
        self._scaled_boards.clear()

    # ---------- sounds ----------
    def get_sound(self, name: str):
        if name not in self._sounds:
            path = os.path.join(SOUNDS, f"{name}.wav")
            try:
                if os.path.exists(path):
                    self._sounds[name] = pygame.mixer.Sound(path)
                else:
                    self._sounds[name] = None
            except Exception as e:
                log.warning("Sound %s failed: %s", name, e)
                self._sounds[name] = None
        return self._sounds[name]

    # ---------- fonts ----------
    def get_font(self, size: int, bold: bool = False, name: str = "arial"):
        key = (name, size, bold)
        if key not in self._fonts:
            try:
                self._fonts[key] = pygame.font.SysFont(name, size, bold=bold)
            except Exception:
                self._fonts[key] = pygame.font.Font(None, size)
        return self._fonts[key]
