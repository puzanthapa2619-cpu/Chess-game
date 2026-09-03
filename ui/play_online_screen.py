"""Play Online lobby: create/join room, random match, connect to server.

This screen is fully non-blocking / event-driven. Earlier versions blocked
the main thread inside tight `while` polling loops while waiting for the
opponent, which froze the whole app for up to two minutes per step. That
made it *look* like "player A is in the room but player B is stuck
waiting" because neither client's screen could redraw, process the Back
button, or reliably reach the point where both sides got the `game_start`
message. Now all networking is driven by the client's `on_message`
callback and a small state machine that `update(dt)` advances every
frame, so both players see live status and land in the game together.
"""
import pygame
from ui.base_screen import Screen
from ui.widgets import Button, TextInput, Dropdown
from client.online_client import OnlineClient
from ui.settings_screen import TIME_CONTROLS


class PlayOnlineScreen(Screen):
    # states: idle | connecting | creating | joining | matchmaking |
    #         waiting_opponent | starting
    def __init__(self, app):
        super().__init__(app)
        s = app.settings
        self.back_btn   = Button((0,0,120,36), "← Back", self._on_back)
        self.host_in    = TextInput((0,0,260,36), "server host",
                                     max_len=64)
        self.host_in.text = s.get("online_host", "127.0.0.1")
        self.port_in    = TextInput((0,0,120,36), "port", max_len=6)
        self.port_in.text = str(s.get("online_port", 5555))
        self.connect_btn = Button((0,0,140,36), "Connect", self._connect, primary=True)

        self.tc_dd      = Dropdown((0,0,220,36), TIME_CONTROLS,
                                    s.get("time_control"),
                                    lambda v: s.set("time_control", v),
                                    label="Time Control")

        self.create_btn = Button((0,0,220,44), "Create Room", self._create, primary=True)
        self.random_btn = Button((0,0,220,44), "Random Match", self._random, primary=True)
        self.code_in    = TextInput((0,0,220,36), "Room code (e.g. R12345)",
                                     max_len=8)
        self.join_btn   = Button((0,0,220,36), "Join Room", self._join)
        self.cancel_btn = Button((0,0,220,36), "Cancel", self._cancel)

        self.info = ""
        self.error = ""
        self.client = None
        self.connected = False
        self.status = "Not connected"

        self.state = "idle"
        self._spin_t = 0.0
        self._pending_game_start = None  # set from network thread, consumed on main thread

        self.widgets = [self.back_btn, self.host_in, self.port_in, self.connect_btn,
                        self.tc_dd, self.create_btn, self.random_btn,
                        self.code_in, self.join_btn, self.cancel_btn]
        self._refresh_widget_state()

    # ---------- connection ----------
    def _connect(self):
        host = self.host_in.text.strip() or "127.0.0.1"
        try:
            port = int(self.port_in.text.strip() or "5555")
        except Exception:
            self.error = "Invalid port"
            return
        self.app.settings.set("online_host", host)
        self.app.settings.set("online_port", port)
        self.client = OnlineClient(host, port)
        username = (self.app.current_user or {}).get("username", "Guest")
        self.state = "connecting"
        if self.client.connect(username):
            self.connected = True
            # All further server messages are handled asynchronously from here on.
            self.client.on_message = self._on_msg
            self.info = f"Connected to {host}:{port}"
            self.error = ""
            self.status = f"Connected as {username}"
            self.state = "idle"
        else:
            self.error = f"Could not connect to {host}:{port}. Start the server first (python server/online_server.py)."
            self.info = ""
            self.connected = False
            self.state = "idle"
        self._refresh_widget_state()

    def _ensure_connected(self):
        if not self.connected:
            self._connect()
        return self.connected

    # ---------- actions (never block) ----------
    def _create(self):
        if not self._ensure_connected(): return
        self.client.create_room(self.app.settings.get("time_control", "10+0"))
        self.state = "creating"
        self.info = "Creating room..."
        self.error = ""
        self._refresh_widget_state()

    def _join(self):
        if not self._ensure_connected(): return
        code = self.code_in.text.strip().upper()
        if not code:
            self.error = "Enter a room code"
            return
        self.client.join_room(code)
        self.state = "joining"
        self.info = f"Joining room {code}..."
        self.error = ""
        self._refresh_widget_state()

    def _random(self):
        if not self._ensure_connected(): return
        self.client.random_match(self.app.settings.get("time_control", "10+0"))
        self.state = "matchmaking"
        self.info = "Searching for opponent..."
        self.error = ""
        self._refresh_widget_state()

    def _cancel(self):
        # Bail out of whatever we were waiting on and go back to a clean lobby.
        if self.client:
            try: self.client.close()
            except Exception: pass
        self.client = None
        self.connected = False
        self.state = "idle"
        self.info = ""
        self.error = "Cancelled."
        self.status = "Not connected"
        self._refresh_widget_state()

    def _on_back(self):
        self._teardown_client()
        self.app.goto("home")

    def _teardown_client(self):
        if self.client:
            try: self.client.close()
            except Exception: pass
        self.client = None
        self.connected = False

    # ---------- network callback (runs on the client's reader thread) ----------
    def _on_msg(self, msg: dict):
        t = msg.get("type")
        if t == "room_created":
            self.app.online_my_color = True   # white
            self.app.online_white_name = (self.app.current_user or {}).get("username", "Guest")
            self.app.online_black_name = "Opponent"
            self.info = f"Room created: {msg['code']} — share this code. Waiting for opponent..."
            self.state = "waiting_opponent"
        elif t == "room_joined":
            color = msg.get("color", "black")
            me = (self.app.current_user or {}).get("username", "Guest")
            self.app.online_my_color = (color == "white")
            self.app.online_white_name = me if color == "white" else "Opponent"
            self.app.online_black_name = me if color == "black" else "Opponent"
            self.info = "Joined room — waiting for game to start..."
            self.state = "waiting_opponent"
        elif t == "matchmaking":
            self.info = msg.get("msg", "Searching for opponent...")
            self.state = "matchmaking"
        elif t == "game_start":
            self.app.online_white_name = msg.get("white", self.app.online_white_name)
            self.app.online_black_name = msg.get("black", self.app.online_black_name)
            # Don't touch screen state from a background thread — flag it and
            # let the main-thread update() perform the actual transition.
            self._pending_game_start = msg
            self.state = "starting"
        elif t == "error":
            self.error = msg.get("msg", "Error")
            self.state = "idle"
        # "hello_ok"/"pong" etc. are ignored here.

    def on_enter(self, **ctx):
        self._layout()

    def on_exit(self):
        # Leaving the lobby without starting a game (e.g. via Back) drops the connection.
        pass

    def on_resize(self):
        self._layout()

    def _refresh_widget_state(self):
        waiting = self.state in ("creating", "joining", "matchmaking", "waiting_opponent", "starting")
        for w in (self.host_in, self.port_in, self.connect_btn, self.tc_dd,
                  self.create_btn, self.random_btn, self.code_in, self.join_btn):
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
        self.tc_dd.rect.topleft = (cx - 110, top_y + 90)

        y2 = top_y + 200
        self.create_btn.rect.topleft = (cx - 240, y2)
        self.random_btn.rect.topleft = (cx + 20, y2)
        self.code_in.rect.topleft = (cx - 110, y2 + 90)
        self.join_btn.rect.topleft = (cx - 110, y2 + 140)
        self.cancel_btn.rect.topleft = (cx - 110, y2 + 190)

    def update(self, dt):
        self.app.background.draw(self.app.screen, dt)
        self._spin_t += dt
        if self.client and not self.client.connected and self.state != "idle":
            # Connection dropped while we were waiting.
            self.error = "Lost connection to server."
            self.state = "idle"
            self._refresh_widget_state()

        # Perform the actual screen transition on the main thread only.
        if self._pending_game_start is not None:
            self._pending_game_start = None
            client = self.client
            self.client = None  # ownership moves to the game screen
            self.app.goto("game", mode="online", online_client=client)
            return

    def _status_line(self):
        if self.state == "connecting":
            return "Connecting..."
        if self.state == "creating":
            return "Creating room..."
        if self.state == "joining":
            return "Joining room..."
        if self.state == "matchmaking":
            dots = "." * (1 + int(self._spin_t * 2) % 3)
            return f"Searching for opponent{dots}"
        if self.state == "waiting_opponent":
            dots = "." * (1 + int(self._spin_t * 2) % 3)
            return f"Waiting for opponent{dots}"
        if self.state == "starting":
            return "Opponent found — starting game..."
        return self.status

    def draw(self, surf):
        c = self.app.theme.c
        f = self.app.assets.get_font(36, bold=True)
        surf.blit(f.render("Play Online", True, c["text"]),
                  (surf.get_width() // 2 - 100, 60))
        fs = self.app.assets.get_font(14)
        surf.blit(fs.render(self._status_line(), True, c["text_dim"]),
                  (surf.get_width() // 2 - 90, 105))

        # Instructions
        card = pygame.Rect(60, 100, 320, 200)
        pygame.draw.rect(surf, c["panel"], card, border_radius=10)
        pygame.draw.rect(surf, c["border"], card, width=1, border_radius=10)
        fh = self.app.assets.get_font(14, bold=True)
        fp = self.app.assets.get_font(12)
        surf.blit(fh.render("How to play online", True, c["accent"]),
                  (card.x + 14, card.y + 12))
        lines = [
            "1) Start the server on any machine:",
            "     python server/online_server.py",
            "2) Enter host + port, click Connect.",
            "3) Create a Room and share the code,",
            "     Join a friend's Room, or",
            "     click Random Match to be paired.",
        ]
        for i, ln in enumerate(lines):
            surf.blit(fp.render(ln, True, c["text_dim"]),
                      (card.x + 14, card.y + 40 + i * 20))

        super().draw(surf)
        self.tc_dd.draw_open(surf, self.app.theme, self.app.assets)

        # Info/error at bottom
        if self.info:
            surf.blit(fs.render(self.info, True, c["success"]),
                      (surf.get_width() // 2 - 200, surf.get_height() - 60))
        if self.error:
            surf.blit(fs.render(self.error, True, c["error"]),
                      (surf.get_width() // 2 - 250, surf.get_height() - 40))
