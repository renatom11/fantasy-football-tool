"""Compare ESPN's ranking/ADP against a consensus ADP."""

import argparse
import sys

from .load import load_file


def to_round_pick(overall, teams=12):
    """147.0 -> '13.03' for a 12-team draft."""
    if overall is None:
        return ""
    n = int(round(overall))
    rnd, pick = divmod(n - 1, teams)
    return f"{rnd + 1}.{pick + 1:02d}"


def join(consensus_rows, espn_rows):
    """Merge two loaded sources on player key.

    Returns (merged, consensus_only, espn_only). `merged` carries both
    sources' numbers plus the deltas.
    """
    espn_by_key = {r["key"]: r for r in espn_rows}
    merged, consensus_only = [], []

    for c in consensus_rows:
        e = espn_by_key.pop(c["key"], None)
        if e is None:
            consensus_only.append(c)
            continue
        # Positive delta = ESPN is lower on him (available later on ESPN).
        adp_delta = (e["adp"] - c["adp"]) if e["adp"] is not None else None
        rank_delta = (e["rank"] - c["adp"]) if e["rank"] is not None else None
        merged.append({
            "key": c["key"],
            "name": c["name"],
            "espn_name": e["name"],
            "pos": c["pos"] or e["pos"],
            "team": c["team"] or e["team"],
            "bye": c["bye"] if c["bye"] is not None else e["bye"],
            "consensus_adp": c["adp"],
            "consensus_stdev": c["stdev"],
            "times_drafted": c["times_drafted"],
            "espn_adp": e["adp"],
            "espn_rank": e["rank"],
            "adp_delta": adp_delta,
            "rank_delta": rank_delta,
        })

    return merged, consensus_only, list(espn_by_key.values())


def positional_rank(rows, field):
    """Annotate each row with its rank within its position by `field`."""
    ranked = [r for r in rows if r.get(field) is not None]
    for pos in {r["pos"] for r in ranked}:
        group = sorted((r for r in ranked if r["pos"] == pos), key=lambda r: r[field])
        for i, r in enumerate(group, start=1):
            r[f"{field}_posrank"] = f"{pos}{i}"
    return rows


def _fmt(value, width, decimals=1):
    if value is None:
        return "-".rjust(width)
    return f"{value:.{decimals}f}".rjust(width)


def render_table(rows, teams=12, delta_field="adp_delta", limit=None):
    """Fixed-width table, biggest disagreements first."""
    rows = [r for r in rows if r.get(delta_field) is not None]
    rows.sort(key=lambda r: -abs(r[delta_field]))
    if limit:
        rows = rows[:limit]

    header = (f"{'PLAYER':<24}{'POS':<5}{'TM':<5}{'BYE':>4}"
              f"{'CONS':>7}{'PICK':>7}{'ESPN':>7}{'PICK':>7}{'ESPNrk':>8}{'DELTA':>8}  VERDICT")
    lines = [header, "-" * len(header)]
    for r in rows:
        d = r[delta_field]
        verdict = "ESPN VALUE (falls)" if d > 0 else "ESPN REACH (costs more)"
        lines.append(
            f"{r['name'][:23]:<24}{r['pos']:<5}{r['team']:<5}"
            f"{_fmt(r['bye'], 4, 0)}"
            f"{_fmt(r['consensus_adp'], 7)}{to_round_pick(r['consensus_adp'], teams):>7}"
            f"{_fmt(r['espn_adp'], 7)}{to_round_pick(r['espn_adp'], teams):>7}"
            f"{_fmt(r['espn_rank'], 8, 0)}{d:+8.1f}  {verdict}"
        )
    return "\n".join(lines)


def write_csv(rows, path, teams=12):
    import csv
    fields = ["name", "pos", "team", "bye", "consensus_adp", "consensus_pick",
              "consensus_stdev", "times_drafted", "espn_adp", "espn_pick",
              "espn_rank", "adp_delta", "rank_delta", "espn_name"]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in sorted(rows, key=lambda r: (r["consensus_adp"] is None, r["consensus_adp"])):
            row = dict(r)
            row["consensus_pick"] = to_round_pick(r["consensus_adp"], teams)
            row["espn_pick"] = to_round_pick(r["espn_adp"], teams)
            for k in ("adp_delta", "rank_delta"):
                if row.get(k) is not None:
                    row[k] = round(row[k], 1)
            w.writerow(row)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--consensus", required=True, help="consensus ADP export (csv)")
    p.add_argument("--espn", required=True, help="ESPN ranking/ADP export (csv)")
    p.add_argument("--teams", type=int, default=12)
    p.add_argument("--pos", help="filter to one position (RB, WR, ...)")
    p.add_argument("--max-adp", type=float, help="only players inside this consensus ADP")
    p.add_argument("--min-drafted", type=float, default=0,
                   help="drop consensus rows with fewer than N drafts (thin samples)")
    p.add_argument("--sort-by", choices=["adp", "rank"], default="adp",
                   help="compare ESPN ADP (default) or ESPN's editorial rank")
    p.add_argument("--top", type=int, default=40)
    p.add_argument("--csv-out", help="also write the full joined table here")
    args = p.parse_args(argv)

    consensus, cmeta = load_file(args.consensus, "consensus", teams=args.teams)
    espn, _ = load_file(args.espn, "espn", teams=args.teams)
    merged, consensus_only, espn_only = join(consensus, espn)

    rows = merged
    if args.pos:
        rows = [r for r in rows if r["pos"] == args.pos.upper()]
    if args.max_adp:
        rows = [r for r in rows if r["consensus_adp"] <= args.max_adp]
    if args.min_drafted:
        rows = [r for r in rows if (r["times_drafted"] or 0) >= args.min_drafted]

    field = "adp_delta" if args.sort_by == "adp" else "rank_delta"
    print(f"consensus: {len(consensus)} players  espn: {len(espn)}  matched: {len(merged)}"
          f"  ({cmeta.get('format','?')}, {args.teams}-team)")
    print()
    print(render_table(rows, teams=args.teams, delta_field=field, limit=args.top))

    if consensus_only or espn_only:
        print()
        print(f"unmatched -- consensus only: {len(consensus_only)}, espn only: {len(espn_only)}")
        for r in (consensus_only + espn_only)[:20]:
            print(f"  [{r['source']}] {r['name']} ({r['pos']} {r['team']})")

    if args.csv_out:
        write_csv(merged, args.csv_out, teams=args.teams)
        print(f"\nwrote {args.csv_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
