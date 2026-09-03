"""Base class for all app screens."""
import pygame


class Screen:
    """Base screen. Subclasses override on_event/draw/update.

    A screen may call self.app.goto('screen_name', **ctx) to switch screens.
    """
    def __init__(self, app):
        self.app = app
        self.widgets = []
        self.deferred_open_dropdown = None  # renders on top

    # lifecycle hooks
    def on_enter(self, **ctx): pass
    def on_exit(self): pass
    def on_resize(self): pass

    def on_event(self, event) -> bool:
        for w in self.widgets:
            if w.handle_event(event):
                return True
        return False

    def update(self, dt): pass

    def draw(self, surf):
        for w in self.widgets:
            w.draw(surf, self.app.theme, self.app.assets)
