"""Profile screen: stats, rating graph, achievements, recent games."""
import pygame
from ui.base_screen import Screen
from ui.widgets import Button, ScrollList
from database.db import Database


class ProfileScreen(Screen):
    def __init__(self, app):
        super().__init__(app)
        self.db = Database()
        self.back_btn = Button((0,0,120,36), "← Back",
                                lambda: self.app.goto("home"))
        self.recent_list = ScrollList((0,0,420,260), 34, [], self._row_game)
        self.ach_list = ScrollList((0,0,420,220), 40, [], self._row_ach)
        self.widgets = [self.back_btn, self.recent_list, self.ach_list]
        self.rating_history = []
        self.favorite_opening = "-"

    def on_enter(self, **ctx):
        self._layout()
        user = self.app.current_user
        if user and user.get("id", 0) > 0:
            self.rating_history = [dict(r) for r in
                                   self.db.rating_history(user["id"])]
            recent = self.db.matches_for_user(user["id"], limit=20)
            self.recent_list.set_items([dict(r) for r in recent])
            # Favorite opening
            openings = {}
            for m in recent:
                op = m["opening"] or "Unknown"
                openings[op] = openings.get(op, 0) + 1
            if openings:
                self.favorite_opening = max(openings.items(), key=lambda x: x[1])[0]
            ach = self.db.achievements_for(user["id"])
            self.ach_list.set_items([dict(a) for a in ach])
        else:
            self.rating_history = []
            self.recent_list.set_items([])
            self.ach_list.set_items([])

    def on_resize(self):
        self._layout()

    def _layout(self):
        w, h = self.app.screen.get_size()
        self.back_btn.rect.topleft = (24, 20)
        # Left column = stats card + rating graph
        # Right column = recent games + achievements
        right_x = w - 460
        self.recent_list.rect = pygame.Rect(right_x, 100, 420, 280)
        self.ach_list.rect    = pygame.Rect(right_x, 400, 420, h - 430)

    def _row_game(self, surf, row_rect, i, item, theme, assets):
        c = theme.c
        f = assets.get_font(13)
        surf.blit(f.render(f"{item.get('white_name','?')} vs {item.get('black_name','?')}",
                           True, c["text"]),
                  (row_rect.x + 8, row_rect.y + 4))
        surf.blit(f.render(f"{item.get('result','*')} · {item.get('opening','')[:24]}",
                           True, c["text_dim"]),
                  (row_rect.x + 8, row_rect.y + 20))

    def _row_ach(self, surf, row_rect, i, item, theme, assets):
        c = theme.c
        f = assets.get_font(14, bold=True)
        fs = assets.get_font(12)
        pygame.draw.circle(surf, c["accent"],
                           (row_rect.x + 20, row_rect.centery), 12)
        surf.blit(f.render(item.get("name","?"), True, c["text"]),
                  (row_rect.x + 44, row_rect.y + 4))
        surf.blit(fs.render(item.get("description",""), True, c["text_dim"]),
                  (row_rect.x + 44, row_rect.y + 22))

    def draw(self, surf):
        c = self.app.theme.c
        surf.fill(c["bg"])
        f_title = self.app.assets.get_font(28, bold=True)
        surf.blit(f_title.render("Profile", True, c["text"]),
                  (surf.get_width() // 2 - 50, 22))
        user = self.app.current_user
        if not user or user.get("id", 0) == 0:
            f = self.app.assets.get_font(16)
            surf.blit(f.render("Log in to view your profile.",
                               True, c["text_dim"]),
                      (60, 100))
            super().draw(surf)
            return

        # Big avatar card
        card = pygame.Rect(60, 100, 460, 280)
        pygame.draw.rect(surf, c["panel"], card, border_radius=12)
        pygame.draw.rect(surf, c["border"], card, width=1, border_radius=12)
        pygame.draw.circle(surf, c["accent"],
                           (card.x + 65, card.y + 80), 45)
        f_init = self.app.assets.get_font(48, bold=True)
        i = f_init.render(user["username"][0].upper(), True, (255,255,255))
        surf.blit(i, i.get_rect(center=(card.x + 65, card.y + 80)))
        fb = self.app.assets.get_font(24, bold=True)
        fs = self.app.assets.get_font(15)
        surf.blit(fb.render(user["username"], True, c["text"]),
                  (card.x + 130, card.y + 40))
        surf.blit(fs.render(f"Country: {user.get('country','Unknown')}", True, c["text_dim"]),
                  (card.x + 130, card.y + 76))
        surf.blit(fs.render(f"Joined: {str(user.get('date_joined','?'))[:10]}", True, c["text_dim"]),
                  (card.x + 130, card.y + 100))
        # Stats grid
        stats = [("Rating", user.get("rating", 1200), c["accent"]),
                 ("Peak", user.get("peak_rating", user.get("rating",1200)), c["accent"]),
                 ("Wins", user.get("wins",0), c["success"]),
                 ("Losses", user.get("losses",0), c["error"]),
                 ("Draws", user.get("draws",0), c["text_dim"]),
                 ("Games", user.get("games_played",0), c["text"])]
        for i, (lbl, val, col) in enumerate(stats):
            x = card.x + 20 + (i % 3) * 150
            y = card.y + 160 + (i // 3) * 60
            f2 = self.app.assets.get_font(12)
            f3 = self.app.assets.get_font(22, bold=True)
            surf.blit(f2.render(lbl, True, c["text_dim"]), (x, y))
            surf.blit(f3.render(str(val), True, col), (x, y + 15))

        # Win %
        games = max(1, user.get("games_played",0) or 1)
        win_pct = 100 * (user.get("wins",0) or 0) / games
        f_pct = self.app.assets.get_font(14)
        surf.blit(f_pct.render(f"Win rate: {win_pct:.1f}%   Favorite opening: {self.favorite_opening}",
                                True, c["text_dim"]),
                  (card.x + 20, card.bottom - 30))

        # Rating graph
        gcard = pygame.Rect(60, 400, 460, surf.get_height() - 430)
        pygame.draw.rect(surf, c["panel"], gcard, border_radius=12)
        pygame.draw.rect(surf, c["border"], gcard, width=1, border_radius=12)
        surf.blit(self.app.assets.get_font(16, bold=True).render(
            "Rating over time", True, c["text"]),
            (gcard.x + 14, gcard.y + 10))
        self._draw_rating_graph(surf, pygame.Rect(gcard.x + 14, gcard.y + 40,
                                                   gcard.w - 28, gcard.h - 60))

        # Right column headers
        f_h = self.app.assets.get_font(16, bold=True)
        surf.blit(f_h.render("Recent Games", True, c["text"]),
                  (self.recent_list.rect.x, 78))
        surf.blit(f_h.render("Achievements", True, c["text"]),
                  (self.ach_list.rect.x, self.ach_list.rect.y - 22))

        super().draw(surf)

    def _draw_rating_graph(self, surf, rect):
        c = self.app.theme.c
        pygame.draw.rect(surf, c["bg_alt"], rect, border_radius=8)
        pygame.draw.rect(surf, c["border"], rect, width=1, border_radius=8)
        pts = self.rating_history
        if len(pts) < 2:
            f = self.app.assets.get_font(13)
            surf.blit(f.render("Not enough games yet.", True, c["text_faint"]),
                      (rect.x + 10, rect.y + 10))
            return
        ratings = [p["rating"] for p in pts]
        lo, hi = min(ratings) - 30, max(ratings) + 30
        span = max(1, hi - lo)
        coords = []
        for i, r in enumerate(ratings):
            x = rect.x + int((rect.w - 20) * i / max(1, len(ratings) - 1)) + 10
            y = rect.y + rect.h - 10 - int((r - lo) / span * (rect.h - 20))
            coords.append((x, y))
        pygame.draw.lines(surf, c["accent"], False, coords, 2)
        for p in coords:
            pygame.draw.circle(surf, c["accent"], p, 3)
