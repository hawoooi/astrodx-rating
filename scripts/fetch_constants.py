#!/usr/bin/env python3
"""
fetch_constants.py — Fetch actual chart constants (internalLevelValue) from gekichumai/dxrating.

Downloads dxdata.json and saves chart_constants.json with per-chart internal level values.
This replaces the display-level estimation (e.g. "13+" → 13.7) with real constants.

Usage:
  python fetch_constants.py

Output:
  chart_constants.json  — lookup dict keyed by "title_lower|type|difficulty"

Data source:
  https://github.com/gekichumai/dxrating
  Licensed under AGPL-3.0 — Copyright (c) gekichumai contributors
"""

import json, sys, io, urllib.request, urllib.error

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

DXDATA_URL     = "https://raw.githubusercontent.com/gekichumai/dxrating/main/packages/dxdata/dxdata.json"
CONSTANTS_FILE = "chart_constants.json"


def fetch():
    print(f"Fetching from {DXDATA_URL} ...")
    req = urllib.request.Request(DXDATA_URL, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = json.loads(r.read().decode("utf-8"))
    except urllib.error.URLError as e:
        print(f"Error: {e}")
        sys.exit(1)

    songs = raw.get("songs", [])
    print(f"  {len(songs)} songs found")

    constants = {}
    for song in songs:
        title_l = song.get("title", "").lower()
        for sheet in song.get("sheets", []):
            stype = sheet.get("type", "")        # "dx" or "std"
            diff  = sheet.get("difficulty", "")  # "basic", "advanced", "expert", "master", "remaster"
            ilv   = sheet.get("internalLevelValue")
            if ilv is not None:
                key = f"{title_l}|{stype}|{diff}"
                constants[key] = ilv

    with open(CONSTANTS_FILE, "w", encoding="utf-8") as f:
        json.dump(constants, f, ensure_ascii=False)

    print(f"Saved {len(constants)} chart constants to {CONSTANTS_FILE}")


if __name__ == "__main__":
    fetch()
