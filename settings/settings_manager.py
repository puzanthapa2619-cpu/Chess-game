"""Settings manager backed by the global_settings SQLite table."""
from typing import Any
from database.db import Database

DEFAULTS = {
    "theme_mode":      "dark",           # dark / light
    "piece_theme":     "classic",
    "board_theme":     "green",
    "show_coords":     True,
    "show_legal":      True,
    "highlight_last":  True,
    "animate":         True,
    "animation_speed": "normal",         # slow/normal/fast
    "sound":           True,
    "music":           False,
    "fullscreen":      True,
    "resolution":      "1600x900",
    "fps":             60,
    "language":        "English",
    "flip_board":      False,
    "ai_difficulty":   "Normal",
    "ai_elo":          1500,
    "stockfish_path":  "",
    "increment":       0,
    "time_control":    "10+0",           # minutes+increment
    "auto_promote_queen": False,
    "hint_enabled":    True,
    "current_user_id": 0,                # 0 = guest / logged out
}


class SettingsManager:
    def __init__(self):
        self.db = Database()
        # Seed defaults if missing
        for k, v in DEFAULTS.items():
            if self.db.get_setting(k, None) is None:
                self.db.set_setting(k, v)
        self._cache = {k: self.db.get_setting(k, v) for k, v in DEFAULTS.items()}

    def get(self, key: str, default: Any = None) -> Any:
        if key not in self._cache:
            self._cache[key] = self.db.get_setting(key, default)
        return self._cache.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._cache[key] = value
        self.db.set_setting(key, value)

    def get_bool(self, key: str) -> bool:
        v = self.get(key, False)
        return bool(v) if not isinstance(v, str) else v.lower() in ("1", "true", "yes")

    def get_int(self, key: str, default: int = 0) -> int:
        try:
            return int(self.get(key, default))
        except (TypeError, ValueError):
            return default

    def resolution_tuple(self) -> tuple:
        try:
            w, h = self.get("resolution", "1600x900").split("x")
            return (int(w), int(h))
        except Exception:
            return (1600, 900)


# Difficulty presets mapping to Skill Level / Elo
AI_DIFFICULTIES = {
    "Beginner":     {"skill":  0, "elo":  800, "depth": 1, "time": 0.1},
    "Easy":         {"skill":  3, "elo": 1100, "depth": 3, "time": 0.15},
    "Normal":       {"skill":  8, "elo": 1500, "depth": 6, "time": 0.3},
    "Hard":         {"skill": 13, "elo": 1800, "depth": 10, "time": 0.6},
    "Expert":       {"skill": 17, "elo": 2100, "depth": 14, "time": 1.0},
    "Master":       {"skill": 20, "elo": 2400, "depth": 18, "time": 1.5},
    "Grandmaster":  {"skill": 20, "elo": 2700, "depth": 22, "time": 2.5},
    "Custom":       {"skill": 10, "elo": 1500, "depth": 8, "time": 0.5},
}
