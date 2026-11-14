# Primo Too menu ingestion test

Run commands in C:\Users\savar\Coding Projects\HackUMass '26.

## Run

1. Keep your ZenRows key in the local .env: ZENROWS_API_KEY=...
2. Ensure AWS profile delivery-dev and Google Application Default Credentials are signed in.
3. Run:

```powershell
.\.venv\Scripts\python.exe scripts\ingest_menu.py
```

This makes one ZenRows request with JavaScript rendering, without premium proxies or automatic client retries. Source settings are in config/sources.json; config/primo.json is retained only as the original setup record and is no longer read. A live run first checks cloud access, then saves original HTML and a timestamp/hash manifest in S3, downloads that HTML back, parses menu cards, and merges observations into hackumass26.raw.menu_observations. It records a run in raw.ingestion_runs. Raw files use unique run IDs; sequential replay preserves observation IDs.

```powershell
.\.venv\Scripts\python.exe scripts\ingest_menu.py --replay RUN_UUID
```

Replay reads S3; it does not call ZenRows. Do not run the same replay concurrently.

To test ZenRows while cloud credentials are unavailable:

```powershell
.\.venv\Scripts\python.exe scripts\ingest_menu.py --fetch-only
```

This spends ZenRows credits and writes only local artifacts. It is not evidence that S3/BigQuery ingestion works.

## Inspect results

Local artifacts/RUN_UUID contains HTML, extraction JSON, and any failure report. S3 stores raw/menus/ubereats/primo-too/RUN_UUID/response.html and manifest.json, plus a parser-version extraction report. Never commit artifacts or credentials.

```sql
SELECT item_name, price_cents, currency, observed_at, raw_uri
FROM `hackumass26.raw.menu_observations`
WHERE run_id = 'RUN_UUID'
ORDER BY item_name;
```

Prices are displayed menu prices, not checkout totals. Coverage is only the cards present in the returned HTML; lazy-loaded sections may be missing. A successful run is marked success_partial_coverage. Variant stays NULL until sizes/options are verified. Category is retained in the extraction report but is not added to the existing raw table schema. Destination context from the URL is not independently verified.

Missing/ambiguous prices are quarantined, and any rejected cards block publication. Zero items is an error, never a successful empty menu. Raw snapshots remain available for parser repairs. Loading uses temporary BigQuery staging tables that expire after 24 hours; observations and run records persist.

## Validation

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Tests use synthetic HTML and never upload fixtures as live observations. Live collection and replay must be checked separately. Airflow scheduling, dbt transformations, full-menu scrolling, canonical matching, and frontend work are not implemented here.


To continue a successful local-only fetch without another ZenRows request:

```powershell
.\.venv\Scripts\python.exe scripts\ingest_menu.py --resume-local RUN_UUID
```

The local HTML hash is checked before upload. Existing S3 bytes must match exactly; the script refuses to overwrite a different raw snapshot.

## Verified live run (2026-11-14)

- Run: ea260c09-a8ab-415d-a384-1963b9123987
- ZenRows fetched the full user-supplied URL, including destination parameters.
- 121 unique items across 12 section labels; zero rejected cards.
- Raw HTML: s3://student-delivery-raw-lightriver3010/raw/menus/ubereats/primo-too/ea260c09-a8ab-415d-a384-1963b9123987/response.html
- BigQuery: hackumass26.raw.menu_observations; run status in hackumass26.raw.ingestion_runs.
- Sequential replay passed: still 121 rows and 121 distinct observation IDs for this run.
- Six parser regression tests passed; pip check passed.
- Earlier local-only run c1635eb5-2d1d-462a-b4d9-badd1028d719 used the shorter URL and returned only 20 Grinders. It was not loaded into BigQuery.
- Even with 12 sections present, full item/variant completeness and destination-specific pricing remain unverified.

## Multiple sources and Airflow

The active configuration is config/sources.json. Shared cloud settings live in defaults; each sources entry supplies:
- id: permanent unique source ID (also used in S3 paths).
- enabled: true or false.
- provider: currently ubereats only.
- url: full restaurant URL including diningMode and desired destination parameters.
- store_uuid: the Uber Eats storeUuid from the menu links (not the URL's base64-like token).
- expected_heading: exact restaurant heading; optional but recommended.
- currency and fulfillment_mode can override defaults (currently USD and DELIVERY/PICKUP only).

Copy the existing source entry and change its ID, URL, store UUID, and heading to add another Uber Eats restaurant. Do not invent store UUIDs. Different website providers require a new tested adapter in scripts/menu_parsers.py; an arbitrary URL alone is not enough. Primo remains the only configured live source until additional URLs are supplied.

Commands:

```powershell
# Validate and list enabled sources; no network calls.
.\.venv\Scripts\python.exe scripts/ingest_menu.py --list-sources

# Process every enabled source; failures do not skip the others.
.\.venv\Scripts\python.exe scripts/ingest_menu.py

# Process one source with a stable scheduler identity.
.\.venv\Scripts\python.exe scripts/ingest_menu.py --source primo-too --batch-id "scheduled-2026-11-14T12:00:00Z"

# Replay a specific existing run.
.\.venv\Scripts\python.exe scripts/ingest_menu.py --source primo-too --replay ea260c09-a8ab-415d-a384-1963b9123987
```

For Airflow, use one task per source and pass the same Airflow run ID as --batch-id on all attempts of that task. A new scheduled run must use a new ID. A retry uses the same deterministic source/run UUID and reuses a persisted S3 snapshot; it only fetches again if no snapshot is available. Keep at most one active execution for the same source/run; concurrent replays are not supported. The batch command exits nonzero if any source fails and saves an individual outcome summary under artifacts/batches.

Cloud credentials must be configured in the Airflow runtime. Set defaults.profile to null to use the standard AWS credential chain on a VM with a role instead of the local delivery-dev profile. A DAG and Docker runtime are not installed by this refactor.

Successfully merged temporary _stage_* tables are now deleted immediately. Failed-operation tables retain 24-hour expiration as a fallback.
