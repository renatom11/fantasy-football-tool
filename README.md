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
