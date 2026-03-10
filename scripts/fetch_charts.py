#!/usr/bin/env python3
"""
fetch_charts.py — Fetch maimai DX chart data from the official SEGA API.

Fetches song and difficulty data from maimai.sega.jp and saves it locally
as maimai_charts.json. Can also cross-reference with your AstroDX cache
to fill in missing note counts and level values.

Usage:
  python fetch_charts.py                  # fetch and save chart data
  python fetch_charts.py --lookup "title" # look up a specific song
  python fetch_charts.py --enrich         # enrich cache with chart data

Data source:
  https://maimai.sega.jp/data/maimai_songs.json

Credits:
  API endpoint discovered via zetaraku/arcade-songs-fetch
  https://github.com/zetaraku/arcade-songs-fetch
  Licensed under MIT License — Copyright (c) zetaraku
"""

import json
import sys
import io
import urllib.request
import urllib.error
import os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

SEGA_API_URL  = "https://maimai.sega.jp/data/maimai_songs.json"
CHARTS_FILE   = "maimai_charts.json"
CACHE_FILE    = "cache"

DIFFICULTY_FIELDS = {
    "dx": {
        "Basic":     "dx_lev_bas",
        "Advanced":  "dx_lev_adv",
        "Expert":    "dx_lev_exp",
        "Master":    "dx_lev_mas",
        "Re:Master": "dx_lev_remas",
    },
    "std": {
        "Basic":     "lev_bas",
        "Advanced":  "lev_adv",
        "Expert":    "lev_exp",
        "Master":    "lev_mas",
        "Re:Master": "lev_remas",
    },
}


def fetch():
    print(f"Fetching from {SEGA_API_URL} ...")
    req = urllib.request.Request(
        SEGA_API_URL,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = json.loads(r.read().decode("utf-8"))
    except urllib.error.URLError as e:
        print(f"Error: {e}")
        sys.exit(1)

    songs = []
    for entry in raw:
        song = {
            "title":      entry.get("title", ""),
            "artist":     entry.get("artist", ""),
            "category":   entry.get("catcode", ""),
            "image":      entry.get("image_url", ""),
            "version":    entry.get("version", ""),
            "difficulties": {},
        }

        # DX difficulties
        for alias, field in DIFFICULTY_FIELDS["dx"].items():
            val = entry.get(field)
            if val:
                song["difficulties"][f"dx_{alias}"] = val

        # Standard difficulties
        for alias, field in DIFFICULTY_FIELDS["std"].items():
            val = entry.get(field)
            if val:
                song["difficulties"][f"std_{alias}"] = val

        songs.append(song)

    with open(CHARTS_FILE, "w", encoding="utf-8") as f:
        json.dump(songs, f, indent=2, ensure_ascii=False)

    print(f"Saved {len(songs)} songs to {CHARTS_FILE}")
    return songs


def load_charts():
    if not os.path.exists(CHARTS_FILE):
        print(f"{CHARTS_FILE} not found. Run without arguments to fetch first.")
        sys.exit(1)
    with open(CHARTS_FILE, encoding="utf-8") as f:
        return json.load(f)


def lookup(query):
    songs = load_charts()
    query = query.lower()
    results = [s for s in songs if query in s["title"].lower() or query in s["artist"].lower()]

    if not results:
        print("No results.")
        return

    for s in results:
        print(f"\n{s['title']} — {s['artist']}")
        print(f"  Category : {s['category']}")
        print(f"  Version  : {s['version']}")
        if s["difficulties"]:
            print("  Levels:")
            for diff, level in s["difficulties"].items():
                print(f"    {diff:<20} {level}")


def enrich():
    """Cross-reference AstroDX cache with chart data to fill missing note counts."""
    import zlib

    songs = load_charts()

    # Build lookup index by title (lowercase)
    index = {}
    for s in songs:
        key = s["title"].lower()
        index.setdefault(key, []).append(s)

    with open(CACHE_FILE, "rb") as f:
        cache = json.loads(zlib.decompress(f.read(), -15).decode("utf-8"))

    enriched = 0
    for meta in cache["level_metadata"].values():
        title = (meta.get("title") or "").lower()
        matches = index.get(title)
        if not matches:
            continue

        chart = matches[0]
        for diff in meta.get("difficulties", []):
            alias = diff.get("alias", "")
            stats = diff["stats"]

            # Fill level value if missing
            dx_key  = f"dx_{alias}"
            std_key = f"std_{alias}"
            level = chart["difficulties"].get(dx_key) or chart["difficulties"].get(std_key)

            if level and not diff.get("value"):
                diff["value"] = level
                enriched += 1

    import zlib as _zlib
    raw        = json.dumps(cache, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    compressed = _zlib.compress(raw, level=6)[2:-4]
    with open("cache_enriched", "wb") as f:
        f.write(compressed)

    print(f"Enriched {enriched} difficulty entries. Saved to cache_enriched.")


if __name__ == "__main__":
    args = sys.argv[1:]

    if not args:
        fetch()
    elif args[0] == "--lookup" and len(args) > 1:
        lookup(args[1])
    elif args[0] == "--enrich":
        enrich()
    else:
        print(__doc__)
        sys.exit(1)
