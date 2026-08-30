#!/usr/bin/env python3
"""
Usage: python check_missed.py <enriched_file.csv>
Shows rows with no enriched data (no title, company, or city).
"""

import csv, sys

if len(sys.argv) < 2:
    print("Usage: python check_missed.py <enriched_file.csv>")
    sys.exit(1)

path = sys.argv[1]

with open(path, encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

missed = [r for r in rows if not r["title"] and not r["company"] and not r["city"]]
print(f"File   : {path}")
print(f"Total  : {len(rows)}")
print(f"Missed : {len(missed)}\n")
for r in missed:
    print(f"  {r['first_name']} {r['last_name']} — {r['linkedin_url']}")
