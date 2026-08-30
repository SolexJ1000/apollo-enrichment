#!/usr/bin/env python3
"""
Check the live Apollo credit balance for this account.
Read-only — does not consume Apollo credits.

Usage: python check_credits.py
"""

import json
import os
import sys

import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("APOLLO_API_KEY")
URL = "https://api.apollo.io/api/v1/users/api_profile"

CREDIT_FIELDS = [
    ("Credits remaining",        "num_credits_remaining"),
    ("Export credits used",      "num_export_credits_used"),
    ("Lead credits used",        "num_lead_credits_used"),
    ("Direct dial credits used", "num_direct_dial_credits_used"),
    ("AI credits used",          "num_ai_credits_used"),
    ("Power-up credits used",    "num_power_up_credits_used"),
    ("Total unified used",       "total_unified_credits_used"),
]


def main():
    if not API_KEY:
        print("Error: APOLLO_API_KEY not set. Check your .env file.")
        sys.exit(1)

    headers = {"x-api-key": API_KEY}
    params = {"include_credit_usage": "true"}

    try:
        resp = requests.get(URL, headers=headers, params=params, timeout=15)
    except requests.RequestException as e:
        print(f"Network error: {e}")
        sys.exit(1)

    if resp.status_code != 200:
        print(f"Error {resp.status_code}: {resp.text}")
        sys.exit(1)

    data = resp.json()

    print(f"\n{'-' * 52}")
    print(f"  Account : {data.get('first_name', '')} {data.get('last_name', '')} <{data.get('email', '')}>")
    print(f"{'-' * 52}")

    found_any = False
    for label, field in CREDIT_FIELDS:
        if field in data:
            print(f"  {label:<26}: {data[field]}")
            found_any = True

    if not found_any:
        print("  No known credit fields in response — raw JSON below:")
        print(json.dumps(data, indent=2))

    print(f"{'-' * 52}\n")


if __name__ == "__main__":
    main()
