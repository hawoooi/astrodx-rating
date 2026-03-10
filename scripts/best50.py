#!/usr/bin/env python3
"""
best50.py — maimai DX Best 50 rating calculator.

  Best 50 = New 15  (best 15 from the two most recent game versions)
          + Old 35  (best 35 from all earlier versions)

Settings:
  NEW_VERSIONS_COUNT  number of recent versions that count as "new" (default 2)
                      e.g. CiRCLE → new = PRiSM PLUS (v255) + CiRCLE (v260)

Deduplication:
  Same chart in multiple folders → keep highest rated entry.
  Match key: title + artist + charter + level value + difficulty alias

Rating formula (myjian/mai-tools, MIT):
  rating = floor( internal_level × achievement × factor ) + ap_bonus
  AP / AP+ → +1 bonus

Internal level (SEGA API gives display level only):
  "X"  → X.0
  "X+" → X + 0.7

Credits:
  Rating formula  — myjian/mai-tools            https://github.com/myjian/mai-tools
  API endpoint    — zetaraku/arcade-songs-fetch  https://github.com/zetaraku/arcade-songs-fetch
  Song data       — maimai.sega.jp (© SEGA)
"""

import zlib, json, math, io, sys, os, unicodedata
import pandas as pd

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ── Settings ─────────────────────────────────────────────────────────────────
CACHE_FILE        = "cache"
CHARTS_FILE       = "maimai_charts.json"
CONSTANTS_FILE    = "chart_constants.json"
OUTPUT_FILE       = "best50.txt"
NEW_VERSIONS_COUNT = 2      # how many of the most recent versions count as "new"
SKIP_VERSIONS     = set()   # major versions to exclude entirely (e.g. {260} = CiRCLE)
SKIP_TITLES       = {"Xaleid◆scopiX"}  # songs to exclude entirely
FILTER_IMPOSSIBLE = True   # skip scores >= 101% on charts with display level 14+ or higher

# AstroDX alias → gekichumai/dxrating difficulty name
ALIAS_TO_DIFF = {
    "Basic":     "basic",
    "Advanced":  "advanced",
    "Expert":    "expert",
    "Master":    "master",
    "Re:Master": "remaster",
}

# ── Version name map (v100–v260, source: zetaraku/arcade-songs-fetch) ────────
VERSION_NAMES = {
    100: "maimai",
    110: "maimai PLUS",
    120: "GreeN",
    130: "GreeN PLUS",
    140: "ORANGE",
    150: "ORANGE PLUS",
    160: "PiNK",
    170: "PiNK PLUS",
    180: "MURASAKi",
    185: "MURASAKi PLUS",
    190: "MiLK",
    195: "MiLK PLUS",
    199: "FiNALE",
    200: "maimai DX",
    205: "maimai DX PLUS",
    210: "Splash",
    215: "Splash PLUS",
    220: "UNiVERSE",
    225: "UNiVERSE PLUS",
    230: "FESTiVAL",
    235: "FESTiVAL PLUS",
    240: "BUDDiES",
    245: "BUDDiES PLUS",
    250: "PRiSM",
    255: "PRiSM PLUS",
    260: "CiRCLE",
}

def version_name(v):
    return VERSION_NAMES.get(v, f"v{v}")

# ── Rating table (myjian/mai-tools src/common/rank-functions.ts) ─────────────
# (min_achv, factor, max_achv|None, max_factor|None)
# max_factor is used when achievement >= max_achv
RANK_TABLE = [
    (100.5, 0.224, None,     None ),
    (100.0, 0.216, 100.4999, 0.222),
    ( 99.5, 0.211,  99.9999, 0.214),
    ( 99.0, 0.208, None,     None ),
    ( 98.0, 0.203,  98.9999, 0.206),
    ( 97.0, 0.200, None,     None ),
    ( 94.0, 0.168,  96.9999, 0.176),
    ( 90.0, 0.152, None,     None ),
    ( 80.0, 0.136, None,     None ),
    ( 75.0, 0.120,  79.9999, 0.128),
    ( 70.0, 0.112, None,     None ),
    ( 60.0, 0.096, None,     None ),
    ( 50.0, 0.080, None,     None ),
    (  0.0, 0.016, None,     None ),
]

RANK_LABELS = [
    (100.5, "SSS+"), (100.0, "SSS"), (99.5, "SS+"), (99.0, "SS"),
    (98.0,  "S+"),   (97.0,  "S"),   (94.0, "AAA"), (90.0, "AA"),
    (80.0,  "A"),    (75.0,  "BBB"), (70.0, "BB"),  (60.0, "B"),
    (50.0,  "C"),    (0.0,   "D"),
]

CLEAR_LABELS = {
    0: "---", 1: "Clear", 2: "Clear",
    3: "FC",  4: "FC+",   5: "AP",   6: "AP+",
}

AP_CLEAR_TYPES = {5, 6}


def get_factor(achievement):
    achv = min(achievement, 100.5)
    for (min_a, factor, max_a, max_factor) in RANK_TABLE:
        if achv >= min_a:
            if max_a is not None and achv >= max_a:
                return max_factor
            return factor
    return 0.0


def get_rank_label(achievement):
    achv = min(achievement, 100.5)
    for threshold, label in RANK_LABELS:
        if achv >= threshold:
            return label
    return "D"


def get_rating(internal_level, achievement):
    achv = min(achievement, 100.5)
    return math.floor(abs(internal_level) * achv * get_factor(achv))


def parse_level(value):
    s = str(value).strip() if value else ""
    if s.endswith("+"):
        try:
            return float(s[:-1]) + 0.7
        except ValueError:
            return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def major_version(version_str):
    try:
        return int(str(version_str)) // 100
    except (ValueError, TypeError):
        return 0


# ── Load ──────────────────────────────────────────────────────────────────────

def load_cache():
    with open(CACHE_FILE, "rb") as f:
        return json.loads(zlib.decompress(f.read(), -15).decode("utf-8"))


def load_charts():
    if not os.path.exists(CHARTS_FILE):
        print(f"ERROR: {CHARTS_FILE} not found. Run fetch_charts.py first.")
        sys.exit(1)
    with open(CHARTS_FILE, encoding="utf-8") as f:
        return json.load(f)


def load_constants():
    if not os.path.exists(CONSTANTS_FILE):
        print(f"WARNING: {CONSTANTS_FILE} not found. Run fetch_constants.py for accurate chart constants.")
        return {}
    with open(CONSTANTS_FILE, encoding="utf-8") as f:
        return json.load(f)


def lookup_internal_level(constants, title_l, alias):
    """Return actual internalLevelValue for a chart, or None if not found."""
    diff_l = ALIAS_TO_DIFF.get(alias, alias.lower())
    return (constants.get(f"{title_l}|dx|{diff_l}")
            or constants.get(f"{title_l}|std|{diff_l}"))


def build_chart_index(charts):
    index = {}
    for song in charts:
        key = song["title"].lower()
        index.setdefault(key, []).append(song)
    return index


# ── Collect and deduplicate scores ────────────────────────────────────────────

def collect_scores(cache, chart_index, constants):
    scores = []

    for _folder_key, meta in cache["level_metadata"].items():
        title   = meta.get("title") or _folder_key
        artist  = meta.get("artist") or ""
        title_l = title.lower()
        api_matches = chart_index.get(title_l, [])

        for diff in meta.get("difficulties", []):
            stats = diff.get("stats", {})
            if stats.get("completePlays", 0) == 0:
                continue
            if title in SKIP_TITLES:
                continue

            alias   = diff.get("alias", "")
            value   = diff.get("value", "")
            charter = diff.get("charter") or ""
            acc     = stats.get("achievementRate", 0.0)
            ct      = stats.get("clearType", 0)

            if FILTER_IMPOSSIBLE and acc >= 101.0 and parse_level(value) >= 14.7:
                continue

            actual_lv   = lookup_internal_level(constants, title_l, alias)
            internal_lv = actual_lv if actual_lv is not None else parse_level(value)
            base_rating  = get_rating(internal_lv, acc)
            ap_bonus     = 1 if ct in AP_CLEAR_TYPES else 0
            total_rating = base_rating + ap_bonus

            # Version lookup from SEGA API
            ver = 0
            for api_song in api_matches:
                dx_key  = f"dx_{alias}"
                std_key = f"std_{alias}"
                api_val = (api_song["difficulties"].get(dx_key)
                           or api_song["difficulties"].get(std_key))
                if api_val == value:
                    ver = major_version(api_song.get("version", 0))
                    break
            if ver == 0 and api_matches:
                ver = major_version(api_matches[0].get("version", 0))

            scores.append({
                "title":   title,
                "artist":  artist,
                "charter": charter,
                "alias":   alias,
                "value":   value,
                "acc":     acc,
                "rank":    get_rank_label(acc),
                "clear":   CLEAR_LABELS.get(ct, "?"),
                "rating":  total_rating,
                "base":    base_rating,
                "ap":      ap_bonus,
                "int_lv":  internal_lv,
                "version": ver,
            })

    return scores


def deduplicate(scores):
    best = {}
    for s in scores:
        key = (
            s["title"].lower(),
            s["artist"].lower(),
            s["charter"].lower(),
            s["value"],
            s["alias"],
        )
        if key not in best or s["rating"] > best[key]["rating"]:
            best[key] = s
    return list(best.values())


# ── Best 50 split ─────────────────────────────────────────────────────────────

def compute_best50(scores):
    all_versions = sorted(
        set(s["version"] for s in scores if s["version"] > 0 and s["version"] not in SKIP_VERSIONS),
        reverse=True
    )
    new_versions = set(all_versions[:NEW_VERSIONS_COUNT])
    old_versions = set(all_versions[NEW_VERSIONS_COUNT:])

    new_scores = sorted(
        [s for s in scores if s["version"] in new_versions],
        key=lambda s: s["rating"], reverse=True
    )
    old_scores = sorted(
        [s for s in scores if s["version"] in old_versions and s["version"] not in SKIP_VERSIONS],
        key=lambda s: s["rating"], reverse=True
    )

    return new_scores[:15], old_scores[:35], new_versions, old_versions


# ── Pandas formatting ─────────────────────────────────────────────────────────

# Display-column widths (CJK chars occupy 2 columns each)
COL_W = {
    "#":        3,
    "Title":   28,
    "Artist":  20,
    "Diff":     9,
    "Lv":       3,
    "Int.Lv":   6,
    "Acc":     10,
    "Rank":     4,
    "Clear":    5,
    "Rating":   6,
    "AP":       3,
    "Version": 14,
}

def _disp(s):
    """Display-column width of a string (CJK = 2, others = 1)."""
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in str(s))

def _trunc(s, max_disp):
    """Truncate s so its display width <= max_disp, appending … if cut."""
    out, w = [], 0
    for ch in s:
        cw = 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
        if w + cw > max_disp:
            while out and w + 1 > max_disp:
                lw = 2 if unicodedata.east_asian_width(out[-1]) in ("W", "F") else 1
                w -= lw
                out.pop()
            out.append("…")
            return "".join(out)
        out.append(ch)
        w += cw
    return "".join(out)

def _ljust(s, width):
    """Left-pad s to display width using display-column measurement."""
    return str(s) + " " * max(0, width - _disp(str(s)))

def make_dataframe(entries, rank_start=1):
    rows = []
    for i, s in enumerate(entries, rank_start):
        rows.append({
            "#":       i,
            "Title":   _trunc(s["title"],          COL_W["Title"]),
            "Artist":  _trunc(s["artist"],         COL_W["Artist"]),
            "Diff":    s["alias"],
            "Lv":      s["value"],
            "Int.Lv":  f"{s['int_lv']:.1f}",
            "Acc":     f"{s['acc']:.4f}%",
            "Rank":    s["rank"],
            "Clear":   s["clear"],
            "Rating":  s["rating"],
            "AP":      f"+{s['ap']}" if s["ap"] else "",
            "Version": _trunc(version_name(s["version"]), COL_W["Version"]),
        })
    return pd.DataFrame(rows)


def df_to_string(df):
    cols = list(COL_W.keys())
    def fmt_row(vals):
        return "  ".join(_ljust(vals[c], COL_W[c]) for c in cols)
    header = fmt_row({c: c for c in cols})
    lines  = [header, "─" * _disp(header)]
    for _, row in df.iterrows():
        lines.append(fmt_row(dict(row)))
    return "\n".join(lines)


# ── Write output ──────────────────────────────────────────────────────────────

def write_output(new15, old35, new_versions, old_versions):
    total_new  = sum(s["rating"] for s in new15)
    total_old  = sum(s["rating"] for s in old35)
    total      = total_new + total_old

    new_ver_label = " + ".join(version_name(v) for v in sorted(new_versions))
    old_ver_label = " + ".join(version_name(v) for v in sorted(old_versions, reverse=True)[:3])
    if len(old_versions) > 3:
        old_ver_label += " + ..."

    df_new = make_dataframe(new15, rank_start=1)
    df_old = make_dataframe(old35, rank_start=1)

    sep = "═" * 120

    lines = [
        sep,
        f"  maimai DX Best 50",
        f"  Total Rating : {total}",
        f"  New 15 Total : {total_new}   Avg: {total_new/len(new15):.1f}" if new15 else "  New 15 Total : 0",
        f"  Old 35 Total : {total_old}   Avg: {total_old/len(old35):.1f}" if old35 else "  Old 35 Total : 0",
        sep,
        "",
        f"NEW 15  [{new_ver_label}]",
        "─" * 120,
        df_to_string(df_new),
        "",
        f"  Subtotal: {total_new}   ({len(new15)} charts)",
        "",
        f"OLD 35  [{old_ver_label}]",
        "─" * 120,
        df_to_string(df_old),
        "",
        f"  Subtotal: {total_old}   ({len(old35)} charts)",
        "",
        sep,
        "Credits:",
        "  Rating formula  — myjian/mai-tools            https://github.com/myjian/mai-tools",
        "  API endpoint    — zetaraku/arcade-songs-fetch  https://github.com/zetaraku/arcade-songs-fetch",
        "  Song data       — maimai.sega.jp (© SEGA)",
        sep,
    ]

    output = "\n".join(lines)

    # Print to console
    print(output)

    # Write to file
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(output + "\n")

    print(f"\nSaved to {OUTPUT_FILE}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    cache       = load_cache()
    charts      = load_charts()
    chart_index = build_chart_index(charts)
    constants   = load_constants()

    scores             = collect_scores(cache, chart_index, constants)
    scores             = deduplicate(scores)
    new15, old35, new_versions, old_versions = compute_best50(scores)

    write_output(new15, old35, new_versions, old_versions)


if __name__ == "__main__":
    main()
