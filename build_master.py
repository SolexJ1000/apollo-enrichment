#!/usr/bin/env python3
"""
Top up master_enriched.csv from enriched CSVs already in this folder.

Existing cache entries that already carry a real cached_at date are treated
as authoritative and are never overwritten by this script — only genuinely
new people, or legacy entries with no cached_at yet, get filled in (using
the source file's last-modified date as a stand-in timestamp).

Safe to re-run any time — it doesn't call Apollo, just scans local files.

Usage: python build_master.py
"""

import csv
import glob
import os
import re
from datetime import datetime

DIR = os.path.dirname(os.path.abspath(__file__))
MASTER_FILE = os.path.join(DIR, "master_enriched.csv")

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


def is_enriched(row):
    return bool(row.get("title") or row.get("company") or row.get("city"))


def load_master():
    cache = {}
    if os.path.exists(MASTER_FILE):
        with open(MASTER_FILE, newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                key = normalize_url(row.get("linkedin_url"))
                if key:
                    cache[key] = {field: row.get(field, "") or "" for field in MASTER_FIELDS}
    return cache


def main():
    master = load_master()
    starting_count = len(master)

    candidates = sorted(glob.glob(os.path.join(DIR, "*.csv")), key=os.path.getmtime)

    scanned = 0
    filled = 0
    for path in candidates:
        if os.path.abspath(path) == MASTER_FILE:
            continue
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            fields = set(h.strip().lower() for h in (reader.fieldnames or []))
            if not {"linkedin_url", "title", "company"}.issubset(fields):
                continue
            scanned += 1
            file_date = datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d")
            for row in reader:
                row = {k.strip().lower(): (v or "") for k, v in row.items()}
                if not is_enriched(row):
                    continue
                key = normalize_url(row.get("linkedin_url"))
                if not key:
                    continue

                existing = master.get(key)
                if existing and existing.get("cached_at"):
                    continue  # already tracked with a real date — don't clobber

                master[key] = {field: row.get(field, "") for field in DATA_FIELDS}
                master[key]["cached_at"] = file_date
                filled += 1

    with open(MASTER_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=MASTER_FIELDS)
        writer.writeheader()
        for row in sorted(master.values(), key=lambda r: (r["last_name"], r["first_name"])):
            writer.writerow(row)

    print(f"Scanned {scanned} enriched-schema file(s).")
    print(f"Added or backfilled {filled} people (started with {starting_count} already in cache).")
    print(f"Master cache now has {len(master)} people total -> {MASTER_FILE}")


if __name__ == "__main__":
    main()
