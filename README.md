# Student Delivery Savings Platform

## Layout

- menu_ingestion/: fetching, provider extractors, S3/BigQuery loading.
- menu_ingestion/tools/: HTML comparison and inspection tools.
- receipt_extraction/: future Gemini screenshot processing.
- shared/: common paths and future reusable utilities.
- frontend/: future Streamlit pages.
- tests/menu_ingestion/: ingestion and extraction tests.
- tests/receipt_extraction/: future screenshot tests.
- config/: source configuration; sql/: warehouse setup.

Run commands from this directory:

    .\.venv\Scripts\python.exe -m menu_ingestion.ingest_menu --list-sources
    .\.venv\Scripts\python.exe -m menu_ingestion.ingest_menu --source primo-too
    .\.venv\Scripts\python.exe -m unittest discover -s tests -t . -v

Ingestion can consume ZenRows credits; tests use mocks and local fixtures.
See INGESTION.md for details. Existing .env, artifacts, configuration, SQL, and project plan stay in place.

Comparison utilities (these fetch a page and can consume credits):

- python -m menu_ingestion.tools.compare_primo_no_js
- python -m menu_ingestion.tools.compare_doordash_no_js

Offline inspection:

- python -m menu_ingestion.tools.inspect_primo_embedded artifacts/COMPARISON_FOLDER

## Screenshot extraction MVP

See [receipt_extraction/README.md](receipt_extraction/README.md) for setup and the Streamlit upload/review flow. Comparison dataset planning and SQL are under benchmark_data/ and sql/build_benchmarks.sql.
