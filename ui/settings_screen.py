"""Settings screen."""
import pygame

from ui.base_screen import Screen
from ui.widgets import Button, Toggle, Dropdown, Slider, Panel
from utils.assets_manager import list_piece_themes, list_board_themes
from settings.settings_manager import AI_DIFFICULTIES

RESOLUTIONS = ["1280x720", "1366x768", "1600x900", "1920x1080", "2560x1440"]
FPS_OPTIONS = ["30", "60", "90", "120", "144"]
LANGUAGES  = ["English", "Spanish", "French", "German", "Portuguese",
              "Russian", "Hindi", "Chinese", "Japanese", "Nepali"]
ANIM_SPEEDS = ["slow", "normal", "fast"]
THEME_MODES = ["dark", "light"]
TIME_CONTROLS = ["1+0", "3+0", "3+2", "5+0", "5+3", "10+0", "10+5", "15+10",
                 "30+0", "60+0"]


class SettingsScreen(Screen):
    def __init__(self, app):
        super().__init__(app)
        self.dropdowns = []
        self._build()

    def _build(self):
        s = self.app.settings
        self.back_btn = Button((0,0,120,38), "← Back",
                               lambda: self.app.goto("home"))
        self.save_btn = Button((0,0,140,38), "Save & Close",
                               self._save, primary=True)

        self.mode_dd  = Dropdown((0,0,220,32), THEME_MODES,
                                 s.get("theme_mode"),
                                 lambda v: (s.set("theme_mode", v)),
                                 label="Appearance")
        self.piece_dd = Dropdown((0,0,220,32), list_piece_themes(),
                                 s.get("piece_theme"),
                                 lambda v: s.set("piece_theme", v),
                                 label="Piece Theme")
        self.board_dd = Dropdown((0,0,220,32), list_board_themes(),
                                 s.get("board_theme"),
                                 lambda v: s.set("board_theme", v),
                                 label="Board Theme")
        self.anim_dd  = Dropdown((0,0,220,32), ANIM_SPEEDS,
                                 s.get("animation_speed"),
                                 lambda v: s.set("animation_speed", v),
                                 label="Animation Speed")
        self.res_dd   = Dropdown((0,0,220,32), RESOLUTIONS,
                                 s.get("resolution"),
                                 self._on_res,
                                 label="Resolution")
        self.fps_dd   = Dropdown((0,0,220,32), FPS_OPTIONS,
                                 str(s.get("fps")),
                                 lambda v: s.set("fps", int(v)),
                                 label="Target FPS")
        self.lang_dd  = Dropdown((0,0,220,32), LANGUAGES,
                                 s.get("language"),
                                 lambda v: s.set("language", v),
                                 label="Language")
        self.tc_dd    = Dropdown((0,0,220,32), TIME_CONTROLS,
                                 s.get("time_control"),
                                 lambda v: s.set("time_control", v),
                                 label="Time Control")
        self.diff_dd  = Dropdown((0,0,220,32), list(AI_DIFFICULTIES.keys()),
                                 s.get("ai_difficulty"),
                                 lambda v: s.set("ai_difficulty", v),
                                 label="AI Difficulty")
        self.dropdowns = [self.mode_dd, self.piece_dd, self.board_dd,
                          self.anim_dd, self.res_dd, self.fps_dd,
                          self.lang_dd, self.tc_dd, self.diff_dd]

        self.toggles = [
            Toggle((0,0,220,28), "Show Coordinates",
                   s.get_bool("show_coords"),
                   lambda v: s.set("show_coords", v)),
            Toggle((0,0,220,28), "Show Legal Moves",
                   s.get_bool("show_legal"),
                   lambda v: s.set("show_legal", v)),
            Toggle((0,0,220,28), "Highlight Last Move",
                   s.get_bool("highlight_last"),
                   lambda v: s.set("highlight_last", v)),
            Toggle((0,0,220,28), "Piece Animations",
                   s.get_bool("animate"),
                   lambda v: s.set("animate", v)),
            Toggle((0,0,220,28), "Sound Effects",
                   s.get_bool("sound"),
                   lambda v: s.set("sound", v)),
            Toggle((0,0,220,28), "Background Music",
                   s.get_bool("music"),
                   self._toggle_music),
            Toggle((0,0,220,28), "Fullscreen",
                   s.get_bool("fullscreen"),
                   self._toggle_fs),
            Toggle((0,0,220,28), "Auto-promote to Queen",
                   s.get_bool("auto_promote_queen"),
                   lambda v: s.set("auto_promote_queen", v)),
            Toggle((0,0,220,28), "Enable Hints",
                   s.get_bool("hint_enabled"),
                   lambda v: s.set("hint_enabled", v)),
        ]

        self.elo_slider = Slider((0,0,300,30), 800, 3200, s.get_int("ai_elo", 1500),
                                 lambda v: s.set("ai_elo", v),
                                 label="Custom AI Elo (used with 'Custom')")

        self.widgets = [self.back_btn, self.save_btn, self.elo_slider,
                        *self.dropdowns, *self.toggles]

    def _toggle_music(self, v):
        self.app.settings.set("music", v)
        self.app.toggle_music(v)

    def _toggle_fs(self, v):
        self.app.settings.set("fullscreen", v)
        self.app.apply_display_mode()

    def _on_res(self, v):
        self.app.settings.set("resolution", v)
        self.app.apply_display_mode()
        self._layout()

    def _save(self):
        self.app.apply_display_mode()
        self.app.goto("home")

    def on_enter(self, **ctx):
        self._layout()

    def on_resize(self):
        self._layout()

    def _layout(self):
        w, h = self.app.screen.get_size()
        self.back_btn.rect.topleft = (24, 20)
        self.save_btn.rect.topleft = (w - 160, 20)

        # 3 columns of settings
        col_gap = 40
        col_w = 240
        total_w = col_w * 3 + col_gap * 2
        col_x = [(w - total_w) // 2 + i * (col_w + col_gap) for i in range(3)]
        y_top = 145

        # Col 1 : appearance dropdowns
        col1 = [self.mode_dd, self.piece_dd, self.board_dd, self.anim_dd]
        for i, d in enumerate(col1):
            d.rect.topleft = (col_x[0], y_top + i * 70)

        # Col 2 : system dropdowns
        col2 = [self.res_dd, self.fps_dd, self.lang_dd, self.tc_dd, self.diff_dd]
        for i, d in enumerate(col2):
            d.rect.topleft = (col_x[1], y_top + i * 70)

        # Col 3 : toggles
        for i, t in enumerate(self.toggles):
            t.rect.topleft = (col_x[2], y_top + i * 40)

        # Slider below
        self.elo_slider.rect.topleft = (col_x[1], y_top + 5 * 70 + 20)

    def update(self, dt):
        self.app.background.draw(self.app.screen, dt)

    def draw(self, surf):
        c = self.app.theme.c
        w, h = surf.get_size()
        # Header
        title = self.app.assets.get_font(38, bold=True).render(
            "Settings", True, c["text"])
        surf.blit(title, (w // 2 - title.get_width() // 2, 30))

        # Card
        card_rect = pygame.Rect(60, 100, w - 120, h - 160)
        pygame.draw.rect(surf, c["panel"], card_rect, border_radius=12)
        pygame.draw.rect(surf, c["border"], card_rect, width=1, border_radius=12)

        # Column headers
        f = self.app.assets.get_font(18, bold=True)
        col_gap = 40; col_w = 240
        total_w = col_w * 3 + col_gap * 2
        col_x = [(w - total_w) // 2 + i * (col_w + col_gap) for i in range(3)]
        surf.blit(f.render("Appearance", True, c["accent"]), (col_x[0], 100))
        surf.blit(f.render("System & Game", True, c["accent"]), (col_x[1], 100))
        surf.blit(f.render("Options", True, c["accent"]), (col_x[2], 100))

        super().draw(surf)

        # Any open dropdown on top
        for d in self.dropdowns:
            d.draw_open(surf, self.app.theme, self.app.assets)
