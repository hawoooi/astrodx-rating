import json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

targets = [
    ('バベル', 'Master'),
    ('with u', 'Master'),
    ('アンダーキッズ', 'Master'),
    ('テリトリーバトル', 'Master'),
    ('OMAKENO STROKE', 'Master'),
    ('complex mind', 'Master'),
    ('LOSE CONTROL', 'Master'),
    ('SUPersonic generation', 'Master'),
    ('N3V3R G3T OV3R', 'Master'),
    ('Zitronectar', 'Master'),
    ('raputa', 'Expert'),
    ('星空パーティーチューン', 'Master'),
    ('壱雫空', 'Master'),
]

with open('cache_pretty.json', encoding='utf-8') as f:
    data = json.load(f)

for (title_q, diff_q) in targets:
    found = False
    for key, meta in data['level_metadata'].items():
        title = meta.get('title') or key
        if title_q.lower() not in title.lower():
            continue
        for diff in meta.get('difficulties', []):
            if diff.get('alias', '').lower() != diff_q.lower():
                continue
            s = diff.get('stats', {})
            print(f"{title} | {diff_q} | totalNotes={s.get('totalNotesCount',0)} | plays={s.get('completePlays',0)} | acc={s.get('achievementRate',0):.4f} | key={key}")
            found = True
    if not found:
        print(f"NOT FOUND: {title_q} {diff_q}")
