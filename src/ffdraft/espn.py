"""Fetch ESPN's fantasy rankings/ADP and write them in our CSV shape.

ESPN's fantasy endpoints are undocumented but stable. The `leaguedefaults`
view is public (no auth) and returns, per player, both ESPN's editorial draft
rank and the ADP their drafters actually produce.

Blocked by egress policy? Open the URL this prints in a browser, save the
JSON, and re-run with --from-json.
"""

import argparse
import csv
import json
import sys
import urllib.request

BASE = ("https://lm-api-reads.fantasy.espn.com/apis/v3/games/ffl/seasons/"
        "{season}/segments/0/leaguedefaults/{scoring}")

# leaguedefaults scoring id -> rank type key inside draftRanksByRankType.
# 3 is PPR; the others are best-effort and easy to correct if ESPN differs.
SCORING = {"standard": (1, "STANDARD"), "half": (2, "PPR"), "ppr": (3, "PPR")}

POSITIONS = {1: "QB", 2: "RB", 3: "WR", 4: "TE", 5: "K", 16: "DEF"}

PRO_TEAMS = {
    0: "", 1: "ATL", 2: "BUF", 3: "CHI", 4: "CIN", 5: "CLE", 6: "DAL", 7: "DEN",
    8: "DET", 9: "GB", 10: "TEN", 11: "IND", 12: "KC", 13: "LV", 14: "LAR",
    15: "MIA", 16: "MIN", 17: "NE", 18: "NO", 19: "NYG", 20: "NYJ", 21: "PHI",
    22: "ARI", 23: "PIT", 24: "LAC", 25: "SF", 26: "SEA", 27: "TB", 28: "WAS",
    29: "CAR", 30: "JAX", 33: "BAL", 34: "HOU",
}

# Without a browser-ish UA ESPN sometimes returns an error page instead of JSON.
HEADERS = {
    "accept": "application/json",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36",
}


def build_filter(limit=800, rank_type="PPR"):
    return json.dumps({"players": {
        "limit": limit,
        "sortDraftRanks": {"sortPriority": 100, "sortAsc": True, "value": rank_type},
    }})


def url_for(season, scoring="ppr"):
    scoring_id, rank_type = SCORING[scoring]
    return BASE.format(season=season, scoring=scoring_id) + "?view=kona_player_info", rank_type


def fetch(season, scoring="ppr", limit=800, timeout=30):
    """GET the player payload. Raises urllib errors on failure."""
    url, rank_type = url_for(season, scoring)
    req = urllib.request.Request(url, headers={
        **HEADERS, "x-fantasy-filter": build_filter(limit, rank_type)})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8")), rank_type


def extract(payload, rank_type="PPR"):
    """ESPN JSON -> rows matching our CSV columns.

    Tolerates the two shapes ESPN returns: a bare list of player entries, or
    an object with a "players" list.
    """
    entries = payload.get("players", payload) if isinstance(payload, dict) else payload
    rows = []
    for entry in entries:
        p = entry.get("player", entry) if isinstance(entry, dict) else {}
        if not p.get("fullName"):
            continue

        ranks = p.get("draftRanksByRankType") or {}
        rank_block = ranks.get(rank_type) or ranks.get("PPR") or ranks.get("STANDARD") or {}
        ownership = p.get("ownership") or {}

        adp = ownership.get("averageDraftPosition")
        rows.append({
            "Rank": rank_block.get("rank"),
            "Player": p["fullName"],
            "Team": PRO_TEAMS.get(p.get("proTeamId"), ""),
            "Position": POSITIONS.get(p.get("defaultPositionId"), ""),
            "ADP": round(adp, 1) if isinstance(adp, (int, float)) and adp > 0 else None,
            "Auction": rank_block.get("auctionValue"),
            "Percent Owned": round(ownership["percentOwned"], 1)
                             if isinstance(ownership.get("percentOwned"), (int, float)) else None,
        })

    rows.sort(key=lambda r: (r["Rank"] is None, r["Rank"] or 0))
    return rows


def write_csv(rows, path):
    fields = ["Rank", "Player", "Team", "Position", "ADP", "Auction", "Percent Owned"]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--season", type=int, default=2026)
    p.add_argument("--scoring", choices=sorted(SCORING), default="ppr")
    p.add_argument("--limit", type=int, default=800)
    p.add_argument("--from-json", help="parse a saved JSON payload instead of fetching")
    p.add_argument("--out", default="data/raw/espn.csv")
    p.add_argument("--print-url", action="store_true",
                   help="print the request URL and filter header, then exit")
    args = p.parse_args(argv)

    url, rank_type = url_for(args.season, args.scoring)
    if args.print_url:
        print(url)
        print(f"x-fantasy-filter: {build_filter(args.limit, rank_type)}")
        return 0

    if args.from_json:
        with open(args.from_json, encoding="utf-8") as fh:
            payload = json.load(fh)
    else:
        try:
            payload, rank_type = fetch(args.season, args.scoring, args.limit)
        except Exception as exc:
            print(f"fetch failed: {exc}\n\nOpen this in a browser, save the JSON, "
                  f"then re-run with --from-json:\n  {url}\n"
                  f"  header x-fantasy-filter: {build_filter(args.limit, rank_type)}",
                  file=sys.stderr)
            return 1

    rows = extract(payload, rank_type)
    if not rows:
        print("no players parsed -- ESPN's field names may have moved", file=sys.stderr)
        return 1

    write_csv(rows, args.out)
    with_adp = sum(1 for r in rows if r["ADP"])
    print(f"wrote {len(rows)} players to {args.out} ({with_adp} with an ADP, {rank_type})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
