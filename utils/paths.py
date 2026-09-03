"""Central path constants."""
import os

ROOT       = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS     = os.path.join(ROOT, "assets")
IMAGES     = os.path.join(ASSETS, "images")
SOUNDS     = os.path.join(ASSETS, "sounds")
ICONS      = os.path.join(ASSETS, "icons")
FONTS      = os.path.join(ASSETS, "fonts")
PIECES     = os.path.join(ASSETS, "pieces")
BOARDS     = os.path.join(ASSETS, "boards")
DATABASE   = os.path.join(ROOT, "database", "chess.db")
SCHEMA     = os.path.join(ROOT, "database", "schema.sql")
ENGINE_DIR = os.path.join(ROOT, "engine", "stockfish")
LOGS       = os.path.join(ROOT, "logs")
ENV_FILE   = os.path.join(ROOT, ".env")

for d in (os.path.dirname(DATABASE), LOGS):
    os.makedirs(d, exist_ok=True)
