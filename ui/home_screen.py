"""Modern home screen with animated background and menu buttons."""
import math
import time
import pygame

from ui.base_screen import Screen
from ui.widgets import Button


MENU = [
    ("Play Online",   "play_online",  True),
    ("Play vs AI",    "play_ai",      True),
    ("Local 2-Player","local_pvp",    True),
    ("Tournament",    "tournament",   True),
    ("Guest Mode",    "guest_mode",   False),
    ("Analysis",      "analysis",     False),
    ("Game History",  "history",      False),
    ("Leaderboard",   "leaderboard",  False),
    ("Profile",       "profile",      False),
    ("Settings",      "settings",     False),
    ("Logout",        "logout",       False),
]


class HomeScreen(Screen):
    def __init__(self, app):
        super().__init__(app)
        self.buttons = []
        self._build_buttons()

    def _build_buttons(self):
        self.buttons.clear()
        for label, action, primary in MENU:
            self.buttons.append(Button((0, 0, 260, 52), label,
                                        lambda a=action: self._action(a),
                                        primary=primary, font_size=17))
        self.widgets = list(self.buttons)

    def _action(self, key):
        self.app.sounds.play("click", 0.4)
        if key == "logout":
            self.app.on_logout()
            return
        self.app.goto(key)

    def on_enter(self, **ctx):
        self._layout()

    def on_resize(self):
        self._layout()

    def _layout(self):
        w, h = self.app.screen.get_size()
        # Menu column: centered horizontally, offset right
        col_x = w // 2 - 130
        start_y = int(h * 0.32)
        gap = 62
        for i, b in enumerate(self.buttons):
            b.rect.topleft = (col_x, start_y + i * gap)

    def update(self, dt):
        self.app.background.draw(self.app.screen, dt)

    def draw(self, surf):
        c = self.app.theme.c
        w, h = surf.get_size()

        # Big title
        title_font = self.app.assets.get_font(96, bold=True)
        title = title_font.render("ChessMaster", True, c["text"])
        surf.blit(title, (w // 2 - title.get_width() // 2, int(h * 0.10)))
        # Subtitle with subtle pulse
        pulse = 0.5 + 0.5 * math.sin(time.time() * 1.5)
        sub_col = tuple(int(a + (b - a) * pulse) for a, b in zip(c["text_dim"], c["accent"]))
        sub = self.app.assets.get_font(22).render(
            "The complete chess experience", True, sub_col)
        surf.blit(sub, (w // 2 - sub.get_width() // 2, int(h * 0.10) + 100))

        # Top-right user chip
        user = self.app.current_user
        chip_font = self.app.assets.get_font(15, bold=True)
        chip_font_s = self.app.assets.get_font(12)
        name = user.get("username", "Guest") if user else "Guest"
        rating = user.get("rating", 1200) if user else "-"
        chip_w = 220
        chip_rect = pygame.Rect(w - chip_w - 20, 20, chip_w, 62)
        pygame.draw.rect(surf, c["panel"], chip_rect, border_radius=10)
        pygame.draw.rect(surf, c["border"], chip_rect, width=1, border_radius=10)
        # Avatar circle
        pygame.draw.circle(surf, c["accent"], (chip_rect.x + 26, chip_rect.centery), 20)
        initial = self.app.assets.get_font(22, bold=True).render(
            name[0].upper(), True, (255, 255, 255))
        surf.blit(initial, initial.get_rect(center=(chip_rect.x + 26, chip_rect.centery)))
        surf.blit(chip_font.render(name, True, c["text"]),
                  (chip_rect.x + 58, chip_rect.y + 10))
        surf.blit(chip_font_s.render(f"Rating: {rating}", True, c["text_dim"]),
                  (chip_rect.x + 58, chip_rect.y + 32))

        # Menu buttons
        super().draw(surf)

        # Footer
        foot_font = self.app.assets.get_font(12)
        foot = foot_font.render("ChessMaster v1.0  —  © 2026", True, c["text_faint"])
        surf.blit(foot, (w // 2 - foot.get_width() // 2, h - 30))
