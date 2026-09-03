"""Play vs AI setup screen."""
import pygame
from ui.base_screen import Screen
from ui.widgets import Button, Dropdown, Slider
from settings.settings_manager import AI_DIFFICULTIES


class PlayAIScreen(Screen):
    def __init__(self, app):
        super().__init__(app)
        s = app.settings
        self.back_btn = Button((0,0,120,36), "← Back",
                               lambda: self.app.goto("home"))
        self.start_btn = Button((0,0,220,48), "Start Game",
                                self._start, primary=True)
        self.diff_dd = Dropdown((0,0,260,36), list(AI_DIFFICULTIES.keys()),
                                s.get("ai_difficulty"),
                                lambda v: s.set("ai_difficulty", v),
                                label="Difficulty")
        from ui.settings_screen import TIME_CONTROLS
        self.tc_dd = Dropdown((0,0,260,36), TIME_CONTROLS,
                              s.get("time_control"),
                              lambda v: s.set("time_control", v),
                              label="Time Control")
        self.elo_slider = Slider((0,0,300,30), 800, 3200,
                                 s.get_int("ai_elo", 1500),
                                 lambda v: s.set("ai_elo", v),
                                 label="Custom Elo")
        self.widgets = [self.back_btn, self.start_btn, self.diff_dd, self.tc_dd,
                        self.elo_slider]

    def _start(self):
        self.app.goto("game", mode="ai")

    def on_enter(self, **ctx): self._layout()
    def on_resize(self): self._layout()

    def _layout(self):
        w, h = self.app.screen.get_size()
        cx = w // 2
        self.back_btn.rect.topleft = (24, 20)
        self.diff_dd.rect.topleft   = (cx - 130, h//2 - 100)
        self.tc_dd.rect.topleft     = (cx - 130, h//2 - 20)
        self.elo_slider.rect.topleft = (cx - 150, h//2 + 80)
        self.start_btn.rect.topleft = (cx - 110, h//2 + 150)

    def update(self, dt):
        self.app.background.draw(self.app.screen, dt)

    def draw(self, surf):
        c = self.app.theme.c
        f = self.app.assets.get_font(36, bold=True)
        surf.blit(f.render("Play vs AI", True, c["text"]),
                  (surf.get_width() // 2 - 90, 60))
        engine_status = "Stockfish loaded" if self.app.engine.has_stockfish \
                        else "Built-in engine (Stockfish not found)"
        fs = self.app.assets.get_font(13)
        surf.blit(fs.render(engine_status, True, c["text_dim"]),
                  (surf.get_width() // 2 - 120, 110))
        super().draw(surf)
        self.diff_dd.draw_open(surf, self.app.theme, self.app.assets)
        self.tc_dd.draw_open(surf, self.app.theme, self.app.assets)
