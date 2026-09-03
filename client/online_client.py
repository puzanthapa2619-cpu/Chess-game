"""Async socket client for ChessMaster online multiplayer."""
import json
import socket
import threading
import time
from queue import Queue, Empty
from typing import Optional, Callable

from utils.logger import get_logger

log = get_logger("client")


class OnlineClient:
    def __init__(self, host: str = "127.0.0.1", port: int = 5555):
        self.host = host
        self.port = port
        self.sock: Optional[socket.socket] = None
        self.connected = False
        self.rx: "Queue[dict]" = Queue()
        self.buf = b""
        self._reader: Optional[threading.Thread] = None
        self._pinger: Optional[threading.Thread] = None
        self.on_message: Optional[Callable[[dict], None]] = None
        self.ping_ms = 0

    def connect(self, username: str, timeout: float = 5.0) -> bool:
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(timeout)
            self.sock.connect((self.host, self.port))
            self.sock.settimeout(None)
            self.connected = True
            self._reader = threading.Thread(target=self._read_loop, daemon=True)
            self._reader.start()
            self._pinger = threading.Thread(target=self._ping_loop, daemon=True)
            self._pinger.start()
            self.send({"type": "hello", "username": username})
            return True
        except Exception as e:
            log.error("connect fail: %s", e)
            self.connected = False
            return False

    def send(self, msg: dict):
        if not self.connected or not self.sock:
            return
        try:
            self.sock.sendall((json.dumps(msg) + "\n").encode("utf-8"))
        except Exception as e:
            log.error("send fail: %s", e)
            self.connected = False

    def _read_loop(self):
        try:
            while self.connected and self.sock:
                data = self.sock.recv(4096)
                if not data:
                    break
                self.buf += data
                while b"\n" in self.buf:
                    line, self.buf = self.buf.split(b"\n", 1)
                    if not line.strip():
                        continue
                    try:
                        msg = json.loads(line.decode("utf-8"))
                    except Exception:
                        continue
                    if msg.get("type") == "pong":
                        try:
                            self.ping_ms = int((time.time() - float(msg.get("ts", 0))) * 1000)
                        except Exception:
                            pass
                    self.rx.put(msg)
                    if self.on_message:
                        try:
                            self.on_message(msg)
                        except Exception as e:
                            log.error("on_message: %s", e)
        except Exception as e:
            log.error("read loop: %s", e)
        finally:
            self.connected = False

    def _ping_loop(self):
        while self.connected:
            time.sleep(5)
            self.send({"type": "ping", "ts": time.time()})

    def poll(self):
        try:
            return self.rx.get_nowait()
        except Empty:
            return None

    def close(self):
        self.connected = False
        if self.sock:
            try:
                self.sock.close()
            except Exception:
                pass
        self.sock = None

    # Convenience wrappers
    def create_room(self, tc="10+0"):    self.send({"type":"create_room","time_control":tc})
    def join_room(self, code):           self.send({"type":"join_room","code":code})
    def random_match(self, tc="10+0"):   self.send({"type":"random_match","time_control":tc})
    def send_move(self, uci, clock=None): self.send({"type":"move","uci":uci,"clock":clock or {}})
    def send_chat(self, text):           self.send({"type":"chat","text":text})
    def resign(self):                    self.send({"type":"resign"})
    def offer_draw(self):                self.send({"type":"draw_offer"})
    def accept_draw(self):               self.send({"type":"draw_accept"})
    def decline_draw(self):              self.send({"type":"draw_decline"})
    def rematch(self):                   self.send({"type":"rematch"})
    def create_tournament(self, size=8, tc="5+0"):
        self.send({"type": "create_tournament", "size": size, "time_control": tc})
    def join_tournament(self, code):
        self.send({"type": "join_tournament", "code": code})
