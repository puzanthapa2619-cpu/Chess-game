"""Registration screen with email verification popup."""
import pygame
from ui.base_screen import Screen
from ui.widgets import Button, TextInput
from auth.auth_service import AuthService


class RegisterScreen(Screen):
    def __init__(self, app):
        super().__init__(app)
        self.auth = AuthService()
        self.error = ""
        self.info = ""
        self.pending_uid = None
        self.pending_code_fallback = None

        self.username = TextInput((0,0,340,38), "Username (letters + spaces, 4-20)")
        self.email    = TextInput((0,0,340,38), "Email (@gmail.com only)")
        self.password = TextInput((0,0,340,38), "Password (min 6, Aa1)", password=True)
        self.confirm  = TextInput((0,0,340,38), "Confirm password", password=True,
                                  on_submit=self._submit)
        self.reg_btn  = Button((0,0,340,42), "Create Account", self._submit, primary=True)
        self.back_btn = Button((0,0,340,36), "Back to Login",
                               lambda: self.app.goto("login"))
        # Verification code widgets
        self.verify_input = TextInput((0,0,340,38), "Enter verification code")
        self.verify_btn   = Button((0,0,340,42), "Verify Email", self._verify, primary=True)
        self.resend_btn   = Button((0,0,340,36), "Skip / Verify Later",
                                   lambda: self.app.goto("login",
                                       info="Account created. You can verify later."))

        self.widgets = [self.username, self.email, self.password, self.confirm,
                        self.reg_btn, self.back_btn]

    def on_enter(self, **ctx):
        self.pending_uid = None
        self.pending_code_fallback = None
        self.error = ""
        self.info = ""
        self._layout()

    def on_resize(self):
        self._layout()

    def _layout(self):
        w, h = self.app.screen.get_size()
        cx, cy = w // 2, h // 2
        if self.pending_uid is None:
            xs = cx - 170
            ys = cy - 130
            for i, w_ in enumerate([self.username, self.email, self.password,
                                    self.confirm]):
                w_.rect.topleft = (xs, ys + i * 55)
            self.reg_btn.rect.topleft  = (xs, ys + 4 * 55 + 12)
            self.back_btn.rect.topleft = (xs, ys + 4 * 55 + 60)
            self.widgets = [self.username, self.email, self.password, self.confirm,
                            self.reg_btn, self.back_btn]
        else:
            xs = cx - 170
            ys = cy - 40
            self.verify_input.rect.topleft = (xs, ys)
            self.verify_btn.rect.topleft   = (xs, ys + 58)
            self.resend_btn.rect.topleft   = (xs, ys + 106)
            self.widgets = [self.verify_input, self.verify_btn, self.resend_btn]

    def _submit(self):
        ok, msg, extra = self.auth.register(
            self.username.text.strip(),
            self.email.text.strip(),
            self.password.text,
            self.confirm.text)
        if not ok:
            self.error = msg
            self.info = ""
            return
        self.pending_uid = extra["user_id"]
        m = extra["mail"]
        self.info = msg
        if m.get("sent"):
            self.pending_code_fallback = None
        else:
            self.pending_code_fallback = m.get("code")
        self.error = ""
        self._layout()

    def _verify(self):
        if self.pending_uid is None:
            return
        ok, msg = self.auth.verify_code(self.pending_uid,
                                         self.verify_input.text.strip())
        if ok:
            self.app.goto("login", info="Email verified. Please log in.")
        else:
            self.error = msg

    def update(self, dt):
        self.app.background.draw(self.app.screen, dt)

    def draw(self, surf):
        c = self.app.theme.c
        w, h = surf.get_size()

        title_font = self.app.assets.get_font(46, bold=True)
        if self.pending_uid is None:
            title = title_font.render("Create Account", True, c["text"])
        else:
            title = title_font.render("Verify Your Email", True, c["text"])
        surf.blit(title, (w // 2 - title.get_width() // 2, h // 2 - 220))

        # Card
        card = pygame.Rect(w // 2 - 200, h // 2 - 170, 400,
                           380 if self.pending_uid is None else 260)
        pygame.draw.rect(surf, c["panel"], card, border_radius=12)
        pygame.draw.rect(surf, c["border"], card, width=1, border_radius=12)

        super().draw(surf)

        # Info/error
        f = self.app.assets.get_font(14)
        y_msg = card.bottom - 60
        if self.pending_code_fallback:
            code = self.pending_code_fallback
            surf.blit(f.render(
                f"SMTP not configured. Code: {code}", True, c["warn"]),
                (card.x + 30, y_msg - 25))
        if self.error:
            surf.blit(f.render(self.error, True, c["error"]), (card.x + 30, y_msg))
        elif self.info:
            surf.blit(f.render(self.info, True, c["success"]), (card.x + 30, y_msg))
