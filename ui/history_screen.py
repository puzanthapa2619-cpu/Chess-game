"""Game history screen: list of past games with replay."""
import pygame
from ui.base_screen import Screen
from ui.widgets import Button, ScrollList
from database.db import Database


class HistoryScreen(Screen):
    def __init__(self, app):
        super().__init__(app)
        self.db = Database()
        self.back_btn = Button((0,0,120,36), "← Back",
                                lambda: self.app.goto("home"))
        self.list = ScrollList((0,0,900,500), 40, [], self._row,
                                on_click=self._on_click)
        self.widgets = [self.back_btn, self.list]

    def on_enter(self, **ctx):
        self._layout()
        self._reload()

    def on_resize(self):
        self._layout()

    def _layout(self):
        w, h = self.app.screen.get_size()
        self.back_btn.rect.topleft = (24, 20)
        self.list.rect = pygame.Rect(60, 90, w - 120, h - 130)

    def _reload(self):
        user = self.app.current_user
        if not user or user.get("id", 0) == 0:
            self.list.set_items([])
            return
        rows = self.db.matches_for_user(user["id"], limit=200)
        self.list.set_items([dict(r) for r in rows])

    def _on_click(self, i, item):
        # Open analysis of the match
        rows = self.db.moves_for_match(item["id"])
        moves_uci = [r["uci"] for r in rows]
        self.app.goto("analysis",
                      moves_uci=moves_uci,
                      white=item.get("white_name","White"),
                      black=item.get("black_name","Black"),
                      result=item.get("result","*"),
                      match_id=item["id"])

    def _row(self, surf, row_rect, i, item, theme, assets):
        c = theme.c
        f = assets.get_font(14)
        fb = assets.get_font(14, bold=True)
        # Date
        surf.blit(f.render(str(item.get("date_played","?"))[:16], True, c["text_dim"]),
                  (row_rect.x + 12, row_rect.y + 6))
        # Names
        surf.blit(fb.render(f"{item.get('white_name','White')}  vs  {item.get('black_name','Black')}",
                            True, c["text"]),
                  (row_rect.x + 200, row_rect.y + 6))
        # Result
        surf.blit(f.render(item.get("result","*"), True, c["accent"]),
                  (row_rect.x + row_rect.w - 200, row_rect.y + 6))
        # Termination + opening
        info = f"{item.get('termination','')} · {item.get('opening','')} · {item.get('mode','')}"
        surf.blit(f.render(info, True, c["text_dim"]),
                  (row_rect.x + 200, row_rect.y + 24))

    def update(self, dt):
        pass

    def draw(self, surf):
        c = self.app.theme.c
        surf.fill(c["bg"])
        f = self.app.assets.get_font(28, bold=True)
        surf.blit(f.render("Game History", True, c["text"]),
                  (surf.get_width() // 2 - 100, 22))
        if not self.app.current_user or self.app.current_user.get("id", 0) == 0:
            fs = self.app.assets.get_font(16)
            surf.blit(fs.render("Guest mode: history is not saved.",
                                True, c["text_dim"]),
                      (60, 100))
        super().draw(surf)
