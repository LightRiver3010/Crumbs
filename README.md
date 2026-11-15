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

## Run the Streamlit frontend in Docker

The repository includes a frontend-only Docker image for deploying the
Streamlit app to a cloud container service. Docker Desktop or Docker Engine is
required.

Build and run it from the project root:

    docker build -t student-delivery-streamlit .
    docker run --rm -p 8501:8501 -e AWS_USE_DEFAULT_CREDENTIALS=true -e GEMINI_API_KEY student-delivery-streamlit

For local testing with a mounted Google service-account secret, add
`-e GOOGLE_APPLICATION_CREDENTIALS=/run/secrets/google-credentials.json
-v C:\path\to\google-credentials.json:/run/secrets/google-credentials.json:ro`
to the `docker run` command. Prefer workload identity or the provider's
managed secret integration for a deployed service.

Open `http://localhost:8501`. The image listens on port `8501` and exposes
Streamlit's `/_stcore/health` endpoint for a container health check.

The image contains only the Streamlit frontend, its direct Python packages, and
the runtime configuration JSON files. Airflow, dbt, ingestion jobs, tests,
artifacts, virtual environments, `.env` files, and credentials are excluded.
Provide cloud access through the hosting provider's secret or workload
identity mechanism:

- S3: use a task/instance role where possible, or inject AWS environment
  credentials. Set `AWS_USE_DEFAULT_CREDENTIALS=true` to use boto3's standard
  environment/instance-role credential chain. Local development continues to
  use the configured `delivery-dev` profile by default.
- BigQuery: use the provider's Application Default Credentials/workload
  identity, or inject `GOOGLE_APPLICATION_CREDENTIALS` pointing to a mounted
  secret file.
- Gemini: inject `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) and optionally
  `GEMINI_MODEL`.

Never copy `.env` files or cloud credential files into the image, commit them,
or pass their contents in shell history. Cloud providers may require the
container port to be configured from their service settings. The Docker image
uses Cloud Run's injected `PORT` value and falls back to `8501` for local runs.

### Deploy to Google Cloud Run

The following commands use the configured Google project `hackumass26` and
`us-east1` as a starting region. Choose a region compatible with the BigQuery
dataset location and your users.

Authenticate and enable the required services:

    gcloud auth login
    gcloud config set project hackumass26
    gcloud services enable run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com secretmanager.googleapis.com

Create an Artifact Registry repository once, then build and push the image:

    gcloud artifacts repositories create student-delivery --repository-format=docker --location=us-east1
    gcloud builds submit --tag us-east1-docker.pkg.dev/hackumass26/student-delivery/student-delivery-streamlit:latest .

Create a dedicated Cloud Run runtime service account and grant it only the
BigQuery permissions required by the app. Store `GEMINI_API_KEY` and AWS
credentials in Secret Manager, then deploy without putting secret values in
the command line:

    gcloud iam service-accounts create student-delivery-runtime
    gcloud run deploy student-delivery-streamlit `
      --image us-east1-docker.pkg.dev/hackumass26/student-delivery/student-delivery-streamlit:latest `
      --region us-east1 `
      --service-account student-delivery-runtime@hackumass26.iam.gserviceaccount.com `
      --port 8501 `
      --timeout 3600 `
      --session-affinity `
      --set-env-vars AWS_USE_DEFAULT_CREDENTIALS=true `
      --set-secrets GEMINI_API_KEY=gemini-api-key:latest,AWS_ACCESS_KEY_ID=aws-access-key-id:latest,AWS_SECRET_ACCESS_KEY=aws-secret-access-key:latest

Keep unauthenticated access disabled until an authentication layer is
configured. If the app is intentionally public for a demo, add
`--allow-unauthenticated` only after reviewing the absence of application-level
authentication and the receipt-data privacy implications.

Grant the Cloud Run service account access to the BigQuery datasets/tables and
the Secret Manager secrets. The AWS credentials must also have only the S3
permissions needed for the configured receipt bucket. Prefer short-lived or
federated AWS credentials over long-lived access keys where your cloud setup
supports them.

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
