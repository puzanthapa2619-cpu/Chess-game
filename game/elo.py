"""Elo rating calculator."""


def expected(a: int, b: int) -> float:
    return 1.0 / (1.0 + 10 ** ((b - a) / 400.0))


def update_ratings(white_rating: int, black_rating: int, result: str,
                   k: int = 24) -> tuple:
    """Return (new_white, new_black, delta_white, delta_black).

    result: '1-0' | '0-1' | '1/2-1/2'
    """
    ew = expected(white_rating, black_rating)
    eb = 1 - ew
    if result == "1-0":
        sw, sb = 1.0, 0.0
    elif result == "0-1":
        sw, sb = 0.0, 1.0
    else:
        sw, sb = 0.5, 0.5
    dw = round(k * (sw - ew))
    db = round(k * (sb - eb))
    # Bound the individual change to +-25 as requested
    dw = max(-25, min(25, dw)) if result != "1/2-1/2" else max(-15, min(15, dw))
    db = max(-25, min(25, db)) if result != "1/2-1/2" else max(-15, min(15, db))
    return white_rating + dw, black_rating + db, dw, db
