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

`viewer/board.html` is a self-contained draft board (no build step, no dependencies —
open the file or publish it). Regenerate its embedded data after changing any source:

```bash
python3 -c "...ffdraft export..." > out/board.json   # see git history for the exporter
```

It sorts by board order / best value / biggest reach / ESPN rank, filters by position,
and crosses players off on tap (saved per-device in `localStorage`). Because every
crossed-off player is one pick spent, the **your pick** markers slide up the board as the
draft thins, so the top marker is always your real next turn — verified against the
snake math for a 10-team slot-1 draft (19 spent -> R2 2.10, 20 -> R3 3.01, 40 -> R5 5.01).

## Website

The board deploys to GitHub Pages on every push:
`https://renatom11.github.io/fantasy-football-tool/`

- `viewer/board.html` is the single source of truth (also published as the Claude artifact).
- `scripts/build_site.py` wraps it into a full standalone document at `site/index.html`.
- `.github/workflows/pages.yml` rebuilds and deploys. CI runs the build itself, so
  editing `viewer/board.html` alone is enough — the committed `site/index.html` is a
  convenience copy, not the deployed truth.

Note: the repo is private; GitHub Pages sites are still public URLs.
