"""SQLite database access layer for ChessMaster."""
import sqlite3
import json
import threading
from typing import Optional, Any, Dict, List
from utils.paths import DATABASE, SCHEMA
from utils.logger import get_logger

log = get_logger("db")


class Database:
    """Thread-safe SQLite wrapper (one connection per thread)."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init()
            return cls._instance

    def _init(self):
        self._local = threading.local()
        self._ensure_schema()

    def _conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn"):
            c = sqlite3.connect(DATABASE, check_same_thread=False, timeout=15)
            c.row_factory = sqlite3.Row
            c.execute("PRAGMA foreign_keys = ON")
            self._local.conn = c
        return self._local.conn

    def _ensure_schema(self):
        with open(SCHEMA, encoding="utf-8") as f:
            sql = f.read()
        self._conn().executescript(sql)
        self._conn().commit()

    # ---------- generic helpers ----------
    def execute(self, sql: str, params: tuple = ()):
        cur = self._conn().execute(sql, params)
        self._conn().commit()
        return cur

    def query_one(self, sql: str, params: tuple = ()) -> Optional[sqlite3.Row]:
        return self._conn().execute(sql, params).fetchone()

    def query_all(self, sql: str, params: tuple = ()) -> List[sqlite3.Row]:
        return self._conn().execute(sql, params).fetchall()

    # ---------- global settings ----------
    def get_setting(self, key: str, default: Any = None) -> Any:
        row = self.query_one("SELECT value FROM global_settings WHERE key=?", (key,))
        if row is None:
            return default
        try:
            return json.loads(row["value"])
        except (TypeError, json.JSONDecodeError):
            return row["value"]

    def set_setting(self, key: str, value: Any) -> None:
        self.execute(
            "INSERT INTO global_settings(key,value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, json.dumps(value)),
        )

    # ---------- users ----------
    def create_user(self, username: str, email: str, pw_hash: str,
                    verify_code: str) -> int:
        cur = self.execute(
            "INSERT INTO users(username,email,password_hash,verify_code) "
            "VALUES(?,?,?,?)",
            (username, email, pw_hash, verify_code))
        return cur.lastrowid

    def user_by_username(self, username: str) -> Optional[sqlite3.Row]:
        return self.query_one("SELECT * FROM users WHERE username=?", (username,))

    def user_by_email(self, email: str) -> Optional[sqlite3.Row]:
        return self.query_one("SELECT * FROM users WHERE email=?", (email,))

    def user_by_id(self, uid: int) -> Optional[sqlite3.Row]:
        return self.query_one("SELECT * FROM users WHERE id=?", (uid,))

    def mark_verified(self, uid: int) -> None:
        self.execute("UPDATE users SET verified=1, verify_code=NULL WHERE id=?", (uid,))

    def update_last_login(self, uid: int) -> None:
        self.execute("UPDATE users SET last_login=CURRENT_TIMESTAMP WHERE id=?", (uid,))

    def update_user_stats(self, uid: int, wins: int, losses: int, draws: int,
                          rating: int, accuracy: float, games_played: int,
                          peak_rating: Optional[int] = None) -> None:
        if peak_rating is None:
            peak_rating = rating
        self.execute(
            "UPDATE users SET wins=?, losses=?, draws=?, rating=?, "
            "accuracy=?, games_played=?, peak_rating=MAX(peak_rating,?) "
            "WHERE id=?",
            (wins, losses, draws, rating, accuracy, games_played, peak_rating, uid))

    def leaderboard(self, limit: int = 50) -> List[sqlite3.Row]:
        return self.query_all(
            "SELECT username,rating,wins,losses,draws,games_played,accuracy "
            "FROM users ORDER BY rating DESC LIMIT ?", (limit,))

    # ---------- matches ----------
    def create_match(self, **kw) -> int:
        cols = ",".join(kw.keys())
        placeholders = ",".join("?" for _ in kw)
        cur = self.execute(f"INSERT INTO matches({cols}) VALUES({placeholders})",
                           tuple(kw.values()))
        return cur.lastrowid

    def add_move(self, match_id: int, ply: int, san: str, uci: str,
                 fen_before: str, time_ms: int = 0):
        self.execute(
            "INSERT INTO moves(match_id,ply,san,uci,fen_before,time_ms) "
            "VALUES(?,?,?,?,?,?)",
            (match_id, ply, san, uci, fen_before, time_ms))

    def matches_for_user(self, uid: int, limit: int = 100) -> List[sqlite3.Row]:
        return self.query_all(
            "SELECT * FROM matches WHERE white_id=? OR black_id=? "
            "ORDER BY id DESC LIMIT ?", (uid, uid, limit))

    def match_by_id(self, mid: int) -> Optional[sqlite3.Row]:
        return self.query_one("SELECT * FROM matches WHERE id=?", (mid,))

    def moves_for_match(self, mid: int) -> List[sqlite3.Row]:
        return self.query_all(
            "SELECT * FROM moves WHERE match_id=? ORDER BY ply ASC", (mid,))

    # ---------- ratings ----------
    def add_rating_point(self, uid: int, rating: int, delta: int,
                         match_id: Optional[int] = None):
        self.execute(
            "INSERT INTO ratings(user_id,rating,delta,match_id) VALUES(?,?,?,?)",
            (uid, rating, delta, match_id))

    def rating_history(self, uid: int) -> List[sqlite3.Row]:
        return self.query_all(
            "SELECT rating,date,delta FROM ratings WHERE user_id=? ORDER BY id ASC",
            (uid,))

    # ---------- analysis ----------
    def save_analysis(self, match_id: int, data: Dict[str, Any]) -> None:
        data = dict(data)
        data["match_id"] = match_id
        data["evaluation_json"] = json.dumps(data.get("evaluation_json", []))
        data["classification_json"] = json.dumps(data.get("classification_json", []))
        cols = ",".join(data.keys())
        ph = ",".join("?" for _ in data)
        self.execute(f"INSERT INTO analysis({cols}) VALUES({ph})",
                     tuple(data.values()))

    def analysis_for_match(self, mid: int) -> Optional[sqlite3.Row]:
        return self.query_one(
            "SELECT * FROM analysis WHERE match_id=? ORDER BY id DESC LIMIT 1",
            (mid,))

    # ---------- achievements ----------
    def award_achievement(self, uid: int, code: str, name: str, desc: str) -> bool:
        exists = self.query_one(
            "SELECT id FROM achievements WHERE user_id=? AND code=?", (uid, code))
        if exists:
            return False
        self.execute(
            "INSERT INTO achievements(user_id,code,name,description) VALUES(?,?,?,?)",
            (uid, code, name, desc))
        return True

    def achievements_for(self, uid: int) -> List[sqlite3.Row]:
        return self.query_all(
            "SELECT * FROM achievements WHERE user_id=? ORDER BY unlocked_at DESC",
            (uid,))
