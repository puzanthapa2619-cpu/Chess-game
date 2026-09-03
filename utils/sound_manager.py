"""Sound manager (respects the sound/music toggle in settings)."""
import pygame

from utils.assets_manager import AssetManager
from utils.logger import get_logger

log = get_logger("sound")


class SoundManager:
    def __init__(self, assets: AssetManager, settings):
        self.assets = assets
        self.settings = settings

    def play(self, name: str, volume: float = 0.7):
        if not self.settings.get_bool("sound"):
            return
        s = self.assets.get_sound(name)
        if s is not None:
            try:
                s.set_volume(volume)
                s.play()
            except Exception as e:
                log.warning("Play %s failed: %s", name, e)
