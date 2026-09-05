#!/usr/bin/env python3
"""Join ESPN / consensus / Underdog exports into out/board.json for the viewer.

ESPN is the primary board: one row per ESPN player, in ESPN rank order.
The other sources attach as optional baselines.
"""

import csv
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from ffdraft.load import load_file          # noqa: E402
from ffdraft.names import player_key        # noqa: E402

MONTHS = ["january", "february", "march", "april", "may", "june", "july",
          "august", "september", "october", "november", "december"]

# Underdog pads its board to a fixed size; players who essentially never get
# drafted all pile up at the maximum. Treating that as a real ADP would invent
# enormous fake "value" gaps, so anything at the pile-up is "not drafted here".
UD_UNDRAFTED_MARGIN = 1.0


def _adp_columns(fieldnames):
    """Underdog's ADP headers carry dates ('ADP on September  5').

    Returns (baseline_col, latest_col) ordered by that date, so a refreshed
    export with new headers keeps working without a code change.
    """
    dated = []
    for name in fieldnames or []:
        m = re.match(r"\s*ADP on\s+([A-Za-z]+)\s+(\d{1,2})\s*$", name)
        if not m:
            continue
        month = m.group(1).lower()
        if month not in MONTHS:
            continue
        dated.append(((MONTHS.index(month), int(m.group(2))), name))
    if len(dated) < 1:
        raise ValueError("no 'ADP on <Month> <day>' columns found in Underdog export")
    dated.sort()
    return dated[0][1], dated[-1][1]


def load_underdog(path):
    """{player_key: {latest, baseline}} plus the label of the latest column."""
    with open(path, encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        base_col, latest_col = _adp_columns(reader.fieldnames)
        rows = list(reader)

    def num(row, col):
        try:
            return float(row[col])
        except (TypeError, ValueError):
            return None

    latest = [num(r, latest_col) for r in rows]
    floor = max(v for v in latest if v is not None)

    out = {}
    for row, cur in zip(rows, latest):
        if cur is None or cur >= floor - UD_UNDRAFTED_MARGIN:
            continue  # parked at the bottom of the board = undrafted
        key = player_key(row["Player"], row["Position"], "")
        if key in out:
            continue  # first (best-ranked) entry wins
        base = num(row, base_col)
        out[key] = {"cur": cur, "base": None if base is None or base >= floor - UD_UNDRAFTED_MARGIN else base}
    return out, latest_col.strip(), base_col.strip(), floor


def build(espn_path, consensus_path, underdog_path, out_path, teams=10):
    espn, _ = load_file(espn_path, "espn")
    cons, cmeta = load_file(consensus_path, "consensus")
    ud, ud_latest, ud_base, ud_floor = load_underdog(underdog_path)
    cons_by = {r["key"]: r for r in cons}

    players = []
    for e in sorted(espn, key=lambda r: r["rank"]):
        c = cons_by.get(e["key"])
        u = ud.get(e["key"])
        players.append({
            "n": e["name"], "p": e["pos"], "t": e["team"],
            "er": int(e["rank"]), "ea": e["adp"],
            "by": int(c["bye"]) if c and c["bye"] else None,
            "ca": c["adp"] if c else None,
            "chi": int(c["high"]) if c and c["high"] else None,
            "clo": int(c["low"]) if c and c["low"] else None,
            "ctd": int(c["times_drafted"] or 0) if c else None,
            "ua": u["cur"] if u else None,
            "uapr": u["base"] if u else None,
        })

    # Dates so the page can show how fresh each source is: comparing a stale
    # ESPN capture against a current market reads staleness as disagreement.
    espn_day = re.search(r"(\d{4})-(\d{2})-(\d{2})", espn_path)
    ud_day = re.match(r"ADP on\s+([A-Za-z]+)\s+(\d{1,2})", ud_latest)
    meta = {
        "teams": teams, "fmt": "PPR",
        "consensus_drafts": int(float(cmeta.get("total drafts", 0))),
        "consensus_teams": int(float(cmeta.get("teams", 12))),
        "ud_latest": ud_latest, "ud_base": ud_base,
        "espn_date": espn_day.group(0) if espn_day else "",
        "cons_dates": f"{cmeta.get('start date','')} to {cmeta.get('end date','')}",
        "ud_date": f"{ud_day.group(1)} {ud_day.group(2)}" if ud_day else ud_latest,
    }
    if espn_day and ud_day:
        import datetime
        e = datetime.date(int(espn_day.group(1)), int(espn_day.group(2)), int(espn_day.group(3)))
        u = datetime.date(e.year, MONTHS.index(ud_day.group(1).lower()) + 1, int(ud_day.group(2)))
        meta["stale_days"] = (u - e).days
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump({"meta": meta, "players": players}, fh, separators=(",", ":"))

    skill = [p for p in players if p["p"] not in ("K", "DEF")]
    print(f"espn {len(players)} | consensus {sum(1 for p in players if p['ca'] is not None)}"
          f" | underdog {sum(1 for p in players if p['ua'] is not None)}"
          f" (of {len(skill)} skill)")
    print(f"underdog columns: baseline '{ud_base}' -> latest '{ud_latest}'; "
          f"undrafted pile-up at {ud_floor}")
    missing = [p["n"] for p in skill if p["ua"] is None]
    if missing:
        print("skill players with no Underdog ADP:", ", ".join(missing))
    return meta, players


if __name__ == "__main__":
    root = os.path.join(os.path.dirname(__file__), "..")
    build(
        os.path.join(root, "data/raw/espn_2026-08-26.csv"),
        os.path.join(root, "data/raw/consensus_adp_2026-08-25.csv"),
        os.path.join(root, sys.argv[1] if len(sys.argv) > 1 else "data/raw/underdog_adp_2026-09-05.csv"),
        os.path.join(root, "out/board.json"),
    )
