# ChessMaster — Professional Desktop Chess

A full-featured desktop chess application built in Python.

## Features

- **Modern UI** with animated home page, dark/light modes, 7 piece themes,
  23 board themes, sound effects.
- **Authentication**: bcrypt-hashed passwords, `@gmail.com`-only email
  validation, SMTP verification code.
- **Guest mode**: play offline / vs AI without an account.
- **Complete chess rules** via python-chess: castling, en passant,
  promotion (with picker or auto-queen), check, checkmate, stalemate,
  threefold repetition, fifty-move rule, insufficient material.
- **Play vs AI**: 8 difficulties (Beginner → Grandmaster, plus custom
  Elo 800–3200). Uses Stockfish when available, otherwise a built-in
  negamax + alpha-beta engine.
- **Online multiplayer**: create/join room, random matchmaking, live
  move sync, chat, resign, draw offer, rematch, reconnect-safe.
- **Post-game analysis**: move classification (brilliant/great/best/
  excellent/good/book/inaccuracy/mistake/blunder/missed-win/missed-mate),
  centipawn loss, accuracy %, evaluation graph, PGN export, PDF report.
- **Timers** with Fischer increment (1+0 through 60+0).
- **Move history** in SAN, undo (offline), hints (arrow overlay),
  captured piece tray.
- **Persistence**: SQLite database with `users`, `matches`, `moves`,
  `ratings`, `analysis`, `friends`, `achievements`, `settings`.
- **Elo rating** system + rating graph on profile page.
- **Leaderboard**, **game history** with replay, **profile page** with
  avatar, stats, favorite opening, achievements.

## Setup

```bash
cd ChessMaster
pip install -r requirements.txt
python main.py
```

### Optional: Enable SMTP email verification

Copy `.env.example` to `.env` and fill in your Gmail app-password
credentials. Without a `.env`, verification codes are still generated
and written to `logs/emails/` and shown on screen — the app remains
fully usable in development.

### Optional: Install Stockfish for stronger AI

The app runs fine with its built-in engine, but Stockfish gives much
stronger play. Install via your OS package manager:

- **macOS**   : `brew install stockfish`
- **Debian**  : `sudo apt install stockfish`
- **Windows** : download from https://stockfishchess.org/download/ and
  either add to `PATH` or drop the executable at
  `ChessMaster/engine/stockfish/stockfish.exe`.

The app auto-detects Stockfish on PATH or in `engine/stockfish/`.

### Optional: Nicer PDF analysis reports

```bash
pip install reportlab
```

Without it, analysis exports as a `.pdf.txt` plain-text report.

## Online Play

Start the server on any machine reachable from the clients:

```bash
python server/online_server.py --host 0.0.0.0 --port 5555
```

Then in each client → Play Online → enter the server host & port →
Connect → Create Room / Join Room / Random Match.

## Project Structure

```
ChessMaster/
├── assets/
│   ├── pieces/{7 themes}/    12 PNGs each
│   ├── boards/{23 themes}/   light.png, dark.png
│   ├── sounds/               move, capture, check, mate, etc.
│   ├── images/ icons/ fonts/
├── database/
│   ├── schema.sql
│   ├── db.py
│   └── chess.db              (auto-created)
├── engine/
│   ├── stockfish/            (drop your binary here)
│   └── engine_manager.py
├── server/online_server.py
├── client/online_client.py
├── ui/                       theme, widgets, all screens
├── auth/                     validators, mailer, auth_service
├── game/                     board_view, timer, elo, opening_book
├── analysis/                 analyzer, export (PGN/PDF)
├── settings/settings_manager.py
├── utils/                    logger, paths, assets_manager, sound_manager
├── logs/                     rotating app.log (and email fallbacks)
├── main.py
├── requirements.txt
├── setup.py
├── .env.example
└── README.md
```

## Keyboard Shortcuts

- **F11**   — Toggle fullscreen
- **Esc**   — Return to home (from any screen except login/home)

## Credits

Piece SVGs are derived from the Lichess open-source project (GPL-3.0),
converted to high-resolution PNGs. Chess rules are provided by
python-chess by Niklas Fiekas.
