#!/usr/bin/env python3
"""Wrap viewer/board.html (artifact source, headless fragment) into a full
standalone document at site/index.html for GitHub Pages.

The fragment's structure is: <title>, font <link>s, <style>...</style>, then
body markup + script. Everything through </style> belongs in <head>.
"""

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "viewer" / "board.html"
OUT = ROOT / "site" / "index.html"

FAVICON = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' "
           "viewBox='0 0 100 100'%3E%3Ctext y='.9em' font-size='90'%3E"
           "%F0%9F%8F%88%3C/text%3E%3C/svg%3E")

HEAD_EXTRA = f"""<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="description" content="12-team PPR draft board: where ESPN's ADP disagrees with the market (4for4, Draft Sharks, Underdog), with a researched status note for every player.">
<meta name="theme-color" media="(prefers-color-scheme: light)" content="#EBEFED">
<meta name="theme-color" media="(prefers-color-scheme: dark)" content="#0D1315">
<link rel="icon" href="{FAVICON}">
<meta name="apple-mobile-web-app-title" content="Delta Board">
"""


def main():
    frag = SRC.read_text(encoding="utf-8")
    marker = "</style>"
    cut = frag.find(marker)
    if cut < 0 or not frag.lstrip().startswith("<title>"):
        sys.exit("viewer/board.html does not look like the expected fragment "
                 "(<title> first, one </style>); refusing to build a broken site")
    cut += len(marker)
    head, body = frag[:cut], frag[cut:]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        "<!doctype html>\n<html lang=\"en\">\n<head>\n"
        + HEAD_EXTRA + head + "\n</head>\n<body>"
        + body + "\n</body>\n</html>\n",
        encoding="utf-8",
    )
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
