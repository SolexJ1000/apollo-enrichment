#!/usr/bin/env python3
"""
Apollo enrichment script for LinkedIn event attendees.
Usage: python enrich.py <input_file.csv>

Input CSV must have columns: linkedin_url, first_name, last_name
Output CSV will contain: first_name, last_name, linkedin_email, title,
                          company, location, linkedin_url, company_website,
                          linkedin_public_url, city, country
"""

import csv
import os
import re
import sys
import time
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

API_KEY   = os.getenv("APOLLO_API_KEY")
API_URL   = "https://api.apollo.io/v1/people/match"
REQ_DELAY = 0.15   # seconds between requests — well under the 1000/min limit

OUTPUT_FIELDS = [
    "first_name", "last_name", "linkedin_email",
    "title", "company", "location",
    "linkedin_url", "company_website", "linkedin_public_url",
    "city", "country",
]

MASTER_FILE      = os.path.join(os.path.dirname(os.path.abspath(__file__)), "master_enriched.csv")
STALE_AFTER_DAYS = 182  # ~6 months — cached entries older than this are re-fetched
MASTER_FIELDS    = OUTPUT_FIELDS + ["cached_at"]


def normalize_url(url):
    url = (url or "").strip().lower().rstrip("/")
    return re.sub(r"^https?://(www\.)?", "", url)


def is_enriched(row):
    """True if Apollo actually returned something useful (not just an empty match)."""
    return bool(row.get("title") or row.get("company") or row.get("city"))


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
    """Return the cached row only if it exists AND is still fresh; otherwise None."""
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


def save_master(cache):
    with open(MASTER_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=MASTER_FIELDS)
        writer.writeheader()
        for row in sorted(cache.values(), key=lambda r: (r.get("last_name") or "", r.get("first_name") or "")):
            writer.writerow({field: row.get(field, "") for field in MASTER_FIELDS})


def detect_delimiter(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        sample = f.read(2048)
    return "\t" if sample.count("\t") > sample.count(",") else ","


def call_apollo(linkedin_url, first_name, last_name, email=None, organization_name=None, attempt=1):
    headers = {"Content-Type": "application/json", "X-Api-Key": API_KEY}
    payload = {"reveal_personal_emails": False}
    if linkedin_url:
        payload["linkedin_url"] = linkedin_url
    if first_name:
        payload["first_name"] = first_name
    if last_name:
        payload["last_name"] = last_name
    if email:
        payload["email"] = email
    if organization_name:
        payload["organization_name"] = organization_name

    try:
        resp = requests.post(API_URL, json=payload, headers=headers, timeout=15)
    except requests.RequestException as e:
        print(f"  Network error: {e}")
        return None

    if resp.status_code == 429:
        wait = 60 * attempt
        print(f"  Rate limited — waiting {wait}s before retry...")
        time.sleep(wait)
        return call_apollo(linkedin_url, first_name, last_name, email, organization_name, attempt + 1)

    if resp.status_code != 200:
        return None

    person = resp.json().get("person")
    if not person:
        return None

    org = person.get("organization") or {}

    return {
        "first_name":          person.get("first_name")        or first_name,
        "last_name":           person.get("last_name")         or last_name,
        "linkedin_email":      person.get("email")             or "",
        "title":               person.get("title")             or "",
        "company":             org.get("name")                 or "",
        "location":            person.get("formatted_address") or "",
        "linkedin_url":        person.get("linkedin_url")      or linkedin_url,
        "company_website":     org.get("website_url")          or "",
        "linkedin_public_url": person.get("linkedin_url")      or linkedin_url,
        "city":                person.get("city")              or "",
        "country":             person.get("country")           or "",
    }


def fallback_row(linkedin_url, first_name, last_name):
    return {
        "first_name":          first_name,
        "last_name":           last_name,
        "linkedin_email":      "",
        "title":               "",
        "company":             "",
        "location":            "",
        "linkedin_url":        linkedin_url,
        "company_website":     "",
        "linkedin_public_url": linkedin_url,
        "city":                "",
        "country":             "",
    }


def backfill_from_source(result, source_row):
    """Fill company/title/email from the original input row wherever Apollo
    (or the cache) left them blank. Never overwrites a value Apollo returned,
    and never touches location/city/country/company_website — the source
    CSV never has those, so there's nothing to backfill there. Only used for
    the per-file output; the master cache always stores the raw Apollo result."""
    filled = dict(result)
    if not filled.get("company"):
        filled["company"] = source_row.get("company", "").strip()
    if not filled.get("title"):
        filled["title"] = source_row.get("title", "").strip()
    if not filled.get("linkedin_email"):
        filled["linkedin_email"] = source_row.get("email", "").strip()
    return filled


def main():
    if not API_KEY:
        print("Error: APOLLO_API_KEY not set. Check your .env file.")
        sys.exit(1)

    if len(sys.argv) < 2:
        print("Usage: python enrich.py <input_file.csv>")
        sys.exit(1)

    input_path = sys.argv[1]
    if not os.path.exists(input_path):
        print(f"Error: File not found — {input_path}")
        sys.exit(1)

    # ── Read input ──────────────────────────────────────────────────────────
    delimiter = detect_delimiter(input_path)
    with open(input_path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f, delimiter=delimiter))

    # Normalise header names to lowercase with underscores
    normalised = []
    for row in rows:
        normalised.append({k.strip().lower().replace(" ", "_"): (v.strip() if v else "") for k, v in row.items()})
    rows = normalised

    total = len(rows)
    if total == 0:
        print("Input file is empty.")
        sys.exit(0)

    # ── Master cache ─────────────────────────────────────────────────────────
    master = load_master()
    new_lookups = sum(
        1 for row in rows
        if cache_lookup(master, normalize_url(row.get("linkedin_url"))) is None
    )
    cached_count = total - new_lookups

    # ── Credit check & confirmation ─────────────────────────────────────────
    print(f"\n{'-' * 52}")
    print(f"  Input file     : {input_path}")
    print(f"  People         : {total}")
    print(f"  Already cached : {cached_count} (no credits needed)")
    print(f"  New lookups    : {new_lookups}")
    print(f"  Credit cost    : ~{new_lookups} Apollo credits")
    print(f"{'-' * 52}")
    print("  Check balance -> app.apollo.io -> Settings -> Credits")
    print(f"{'-' * 52}\n")

    auto_yes = "--yes" in sys.argv
    if new_lookups == 0:
        print("  Everyone in this file is already in the cache — nothing to fetch.\n")
    elif not auto_yes:
        answer = input(f"  Proceed with enriching {new_lookups} new people? (yes/no): ").strip().lower()
        if answer != "yes":
            print("\n  Aborted — no credits used.")
            sys.exit(0)

    # ── Output file ─────────────────────────────────────────────────────────
    base = os.path.splitext(os.path.basename(input_path))[0]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(os.path.dirname(input_path), f"{base}_enriched_{timestamp}.csv")

    found      = 0
    source_only = 0
    missing    = 0

    print(f"\n  Starting enrichment...\n")

    with open(output_path, "w", newline="", encoding="utf-8") as out_f:
        writer = csv.DictWriter(out_f, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()

        cache_hits = 0

        for i, row in enumerate(rows, 1):
            linkedin_url   = row.get("linkedin_url", "").strip()
            first_name     = row.get("first_name", "").strip()
            last_name      = row.get("last_name", "").strip()
            source_email   = row.get("email", "").strip()
            source_company = row.get("company", "").strip()
            key            = normalize_url(linkedin_url)

            if not linkedin_url:
                print(f"  [{i:>3}/{total}] SKIP  — no LinkedIn URL")
                writer.writerow(backfill_from_source(fallback_row("", first_name, last_name), row))
                missing += 1
                continue

            cached = cache_lookup(master, key)
            if cached:
                output_row = backfill_from_source(cached, row)
                email_display = output_row["linkedin_email"] or "(no email)"
                print(f"  [{i:>3}/{total}] CACHE {output_row['first_name']} {output_row['last_name']} — {email_display} (no credit used)")
                writer.writerow({field: output_row.get(field, "") for field in OUTPUT_FIELDS})
                found += 1
                cache_hits += 1
                continue

            result = call_apollo(linkedin_url, first_name, last_name,
                                  email=source_email or None, organization_name=source_company or None)

            if result:
                if is_enriched(result):
                    master[key] = {**result, "cached_at": datetime.now().strftime("%Y-%m-%d")}
                output_row = backfill_from_source(result, row)
                writer.writerow(output_row)
                email_display = output_row["linkedin_email"] or "(no email)"
                print(f"  [{i:>3}/{total}] OK    {output_row['first_name']} {output_row['last_name']} — {email_display}")
                found += 1
            else:
                output_row = backfill_from_source(fallback_row(linkedin_url, first_name, last_name), row)
                writer.writerow(output_row)
                if output_row.get("company") or output_row.get("title"):
                    print(f"  [{i:>3}/{total}] SOURCE {output_row['first_name']} {output_row['last_name']} — filled from registration data (Apollo had nothing)")
                    source_only += 1
                else:
                    print(f"  [{i:>3}/{total}] MISS  — {linkedin_url}")
                    missing += 1

            time.sleep(REQ_DELAY)

    save_master(master)

    # ── Summary ─────────────────────────────────────────────────────────────
    print(f"\n{'-' * 52}")
    print(f"  Done!")
    print(f"  Enriched (Apollo)   : {found}/{total} (from cache: {cache_hits})")
    print(f"  Filled from source  : {source_only}/{total} (Apollo had nothing, registration data used)")
    print(f"  Still empty         : {missing}/{total}")
    print(f"  Master cache        : {len(master)} people total")
    print(f"  Output              : {output_path}")
    print(f"{'-' * 52}\n")


if __name__ == "__main__":
    main()
