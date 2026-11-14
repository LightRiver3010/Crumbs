# BLS Consumer Expenditure Diary imports

Import and organization only. No SQL, joins, benchmarks, weighting adjustments, currency conversions or inferred values.

## Run from the project root
```powershell
# Read S3, validate all 20 CSVs and organize locally (no BigQuery writes):
.\.venv\Scripts\python.exe -m benchmark_data.import_dataset --year 2025

# Also load raw tables into BigQuery using load jobs, not SQL:
.\.venv\Scripts\python.exe -m benchmark_data.import_dataset --year 2025 --load-bigquery

# Same layout for 2024 once its CSV files are uploaded:
.\.venv\Scripts\python.exe -m benchmark_data.import_dataset --year 2024 --load-bigquery
```
Uses the bucket/profile/region/project in config/sources.json and existing Google ADC credentials. Expected S3 prefixes: reference/bls-ce-diaries/2024/ and /2025/. Input is the extracted BLS CSV files, not ZIP archives. No external dataset download is performed.

## Files
- catalog.py: identifies FMLD, MEMD, EXPD, DTBD, DTID; validates release year and quarter. Requires one of each type for each quarter unless --allow-partial is explicitly selected.
- s3_source.py: lists and downloads originals without modifying S3.
- organize.py: validates CSV structure and required identifiers; writes JSONL with provenance.
- warehouse.py: optional dataset creation and raw table load jobs, with row-count verification.
- import_dataset.py: CLI and import manifest with success/failure state.

Each run is saved under ignored artifacts/bls-ce-diaries/<run>/<year>/q<quarter>/<type>/. Original CSVs are retained alongside records.jsonl. manifest.json records SHA-256, source URI, row counts, column names and any successful BigQuery loads. Failed runs remain available for inspection.

BigQuery destination: hackumass26.bls_ce_diaries_raw, with separate tables such as fmld_2025_q1 and expd_2024_q3. Each load atomically replaces that individual table, preventing duplicate rows on reruns. A whole release is not transactional: a later table failure leaves earlier successful loads in place; the manifest records progress, and rerunning reloads the release. Never target a dataset containing curated tables with the same names.

All BLS columns are stored as STRING in the raw layer, preserving leading zeros, blank strings, exact decimal text and flags. Only provenance year/quarter/row number are integers. This deliberately defers numeric interpretation to future processing. Metadata columns start with bls_. The file quarter is an organizational label, not a derived expenditure date. Do not treat NEWID alone as unique in EXPD or sum DTID imputation iterations. FMLD and MEMD identities are checked within each file. Relationships across files are not joined here.

2025 coverage and weights are retained exactly as supplied. Missing October/November collection and BLS adjustments must be handled in a later analytical layer. No 2024/2025 pooling or student subgroup assumptions are made here.

References:
- https://www.bls.gov/cex/pumd_data.htm
- https://www.bls.gov/cex/pumd-getting-started-guide.htm
- https://www.bls.gov/cex/ce-pumd-2025-shutdown-impact.htm

The old benchmark_data/queries.py scaffold has been removed. The earlier sql/build_benchmarks.sql placeholder is outside this importer and is neither called nor compatible with these raw tables; it must be redesigned when analysis begins.
