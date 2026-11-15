# Airflow menu ingestion

`dags/menu_ingestion.py` creates one task per enabled source in
`config/sources.json`. Each task runs the existing ingestion module with the
Airflow run ID as `--batch-id`, so retries reuse the same deterministic source
run and persisted S3 snapshot.

The DAG runs hourly for the demo:

```text
source tasks (parallel) -> dbt build and test
```

For post-demo twice-daily operation, set
`MENU_INGESTION_SCHEDULE=0 0,12 * * *` (UTC) in the Airflow worker
environment.

Required Airflow environment:

- `DELIVERY_PROJECT_ROOT`: repository path visible to the worker
- `PYTHON_BIN`: Python executable with repository dependencies installed
- `ZENROWS_API_KEY`: Airflow connection/secret-backed environment variable
- AWS credentials for the configured S3 bucket
- Google credentials for BigQuery and dbt

The DAG does not treat an unchanged menu as an error. S3 retains every
immutable raw snapshot; BigQuery retains observations by run; dbt publishes
the latest validated price mart. Failed sources retry independently and do not
publish invalid partial observations.

## Cloud Composer

For managed Airflow on Google Cloud, use the Composer deployment bundle in
[airflow/composer/README.md](composer/README.md). It stages the DAG together
with `menu_ingestion/`, `shared/`, `config/`, `sql/`, and the dbt project under
the Composer DAG bucket. The Composer environment must set
`DELIVERY_PROJECT_ROOT=/home/airflow/gcs/dags/project` and provide ZenRows/AWS
secrets through its secret-management integration. The Composer service
account supplies Google Application Default Credentials for BigQuery and dbt.
