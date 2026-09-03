"""PGN and PDF export."""
import os
from datetime import datetime

import chess
import chess.pgn


def export_pgn(path: str, moves_uci, white_name: str, black_name: str,
               result: str, opening: str = "", event: str = "ChessMaster Game"):
    game = chess.pgn.Game()
    game.headers["Event"] = event
    game.headers["Site"] = "ChessMaster"
    game.headers["Date"] = datetime.now().strftime("%Y.%m.%d")
    game.headers["Round"] = "-"
    game.headers["White"] = white_name
    game.headers["Black"] = black_name
    game.headers["Result"] = result
    if opening:
        game.headers["Opening"] = opening
    node = game
    board = chess.Board()
    for u in moves_uci:
        try:
            m = chess.Move.from_uci(u)
            if m in board.legal_moves:
                node = node.add_variation(m)
                board.push(m)
        except Exception:
            break
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        exporter = chess.pgn.FileExporter(f)
        game.accept(exporter)
    return path


def export_analysis_pdf(path: str, meta: dict, analysis: dict):
    """Export a human-readable text 'PDF' report.

    Attempts real PDF via reportlab if available; else writes a
    plain-text .pdf.txt file. Keeps the app runnable without hard deps.
    """
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
        from reportlab.lib.units import inch
        c = canvas.Canvas(path, pagesize=letter)
        w, h = letter
        y = h - 0.75 * inch
        c.setFont("Helvetica-Bold", 18)
        c.drawString(0.75 * inch, y, "ChessMaster - Game Analysis")
        y -= 0.35 * inch
        c.setFont("Helvetica", 11)
        for line in _summary_lines(meta, analysis):
            if y < 0.75 * inch:
                c.showPage(); y = h - 0.75 * inch
                c.setFont("Helvetica", 11)
            c.drawString(0.75 * inch, y, line[:110])
            y -= 0.20 * inch
        c.save()
        return path
    except Exception:
        # Fallback plain-text
        txt_path = path + ".txt" if not path.endswith(".txt") else path
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write("ChessMaster - Game Analysis Report\n")
            f.write("=" * 44 + "\n\n")
            for line in _summary_lines(meta, analysis):
                f.write(line + "\n")
        return txt_path


def _summary_lines(meta, analysis):
    lines = []
    lines.append(f"Date        : {meta.get('date', datetime.now().strftime('%Y-%m-%d %H:%M'))}")
    lines.append(f"White       : {meta.get('white_name','-')}")
    lines.append(f"Black       : {meta.get('black_name','-')}")
    lines.append(f"Result      : {meta.get('result','*')}")
    lines.append(f"Opening     : {analysis.get('opening','Unknown')}")
    lines.append(f"Duration    : {meta.get('duration_sec', 0)}s")
    lines.append("")
    lines.append("--- Accuracy ---")
    lines.append(f"White       : {analysis.get('accuracy_white',0)} %  (avg CPL {analysis.get('avg_cp_loss_white',0)})")
    lines.append(f"Black       : {analysis.get('accuracy_black',0)} %  (avg CPL {analysis.get('avg_cp_loss_black',0)})")
    lines.append("")
    lines.append("--- Move Classification ---")
    for k in ("brilliant","great","best","excellent","good","book",
              "inaccuracy","mistake","blunder","missed_win","missed_mate"):
        lines.append(f"  {k:<14}: {analysis.get(k,0)}")
    lines.append("")
    lines.append("--- Move-by-move ---")
    for row in analysis.get("classification_json", []):
        lines.append(f"  {row['ply']:>3}. {row['side'][:1].upper()} {row['san']:<8} "
                     f"[{row['classification']:<12}] cp_loss={row['cp_loss']:>4}"
                     f"  best={row.get('best_move','-')}")
    return lines
