#!/usr/bin/env python3
"""
Usage: python clean_list.py <enriched_file.csv>
Removes non-persons and saves a _clean.csv version of the file.
"""

import csv, os, sys

if len(sys.argv) < 2:
    print("Usage: python clean_list.py <enriched_file.csv>")
    sys.exit(1)

input_path = sys.argv[1]

if not os.path.exists(input_path):
    print(f"Error: File not found — {input_path}")
    sys.exit(1)

with open(input_path, encoding="utf-8") as f:
    rows = list(csv.DictReader(f))

if not rows:
    print(f"File is empty: {input_path}")
    sys.exit(1)

# ── Non-person detection ─────────────────────────────────────────────────────
FAKE_KEYWORDS = [
    "web3", "onchain", "defi", "crypto", "bitcoin", "blockchain",
    "technology", "advisor", "nft", "token", "(new)", "florida",
]

def is_non_person(row):
    first = row["first_name"].lower().strip()
    last  = row["last_name"].lower().strip()
    full  = f"{first} {last}".strip()
    url   = row["linkedin_url"].lower()

    if first and first == last:
        return True

    for kw in FAKE_KEYWORDS:
        if kw in full:
            return True

    slug = url.split("/in/")[-1] if "/in/" in url else ""
    for kw in ["technology", "web3", "onchain", "bitcoin", "defi", "nft"]:
        if kw in slug:
            return True

    return False

non_persons = [r for r in rows if is_non_person(r)]
real_people  = [r for r in rows if not is_non_person(r)]

print(f"Non-persons removed ({len(non_persons)}):")
for r in non_persons:
    print(f"  {r['first_name']} {r['last_name']} — {r['linkedin_url']}")

print(f"\nReal people remaining: {len(real_people)}")

# ── Save cleaned CSV ─────────────────────────────────────────────────────────
base     = os.path.splitext(input_path)[0]
out_path = f"{base}_clean.csv"
fieldnames = list(rows[0].keys())

with open(out_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(real_people)

print(f"\nCleaned file saved: {out_path}")

missed_real = [r for r in real_people if not r["title"] and not r["company"] and not r["city"]]
print(f"\nReal people with no enriched data (retry candidates): {len(missed_real)}")
