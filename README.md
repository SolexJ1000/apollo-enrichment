# Apollo Enrichment

Scripts for enriching LinkedIn event attendee lists via the Apollo.io People
Match API — with a persistent cache so the same person is never paid for
twice across events.

## Setup

```
pip install -r requirements.txt
cp .env.example .env   # then fill in your real APOLLO_API_KEY
```

## Workflow

1. **`enrich.py <input.csv>`** — enrich a raw attendee list (columns:
   `linkedin_url, first_name, last_name`, optionally `company`, `title`,
   `email`). Checks `master_enriched.csv` first and only calls Apollo for
   people not already cached (or whose cache entry is older than 6 months).
   Sends any `company`/`email` already present in the input as extra match
   hints to Apollo, and backfills them into the output for rows Apollo
   doesn't fully resolve — without writing unverified data into the cache.

2. **`clean_list.py <enriched.csv>`** — strips out obvious non-person /
   bot-style rows from the enriched output.

3. **`retry_missed.py <clean.csv>`** — recovers anyone still missing data
   *only* from the master cache (in case another list already enriched
   them since). Deliberately does not call Apollo again for these rows —
   testing showed a bare retry essentially never finds new data, since
   Apollo already returned everything it had the first time.

4. **`check_missed.py <file.csv>`** — lists rows with no title/company/city.

5. **`check_credits.py`** — prints your current Apollo credit balance and
   usage, straight from the account (`GET /v1/users/api_profile`).

6. **`build_master.py`** — (re)builds `master_enriched.csv` from whatever
   enriched CSVs are sitting in the folder. Safe to re-run any time; never
   overwrites an already-dated cache entry, only fills gaps.

## Notes

- `master_enriched.csv` and all attendee CSVs are gitignored — this repo
  ships the tooling, not attendee data.
- Apollo bills 1 credit for essentially any `linkedin_url` match attempt,
  successful or not — the cache is what actually controls cost, not the
  request parameters.
