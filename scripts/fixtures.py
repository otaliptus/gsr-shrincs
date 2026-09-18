#!/usr/bin/env python3
"""Regenerate public reproducible fixtures; never use these keys for funds."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from reference.oracle import real_vectors, synthetic_stateful


def main():
    vectors = real_vectors()
    for depth in (1, 7, 8, 9, 15, 16, 17, 31, 32, 33, 63, 64, 65, 254, 255):
        for index in (0, 2 ** min(depth, 64) - 1):
            vectors.append(synthetic_stateful(depth, index))
    (ROOT / "fixtures/vectors.json").write_text(
        json.dumps(
            dict(
                warning="PUBLIC TEST KEYS; not production signing",
                source="4cd63a6497a0ba7c5e99699b94d33973546d9e37",
                vectors=vectors,
            ),
            indent=2,
        )
        + "\n"
    )
    print(f"Generated {len(vectors)} verified vectors")


if __name__ == "__main__":
    main()
