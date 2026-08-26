"""Normalize player names and teams so different sources can be joined."""

import re
import unicodedata

# Suffixes that sources add or drop inconsistently (ESPN says "Kyle Pitts",
# consensus says "Kyle Pitts Sr.").
SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v"}

# First-name nicknames that differ across sources (ESPN "Kenny Gainwell",
# Underdog "Kenneth Gainwell"). Keep this to proven cases only: folding
# nicknames aggressively merges different players who share a surname.
FIRST_NAME_ALIASES = {"kenny": "kenneth"}

# Team abbreviation variants -> canonical (consensus/FFPC style).
TEAM_ALIASES = {
    "WSH": "WAS", "WFT": "WAS",
    "JAC": "JAX",
    "LA": "LAR", "STL": "LAR",
    "SD": "LAC",
    "OAK": "LV", "LVR": "LV",
    "KCC": "KC", "SFO": "SF", "TAM": "TB", "NOR": "NO", "NWE": "NE",
    "GNB": "GB", "ARZ": "ARI", "BLT": "BAL", "CLV": "CLE", "HST": "HOU",
    "FA": "", "": "",
}

# Full team name -> abbreviation, for D/ST rows named after a city or nickname.
TEAM_NAMES = {
    "arizona": "ARI", "cardinals": "ARI",
    "atlanta": "ATL", "falcons": "ATL",
    "baltimore": "BAL", "ravens": "BAL",
    "buffalo": "BUF", "bills": "BUF",
    "carolina": "CAR", "panthers": "CAR",
    "chicago": "CHI", "bears": "CHI",
    "cincinnati": "CIN", "bengals": "CIN",
    "cleveland": "CLE", "browns": "CLE",
    "dallas": "DAL", "cowboys": "DAL",
    "denver": "DEN", "broncos": "DEN",
    "detroit": "DET", "lions": "DET",
    "green bay": "GB", "packers": "GB",
    "houston": "HOU", "texans": "HOU",
    "indianapolis": "IND", "colts": "IND",
    "jacksonville": "JAX", "jaguars": "JAX",
    "kansas city": "KC", "chiefs": "KC",
    "las vegas": "LV", "raiders": "LV",
    "la chargers": "LAC", "los angeles chargers": "LAC", "chargers": "LAC",
    "la rams": "LAR", "los angeles rams": "LAR", "rams": "LAR",
    "miami": "MIA", "dolphins": "MIA",
    "minnesota": "MIN", "vikings": "MIN",
    "new england": "NE", "patriots": "NE",
    "new orleans": "NO", "saints": "NO",
    "ny giants": "NYG", "new york giants": "NYG", "giants": "NYG",
    "ny jets": "NYJ", "new york jets": "NYJ", "jets": "NYJ",
    "philadelphia": "PHI", "eagles": "PHI",
    "pittsburgh": "PIT", "steelers": "PIT",
    "san francisco": "SF", "49ers": "SF", "niners": "SF",
    "seattle": "SEA", "seahawks": "SEA",
    "tampa bay": "TB", "buccaneers": "TB", "bucs": "TB",
    "tennessee": "TEN", "titans": "TEN",
    "washington": "WAS", "commanders": "WAS",
}

# Position spellings that vary by source.
POSITION_ALIASES = {
    "PK": "K", "KICKER": "K",
    "DST": "DEF", "D/ST": "DEF", "DEFENSE": "DEF", "D": "DEF",
    "FB": "RB",
}

_DEF_MARKERS = re.compile(r"\b(d/?st|defense|def)\b", re.I)


def normalize_team(team):
    """Canonical team abbreviation, or '' when unknown/free agent."""
    t = (team or "").strip().upper()
    return TEAM_ALIASES.get(t, t)


def normalize_position(pos):
    """Canonical position: QB/RB/WR/TE/K/DEF."""
    p = (pos or "").strip().upper().replace("/", "")
    p = POSITION_ALIASES.get(p, POSITION_ALIASES.get((pos or "").strip().upper(), p))
    return p


def is_defense(name, pos=""):
    """True when the row is a team defense rather than a person."""
    return normalize_position(pos) == "DEF" or bool(_DEF_MARKERS.search(name or ""))


def defense_team(name, team=""):
    """Team abbreviation for a D/ST row, from its team column or its name."""
    canon = normalize_team(team)
    if canon:
        return canon
    stripped = _DEF_MARKERS.sub("", name or "").strip().lower()
    return TEAM_NAMES.get(stripped, "")


def normalize_name(name):
    """Strip accents, punctuation, case, and name suffixes.

    "Ka'imi Fairbairn" -> "kaimi fairbairn"; "Kyle Pitts Sr." -> "kyle pitts".
    """
    n = unicodedata.normalize("NFKD", name or "")
    n = "".join(c for c in n if not unicodedata.combining(c))
    n = n.lower()
    n = re.sub(r"[.'’`]", "", n)          # Ka'imi -> kaimi, A.J. -> aj
    n = re.sub(r"[^a-z0-9 ]+", " ", n)         # hyphens/commas -> space
    parts = [p for p in n.split() if p]
    while len(parts) > 2 and parts[-1] in SUFFIXES:
        parts.pop()
    if parts:
        parts[0] = FIRST_NAME_ALIASES.get(parts[0], parts[0])
    return " ".join(parts)


def player_key(name, pos="", team=""):
    """Join key for one player row.

    Defenses key on team (names differ wildly across sources). Skill players
    key on normalized name plus position, so two players who share a name are
    only merged when they also share a position.
    """
    if is_defense(name, pos):
        return ("DEF", defense_team(name, team))
    return (normalize_position(pos), normalize_name(name))
