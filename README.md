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
