# Cloud Composer deployment

The Composer deployment keeps Airflow separate from the Streamlit Cloud Run
service. Composer supplies the scheduler, workers, metadata database, and UI;
the bundle supplies the DAG and the ingestion/dbt source files that the DAG
executes.

## 1. Create or select a Composer environment

Use a Composer environment in the same broad US region as the BigQuery dataset.
Composer's service account needs permission to run BigQuery jobs, access the
configured BigQuery datasets, read/write the S3 bucket through AWS credentials,
and read the required Secret Manager secrets.

## 2. Install Composer dependencies

Composer already provides Airflow. Install only the additional packages listed
in `requirements.txt`:

```powershell
gcloud composer environments update hackumass26-composer `
  --location us-east1 `
  --update-pypi-packages-from-file airflow/composer/requirements.txt
```

## 3. Stage and upload the DAG bundle

From the repository root:

```powershell
.\airflow\composer\stage.ps1 -OutputPath .\composer-bundle
```

Upload the staged `dags/` contents to the Composer DAG bucket:

```powershell
$DAG_PREFIX = gcloud composer environments describe hackumass26-composer `
  --location us-east1 `
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
gcloud composer environments update hackumass26-composer `
  --location us-east1 `
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
gcloud composer environments run hackumass26-composer `
  --location us-east1 dags list
```

Enable `delivery_menu_ingestion` in the Airflow UI, trigger one manual run,
and inspect each source task before relying on the hourly schedule. The DAG
runs one task per enabled source, then runs dbt after all source tasks finish.
