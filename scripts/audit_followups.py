#!/usr/bin/env python3
"""Check committed follow-up evidence before any CI regeneration."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from runner.followup import audit_followups


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--portable", action="store_true", help="check recorded provenance without local executables or build trees")
    args = parser.parse_args()
    environment = json.loads((ROOT / "reports/environment.json").read_text())
    audit_followups(ROOT, environment, check_builds=not args.portable)
    print("Committed follow-up provenance passed; local executables were not verified." if args.portable
          else "Follow-up evidence and local builds passed")


if __name__ == "__main__":
    main()
