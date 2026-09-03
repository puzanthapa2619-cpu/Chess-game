"""ChessMaster - main entry point.

Boots pygame, initializes services, dispatches between screens.
"""
import os
import sys
import time
import pygame

# Make sub-packages importable when run from project root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.logger import get_logger
from utils.paths import IMAGES, SOUNDS
from utils.assets_manager import AssetManager
from utils.sound_manager import SoundManager
from settings.settings_manager import SettingsManager
from database.db import Database
from engine.engine_manager import EngineManager
from ui.theme import Theme
from ui.animated_background import AnimatedBackground

log = get_logger("app")


class ChessMasterApp:
    def __init__(self):
        pygame.init()
        try:
            pygame.mixer.init()
        except Exception as e:
            log.warning("Mixer init failed: %s", e)

        pygame.display.set_caption("ChessMaster")
        self.settings = SettingsManager()
        self.db = Database()

        self.screen = self._make_display()
        self.clock = pygame.time.Clock()

        self.assets = AssetManager()
        self.sounds = SoundManager(self.assets, self.settings)
        self.theme = Theme(self.settings)
        self.background = AnimatedBackground(self.assets, self.settings)
        self.engine = EngineManager(self.settings.get("stockfish_path", ""))

        self.current_user = self._restore_user()

        # Online session state
        self.online_my_color = True
        self.online_white_name = "White"
        self.online_black_name = "Black"

        # Screens (lazy loaded)
        self._screens = {}
        self.screen_name = None
        self.screen_obj = None

        # Toast
        self._toast_text = ""
        self._toast_until = 0

        # Start on login (or home if already logged in)
        if self.current_user:
            self.goto("home")
        else:
            self.goto("login")

    def _restore_user(self):
        uid = self.settings.get("current_user_id", 0)
        if uid:
            row = self.db.user_by_id(uid)
            if row:
                d = dict(row)
                d.pop("password_hash", None)
                d.pop("verify_code", None)
                return d
        return None

    # ---------- display ----------
    def _make_display(self):
        fs = self.settings.get_bool("fullscreen")
        w, h = self.settings.resolution_tuple()
        flags = pygame.RESIZABLE
        if fs:
            flags |= pygame.FULLSCREEN
            # Use current monitor size when fullscreen
            info = pygame.display.Info()
            w = info.current_w or w
            h = info.current_h or h
        return pygame.display.set_mode((w, h), flags)

    def apply_display_mode(self):
        self.screen = self._make_display()
        self.assets.invalidate_size()
        if self.screen_obj:
            self.screen_obj.on_resize()

    def toggle_music(self, on: bool):
        # Music is optional; no music file bundled by default.
        # Users can drop a file at assets/sounds/music.ogg and it will loop.
        try:
            if on:
                mp = os.path.join(SOUNDS, "music.ogg")
                if os.path.exists(mp):
                    pygame.mixer.music.load(mp)
                    pygame.mixer.music.set_volume(0.4)
                    pygame.mixer.music.play(-1)
            else:
                pygame.mixer.music.stop()
        except Exception as e:
            log.warning("Music toggle: %s", e)

    # ---------- screens ----------
    def _make_screen(self, name: str):
        if name == "login":
            from ui.login_screen import LoginScreen; return LoginScreen(self)
        if name == "register":
            from ui.register_screen import RegisterScreen; return RegisterScreen(self)
        if name == "home":
            from ui.home_screen import HomeScreen; return HomeScreen(self)
        if name == "settings":
            from ui.settings_screen import SettingsScreen; return SettingsScreen(self)
        if name == "play_ai":
            from ui.play_ai_screen import PlayAIScreen; return PlayAIScreen(self)
        if name == "play_online":
            from ui.play_online_screen import PlayOnlineScreen; return PlayOnlineScreen(self)
        if name == "tournament":
            from ui.tournament_screen import TournamentScreen; return TournamentScreen(self)
        if name == "tournament_result":
            from ui.tournament_result_screen import TournamentResultScreen; return TournamentResultScreen(self)
        if name == "game":
            from ui.game_screen import GameScreen; return GameScreen(self)
        if name == "analysis":
            from ui.analysis_screen import AnalysisScreen; return AnalysisScreen(self)
        if name == "history":
            from ui.history_screen import HistoryScreen; return HistoryScreen(self)
        if name == "leaderboard":
            from ui.leaderboard_screen import LeaderboardScreen; return LeaderboardScreen(self)
        if name == "profile":
            from ui.profile_screen import ProfileScreen; return ProfileScreen(self)
        raise ValueError(f"Unknown screen: {name}")

    def goto(self, name: str, **ctx):
        # Guest routing
        if name == "guest_mode":
            self.current_user = {"id": 0, "username": "Guest", "rating": 1200,
                                 "wins": 0, "losses": 0, "draws": 0,
                                 "games_played": 0, "accuracy": 0}
            name = "play_ai"

        # Local hot-seat: two players, one device, no lobby screen needed.
        if name == "local_pvp":
            return self.goto("game", mode="local")

        # Some screens are login-required
        if name in ("history", "leaderboard", "profile", "play_online", "tournament") \
                and (not self.current_user or self.current_user.get("id", 0) == 0):
            if name == "leaderboard":
                pass  # allow guest
            else:
                self.toast("Please log in to access this feature.")
                if not self.current_user:
                    return self.goto("login")

        if self.screen_obj:
            self.screen_obj.on_exit()
        if name not in self._screens:
            self._screens[name] = self._make_screen(name)
        self.screen_obj = self._screens[name]
        self.screen_name = name
        self.screen_obj.on_enter(**ctx)

    # ---------- auth flow ----------
    def on_login(self, user_dict):
        self.current_user = user_dict
        self.settings.set("current_user_id", user_dict.get("id", 0))
        self.goto("home")

    def enter_guest_mode(self):
        self.current_user = {"id": 0, "username": "Guest", "rating": 1200,
                             "wins": 0, "losses": 0, "draws": 0,
                             "games_played": 0, "accuracy": 0}
        self.goto("home")

    def on_logout(self):
        self.settings.set("current_user_id", 0)
        self.current_user = None
        self._screens = {}   # reset all screens
        self.goto("login")

    # ---------- toast ----------
    def toast(self, text: str, duration: float = 3.0):
        self._toast_text = text
        self._toast_until = time.time() + duration

    def _draw_toast(self, surf):
        if not self._toast_text or time.time() > self._toast_until:
            return
        f = self.assets.get_font(15, bold=True)
        t = f.render(self._toast_text, True, (255, 255, 255))
        pad = 14
        rect = pygame.Rect(0, 0, t.get_width() + pad * 2, t.get_height() + pad)
        rect.midbottom = (surf.get_width() // 2, surf.get_height() - 30)
        pygame.draw.rect(surf, (20, 20, 20), rect, border_radius=8)
        pygame.draw.rect(surf, self.theme.c["accent"], rect, width=2, border_radius=8)
        surf.blit(t, t.get_rect(center=rect.center))

    # ---------- main loop ----------
    def run(self):
        running = True
        while running:
            dt = self.clock.tick(self.settings.get_int("fps", 60)) / 1000.0
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    running = False; break
                if e.type == pygame.VIDEORESIZE:
                    if not self.settings.get_bool("fullscreen"):
                        self.screen = pygame.display.set_mode(
                            (max(1024, e.w), max(680, e.h)), pygame.RESIZABLE)
                        self.assets.invalidate_size()
                        if self.screen_obj:
                            self.screen_obj.on_resize()
                    continue
                if e.type == pygame.KEYDOWN and e.key == pygame.K_F11:
                    self.settings.set("fullscreen", not self.settings.get_bool("fullscreen"))
                    self.apply_display_mode(); continue
                if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                    if self.screen_name not in ("home", "login"):
                        self.goto("home"); continue
                if self.screen_obj:
                    self.screen_obj.on_event(e)

            if self.screen_obj:
                self.screen_obj.update(dt)
                self.screen_obj.draw(self.screen)
            self._draw_toast(self.screen)
            pygame.display.flip()

        try:
            self.engine.close()
        except Exception:
            pass
        pygame.quit()


def main():
    try:
        ChessMasterApp().run()
    except Exception as e:
        log.exception("Fatal error: %s", e)
        raise


if __name__ == "__main__":
    main()
