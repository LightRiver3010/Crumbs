# Primo Too menu ingestion test

Run commands in C:\Users\savar\Coding Projects\HackUMass '26.

## Run

1. Keep your ZenRows key in the local .env: ZENROWS_API_KEY=...
2. Ensure AWS profile delivery-dev and Google Application Default Credentials are signed in.
3. Run:

```powershell
.\.venv\Scripts\python.exe -m menu_ingestion.ingest_menu
```

This makes one ZenRows request using the source verification flags to select rendering, without premium proxies or automatic client retries. Source settings are in config/sources.json; the old per-restaurant configuration is no longer used. A live run first checks cloud access, then saves original HTML and a timestamp/hash manifest in S3, downloads that HTML back, parses menu cards, and merges observations into hackumass26.raw.menu_observations. It records a run in raw.ingestion_runs. Raw files use unique run IDs; sequential replay preserves observation IDs.

```powershell
.\.venv\Scripts\python.exe -m menu_ingestion.ingest_menu --replay RUN_UUID
```

Replay reads S3; it does not call ZenRows. Do not run the same replay concurrently.

To test ZenRows while cloud credentials are unavailable:

```powershell
.\.venv\Scripts\python.exe -m menu_ingestion.ingest_menu --fetch-only
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

Prices are displayed menu prices, not checkout totals. Coverage is only the cards present in the returned HTML; lazy-loaded sections may be missing. A successful run is marked success_partial_coverage. Variant stays NULL until sizes/options are verified, except DoorDash starting prices marked starting_price; options_unverified. Category is retained in the extraction report but is not added to the existing raw table schema. Destination context from the URL is not independently verified.

Malformed/ambiguous records are quarantined and block publication. DoorDash items with no displayed price are explicitly excluded in the extraction report, not interpreted as zero; other valid records can still be published. Zero items is an error, never a successful empty menu. Raw snapshots remain available for parser repairs. Loading uses temporary BigQuery staging tables that expire after 24 hours; observations and run records persist.

## Validation

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -t . -v
```

Tests use synthetic HTML and never upload fixtures as live observations. Live collection and replay must be checked separately. Airflow scheduling, dbt transformations, full-menu scrolling, canonical matching, and frontend work are not implemented here.


To continue a successful local-only fetch without another ZenRows request:

```powershell
.\.venv\Scripts\python.exe -m menu_ingestion.ingest_menu --resume-local RUN_UUID
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
- provider: ubereats or doordash.
- url: full restaurant URL including diningMode and desired destination parameters.
- store_id: a string containing the provider-native store identifier. Uber Eats uses the storeUuid value from its links; DoorDash uses the numeric store ID, not the menu ID.
- expected_heading: exact restaurant heading; optional but recommended.
- currency and fulfillment_mode can override defaults (currently USD and DELIVERY/PICKUP only).

Copy the existing source entry and change its ID, URL, store UUID, and heading to add another Uber Eats restaurant. Do not invent store UUIDs. Other website providers require a new tested adapter registered in menu_ingestion/menu_parsers.py. Primo (Uber Eats) and Taco Bell Northampton (DoorDash) are configured.

Commands:

```powershell
# Validate and list enabled sources; no network calls.
.\.venv\Scripts\python.exe -m menu_ingestion.ingest_menu --list-sources

# Process every enabled source; failures do not skip the others.
.\.venv\Scripts\python.exe -m menu_ingestion.ingest_menu

# Process one source with a stable scheduler identity.
.\.venv\Scripts\python.exe -m menu_ingestion.ingest_menu --source primo-too --batch-id "scheduled-2026-11-14T12:00:00Z"

# Replay a specific existing run.
.\.venv\Scripts\python.exe -m menu_ingestion.ingest_menu --source primo-too --replay ea260c09-a8ab-415d-a384-1963b9123987
```

For Airflow, use one task per source and pass the same Airflow run ID as --batch-id on all attempts of that task. A new scheduled run must use a new ID. A retry uses the same deterministic source/run UUID and reuses a persisted S3 snapshot; it only fetches again if no snapshot is available. Keep at most one active execution for the same source/run; concurrent replays are not supported. The batch command exits nonzero if any source fails and saves an individual outcome summary under artifacts/batches.

Cloud credentials must be configured in the Airflow runtime. Set defaults.profile to null to use the standard AWS credential chain on a VM with a role instead of the local delivery-dev profile. A DAG and Docker runtime are not installed by this refactor.

Successfully merged temporary _stage_* tables are now deleted immediately. Failed-operation tables retain 24-hour expiration as a fallback.


## Provider adapters and store IDs

- menu_ingestion/extract_ubereats.py: extracts item cards, accepts store_id, and translates Uber Eats' native storeUuid field internally.
- menu_ingestion/extract_doordash.py: safely decodes JSON from Next.js script chunks, selects MenuPageItem records, checks each record's storeId plus the canonical store URL, and uses native item IDs. It never executes downloaded JavaScript.
- menu_ingestion/menu_parsers.py: provider registry, parser versions, fetch selectors, and coverage descriptions.
- Both adapters take parse_menu(html, store_id, expected_heading=None). New configurations/manifests use store_id only. A compatibility reader still accepts store_uuid in historical immutable manifests.
- Store IDs remain strings. BigQuery branch_id contains this provider-native store ID; use (provider, branch_id) together. A cross-provider canonical restaurant-location mapping is still future work.
- Run IDs remain UUIDs because they identify ingestion attempts, not restaurants.
- DoorDash store 1199296 is Taco Bell Northampton; 1751802 in the URL is the menu ID.
- DoorDash starting-at prices retain the + semantics in the extraction report and variant column; do not treat them as a fully specified meal price. Blank prices are excluded. Structured page data does not establish current item availability or final checkout totals.

Run DoorDash only:

```powershell
.\.venv\Scripts\python.exe -m menu_ingestion.ingest_menu --source taco-bell
```


## Verified DoorDash run (2026-11-14)

- Source: taco-bell; store_id: 1199296; run: f28d41a9-cfe3-5a0c-b561-637128ca59a0.
- ZenRows returned HTTP 200; original HTML stored in S3 under raw/menus/doordash/taco-bell/RUN_ID/response.html.
- The first parser pass stopped on the explicit US$ currency format. The parser was fixed and the saved S3 response replayed without another fetch.
- 178 unique observations verified in hackumass26.raw.menu_observations; 29 are starting-at prices. Four missing-price items are excluded in the extraction report.
- 25 offline regression tests pass, covering both providers, store identity, duplicate detection, missing and starting prices, money reconciliation, and legacy manifests.


## Verified HTML-only fetching

Every source entry includes two booleans:

```json
"html_only_tested": false,
"html_only_matches_js": false
```

Only true + true enables HTML-only. Any other combination uses JavaScript. Missing flags default to false for compatibility; new sources should explicitly include both. Strings such as "true" are rejected. Verification is per source and cannot be inherited from defaults. Reset both flags when changing the URL, destination, fulfillment mode, store, or provider until that configuration is compared again.

Primo Too is true/true based on all 121 item IDs, names and prices matching the stored rendered baseline. Its HTML-only path reads the embedded __REACT_QUERY_STATE__ JSON, not just the 20 initially visible cards. Rendered snapshots retain the existing card parser.

Taco Bell is true/false: the non-rendered request on 2026-11-14 returned HTTP 422 and X-Request-Cost 0. No menu data was returned to compare with the 178-row BigQuery baseline. This is a failed verification, not evidence that the prices differ or that HTML-only can never work. Its extractor supports embedded records in either response type, but automatic fetching keeps JavaScript on. Popeyes remains false/false.

The mode is recorded in each snapshot manifest. Replay follows that historical mode rather than today's flags; old manifests default to rendered parsing. No automatic paid fallback is performed if an HTML-only fetch or parse fails. Verification flags are not automatically updated by ingestion; recurring comparisons are future work.

Tests use mocked HTTP calls and saved local data and do not spend ZenRows credits. The only new external fetch for this change was the requested DoorDash HTML-only test. Comparison report: artifacts/taco-bell-no-js-20261114T130846Z/comparison.json. No BigQuery observation records were changed by these comparisons.


## Package layout

Run commands from the project root using Python modules: python -m menu_ingestion.ingest_menu. Provider adapters and orchestration are in menu_ingestion; comparison utilities are in menu_ingestion/tools. Receipt extraction and frontend packages are placeholders. Shared path configuration is in shared/paths.py. Tests mirror the application folders.
