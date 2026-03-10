"""Patch scores in cache_pretty.json for the requested charts."""
import json, sys, io, math, urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

CACHE_FILE = 'cache_pretty.json'

# target: (title_substr, diff, accuracy, clear_label, dx_pct)
# clear_label: 'FC' -> clearType 3, 'FC+' -> clearType 4, '' -> clearType 2 (one miss)
TARGETS = [
    ('バベル',                'Master', 100.6732,  'FC',  0.87),
    ('with u',               'Master', 100.1951,  'FC',  0.87),
    ('アンダーキッズ',        'Master', 100.7304,  'FC+', 0.94),
    ('テリトリーバトル',      'Master', 100.2230,  '',    0.87),
    ('OMAKENO Stroke',       'Master', 100.1042,  '',    0.87),
    ('Complex Mind',         'Master', 100.5012,  'FC',  0.87),
    ('LOSE CONTROL',         'Master', 100.1923,  '',    0.87),
    ('Supersonic Generation','Master', 99.1000,   '',    0.87),
    ('N3V3R G3T OV3R',       'Master', 98.6708,   '',    0.87),
    ('Zitronectar',          'Master', 99.3042,   '',    0.87),
    ('raputa',               'Expert', 100.1420,  '',    0.87),
    ('星空パーティーチューン', 'Master', 100.3998,  '',    0.87),
    ('壱雫空',               'Master', 100.2860,  '',    0.87),
]

CLEAR_TYPE = {'FC': 3, 'FC+': 4, '': 2}

# ── Fetch note counts from dxdata for charts missing them ─────────────────────
def fetch_note_counts(needed_titles):
    print("Fetching note counts from gekichumai/dxrating...")
    url = "https://raw.githubusercontent.com/gekichumai/dxrating/main/packages/dxdata/dxdata.json"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = json.loads(r.read().decode('utf-8'))

    counts = {}
    for song in raw.get('songs', []):
        title = song.get('title', '')
        tl = title.lower()
        for q in needed_titles:
            if q.lower() not in tl:
                continue
            for sheet in song.get('sheets', []):
                diff = sheet.get('difficulty', '')
                nc = sheet.get('noteCounts', {})
                total = nc.get('total')
                if total:
                    key = (tl, diff)
                    counts[key] = total
    return counts


def calc_distribution(N, fc, dx_pct):
    """
    Returns (criticalCount, perfectCount, goodCount, dxScore).
    fc=True  -> all N notes are critical/perfect (no miss)
    fc=False -> N-1 notes are critical/perfect, 1 implicit miss
    """
    target_dx = math.floor(N * 3 * dx_pct)
    if fc:
        played = N
    else:
        played = N - 1

    # 3C + 2P = target_dx,  C + P = played
    C = target_dx - 2 * played
    P = 3 * played - target_dx

    if C < 0 or P < 0:
        # fallback: all criticals
        C = played
        P = 0
        target_dx = 3 * played

    return C, P, 0, target_dx


def main():
    with open(CACHE_FILE, encoding='utf-8') as f:
        data = json.load(f)

    lm = data['level_metadata']

    # First pass: find entries and collect which need note counts from API
    entries = []  # (key, meta, diff_entry, target)
    missing_note_counts = []

    for target in TARGETS:
        title_q, diff_q, acc, clear_lbl, dx_pct = target
        found = False
        for key, meta in lm.items():
            title = meta.get('title') or key
            if title_q.lower() not in title.lower():
                continue
            for diff_entry in meta.get('difficulties', []):
                if diff_entry.get('alias', '').lower() != diff_q.lower():
                    continue
                entries.append((key, meta, diff_entry, target))
                if diff_entry['stats'].get('totalNotesCount', 0) == 0:
                    missing_note_counts.append((title.lower(), diff_q.lower()))
                found = True
                break
            if found:
                break
        if not found:
            print(f"  WARNING: not found: {title_q} {diff_q}")

    # Fetch missing note counts if needed
    ext_counts = {}
    if missing_note_counts:
        diff_map = {'master': 'master', 'expert': 'expert', 'basic': 'basic',
                    'advanced': 'advanced', 're:master': 'remaster'}
        needed = set(t for t, _ in missing_note_counts)
        ext_counts = fetch_note_counts(needed)

    # Apply edits
    for (key, meta, diff_entry, target) in entries:
        title_q, diff_q, acc, clear_lbl, dx_pct = target
        title = meta.get('title') or key
        s = diff_entry['stats']
        N = s.get('totalNotesCount', 0)

        # Look up from API if needed
        if N == 0:
            diff_l = diff_q.lower()
            if diff_l == 're:master': diff_l = 'remaster'
            title_l = (meta.get('title') or key).lower()
            N = ext_counts.get((title_l, diff_l), 0)
            if N == 0:
                print(f"  SKIP (no note count): {title} {diff_q}")
                continue

        fc = clear_lbl in ('FC', 'FC+')
        ct = CLEAR_TYPE.get(clear_lbl, 2)
        C, P, G, dx = calc_distribution(N, fc, dx_pct)

        existing_plays = s.get('completePlays', 0)
        plays = max(existing_plays, 1)

        s['clearType']       = ct
        s['achievementRate'] = acc
        s['dxScore']         = dx
        s['maxCombo']        = 0
        s['clearedPlays']    = plays
        s['completePlays']   = plays
        s['totalNotesCount'] = N
        s['criticalCount']   = C
        s['perfectCount']    = P
        s['greatCount']      = G
        s['goodCount']       = 0

        print(f"  OK  {title} {diff_q}: acc={acc} ct={ct} N={N} dx={dx} C={C} P={P}")

    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print("Saved.")

main()
