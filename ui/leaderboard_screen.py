"""Leaderboard screen."""
import pygame
from ui.base_screen import Screen
from ui.widgets import Button, ScrollList
from database.db import Database


class LeaderboardScreen(Screen):
    def __init__(self, app):
        super().__init__(app)
        self.db = Database()
        self.back_btn = Button((0,0,120,36), "← Back",
                                lambda: self.app.goto("home"))
        self.list = ScrollList((0,0,900,500), 36, [], self._row)
        self.widgets = [self.back_btn, self.list]

    def on_enter(self, **ctx):
        self._layout()
        rows = self.db.leaderboard(100)
        self.list.set_items([dict(r) for r in rows])

    def on_resize(self):
        self._layout()

    def _layout(self):
        w, h = self.app.screen.get_size()
        self.back_btn.rect.topleft = (24, 20)
        self.list.rect = pygame.Rect(60, 130, w - 120, h - 170)

    def _row(self, surf, row_rect, i, item, theme, assets):
        c = theme.c
        f = assets.get_font(15)
        fb = assets.get_font(15, bold=True)
        cols = [
            (str(i + 1),                        60,  c["text_dim"]),
            (item.get("username","?"),         220,  c["text"]),
            (str(item.get("rating",1200)),     140,  c["accent"]),
            (str(item.get("wins",0)),           80,  c["success"]),
            (str(item.get("losses",0)),         80,  c["error"]),
            (str(item.get("draws",0)),          80,  c["text_dim"]),
            (str(item.get("games_played",0)),  110,  c["text"]),
            (f"{item.get('accuracy',0):.1f}%", 100,  c["text_dim"]),
        ]
        x = row_rect.x + 10
        for text, w_col, col in cols:
            font_use = fb if col == c["accent"] else f
            surf.blit(font_use.render(text, True, col), (x, row_rect.y + 8))
            x += w_col

    def draw(self, surf):
        c = self.app.theme.c
        surf.fill(c["bg"])
        f = self.app.assets.get_font(28, bold=True)
        surf.blit(f.render("Leaderboard", True, c["text"]),
                  (surf.get_width() // 2 - 90, 22))
        # Column headers
        headers = [("Rank",60),("Player",220),("Rating",140),
                   ("W",80),("L",80),("D",80),("Games",110),("Acc",100)]
        x = 70
        fh = self.app.assets.get_font(13, bold=True)
        for text, wc in headers:
            surf.blit(fh.render(text, True, c["text_dim"]), (x, 100))
            x += wc
        super().draw(surf)
