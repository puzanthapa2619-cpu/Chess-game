-- ChessMaster SQLite schema
CREATE TABLE IF NOT EXISTS users (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    username       TEXT UNIQUE NOT NULL,
    email          TEXT UNIQUE NOT NULL,
    password_hash  TEXT NOT NULL,
    verified       INTEGER DEFAULT 0,
    verify_code    TEXT,
    country        TEXT DEFAULT 'Unknown',
    avatar         TEXT DEFAULT 'default.png',
    wins           INTEGER DEFAULT 0,
    losses         INTEGER DEFAULT 0,
    draws          INTEGER DEFAULT 0,
    rating         INTEGER DEFAULT 1200,
    peak_rating    INTEGER DEFAULT 1200,
    accuracy       REAL DEFAULT 0.0,
    games_played   INTEGER DEFAULT 0,
    date_joined    TEXT DEFAULT CURRENT_TIMESTAMP,
    theme          TEXT DEFAULT 'dark',
    last_login     TEXT
);

CREATE TABLE IF NOT EXISTS matches (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    white_id        INTEGER,
    black_id        INTEGER,
    white_name      TEXT,
    black_name      TEXT,
    result          TEXT,             -- '1-0', '0-1', '1/2-1/2', '*'
    termination     TEXT,             -- 'checkmate','resignation','timeout','draw',...
    time_control    TEXT,
    mode            TEXT,             -- 'ai','online','offline','guest'
    pgn             TEXT,
    final_fen       TEXT,
    opening         TEXT,
    duration_sec    INTEGER,
    date_played     TEXT DEFAULT CURRENT_TIMESTAMP,
    white_rating_before INTEGER,
    black_rating_before INTEGER,
    white_rating_after  INTEGER,
    black_rating_after  INTEGER,
    FOREIGN KEY(white_id) REFERENCES users(id),
    FOREIGN KEY(black_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS moves (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id   INTEGER NOT NULL,
    ply        INTEGER,
    san        TEXT,
    uci        TEXT,
    fen_before TEXT,
    time_ms    INTEGER,
    FOREIGN KEY(match_id) REFERENCES matches(id)
);

CREATE TABLE IF NOT EXISTS ratings (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    rating     INTEGER,
    date       TEXT DEFAULT CURRENT_TIMESTAMP,
    delta      INTEGER,
    match_id   INTEGER,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS settings (
    user_id    INTEGER PRIMARY KEY,
    key_json   TEXT,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS global_settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS game_history (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER,
    match_id   INTEGER,
    result     TEXT,
    date       TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(match_id) REFERENCES matches(id)
);

CREATE TABLE IF NOT EXISTS analysis (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id              INTEGER NOT NULL,
    accuracy_white        REAL,
    accuracy_black        REAL,
    avg_cp_loss_white     REAL,
    avg_cp_loss_black     REAL,
    brilliant             INTEGER DEFAULT 0,
    great                 INTEGER DEFAULT 0,
    best                  INTEGER DEFAULT 0,
    excellent             INTEGER DEFAULT 0,
    good                  INTEGER DEFAULT 0,
    book                  INTEGER DEFAULT 0,
    inaccuracy            INTEGER DEFAULT 0,
    mistake               INTEGER DEFAULT 0,
    blunder               INTEGER DEFAULT 0,
    missed_win            INTEGER DEFAULT 0,
    missed_mate           INTEGER DEFAULT 0,
    evaluation_json       TEXT,
    classification_json   TEXT,
    date                  TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(match_id) REFERENCES matches(id)
);

CREATE TABLE IF NOT EXISTS friends (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER,
    friend_id  INTEGER,
    status     TEXT DEFAULT 'pending',  -- pending/accepted/blocked
    date       TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(friend_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS achievements (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER,
    code       TEXT,
    name       TEXT,
    description TEXT,
    unlocked_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS idx_matches_white ON matches(white_id);
CREATE INDEX IF NOT EXISTS idx_matches_black ON matches(black_id);
CREATE INDEX IF NOT EXISTS idx_moves_match  ON moves(match_id);
CREATE INDEX IF NOT EXISTS idx_ratings_user ON ratings(user_id);
