"""Tournament lobby: create or join an online single-elimination bracket.

Same non-blocking, event-driven pattern as PlayOnlineScreen: all networking
goes through the client's on_message callback, and update(dt) is the only
place that performs screen transitions, so the UI never freezes waiting on
the network and both/all players see live status.
"""
import pygame
from ui.base_screen import Screen
from ui.widgets import Button, TextInput, Dropdown
from client.online_client import OnlineClient


class TournamentScreen(Screen):
    def __init__(self, app):
        super().__init__(app)
        s = app.settings
        self.back_btn   = Button((0,0,120,36), "← Back", self._on_back)
        self.host_in    = TextInput((0,0,260,36), "server host", max_len=64)
        self.host_in.text = s.get("online_host", "127.0.0.1")
        self.port_in    = TextInput((0,0,120,36), "port", max_len=6)
        self.port_in.text = str(s.get("online_port", 5555))
        self.connect_btn = Button((0,0,140,36), "Connect", self._connect, primary=True)

        self.size_dd    = Dropdown((0,0,160,36), ["4", "8"], "8", lambda v: None,
                                    label="Players")
        self.create_btn = Button((0,0,220,44), "Create Tournament", self._create, primary=True)
        self.code_in    = TextInput((0,0,220,36), "Tournament code (e.g. T12345)", max_len=8)
        self.join_btn   = Button((0,0,220,36), "Join Tournament", self._join)
        self.cancel_btn = Button((0,0,220,36), "Cancel", self._cancel)

        self.info = ""
        self.error = ""
        self.client = None
        self.connected = False

        self.state = "idle"   # idle|connecting|creating|joining|waiting_lobby|starting
        self.code = None
        self.lobby_count = 0
        self.lobby_size = 8
        self.lobby_players = []
        self._spin_t = 0.0
        self._pending_match_start = None

        self.widgets = [self.back_btn, self.host_in, self.port_in, self.connect_btn,
                        self.size_dd, self.create_btn, self.code_in, self.join_btn,
                        self.cancel_btn]
        self._refresh_widget_state()

    # ---------- connection ----------
    def _connect(self):
        host = self.host_in.text.strip() or "127.0.0.1"
        try:
            port = int(self.port_in.text.strip() or "5555")
        except Exception:
            self.error = "Invalid port"; return
        self.app.settings.set("online_host", host)
        self.app.settings.set("online_port", port)
        self.client = OnlineClient(host, port)
        username = (self.app.current_user or {}).get("username", "Guest")
        self.state = "connecting"
        if self.client.connect(username):
            self.connected = True
            self.client.on_message = self._on_msg
            self.info = f"Connected to {host}:{port}"
            self.error = ""
            self.state = "idle"
        else:
            self.error = f"Could not connect to {host}:{port}. Start the server first."
            self.connected = False
            self.state = "idle"
        self._refresh_widget_state()

    def _ensure_connected(self):
        if not self.connected:
            self._connect()
        return self.connected

    # ---------- actions ----------
    def _create(self):
        if not self._ensure_connected(): return
        size = int(self.size_dd.current)
        self.client.create_tournament(size=size, tc="5+0")
        self.state = "creating"
        self.info = "Creating tournament..."
        self.error = ""
        self._refresh_widget_state()

    def _join(self):
        if not self._ensure_connected(): return
        code = self.code_in.text.strip().upper()
        if not code:
            self.error = "Enter a tournament code"; return
        self.client.join_tournament(code)
        self.state = "joining"
        self.info = f"Joining tournament {code}..."
        self.error = ""
        self._refresh_widget_state()

    def _cancel(self):
        if self.client:
            try: self.client.close()
            except Exception: pass
        self.client = None
        self.connected = False
        self.state = "idle"
        self.info = ""
        self.error = "Cancelled."
        self.code = None
        self._refresh_widget_state()

    def _on_back(self):
        if self.client:
            try: self.client.close()
            except Exception: pass
        self.client = None
        self.connected = False
        self.app.goto("home")

    # ---------- network callback (reader thread) ----------
    def _on_msg(self, msg: dict):
        t = msg.get("type")
        if t == "tournament_created":
            self.code = msg.get("code")
            self.lobby_size = msg.get("size", 8)
            self.info = f"Tournament created: {self.code} — share this code."
            self.state = "waiting_lobby"
        elif t == "tournament_lobby":
            self.code = msg.get("code", self.code)
            self.lobby_count = msg.get("count", 0)
            self.lobby_size = msg.get("size", self.lobby_size)
            self.lobby_players = msg.get("players", [])
            self.info = f"Tournament {self.code}: {self.lobby_count}/{self.lobby_size} joined."
            self.state = "waiting_lobby"
        elif t == "tournament_match_start":
            me = (self.app.current_user or {}).get("username", "Guest")
            self.app.online_white_name = msg.get("white", "White")
            self.app.online_black_name = msg.get("black", "Black")
            self.app.online_my_color = (msg.get("color") == "white")
            # Round 1 begins — hand the connection off to the game screen.
            self._pending_match_start = msg
            self.state = "starting"
        elif t == "error":
            self.error = msg.get("msg", "Error")
            if self.state in ("creating", "joining"):
                self.state = "idle"

    def on_enter(self, **ctx):
        self._layout()

    def on_resize(self):
        self._layout()

    def _refresh_widget_state(self):
        waiting = self.state in ("creating", "joining", "waiting_lobby", "starting")
        for w in (self.host_in, self.port_in, self.connect_btn, self.size_dd,
                  self.create_btn, self.code_in, self.join_btn):
            w.enabled = not waiting
        self.cancel_btn.enabled = waiting
        self.cancel_btn.visible = waiting

    def _layout(self):
        w, h = self.app.screen.get_size()
        self.back_btn.rect.topleft = (24, 20)
        cx = w // 2
        top_y = 130
        self.host_in.rect.topleft = (cx - 260, top_y)
        self.port_in.rect.topleft = (cx + 10, top_y)
        self.connect_btn.rect.topleft = (cx + 140, top_y)
        self.size_dd.rect.topleft = (cx - 80, top_y + 90)

        y2 = top_y + 200
        self.create_btn.rect.topleft = (cx - 240, y2)
        self.code_in.rect.topleft = (cx + 20, y2)
        self.join_btn.rect.topleft = (cx + 20, y2 + 50)
        self.cancel_btn.rect.topleft = (cx - 110, y2 + 130)

    def update(self, dt):
        self.app.background.draw(self.app.screen, dt)
        self._spin_t += dt
        if self.client and not self.client.connected and self.state != "idle":
            self.error = "Lost connection to server."
            self.state = "idle"
            self._refresh_widget_state()

        if self._pending_match_start is not None:
            msg = self._pending_match_start
            self._pending_match_start = None
            client = self.client
            self.client = None
            self.app.goto("game", mode="online", online_client=client,
                          tournament_ctx={
                              "tournament_code": msg.get("tournament_code"),
                              "round_name": msg.get("round_name"),
                              "match_index": msg.get("match_index"),
                              "matches_in_round": msg.get("matches_in_round"),
                              "time_control": msg.get("time_control", "5+0"),
                          })
            return

    def _status_line(self):
        if self.state == "connecting": return "Connecting..."
        if self.state == "creating": return "Creating tournament..."
        if self.state == "joining": return "Joining tournament..."
        if self.state == "waiting_lobby":
            dots = "." * (1 + int(self._spin_t * 2) % 3)
            return f"Waiting for players{dots}"
        if self.state == "starting": return "Bracket ready — starting round 1..."
        return "Not connected" if not self.connected else "Connected"

    def draw(self, surf):
        c = self.app.theme.c
        f = self.app.assets.get_font(36, bold=True)
        surf.blit(f.render("Tournament", True, c["text"]),
                  (surf.get_width() // 2 - 110, 60))
        fs = self.app.assets.get_font(14)
        surf.blit(fs.render(self._status_line(), True, c["text_dim"]),
                  (surf.get_width() // 2 - 90, 105))

        card = pygame.Rect(60, 100, 320, 240)
        pygame.draw.rect(surf, c["panel"], card, border_radius=10)
        pygame.draw.rect(surf, c["border"], card, width=1, border_radius=10)
        fh = self.app.assets.get_font(14, bold=True)
        fp = self.app.assets.get_font(12)
        surf.blit(fh.render("Single-elimination bracket", True, c["accent"]),
                  (card.x + 14, card.y + 12))
        lines = [
            "1) Connect to the server.",
            "2) One player creates a tournament",
            "     and shares the code.",
            "3) Everyone else joins with it.",
            "4) Once the bracket is full, round 1",
            "     starts automatically for all.",
            "",
            "Winner gets a Demo eSewa Wallet",
            "prize credit — simulated, not",
            "real money.",
        ]
        for i, ln in enumerate(lines):
            surf.blit(fp.render(ln, True, c["text_dim"]),
                      (card.x + 14, card.y + 40 + i * 18))

        if self.state == "waiting_lobby" and self.lobby_players:
            names_card = pygame.Rect(surf.get_width() - 300, 100, 240, 240)
            pygame.draw.rect(surf, c["panel"], names_card, border_radius=10)
            pygame.draw.rect(surf, c["border"], names_card, width=1, border_radius=10)
            surf.blit(fh.render(f"Players ({self.lobby_count}/{self.lobby_size})",
                                 True, c["accent"]), (names_card.x + 14, names_card.y + 12))
            for i, name in enumerate(self.lobby_players):
                surf.blit(fp.render(f"• {name}", True, c["text"]),
                          (names_card.x + 14, names_card.y + 44 + i * 20))
            if self.code:
                surf.blit(fp.render(f"Code: {self.code}", True, c["success"]),
                          (names_card.x + 14, names_card.y + 210))

        super().draw(surf)
        self.size_dd.draw_open(surf, self.app.theme, self.app.assets)

        if self.info:
            surf.blit(fs.render(self.info, True, c["success"]),
                      (surf.get_width() // 2 - 200, surf.get_height() - 60))
        if self.error:
            surf.blit(fs.render(self.error, True, c["error"]),
                      (surf.get_width() // 2 - 250, surf.get_height() - 40))
