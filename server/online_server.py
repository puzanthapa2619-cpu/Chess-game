"""ChessMaster online multiplayer server.

Line-delimited JSON over TCP sockets. Supports:
  - create/join room
  - random matchmaking
  - move relay + live sync
  - chat
  - resign / draw offer / rematch
  - ping/pong
  - disconnect handling

Run:  python server/online_server.py --host 0.0.0.0 --port 5555
"""
import argparse
import json
import random
import socket
import threading
import time
from typing import Dict, Optional, List

import chess


class Client:
    def __init__(self, conn: socket.socket, addr):
        self.conn = conn
        self.addr = addr
        self.username = f"Guest{random.randint(1000,9999)}"
        self.room: Optional["Room"] = None
        self.color: Optional[bool] = None      # True=white, False=black
        self.tournament: Optional["Tournament"] = None
        self.alive = True
        self.last_ping = time.time()
        self.buf = b""

    def send(self, msg: dict):
        try:
            self.conn.sendall((json.dumps(msg) + "\n").encode("utf-8"))
        except Exception:
            self.alive = False


class Room:
    _counter = 0
    _lock = threading.Lock()

    def __init__(self, code: str, time_control: str = "10+0"):
        self.code = code
        self.white: Optional[Client] = None
        self.black: Optional[Client] = None
        self.board = chess.Board()
        self.time_control = time_control
        self.created_at = time.time()
        self.moves: List[str] = []
        self.draw_offer_by: Optional[bool] = None  # side that offered
        self.tournament: Optional["Tournament"] = None
        self.match: Optional[dict] = None

    @classmethod
    def new_code(cls) -> str:
        with cls._lock:
            cls._counter += 1
            return f"R{random.randint(10000,99999)}"

    def add_player(self, c: Client) -> bool:
        if self.white is None:
            self.white = c; c.color = True
            return True
        if self.black is None:
            self.black = c; c.color = False
            return True
        return False

    def opponent_of(self, c: Client) -> Optional[Client]:
        return self.black if c is self.white else self.white

    def is_full(self) -> bool:
        return self.white is not None and self.black is not None

    def broadcast(self, msg: dict, exclude: Optional[Client] = None):
        for p in (self.white, self.black):
            if p is not None and p is not exclude and p.alive:
                p.send(msg)


class Tournament:
    """Single-elimination bracket. Purely in-memory; the 'prize' is a fixed
    number sent to clients for display only — this server never moves real
    money and is not connected to any real payment provider. Clients label
    it as a simulated/demo wallet.
    """
    _lock = threading.Lock()
    _counter = 0

    DEMO_PRIZE_AMOUNT = 1000          # fictional NPR amount, for display only
    DEMO_WALLET_LABEL = "Demo eSewa Wallet (simulated — not real money)"

    def __init__(self, code: str, size: int, time_control: str = "5+0"):
        self.code = code
        self.size = size
        self.time_control = time_control
        self.players: List[Client] = []       # join order
        self.status = "waiting"               # waiting | active | done
        self.rounds: List[List[dict]] = []     # rounds[i] = list of match dicts
        self.round_idx = 0
        self.champion: Optional[Client] = None
        self.created_at = time.time()

    @classmethod
    def new_code(cls) -> str:
        with cls._lock:
            cls._counter += 1
            return f"T{random.randint(10000,99999)}"

    def is_full(self) -> bool:
        return len(self.players) >= self.size

    def lobby_names(self) -> List[str]:
        return [p.username for p in self.players]

    @staticmethod
    def round_name(num_matches: int) -> str:
        return {1: "Final", 2: "Semifinal", 4: "Quarterfinal",
                8: "Round of 16"}.get(num_matches, f"Round of {num_matches*2}")

    def broadcast_all(self, msg: dict):
        for p in self.players:
            if p.alive:
                p.send(msg)


class Server:
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self.rooms: Dict[str, Room] = {}
        self.tournaments: Dict[str, Tournament] = {}
        self.clients: List[Client] = []
        self.matchmaking_queue: List[Client] = []
        self.lock = threading.Lock()
        self.stopped = False

    def start(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((self.host, self.port))
        s.listen(64)
        print(f"[server] listening on {self.host}:{self.port}")
        threading.Thread(target=self._ping_loop, daemon=True).start()
        try:
            while not self.stopped:
                conn, addr = s.accept()
                c = Client(conn, addr)
                with self.lock:
                    self.clients.append(c)
                threading.Thread(target=self._handle, args=(c,), daemon=True).start()
        except KeyboardInterrupt:
            pass
        finally:
            self.stopped = True
            s.close()

    def _ping_loop(self):
        while not self.stopped:
            time.sleep(10)
            for c in list(self.clients):
                if not c.alive:
                    self._drop(c); continue
                # Kick clients that haven't pinged in 60s
                if time.time() - c.last_ping > 60:
                    c.alive = False
                    self._drop(c)

    def _handle(self, c: Client):
        try:
            while c.alive:
                data = c.conn.recv(4096)
                if not data:
                    break
                c.buf += data
                while b"\n" in c.buf:
                    line, c.buf = c.buf.split(b"\n", 1)
                    if not line.strip():
                        continue
                    try:
                        msg = json.loads(line.decode("utf-8"))
                    except Exception:
                        c.send({"type": "error", "msg": "invalid json"})
                        continue
                    self._route(c, msg)
        except Exception as e:
            print(f"[server] client {c.addr} err: {e}")
        finally:
            self._drop(c)

    def _drop(self, c: Client):
        with self.lock:
            if c in self.clients:
                self.clients.remove(c)
            if c in self.matchmaking_queue:
                self.matchmaking_queue.remove(c)
        try:
            c.conn.close()
        except Exception:
            pass
        room = c.room
        if room:
            opp = room.opponent_of(c)
            if opp and opp.alive:
                opp.send({"type": "opponent_disconnected"})
                if room.tournament and not room.board.is_game_over():
                    winner = "black" if c is room.white else "white"
                    opp.send({"type": "game_over", "reason": "forfeit",
                              "winner": winner})
                    self._tournament_report_result(room, winner)
            # Room is preserved for 30s for possible reconnection
            # For simplicity: if opponent also gone -> delete
            if (room.white is None or not room.white.alive) and \
               (room.black is None or not room.black.alive):
                self.rooms.pop(room.code, None)
        t = c.tournament
        if t and t.status == "waiting" and c in t.players:
            t.players.remove(c)
            t.broadcast_all({"type": "tournament_lobby", "code": t.code,
                              "count": len(t.players), "size": t.size,
                              "players": t.lobby_names()})

    def _route(self, c: Client, msg: dict):
        t = msg.get("type")
        if t == "hello":
            c.username = str(msg.get("username", c.username))[:24]
            c.send({"type": "hello_ok", "username": c.username})
        elif t == "ping":
            c.last_ping = time.time()
            c.send({"type": "pong", "ts": msg.get("ts")})
        elif t == "create_room":
            self._create_room(c, msg.get("time_control", "10+0"))
        elif t == "join_room":
            self._join_room(c, msg.get("code", ""))
        elif t == "random_match":
            self._random_match(c, msg.get("time_control", "10+0"))
        elif t == "create_tournament":
            self._create_tournament(c, int(msg.get("size", 8)),
                                     msg.get("time_control", "5+0"))
        elif t == "join_tournament":
            self._join_tournament(c, msg.get("code", ""))
        elif t == "move":
            self._on_move(c, msg)
        elif t == "chat":
            if c.room:
                c.room.broadcast({"type": "chat", "from": c.username,
                                  "text": msg.get("text", "")[:200]})
        elif t == "resign":
            if c.room:
                winner = "black" if c.color else "white"
                c.room.broadcast({"type": "game_over",
                                  "reason": "resignation",
                                  "winner": winner})
                if c.room.tournament:
                    self._tournament_report_result(c.room, winner)
        elif t == "draw_offer":
            if c.room and c.room.opponent_of(c):
                c.room.draw_offer_by = c.color
                c.room.opponent_of(c).send({"type": "draw_offer",
                                            "from": c.username})
        elif t == "draw_accept":
            if c.room:
                c.room.broadcast({"type": "game_over",
                                  "reason": "agreement",
                                  "winner": "draw"})
                if c.room.tournament:
                    self._tournament_report_result(c.room, "draw")
        elif t == "draw_decline":
            if c.room and c.room.opponent_of(c):
                c.room.opponent_of(c).send({"type": "draw_declined"})
                c.room.draw_offer_by = None
        elif t == "rematch":
            if c.room:
                c.room.board = chess.Board()
                c.room.moves = []
                # Swap colors
                c.room.white, c.room.black = c.room.black, c.room.white
                if c.room.white: c.room.white.color = True
                if c.room.black: c.room.black.color = False
                c.room.broadcast({"type": "rematch_started",
                                  "white": c.room.white.username if c.room.white else "",
                                  "black": c.room.black.username if c.room.black else ""})
        else:
            c.send({"type": "error", "msg": f"unknown type: {t}"})

    def _create_room(self, c: Client, tc: str):
        room = Room(Room.new_code(), tc)
        room.add_player(c)
        c.room = room
        self.rooms[room.code] = room
        c.send({"type": "room_created", "code": room.code, "color": "white"})

    def _join_room(self, c: Client, code: str):
        room = self.rooms.get(code.upper().strip())
        if not room:
            c.send({"type": "error", "msg": "Room not found."})
            return
        if room.is_full():
            c.send({"type": "error", "msg": "Room is full."})
            return
        room.add_player(c)
        c.room = room
        c.send({"type": "room_joined", "code": room.code, "color": "black"})
        self._start_if_ready(room)

    def _random_match(self, c: Client, tc: str):
        with self.lock:
            # Find a waiting player with matching time control
            for other in list(self.matchmaking_queue):
                if other.alive:
                    self.matchmaking_queue.remove(other)
                    room = Room(Room.new_code(), tc)
                    room.add_player(other); other.room = room
                    room.add_player(c); c.room = room
                    self.rooms[room.code] = room
                    other.send({"type": "room_joined", "code": room.code,
                                "color": "white"})
                    c.send({"type": "room_joined", "code": room.code,
                            "color": "black"})
                    self._start_if_ready(room)
                    return
            self.matchmaking_queue.append(c)
        c.send({"type": "matchmaking", "msg": "Searching for opponent..."})

    # ---------- tournaments ----------
    def _create_tournament(self, c: Client, size: int, tc: str):
        if size not in (4, 8):
            size = 8
        t = Tournament(Tournament.new_code(), size, tc)
        t.players.append(c)
        c.tournament = t
        self.tournaments[t.code] = t
        c.send({"type": "tournament_created", "code": t.code, "size": size})
        c.send({"type": "tournament_lobby", "code": t.code,
                "count": len(t.players), "size": size,
                "players": t.lobby_names()})

    def _join_tournament(self, c: Client, code: str):
        t = self.tournaments.get(code.upper().strip())
        if not t:
            c.send({"type": "error", "msg": "Tournament not found."})
            return
        if t.status != "waiting":
            c.send({"type": "error", "msg": "Tournament already started."})
            return
        if t.is_full():
            c.send({"type": "error", "msg": "Tournament is full."})
            return
        if c in t.players:
            c.send({"type": "error", "msg": "Already joined."})
            return
        t.players.append(c)
        c.tournament = t
        t.broadcast_all({"type": "tournament_lobby", "code": t.code,
                          "count": len(t.players), "size": t.size,
                          "players": t.lobby_names()})
        if t.is_full():
            self._start_tournament(t)

    def _start_tournament(self, t: Tournament):
        t.status = "active"
        players = list(t.players)
        random.shuffle(players)
        matches = [{"a": players[i], "b": players[i + 1], "winner": None, "room": None}
                   for i in range(0, len(players), 2)]
        t.rounds = [matches]
        t.round_idx = 0
        self._launch_round(t)

    def _launch_round(self, t: Tournament):
        matches = t.rounds[t.round_idx]
        rname = Tournament.round_name(len(matches))
        for idx, m in enumerate(matches):
            room = Room(Room.new_code(), t.time_control)
            room.tournament = t
            room.match = m
            a, b = m["a"], m["b"]
            if random.random() < 0.5:
                a, b = b, a
            room.add_player(a)
            room.add_player(b)
            a.room = room
            b.room = room
            self.rooms[room.code] = room
            m["room"] = room
            common = {"type": "tournament_match_start",
                      "tournament_code": t.code,
                      "round_name": rname,
                      "match_index": idx + 1,
                      "matches_in_round": len(matches),
                      "time_control": t.time_control,
                      "fen": room.board.fen(),
                      "code": room.code,
                      "white": room.white.username,
                      "black": room.black.username}
            room.white.send({**common, "color": "white"})
            room.black.send({**common, "color": "black"})

    def _tournament_report_result(self, room: Room, winner: str):
        t = room.tournament
        m = room.match
        if not t or not m or m.get("winner") is not None:
            return  # not a tournament room, or already reported

        if winner == "draw":
            # Knockout format needs a decisive result: replay with colors
            # swapped (an "armageddon" style tie-break) rather than
            # eliminating no one.
            room.board = chess.Board()
            room.moves = []
            room.draw_offer_by = None
            room.white, room.black = room.black, room.white
            if room.white: room.white.color = True
            if room.black: room.black.color = False
            room.broadcast({"type": "tournament_draw_replay",
                             "white": room.white.username if room.white else "",
                             "black": room.black.username if room.black else "",
                             "fen": room.board.fen()})
            return

        win_client = room.white if winner == "white" else room.black
        lose_client = room.opponent_of(win_client)
        m["winner"] = win_client
        rname = Tournament.round_name(len(t.rounds[t.round_idx]))
        if lose_client and lose_client.alive:
            lose_client.send({"type": "tournament_eliminated",
                               "tournament_code": t.code, "round_name": rname})
        self.rooms.pop(room.code, None)

        matches = t.rounds[t.round_idx]
        if not all(mm["winner"] is not None for mm in matches):
            return  # round still in progress

        winners = [mm["winner"] for mm in matches]
        if len(winners) == 1:
            self._tournament_finish(t, winners[0])
        else:
            next_matches = [{"a": winners[i], "b": winners[i + 1], "winner": None, "room": None}
                             for i in range(0, len(winners), 2)]
            t.rounds.append(next_matches)
            t.round_idx += 1
            self._launch_round(t)

    def _tournament_finish(self, t: Tournament, champion: Client):
        t.status = "done"
        t.champion = champion
        for p in t.players:
            if p.alive:
                p.send({"type": "tournament_champion",
                        "tournament_code": t.code,
                        "champion": champion.username,
                        "prize_amount": Tournament.DEMO_PRIZE_AMOUNT,
                        "wallet_label": Tournament.DEMO_WALLET_LABEL,
                        "is_champion": p is champion})
        self.tournaments.pop(t.code, None)

    def _start_if_ready(self, room: Room):
        if room.is_full():
            room.broadcast({
                "type": "game_start",
                "white": room.white.username,
                "black": room.black.username,
                "time_control": room.time_control,
                "fen": room.board.fen(),
            })

    def _on_move(self, c: Client, msg: dict):
        room = c.room
        if not room or not room.is_full():
            c.send({"type": "error", "msg": "No active game."})
            return
        if room.board.turn != c.color:
            c.send({"type": "error", "msg": "Not your turn."})
            return
        try:
            move = chess.Move.from_uci(msg.get("uci", ""))
        except Exception:
            c.send({"type": "error", "msg": "Invalid move."})
            return
        if move not in room.board.legal_moves:
            c.send({"type": "error", "msg": "Illegal move."})
            return
        room.board.push(move)
        room.moves.append(move.uci())
        room.draw_offer_by = None
        payload = {"type": "move", "uci": move.uci(), "fen": room.board.fen(),
                   "clock": msg.get("clock", {})}
        room.broadcast(payload)
        if room.board.is_game_over():
            result = room.board.result()
            winner = ("white" if result == "1-0" else
                      "black" if result == "0-1" else "draw")
            room.broadcast({"type": "game_over",
                            "reason": "checkmate" if room.board.is_checkmate() else
                                      "stalemate" if room.board.is_stalemate() else
                                      "draw",
                            "winner": winner, "result": result})
            if room.tournament:
                self._tournament_report_result(room, winner)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=5555)
    args = ap.parse_args()
    Server(args.host, args.port).start()


if __name__ == "__main__":
    main()
