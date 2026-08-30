#!/usr/bin/env python3
"""
Finalize a cleaned CSV: recover any data available for free from the master
cache, then dedupe by LinkedIn URL and write the final attendee list.

No Apollo calls are made here. A live test found that once a person comes
back without title/company/city on enrich.py's first pass (which already
sends email/organization_name hints when available), a second Apollo call
essentially never recovers anything -- 0/19 real people in a name-only
retry test -- and resending an already-tried hint costs a credit either
way, win or lose. What's left after the first pass is very likely a
genuine gap in Apollo's own data, not something a retry fixes.

Usage:
  python retry_missed.py <clean_file.csv>
"""

import csv
import os
import re
import sys
from datetime import datetime

MASTER_FILE      = os.path.join(os.path.dirname(os.path.abspath(__file__)), "master_enriched.csv")
STALE_AFTER_DAYS = 182  # ~6 months — cached entries older than this are treated as not-cached
DATA_FIELDS = [
    "first_name", "last_name", "linkedin_email",
    "title", "company", "location",
    "linkedin_url", "company_website", "linkedin_public_url",
    "city", "country",
]
MASTER_FIELDS = DATA_FIELDS + ["cached_at"]


def normalize_url(url):
    url = (url or "").strip().lower().rstrip("/")
    return re.sub(r"^https?://(www\.)?", "", url)


def is_fresh(cache_row):
    cached_at = cache_row.get("cached_at", "")
    if not cached_at:
        return False
    try:
        cached_date = datetime.strptime(cached_at, "%Y-%m-%d")
    except ValueError:
        return False
    return (datetime.now() - cached_date).days <= STALE_AFTER_DAYS


def cache_lookup(master, key):
    if key and key in master and is_fresh(master[key]):
        return master[key]
    return None


def load_master():
    cache = {}
    if os.path.exists(MASTER_FILE):
        with open(MASTER_FILE, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                key = normalize_url(row.get("linkedin_url"))
                if key:
                    cache[key] = {field: row.get(field, "") or "" for field in MASTER_FIELDS}
    return cache


def is_missed(row):
    return not row["title"] and not row["company"] and not row["city"]


def main():
    if len(sys.argv) < 2:
        print("Usage: python retry_missed.py <clean_file.csv>")
        sys.exit(1)

    clean_file = sys.argv[1]
    if not os.path.exists(clean_file):
        print(f"Error: File not found — {clean_file}")
        sys.exit(1)

    print(f"\nLoading: {clean_file}")

    with open(clean_file, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    master = load_master()

    # ── Recover missed rows from the master cache (free — no Apollo calls) ────
    recovered = 0
    for row in rows:
        if not is_missed(row):
            continue
        key = normalize_url(row.get("linkedin_url"))
        cached = cache_lookup(master, key)
        if cached:
            for field in DATA_FIELDS:
                if field in row:
                    row[field] = cached.get(field, "")
            recovered += 1

    still_missing = sum(1 for r in rows if is_missed(r))

    # ── Deduplicate by LinkedIn URL and write the final file ──────────────────
    seen = {}
    for row in rows:
        key = normalize_url(row.get("linkedin_url"))
        seen[key] = row
    deduped = list(seen.values())
    removed_dupes = len(rows) - len(deduped)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path  = f"attendees_final_{timestamp}.csv"

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(deduped)

    # ── Summary ─────────────────────────────────────────────────────────────
    print(f"\n{'-' * 54}")
    print(f"  FINALIZE SUMMARY")
    print(f"{'-' * 54}")
    print(f"  Recovered from cache (free)    : {recovered}")
    print(f"  Still missing (no Apollo data) : {still_missing}")
    print(f"  Duplicates removed             : {removed_dupes}")
    print(f"  Total rows in output           : {len(deduped)}")
    print(f"  Output file                    : {out_path}")
    print(f"{'-' * 54}\n")


if __name__ == "__main__":
    main()
