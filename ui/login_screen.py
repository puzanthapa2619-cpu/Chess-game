"""Login screen."""
import pygame
from ui.base_screen import Screen
from ui.widgets import Button, TextInput, Panel
from auth.auth_service import AuthService


class LoginScreen(Screen):
    def __init__(self, app):
        super().__init__(app)
        self.auth = AuthService()
        self.error = ""
        self.info = ""
        self.username_or_email = TextInput((0, 0, 320, 40), "Username or Email")
        self.password = TextInput((0, 0, 320, 40), "Password", password=True,
                                  on_submit=self._submit)
        self.login_btn = Button((0, 0, 320, 44), "Log In", self._submit, primary=True)
        self.register_btn = Button((0, 0, 155, 38), "Create Account",
                                   lambda: app.goto("register"))
        self.guest_btn = Button((0, 0, 155, 38), "Play as Guest",
                                lambda: app.enter_guest_mode())
        self.widgets = [self.username_or_email, self.password, self.login_btn,
                        self.register_btn, self.guest_btn]

    def on_enter(self, **ctx):
        self.info = ctx.get("info", "")
        self.error = ""
        self._layout()

    def on_resize(self):
        self._layout()

    def _layout(self):
        w, h = self.app.screen.get_size()
        cx = w // 2
        cy = h // 2
        # Center card
        self.username_or_email.rect.topleft = (cx - 160, cy - 60)
        self.password.rect.topleft = (cx - 160, cy - 8)
        self.login_btn.rect.topleft = (cx - 160, cy + 50)
        self.register_btn.rect.topleft = (cx - 160, cy + 108)
        self.guest_btn.rect.topleft = (cx + 5, cy + 108)

    def _submit(self):
        ok, msg, user = self.auth.login(
            self.username_or_email.text.strip(),
            self.password.text)
        if ok:
            self.app.on_login(user)
        else:
            self.error = msg
            self.info = ""

    def update(self, dt):
        self.app.background.draw(self.app.screen, dt)

    def draw(self, surf):
        c = self.app.theme.c
        w, h = surf.get_size()

        # Title
        title_font = self.app.assets.get_font(56, bold=True)
        title = title_font.render("ChessMaster", True, c["text"])
        surf.blit(title, (w // 2 - title.get_width() // 2, h // 2 - 220))
        sub = self.app.assets.get_font(18).render(
            "Play. Learn. Master.", True, c["text_dim"])
        surf.blit(sub, (w // 2 - sub.get_width() // 2, h // 2 - 165))

        # Card background
        card_rect = pygame.Rect(w // 2 - 200, h // 2 - 100, 400, 300)
        pygame.draw.rect(surf, c["panel"], card_rect, border_radius=12)
        pygame.draw.rect(surf, c["border"], card_rect, width=1, border_radius=12)

        super().draw(surf)

        # Error/info
        if self.error:
            f = self.app.assets.get_font(14)
            surf.blit(f.render(self.error, True, c["error"]),
                      (w // 2 - 160, h // 2 + 160))
        if self.info:
            f = self.app.assets.get_font(14)
            surf.blit(f.render(self.info, True, c["success"]),
                      (w // 2 - 160, h // 2 + 160))
