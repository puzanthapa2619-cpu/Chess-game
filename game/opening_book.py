"""Small built-in opening name lookup based on move-prefix matching.

Not a full ECO database, but recognises the most common openings so the
analysis screen has something meaningful to show.
"""

# Sequences are SAN move lists
OPENINGS = [
    (["e4"],                                       "King's Pawn Opening"),
    (["e4", "e5"],                                 "Open Game"),
    (["e4", "e5", "Nf3"],                          "King's Knight Opening"),
    (["e4", "e5", "Nf3", "Nc6"],                   "King's Knight Opening"),
    (["e4", "e5", "Nf3", "Nc6", "Bb5"],            "Ruy Lopez"),
    (["e4", "e5", "Nf3", "Nc6", "Bc4"],            "Italian Game"),
    (["e4", "e5", "Nf3", "Nc6", "Bc4", "Bc5"],     "Italian Game: Giuoco Piano"),
    (["e4", "e5", "Nf3", "Nc6", "Bc4", "Nf6"],     "Italian Game: Two Knights Defense"),
    (["e4", "e5", "Nf3", "Nc6", "d4"],             "Scotch Game"),
    (["e4", "e5", "Nf3", "Nf6"],                   "Petrov's Defense"),
    (["e4", "e5", "f4"],                           "King's Gambit"),
    (["e4", "c5"],                                 "Sicilian Defense"),
    (["e4", "c5", "Nf3"],                          "Sicilian Defense"),
    (["e4", "c5", "Nf3", "d6"],                    "Sicilian, Najdorf-bound"),
    (["e4", "c5", "Nf3", "d6", "d4"],              "Sicilian, Open"),
    (["e4", "c5", "Nf3", "Nc6"],                   "Sicilian, Old Sicilian"),
    (["e4", "c5", "Nc3"],                          "Sicilian, Closed"),
    (["e4", "c6"],                                 "Caro-Kann Defense"),
    (["e4", "e6"],                                 "French Defense"),
    (["e4", "d5"],                                 "Scandinavian Defense"),
    (["e4", "d6"],                                 "Pirc Defense"),
    (["e4", "g6"],                                 "Modern Defense"),
    (["e4", "Nf6"],                                "Alekhine's Defense"),
    (["d4"],                                       "Queen's Pawn Opening"),
    (["d4", "d5"],                                 "Closed Game"),
    (["d4", "d5", "c4"],                           "Queen's Gambit"),
    (["d4", "d5", "c4", "e6"],                     "Queen's Gambit Declined"),
    (["d4", "d5", "c4", "c6"],                     "Slav Defense"),
    (["d4", "d5", "c4", "dxc4"],                   "Queen's Gambit Accepted"),
    (["d4", "Nf6"],                                "Indian Defense"),
    (["d4", "Nf6", "c4"],                          "Indian Game"),
    (["d4", "Nf6", "c4", "g6"],                    "King's Indian Defense"),
    (["d4", "Nf6", "c4", "e6"],                    "Nimzo-Indian setup"),
    (["d4", "Nf6", "c4", "e6", "Nc3", "Bb4"],      "Nimzo-Indian Defense"),
    (["d4", "Nf6", "c4", "e6", "Nf3"],             "Queen's Indian setup"),
    (["d4", "f5"],                                 "Dutch Defense"),
    (["c4"],                                       "English Opening"),
    (["Nf3"],                                      "Réti Opening"),
    (["g3"],                                       "King's Fianchetto Opening"),
    (["b3"],                                       "Nimzo-Larsen Attack"),
    (["f4"],                                       "Bird's Opening"),
]


def identify_opening(sans):
    """Given a list of SAN moves, return best-matching opening name."""
    best = "Unknown Opening"
    best_len = 0
    for seq, name in OPENINGS:
        if len(seq) > len(sans):
            continue
        if sans[:len(seq)] == seq and len(seq) > best_len:
            best = name
            best_len = len(seq)
    return best
