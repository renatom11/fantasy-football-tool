#!/usr/bin/env python3
"""Join the ESPN board with its market baselines into out/board.json.

ESPN is the primary board: one row per ESPN player, in ESPN rank order.
Baselines attached per player:
  * 4for4  - their blended ADP (the ADP column is the 12-team overall pick),
             plus the spread across the individual sites they aggregate.
  * Underdog - best-ball ADP, with movement since the export's first column.
  * Draft Sharks - their consensus ADP.
Plus, per player, a hand-researched status/role/narrative note (data/notes).
"""

import csv
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from ffdraft.load import load_file          # noqa: E402
from ffdraft.names import (is_defense, normalize_name, normalize_position,  # noqa: E402
                           normalize_team, player_key)

MONTHS = ["january", "february", "march", "april", "may", "june", "july",
          "august", "september", "october", "november", "december"]

# 4for4 aggregates these; NFL and BB10s ship empty, so they are left out.
SITES = ["CBS", "Fantrax", "FFPC", "NFFC", "Sleeper", "Y!", "Drafters", "Underdog"]

# Underdog pads its board to a fixed size; everyone who essentially never gets
# drafted piles up at the maximum. Treating that as an ADP invents huge fake gaps.
UD_UNDRAFTED_MARGIN = 1.0


def _num(value):
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def load_4for4(path):
    """{player_key: {adp, lo, hi, n}} - blended pick plus the site spread."""
    out = {}
    with open(path, encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            pos = row["Position"].split("-")[0]          # "RB-01" -> "RB", "K-1" -> "K"
            key = player_key(row["Player"], pos, row["Team"])
            if key in out:
                continue
            adp = _num(row["ADP"])
            if adp is None:
                continue
            picks = [v for v in (_num(row.get(s)) for s in SITES) if v is not None]
            out[key] = {
                "adp": adp,
                "lo": int(min(picks)) if picks else None,
                "hi": int(max(picks)) if picks else None,
                "n": len(picks),
            }
    return out


def _adp_columns(fieldnames):
    """Underdog's ADP headers carry dates ('ADP on September  5')."""
    dated = []
    for name in fieldnames or []:
        m = re.match(r"\s*ADP on\s+([A-Za-z]+)\s+(\d{1,2})\s*$", name)
        if m and m.group(1).lower() in MONTHS:
            dated.append(((MONTHS.index(m.group(1).lower()), int(m.group(2))), name))
    if not dated:
        raise ValueError("no 'ADP on <Month> <day>' columns in the Underdog export")
    dated.sort()
    return dated[0][1], dated[-1][1]


def load_underdog(path):
    with open(path, encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        base_col, latest_col = _adp_columns(reader.fieldnames)
        rows = list(reader)

    latest = [_num(r[latest_col]) for r in rows]
    floor = max(v for v in latest if v is not None)
    cutoff = floor - UD_UNDRAFTED_MARGIN

    out = {}
    for row, cur in zip(rows, latest):
        if cur is None or cur >= cutoff:
            continue
        key = player_key(row["Player"], row["Position"], "")
        if key in out:
            continue
        base = _num(row[base_col])
        out[key] = {"cur": cur, "base": None if base is None or base >= cutoff else base}
    return out, latest_col.strip(), base_col.strip()


def load_draftsharks(path, espn_rows):
    """Draft Sharks' consensus ADP, keyed onto the ESPN players.

    Their export abbreviates first names ("B. Robinson"), so players are
    matched on position + team + surname + first initial. That is ambiguous
    exactly once in this data - Bijan Robinson and Brian Robinson Jr. are both
    ATL running backs - so same-bucket players are paired in rank order,
    which puts the earlier DS rank on the earlier ESPN rank.
    """
    def bucket(name, pos, team):
        parts = normalize_name(name).split()
        if not parts:
            return None
        return (normalize_position(pos), normalize_team(team), parts[-1], parts[0][:1])

    espn_buckets = {}
    for r in espn_rows:
        if is_defense(r["name"], r["pos"]):
            continue
        espn_buckets.setdefault(bucket(r["name"], r["pos"], r["team"]), []).append(r)

    ds_buckets, by_key = {}, {}
    with open(path, encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            adp = _num(row["consensus_adp"])
            if adp is None:
                continue
            pos = re.sub(r"\d+$", "", row["pos_rank"])
            if normalize_position(pos) == "DEF":
                by_key[player_key(row["player"], pos, row["team"])] = adp
                continue
            b = bucket(row["player"], pos, row["team"])
            ds_buckets.setdefault(b, []).append((int(row["ds_rank"]), adp))

    unmatched = 0
    for b, ds_rows in ds_buckets.items():
        targets = espn_buckets.get(b)
        if not targets:
            unmatched += 1
            continue
        ds_rows.sort()
        for espn_row, (_, adp) in zip(sorted(targets, key=lambda r: r["rank"]), ds_rows):
            by_key[espn_row["key"]] = adp
    return by_key, unmatched


def load_notes(path):
    """{"Name|POS": {status, role, note, sources}} - researched per player."""
    if not path or not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def build(espn_path, f4_path, underdog_path, ds_path, out_path, teams=12,
          notes_path=None):
    espn, _ = load_file(espn_path, "espn")
    f4 = load_4for4(f4_path)
    ud, ud_latest, ud_base = load_underdog(underdog_path)
    ds, ds_unmatched = load_draftsharks(ds_path, espn)
    notes = load_notes(notes_path)

    players = []
    for e in sorted(espn, key=lambda r: r["rank"]):
        m = f4.get(e["key"])
        u = ud.get(e["key"])
        players.append({
            "n": e["name"], "p": e["pos"], "t": e["team"],
            "er": int(e["rank"]), "ea": e["adp"],
            "by": int(e["bye"]) if e["bye"] else None,
            "fa": m["adp"] if m else None,
            "flo": m["lo"] if m else None,
            "fhi": m["hi"] if m else None,
            "fn": m["n"] if m else None,
            "da": ds.get(e["key"]),
            "ua": u["cur"] if u else None,
            "uapr": u["base"] if u else None,
        })
        note = notes.get(f"{e['name']}|{e['pos']}")
        if note:
            players[-1].update({"st": note["status"], "ro": note["role"],
                                "nt": note["note"], "sr": note.get("sources", [])})

    espn_day = re.search(r"(\d{4})-(\d{2})-(\d{2})", espn_path)
    f4_day = re.search(r"(\d{4})-(\d{2})-(\d{2})", f4_path)
    ud_day = re.match(r"ADP on\s+([A-Za-z]+)\s+(\d{1,2})", ud_latest)
    meta = {
        "teams": teams, "fmt": "PPR",
        "espn_date": espn_day.group(0) if espn_day else "",
        "f4_date": f4_day.group(0) if f4_day else "",
        "ud_date": f"{ud_day.group(1)} {ud_day.group(2)}" if ud_day else ud_latest,
        "ud_base": ud_base, "sites": len(SITES), "ds_date": "2026-09-04",
    }
    notes_day = re.search(r"(\d{4})-(\d{2})-(\d{2})", notes_path or "")
    meta["notes_date"] = notes_day.group(0) if notes_day else ""
    if espn_day and ud_day:
        e = datetime.date(*(int(g) for g in espn_day.groups()))
        u = datetime.date(e.year, MONTHS.index(ud_day.group(1).lower()) + 1, int(ud_day.group(2)))
        meta["stale_days"] = (u - e).days

    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump({"meta": meta, "players": players}, fh, separators=(",", ":"))

    rated_n = [p for p in players if p["p"] != "HC"]
    skill = [p for p in players if p["p"] not in ("K", "DEF", "HC")]
    print(f"espn {len(players)} ({len(players) - len(rated_n)} head-coach rows)"
          f" | 4for4 {sum(1 for p in players if p['fa'] is not None)}"
          f" | sharks {sum(1 for p in players if p['da'] is not None)}"
          f" | underdog {sum(1 for p in players if p['ua'] is not None)} (of {len(skill)} skill)"
          f" | byes {sum(1 for p in players if p['by'] is not None)}"
          f" | notes {sum(1 for p in players if 'nt' in p)}")
    print(f"  draft-sharks rows with no ESPN match: {ds_unmatched}")
    # Head coaches are an ESPN-only draft slot; no ADP source lists them.
    rated = [p for p in players if p["p"] != "HC"]
    for label, miss in (("4for4", [p["n"] for p in rated if p["fa"] is None]),
                        ("sharks", [p["n"] for p in rated if p["da"] is None]),
                        ("underdog", [p["n"] for p in skill if p["ua"] is None]),
                        ("bye", [p["n"] for p in players if p["by"] is None]),
                        ("notes", [p["n"] for p in players if "nt" not in p])):
        if miss:
            print(f"  missing {label}: {', '.join(miss[:8])}{' ...' if len(miss) > 8 else ''}")
    return meta, players


if __name__ == "__main__":
    root = os.path.join(os.path.dirname(__file__), "..")
    j = lambda p: os.path.join(root, p)
    build(j("data/raw/espn_2026-09-05.csv"), j("data/raw/4for4_adp_2026-09-05.csv"),
          j("data/raw/underdog_adp_2026-09-05.csv"),
          j("data/raw/draftsharks_consensus_2026-09-04.tsv"), j("out/board.json"),
          notes_path=j("data/notes/player_notes_2026-09-05.json"))
