#!/usr/bin/env python3
"""
Search your AstroDX scores.

Usage:
  python search.py <query>
  python search.py <query> --played
  python search.py <query> --diff Master

Options:
  --played       Only show difficulties you have played
  --diff <name>  Filter by difficulty alias (Basic, Advanced, Expert, Master, Re:Master)

Examples:
  python search.py "bad apple"
  python search.py "deco" --played
  python search.py "" --played --diff Master
"""

import zlib
import json
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

CACHE_FILE = "cache"

CLEAR_TYPES = {
    0: "---",
    1: "Clear",
    2: "Clear",
    3: "FC",
    4: "FC+",
    5: "AP",
    6: "AP+",
}


def load():
    with open(CACHE_FILE, "rb") as f:
        return json.loads(zlib.decompress(f.read(), -15).decode("utf-8"))


def search(query, played_only=False, diff_filter=None):
    data = load()
    query = query.lower()
    results = []

    for key, meta in data["level_metadata"].items():
        title   = meta.get("title") or key
        artist  = meta.get("artist") or ""
        charter = meta.get("charter") or ""

        if query and query not in title.lower() and query not in artist.lower():
            continue

        for diff in meta.get("difficulties", []):
            alias = diff.get("alias", "")
            if diff_filter and alias.lower() != diff_filter.lower():
                continue

            stats = diff.get("stats", {})
            plays = stats.get("completePlays", 0)

            if played_only and plays == 0:
                continue

            results.append({
                "title":   title,
                "artist":  artist,
                "charter": charter,
                "diff":    alias,
                "level":   diff.get("value", "?"),
                "acc":     stats.get("achievementRate", 0.0),
                "dx":      stats.get("dxScore", 0),
                "clear":   CLEAR_TYPES.get(stats.get("clearType", 0), "?"),
                "plays":   plays,
            })

    results.sort(key=lambda r: r["acc"], reverse=True)
    return results


def print_results(results):
    if not results:
        print("No results found.")
        return

    print(f"{'Title':<38} {'Artist':<22} {'Diff':<10} {'Lv':>3}  {'Acc':>8}  {'DX':>6}  {'Clear':<16}  Plays")
    print("-" * 120)
    for r in results:
        print(
            f"{r['title'][:37]:<38} {r['artist'][:21]:<22} {r['diff']:<10} {r['level']:>3}  "
            f"{r['acc']:>7.4f}%  {r['dx']:>6}  {r['clear']:<16}  {r['plays']}"
        )
    print(f"\n{len(results)} result(s)")


if __name__ == "__main__":
    args = sys.argv[1:]

    if not args:
        print(__doc__)
        sys.exit(1)

    query       = args[0]
    played_only = "--played" in args
    diff_filter = None

    if "--diff" in args:
        idx = args.index("--diff")
        if idx + 1 < len(args):
            diff_filter = args[idx + 1]

    print_results(search(query, played_only, diff_filter))
