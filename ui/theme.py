"""Colour palette + fonts for the ChessMaster UI (dark & light modes)."""


DARK = {
    "bg":         (24, 26, 27),
    "bg_alt":     (32, 34, 36),
    "panel":      (40, 42, 45),
    "panel_hi":   (56, 59, 63),
    "border":     (18, 20, 22),
    "text":       (232, 232, 230),
    "text_dim":   (170, 168, 165),
    "text_faint": (120, 118, 116),
    "accent":     (129, 182, 76),     # chess.com green
    "accent_hi":  (149, 202, 96),
    "accent_alt": (65, 130, 205),     # blue for links
    "warn":       (240, 180, 80),
    "error":      (232, 76, 76),
    "success":    (110, 200, 130),
    "chip":       (60, 63, 68),
}

LIGHT = {
    "bg":         (245, 244, 240),
    "bg_alt":     (255, 254, 250),
    "panel":      (255, 255, 255),
    "panel_hi":   (238, 238, 232),
    "border":     (200, 198, 190),
    "text":       (34, 34, 30),
    "text_dim":   (100, 100, 96),
    "text_faint": (150, 150, 145),
    "accent":     (129, 182, 76),
    "accent_hi":  (109, 162, 60),
    "accent_alt": (48, 110, 190),
    "warn":       (200, 140, 40),
    "error":      (200, 50, 50),
    "success":    (60, 160, 90),
    "chip":       (220, 220, 214),
}


class Theme:
    def __init__(self, settings):
        self.settings = settings

    @property
    def mode(self):
        return self.settings.get("theme_mode", "dark")

    @property
    def c(self):
        return DARK if self.mode == "dark" else LIGHT
