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

## Scheduled ingestion

The Airflow DAG in `airflow/dags/menu_ingestion.py` creates one ingestion task
per enabled source, then runs the dbt build and tests after all source tasks
finish. It defaults to hourly execution for the demo. Set
`MENU_INGESTION_SCHEDULE=0 0,12 * * *` for twice-daily post-demo collection.

Install the orchestration dependencies separately from the application:

    python -m pip install -r requirements-airflow.txt

The worker must expose the repository through `DELIVERY_PROJECT_ROOT`, provide
`ZENROWS_API_KEY` through its secret manager, and have AWS and Google
credentials. See [airflow/README.md](airflow/README.md) for the task contract
and retry/idempotency behavior. The dbt project is under `dbt/`; its profile
uses environment variables and contains no credentials.

## Screenshot extraction MVP

See [receipt_extraction/README.md](receipt_extraction/README.md) for setup and the Streamlit upload/review flow. Comparison dataset planning and SQL are under benchmark_data/ and sql/build_benchmarks.sql.
