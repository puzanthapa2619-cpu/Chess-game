"""Analysis screen. Shows post-game evaluation, classifications, graph."""
import threading
import pygame

from ui.base_screen import Screen
from ui.widgets import Button, ScrollList
from analysis.analyzer import GameAnalyzer
from analysis.export import export_analysis_pdf
from database.db import Database
import chess

CLASS_COLORS = {
    "brilliant":   (0, 220, 200),
    "great":       (0, 180, 220),
    "best":        (80, 200, 80),
    "excellent":   (120, 210, 120),
    "good":        (170, 210, 130),
    "book":        (200, 180, 130),
    "inaccuracy":  (240, 200, 90),
    "mistake":     (240, 150, 60),
    "blunder":     (220, 70, 70),
    "missed_win":  (200, 100, 200),
    "missed_mate": (255, 60, 60),
}


class AnalysisScreen(Screen):
    def __init__(self, app):
        super().__init__(app)
        self.db = Database()
        self.result = None
        self.moves_uci = []
        self.white = "White"; self.black = "Black"; self.game_result = "*"
        self.match_id = None
        self.progress = (0, 0)
        self.thread = None

        self.back_btn  = Button((0,0,120,36), "← Back",
                                 lambda: self.app.goto("home"))
        self.pdf_btn   = Button((0,0,160,36), "Export PDF Report",
                                 self._export_pdf, primary=True)
        self.list = ScrollList((0,0,340,400), 24, [], self._render_row)

    def on_enter(self, moves_uci=None, white="White", black="Black",
                 result="*", match_id=None, **ctx):
        self.moves_uci = moves_uci or []
        self.white = white; self.black = black; self.game_result = result
        self.match_id = match_id
        self.result = None
        self.progress = (0, len(self.moves_uci))
        self._layout()
        # Start analysis thread
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def on_resize(self):
        self._layout()

    def _layout(self):
        w, h = self.app.screen.get_size()
        self.back_btn.rect.topleft = (24, 20)
        self.pdf_btn.rect.topleft  = (w - 180, 20)
        # Moves list on right side
        self.list.rect = pygame.Rect(w - 380, 90, 340, h - 130)
        self.widgets = [self.back_btn, self.pdf_btn, self.list]

    def _run(self):
        analyzer = GameAnalyzer(self.app.engine, time_per_move=0.20)
        def prog(i, n): self.progress = (i, n)
        try:
            data = analyzer.analyze(self.moves_uci, progress_callback=prog)
            self.result = data
            self.list.set_items(data.get("classification_json", []))
            if self.match_id:
                try:
                    self.db.save_analysis(self.match_id, data)
                except Exception:
                    pass
        except Exception as e:
            from utils.logger import get_logger
            get_logger("analysis").error("Analysis failed: %s", e)

    def _export_pdf(self):
        if not self.result: return
        import os, time as _t
        os.makedirs("exports", exist_ok=True)
        path = os.path.join("exports", f"analysis_{int(_t.time())}.pdf")
        meta = {"white_name": self.white, "black_name": self.black,
                "result": self.game_result}
        real = export_analysis_pdf(path, meta, self.result)
        self.app.toast(f"Report saved to {real}")

    def _render_row(self, surf, row_rect, i, item, theme, assets):
        c = theme.c
        f = assets.get_font(13)
        cls = item["classification"]
        col = CLASS_COLORS.get(cls, c["text"])
        surf.blit(f.render(f"{item['ply']:>3}.", True, c["text_dim"]),
                  (row_rect.x + 6, row_rect.y + 5))
        surf.blit(f.render(item["san"], True, c["text"]),
                  (row_rect.x + 45, row_rect.y + 5))
        surf.blit(f.render(cls.replace("_", " "), True, col),
                  (row_rect.x + 110, row_rect.y + 5))
        surf.blit(f.render(f"cpl {item['cp_loss']}", True, c["text_dim"]),
                  (row_rect.x + 230, row_rect.y + 5))

    def update(self, dt):
        pass

    def draw(self, surf):
        c = self.app.theme.c
        surf.fill(c["bg"])
        w, h = surf.get_size()
        # Header
        f_title = self.app.assets.get_font(28, bold=True)
        surf.blit(f_title.render("Game Analysis", True, c["text"]),
                  (w // 2 - 100, 22))
        # Progress or summary
        if self.result is None:
            i, n = self.progress
            f = self.app.assets.get_font(18)
            surf.blit(f.render(f"Analyzing... {i}/{n}", True, c["text_dim"]),
                      (60, 100))
            # Progress bar
            bar = pygame.Rect(60, 140, 400, 14)
            pygame.draw.rect(surf, c["chip"], bar, border_radius=7)
            if n > 0:
                fill = bar.copy(); fill.w = int(bar.w * i / max(1, n))
                pygame.draw.rect(surf, c["accent"], fill, border_radius=7)
        else:
            self._draw_summary(surf)
            self._draw_graph(surf)
        super().draw(surf)

    def _draw_summary(self, surf):
        c = self.app.theme.c
        r = self.result
        f = self.app.assets.get_font(16)
        fb = self.app.assets.get_font(20, bold=True)
        surf.blit(fb.render(f"{self.white}  vs  {self.black}   ({self.game_result})",
                            True, c["text"]),
                  (60, 88))
        surf.blit(f.render(f"Opening: {r.get('opening','?')}", True, c["text_dim"]),
                  (60, 118))
        # Accuracy blocks
        y = 155
        for label, key in (("White Accuracy", "accuracy_white"),
                           ("Black Accuracy", "accuracy_black")):
            surf.blit(f.render(f"{label}: {r[key]}%", True, c["accent"]),
                      (60, y))
            y += 24
        y += 8
        surf.blit(f.render(f"Avg CPL W/B: {r['avg_cp_loss_white']} / {r['avg_cp_loss_black']}",
                           True, c["text_dim"]), (60, y))
        y += 30
        # Counts
        cats = [("brilliant","Brilliant"),("great","Great"),("best","Best"),
                ("excellent","Excellent"),("good","Good"),("book","Book"),
                ("inaccuracy","Inaccuracy"),("mistake","Mistake"),
                ("blunder","Blunder"),("missed_win","Missed Win"),
                ("missed_mate","Missed Mate")]
        for i, (k, lbl) in enumerate(cats):
            col = CLASS_COLORS.get(k, c["text"])
            dot = pygame.Rect(60, y + 5, 10, 10)
            pygame.draw.rect(surf, col, dot, border_radius=3)
            surf.blit(f.render(f"{lbl}: {r.get(k,0)}", True, c["text"]),
                      (78, y))
            y += 22

    def _draw_graph(self, surf):
        c = self.app.theme.c
        r = self.result
        evals = r.get("evaluation_json", [])
        if not evals: return
        # Graph rect
        gx = 60; gy = surf.get_height() - 230
        gw = surf.get_width() - 480; gh = 180
        pygame.draw.rect(surf, c["bg_alt"], (gx, gy, gw, gh), border_radius=8)
        pygame.draw.rect(surf, c["border"], (gx, gy, gw, gh), width=1, border_radius=8)
        # Zero line
        mid_y = gy + gh // 2
        pygame.draw.line(surf, c["text_faint"], (gx, mid_y), (gx + gw, mid_y), 1)
        # Clamp evals to ±1000 cp for display
        pts = []
        for i, e in enumerate(evals):
            e = max(-1000, min(1000, e))
            x = gx + int(gw * i / max(1, len(evals) - 1))
            y = mid_y - int((e / 1000) * (gh // 2 - 6))
            pts.append((x, y))
        # Fill under curve
        fill_pts = [(gx, mid_y)] + pts + [(gx + gw, mid_y)]
        area = pygame.Surface((gw, gh), pygame.SRCALPHA)
        adj = [(p[0] - gx, p[1] - gy) for p in fill_pts]
        pygame.draw.polygon(area, (129, 182, 76, 90), adj)
        surf.blit(area, (gx, gy))
        if len(pts) > 1:
            pygame.draw.lines(surf, c["accent"], False, pts, 2)
        # Title
        f = self.app.assets.get_font(14, bold=True)
        surf.blit(f.render("Evaluation Graph (cp)", True, c["text"]),
                  (gx + 6, gy - 22))
