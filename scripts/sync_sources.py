"""Sync external content sources into the knowledge library.

Usage:
  python scripts/sync_sources.py                      # all adapters
  python scripts/sync_sources.py ncert wikipedia      # chosen adapters
  python scripts/sync_sources.py ncert --limit 4      # cap docs per adapter

Idempotent: each adapter skips documents whose source URL is already
indexed (Wikipedia replaces Phase-1 lead summaries with full articles).
Safe to re-run any time; failures on one item never abort the sync.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.library import store
from src.library.adapters import ADAPTERS


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("adapters", nargs="*",
                        help=f"which of {sorted(ADAPTERS)} to run "
                             "(default: all)")
    parser.add_argument("--limit", type=int, default=0,
                        help="max new documents per adapter (0 = no cap)")
    args = parser.parse_args()

    unknown = [n for n in args.adapters if n not in ADAPTERS]
    if unknown:
        parser.error(f"unknown adapter(s) {unknown}; choose from "
                     f"{sorted(ADAPTERS)}")
    names = args.adapters or list(ADAPTERS)
    con = store.connect()
    for name in names:
        print(f"[{name}]")
        added = ADAPTERS[name](con, limit=args.limit)
        print(f"[{name}] {added} document(s) added")
    print("Library:", store.stats(con))
    con.close()


if __name__ == "__main__":
    main()
