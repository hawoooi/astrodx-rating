import zlib, json, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

data = json.loads(zlib.decompress(open("cache", "rb").read(), -15).decode("utf-8"))

# Find the key with the 96% Expert score
target_key = None
for key, meta in data["level_metadata"].items():
    for diff in meta.get("difficulties", []):
        if abs(diff["stats"].get("achievementRate", 0) - 96.8357163439371) < 0.0001:
            target_key = key
            break
    if target_key:
        break

print(f"Found key: {target_key}")

# Patch Re:Master
notes = 2222
for diff in data["level_metadata"][target_key]["difficulties"]:
    if diff["alias"] == "Re:Master":
        diff["stats"].update({
            "clearType":       5,
            "achievementRate": 101.0,
            "dxScore":         notes * 3,
            "clearedPlays":    1,
            "completePlays":   1,
            "totalNotesCount": notes,
            "criticalCount":   notes,
            "perfectCount":    0,
            "greatCount":      0,
            "goodCount":       0,
            "maxCombo":        0,
        })
        print("Patched Re:Master stats:")
        print(json.dumps(diff["stats"], indent=2))
        break

# Repack
raw = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
compressed = zlib.compress(raw, level=6)[2:-4]
open("cache_repack_test", "wb").write(compressed)
print("\nWritten to cache_repack_test")
