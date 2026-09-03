"""Animated gradient background with drifting chess-piece silhouettes."""
import math
import random
import time
import pygame


class AnimatedBackground:
    def __init__(self, assets, settings):
        self.assets = assets
        self.settings = settings
        self.particles = []
        self.last_size = (0, 0)
        self.start = time.time()

    def _spawn(self, w, h):
        codes = ["wK","wQ","wN","wB","bK","bQ","bN","bB"]
        self.particles = []
        for _ in range(14):
            self.particles.append({
                "code": random.choice(codes),
                "x": random.uniform(0, w),
                "y": random.uniform(0, h),
                "vx": random.uniform(-15, 15),
                "vy": random.uniform(-10, 10),
                "size": random.randint(70, 130),
                "alpha": random.randint(15, 40),
                "rot": random.uniform(0, 360),
                "vrot": random.uniform(-5, 5),
            })
        self.last_size = (w, h)

    def draw(self, surf, dt):
        w, h = surf.get_size()
        if (w, h) != self.last_size:
            self._spawn(w, h)

        # Gradient background
        mode = self.settings.get("theme_mode", "dark")
        if mode == "dark":
            top    = (18, 22, 30)
            bottom = (10, 12, 18)
        else:
            top    = (240, 240, 235)
            bottom = (215, 218, 214)
        # Simple vertical gradient
        for y in range(0, h, 4):
            t = y / max(1, h)
            col = (int(top[0] + (bottom[0]-top[0]) * t),
                   int(top[1] + (bottom[1]-top[1]) * t),
                   int(top[2] + (bottom[2]-top[2]) * t))
            pygame.draw.rect(surf, col, (0, y, w, 4))

        # Drifting pieces
        theme = self.settings.get("piece_theme", "classic")
        for p in self.particles:
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            p["rot"] += p["vrot"] * dt
            if p["x"] < -150: p["x"] = w + 100
            if p["x"] > w + 150: p["x"] = -100
            if p["y"] < -150: p["y"] = h + 100
            if p["y"] > h + 150: p["y"] = -100
            img = self.assets.get_piece(theme, p["code"], p["size"])
            if img:
                s = img.copy()
                s.set_alpha(p["alpha"])
                rotated = pygame.transform.rotate(s, p["rot"])
                surf.blit(rotated,
                          rotated.get_rect(center=(int(p["x"]), int(p["y"]))))
