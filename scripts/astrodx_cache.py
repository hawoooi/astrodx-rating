#!/usr/bin/env python3
"""
AstroDX cache file tool — decrypt and recompress chart-meta.fufu / cache

Usage:
  python astrodx_cache.py decrypt <input> [output]
  python astrodx_cache.py repack  <input> [output]

Examples:
  python astrodx_cache.py decrypt cache scores.json
  python astrodx_cache.py repack  scores.json cache
"""

import zlib
import json
import sys


def decrypt(input_path, output_path):
    with open(input_path, "rb") as f:
        compressed = f.read()

    try:
        raw = zlib.decompress(compressed, -15)
    except zlib.error as e:
        print(f"Error: decompression failed — {e}")
        sys.exit(1)

    data = json.loads(raw.decode("utf-8"))

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Decrypted:  {input_path} -> {output_path}")
    print(f"  Compressed   : {len(compressed):,} bytes")
    print(f"  Decompressed : {len(raw):,} bytes")
    print(f"  Levels       : {len(data.get('level_metadata', {}))}")


def repack(input_path, output_path):
    with open(input_path, encoding="utf-8") as f:
        data = json.load(f)

    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

    # zlib.compress produces: [2-byte header][deflate payload][4-byte checksum]
    # The game expects raw deflate only, so strip the wrapper.
    compressed = zlib.compress(raw, level=6)[2:-4]

    with open(output_path, "wb") as f:
        f.write(compressed)

    # Verify round-trip
    recovered = json.loads(zlib.decompress(compressed, -15).decode("utf-8"))
    if recovered != data:
        print("Error: round-trip verification failed. Output file may be corrupt.")
        sys.exit(1)

    print(f"Repacked:   {input_path} -> {output_path}")
    print(f"  JSON size        : {len(raw):,} bytes")
    print(f"  Compressed size  : {len(compressed):,} bytes")
    print(f"  Verification     : OK")


def usage():
    print(__doc__)
    sys.exit(1)


if __name__ == "__main__":
    args = sys.argv[1:]

    if len(args) < 2:
        usage()

    mode = args[0]

    if mode == "decrypt":
        input_path  = args[1]
        output_path = args[2] if len(args) > 2 else "scores.json"
        decrypt(input_path, output_path)

    elif mode == "repack":
        input_path  = args[1]
        output_path = args[2] if len(args) > 2 else "cache"
        repack(input_path, output_path)

    else:
        usage()
