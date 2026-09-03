"""Shown when a tournament finishes. Displays the champion and, purely for
fun, credits a local "Demo eSewa Wallet" balance stored on-device. This is
never connected to any real payment provider and no money moves between
players — it's a cosmetic reward, not a transaction.
"""
import pygame
from ui.base_screen import Screen
from ui.widgets import Button


class TournamentResultScreen(Screen):
    def __init__(self, app):
        super().__init__(app)
        self.home_btn = Button((0, 0, 200, 44), "Return to Home", self._go_home, primary=True)
        self.widgets = [self.home_btn]
        self.result = {}
        self._credited = 0

    def on_enter(self, result=None, **ctx):
        self.result = result or {}
        self._credited = 0
        if self.result.get("is_champion"):
            prize = int(self.result.get("prize_amount", 0))
            bal = self.app.settings.get("demo_wallet_balance", 0)
            self.app.settings.set("demo_wallet_balance", bal + prize)
            self._credited = prize
        self._layout()

    def on_resize(self):
        self._layout()

    def _layout(self):
        w, h = self.app.screen.get_size()
        self.home_btn.rect.center = (w // 2, h - 100)

    def _go_home(self):
        self.app.goto("home")

    def draw(self, surf):
        c = self.app.theme.c
        w, h = surf.get_size()
        surf.fill(c["bg"])

        champion = self.result.get("champion", "?")
        is_champ = bool(self.result.get("is_champion"))
        wallet_label = self.result.get("wallet_label", "Demo eSewa Wallet (simulated)")

        f_title = self.app.assets.get_font(40, bold=True)
        if is_champ:
            title = "🏆 You Are the Champion!"
        else:
            title = "Tournament Complete"
        t = f_title.render(title, True, c["accent"])
        surf.blit(t, (w // 2 - t.get_width() // 2, 70))

        f_sub = self.app.assets.get_font(18)
        sub = f"Champion: {champion}"
        s = f_sub.render(sub, True, c["text"])
        surf.blit(s, (w // 2 - s.get_width() // 2, 130))

        # Wallet card
        card = pygame.Rect(w // 2 - 240, 190, 480, 220)
        pygame.draw.rect(surf, c["panel"], card, border_radius=14)
        pygame.draw.rect(surf, c["border"], card, width=1, border_radius=14)

        f_h = self.app.assets.get_font(16, bold=True)
        surf.blit(f_h.render(wallet_label, True, c["accent"]),
                  (card.centerx - f_h.size(wallet_label)[0] // 2, card.y + 18))

        if is_champ:
            f_amt = self.app.assets.get_font(46, bold=True)
            amt_text = f"+ Rs. {self._credited}"
            a = f_amt.render(amt_text, True, c["success"])
            surf.blit(a, (card.centerx - a.get_width() // 2, card.y + 60))
            bal = self.app.settings.get("demo_wallet_balance", 0)
            f_bal = self.app.assets.get_font(14)
            bal_text = f"Demo wallet balance: Rs. {bal}"
            b = f_bal.render(bal_text, True, c["text_dim"])
            surf.blit(b, (card.centerx - b.get_width() // 2, card.y + 120))
        else:
            f_msg = self.app.assets.get_font(16)
            msg = f"{champion} received the prize."
            m = f_msg.render(msg, True, c["text"])
            surf.blit(m, (card.centerx - m.get_width() // 2, card.y + 80))

        f_disc = self.app.assets.get_font(12)
        disclaimer_lines = [
            "This is a simulated balance for entertainment only.",
            "No real eSewa account is used and no real money is",
            "transferred by this app — nothing here is gambling.",
        ]
        for i, line in enumerate(disclaimer_lines):
            d = f_disc.render(line, True, c["text_dim"])
            surf.blit(d, (card.centerx - d.get_width() // 2,
                          card.bottom - 60 + i * 16))

        super().draw(surf)
