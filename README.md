# fantasy-football-tool

Draft helper. First job: see where **ESPN's rankings and ADP disagree with a
generalized consensus ADP**, so you know who falls to you on ESPN and who you
have to reach for.

## Usage

```bash
python3 -c "import sys; sys.path.insert(0,'src'); from ffdraft.compare import main; main()" \
  --consensus data/raw/consensus_adp_2026-08-25.csv \
  --espn data/raw/espn.csv \
  --top 40 --csv-out out/compare.csv
```

Useful flags: `--pos RB`, `--max-adp 120` (draftable range only),
`--min-drafted 100` (drop thin-sample consensus rows), `--sort-by rank`
(compare ESPN's *editorial* ranking instead of its ADP), `--teams 12`.

## Reading the output

`DELTA = ESPN ADP - consensus ADP`, in overall picks.

- **positive** -> ESPN drafters let him fall. Wait on him; he's cheaper here.
- **negative** -> ESPN drafters reach. You pay above market or lose him.

`CONS`/`ESPN` are overall pick numbers, `PICK` the same as round.pick.

## Layout

- `data/raw/` - exports as pasted, unmodified
- `src/ffdraft/names.py` - name/team/position normalization for joining sources
- `src/ffdraft/load.py` - tolerant CSV loader (skips metadata preamble, guesses columns)
- `src/ffdraft/compare.py` - join, deltas, table + CSV output

No third-party dependencies; stdlib Python 3 only.

## Pulling ESPN automatically

ESPN's fantasy endpoints are undocumented but public for league defaults, and
carry both numbers we care about: their editorial draft rank and the ADP their
drafters actually produce.

```bash
python3 -c "import sys; sys.path.insert(0,'src'); from ffdraft.espn import main; main()" \
  --season 2026 --scoring ppr --out data/raw/espn.csv
```

If your network blocks the call, `--print-url` prints the request URL and the
`x-fantasy-filter` header. Open it in a browser, save the JSON, then:

```bash
... from ffdraft.espn import main; main()" --from-json espn.json --out data/raw/espn.csv
```

Then feed `data/raw/espn.csv` to the comparison above. Private-league data
(your actual draft board) needs `SWID` / `espn_s2` cookies and is not wired up
yet.

## Data provenance

- `data/raw/consensus_adp_2026-08-25.csv` - consensus export, PPR, **12-team**, 7,726 drafts.
- `data/raw/espn_2026-08-26.csv` - ESPN rank + ADP for the top 200, **hand-transcribed
  from a screen recording of the ESPN draft room** because the API is unreachable
  from the dev sandbox. Ranks 1-200 are complete with no gaps or duplicates, but the
  digits are read off video: re-pull with `ffdraft/espn.py` when a network path exists
  and diff before trusting it for a real draft.
- `data/raw/underdog_adp_2026-08-26.csv` - Underdog ADP incl. April->August movement. Unused so far.

### League size

The consensus sample is 12-team; the target league is **10-team, first pick**. Raw ADP
(overall pick number) compares fine across the two, but round.pick does not, so pass
`--teams 10` to get rounds that match the actual draft board.

## Viewer

`viewer/board.html` is the board itself (published as the Claude artifact;
`scripts/build_site.py` wraps it into `site/index.html` for the — currently
manual-only — GitHub Pages deploy).

It shows **ESPN's top 200 in ESPN's order**, each player tagged against a
selectable market baseline:

- **Market toggle** — Consensus (FFC, 7,726 12-team PPR drafts), Underdog
  (best-ball, half-PPR, no K/DST), or the average of both.
- **WAIT / HURRY / FAIR tags** — delta = ESPN ADP − market ADP. Positive
  (green, WAIT) means ESPN drafters take him later than the market, so he
  falls to you; negative (red, HURRY) means ESPN reaches, so market price is
  unpayable there. |delta| < 3 reads FAIR.
- **Seen X–Y** — the consensus sample's earliest/latest actual pick.
- **UD n ↑k** — Underdog ADP and board movement since April (↑ = climbing).
- Tap to cross off drafted players (localStorage); "Hide drafted" filters them.

The earlier live pick markers ("your pick", "on the clock") were removed on
request. Rebuild the embedded data with the exporter in git history, then
`python3 scripts/build_site.py`.
