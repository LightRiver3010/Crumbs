# Cloud Composer deployment

The Composer deployment keeps Airflow separate from the Streamlit Cloud Run
service. Composer supplies the scheduler, workers, metadata database, and UI;
the bundle supplies the DAG and the ingestion/dbt source files that the DAG
executes.

## 1. Create or select a Composer environment

Use a Composer environment in `us-east4` for the `hackumass26` project.
Composer's service account needs permission to run BigQuery jobs, access the
configured BigQuery datasets, read/write the configured S3 bucket through AWS
credentials, and read the required Secret Manager secrets. The S3 region and
BigQuery dataset location are separate settings and should not be changed by
this Composer-region update.

## 2. Install Composer dependencies

Composer already provides Airflow. Install only the additional packages listed
in `requirements.txt`:

```powershell
gcloud composer environments update crumbs2 `
  --project hackumass26 --location us-east4 `
  --update-pypi-packages-from-file airflow/composer/requirements.txt
```

## 3. Stage and upload the DAG bundle

From the repository root:

```powershell
.\airflow\composer\stage.ps1 -OutputPath .\composer-bundle
```

Upload the staged `dags/` contents to the Composer DAG bucket:

```powershell
$DAG_PREFIX = gcloud composer environments describe crumbs2 `
  --project hackumass26 --location us-east4 `
  --format="value(config.dagGcsPrefix)"
gcloud storage cp -r .\composer-bundle\dags\* "$DAG_PREFIX/"
```

The resulting layout must be:

```text
dags/
  menu_ingestion.py
  project/
    config/
    dbt/
    menu_ingestion/
    shared/
    sql/
```

## 4. Configure runtime paths and credentials

Set these non-secret environment variables on the Composer environment:

```powershell
gcloud composer environments update crumbs2 `
  --project hackumass26 --location us-east4 `
  --update-env-variables="DELIVERY_PROJECT_ROOT=/home/airflow/gcs/dags/project,AWS_USE_DEFAULT_CREDENTIALS=true,DELIVERY_ARTIFACTS_ROOT=/tmp/delivery-artifacts"
```

Configure Secret Manager as the Airflow secrets backend, then create these
secrets using the default Airflow Variable naming convention:

```text
airflow-variables-ZENROWS_API_KEY
airflow-variables-AWS_ACCESS_KEY_ID
airflow-variables-AWS_SECRET_ACCESS_KEY
airflow-variables-AWS_SESSION_TOKEN       # optional
```

Grant the Composer service account `roles/secretmanager.secretAccessor` on
these secrets. The DAG reads the corresponding Airflow Variables at task
runtime and passes them only to the ingestion subprocess. Do not put secret
values in this file, in the DAG, or in a shell command. Google ADC for
BigQuery/dbt comes from the Composer environment service account.

The DAG is scheduled at `0 * * * *` by default, which means once per hour at
minute zero in the Airflow timezone. Set
`MENU_INGESTION_SCHEDULE=0 0,12 * * *` only if twice-daily operation is desired.

## 5. Verify the deployment

```powershell
gcloud composer environments run crumbs2 `
  --project hackumass26 --location us-east4 dags list
```

The environment must exist in the Google project and region used by the
commands above. A live Airflow web UI alone is insufficient; the scheduler
must also be running. Confirm the DAG is unpaused and inspect its next run:

```powershell
gcloud composer environments run crumbs2 `
  --project hackumass26 --location us-east4 dags unpause -- delivery_menu_ingestion
gcloud composer environments run crumbs2 `
  --project hackumass26 --location us-east4 dags list
```

Trigger one manual run and inspect each source task before relying on the
hourly schedule. The DAG runs one task per enabled source, then runs dbt after
all source tasks finish.

## Deployment state and remaining setup (2026-11-18)

- Actual environment: `crumbs2`, project `hackumass26`, region `us-east4`.
- Application DAG: `delivery_menu_ingestion` (not `crumbs2`).
- The previous hundreds of runs were only `airflow_monitoring` executing `echo test`.
- The application bundle has been uploaded to `gs://us-east4-crumbs2-d5b9b70e-bucket/dags/`.
- The DAG defaults to the sibling `project/` directory, uses the worker Python executable, forces the AWS default credential chain, and writes artifacts under `/tmp`.
- It starts paused, limits active ingestion tasks to two, and retains the hourly schedule. There are 37 enabled sources; unpausing starts recurring paid ZenRows requests.
- Composer dependency installation was submitted separately; verify its operation succeeds before triggering.

### Credentials still required

Composer cannot use the developer laptop's `delivery-dev` AWS login. Supply unattended AWS credentials through the configured secrets backend or Airflow Variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and `AWS_SESSION_TOKEN` only for temporary credentials). Temporary session credentials expire and need renewal; do not copy a short-lived laptop session as a permanent scheduling solution. Set `ZENROWS_API_KEY` through the same mechanism. Never upload `.env` or put values in the DAG or commands. Secret Manager-backed Variables are preferred; manually configured Airflow Variables are also supported by the DAG's runtime lookup.

BigQuery/dbt use the Composer service account `vertex-express@hackumass26.iam.gserviceaccount.com`. Its warehouse access must be validated in a real task. No credential values were displayed or included in the deployment bundle.

After dependencies and credentials are ready: verify no DAG import errors, trigger one manual run while paused, inspect per-source outcomes and `dbt_build_and_test`, verify S3 snapshots and warehouse rows, then unpause for hourly operation. A visible DAG alone is not proof of successful ingestion. Keep `airflow_monitoring.py` intact.

Verification: Airflow REST API confirms `delivery_menu_ingestion` is active, paused, has no import errors, uses `0 * * * *`, and contains 38 tasks (37 sources plus dbt). All 42 ingestion regression tests passed, along with bundle syntax and missing-Streamlit checks. Dependency operation: `d81010e4-d4e7-4939-aa09-a8012c891024` (installation still running at handoff). No live scraper run has been triggered.
