"""Load a ranking/ADP export into a common row shape.

Sources disagree on column names and often prepend a metadata block, so the
loader finds the real header row and maps whatever it finds onto:

    key, name, pos, team, rank, adp, bye, times_drafted, stdev, high, low
"""

import csv
import io
import re

from .names import normalize_position, normalize_team, player_key

# Header spellings mapped onto our field names. Checked longest-first so
# "avg pick" wins over a bare "avg".
COLUMN_ALIASES = {
    "name": ["name", "player", "player name", "full name", "athlete"],
    "pos": ["position", "pos", "player position", "slot"],
    "team": ["team", "nfl team", "pro team", "tm"],
    "rank": ["overall rank", "rank", "rk", "espn rank", "ovr", "#"],
    "adp": ["adp", "avg pick", "average pick", "avg", "average draft position",
            "overall", "auction adp", "avg. pick"],
    "bye": ["bye", "bye week"],
    "times_drafted": ["times drafted", "drafted", "n", "count"],
    "stdev": ["std. dev", "std dev", "stdev", "sd", "std deviation"],
    "high": ["high", "best", "min"],
    "low": ["low", "worst", "max"],
}


def _canon_header(cell):
    return re.sub(r"\s+", " ", (cell or "").strip().lower()).strip()


def _map_columns(header):
    """header cells -> {field: column index}. Each column is used once."""
    cells = [_canon_header(c) for c in header]
    mapping = {}
    taken = set()
    for field, aliases in COLUMN_ALIASES.items():
        for alias in sorted(aliases, key=len, reverse=True):
            for i, cell in enumerate(cells):
                if i in taken or cell != alias:
                    continue
                mapping[field] = i
                taken.add(i)
                break
            if field in mapping:
                break
    return mapping


def _find_header(rows):
    """Index of the row that looks like a header (has a name-ish column)."""
    for i, row in enumerate(rows[:40]):
        cells = [_canon_header(c) for c in row]
        if any(c in COLUMN_ALIASES["name"] for c in cells) and len(row) >= 2:
            return i
    raise ValueError("no header row found (need a Name/Player column)")


def _num(value):
    """Parse a number, tolerating '1,954', '$12', '12.7%', '-', ''."""
    if value is None:
        return None
    s = str(value).strip().replace(",", "").replace("$", "").replace("%", "")
    if not s or s in {"-", "--", "N/A", "NA"}:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _round_pick_to_overall(value, teams):
    """'2.03' (round.pick) -> 15.0 overall. Returns None if it isn't one."""
    m = re.fullmatch(r"(\d{1,2})\.(\d{2})", str(value).strip())
    if not m:
        return None
    rnd, pick = int(m.group(1)), int(m.group(2))
    if pick < 1 or pick > teams:
        return None
    return float((rnd - 1) * teams + pick)


def read_meta(text):
    """Key/value pairs from a leading metadata block ('Teams:,12')."""
    meta = {}
    for row in csv.reader(io.StringIO(text)):
        if len(row) >= 2 and row[0].strip().endswith(":"):
            meta[row[0].strip().rstrip(":").lower()] = row[1].strip()
        elif row and _canon_header(row[0]) in COLUMN_ALIASES["name"] + ["adp", "rank", "rk"]:
            break
    return meta


def load(text, source, teams=None):
    """Parse an export into (rows, meta). `source` labels the rows."""
    meta = read_meta(text)
    if teams is None:
        teams = int(_num(meta.get("teams")) or 12)

    all_rows = [r for r in csv.reader(io.StringIO(text)) if any(c.strip() for c in r)]
    h = _find_header(all_rows)
    cols = _map_columns(all_rows[h])
    if "name" not in cols:
        raise ValueError(f"{source}: could not find a Name column")

    def cell(row, field):
        i = cols.get(field)
        return row[i].strip() if i is not None and i < len(row) else ""

    out = []
    for row in all_rows[h + 1:]:
        name = cell(row, "name")
        if not name or _canon_header(name) in COLUMN_ALIASES["name"]:
            continue  # blank or a repeated header mid-file

        adp = _num(cell(row, "adp"))
        # Some exports put "2.03" (round.pick) in the ADP column and the true
        # overall number in a second column; prefer the plain overall number.
        if adp is None or (cols.get("adp") is not None and
                           _round_pick_to_overall(cell(row, "adp"), teams) is not None):
            rp = _round_pick_to_overall(cell(row, "adp"), teams)
            overall = _num(cell(row, "rank"))
            adp = overall if overall is not None else rp

        out.append({
            "source": source,
            "key": player_key(name, cell(row, "pos"), cell(row, "team")),
            "name": name,
            "pos": normalize_position(cell(row, "pos")),
            "team": normalize_team(cell(row, "team")),
            "rank": _num(cell(row, "rank")),
            "adp": adp,
            "bye": _num(cell(row, "bye")),
            "times_drafted": _num(cell(row, "times_drafted")),
            "stdev": _num(cell(row, "stdev")),
            "high": _num(cell(row, "high")),
            "low": _num(cell(row, "low")),
        })
    return out, meta


def load_file(path, source=None, teams=None):
    with open(path, encoding="utf-8-sig") as fh:
        text = fh.read()
    return load(text, source or path, teams=teams)
