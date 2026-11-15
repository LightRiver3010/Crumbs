"""Airflow orchestration for scheduled menu collection and warehouse publishing."""
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import subprocess

from airflow import DAG
from airflow.models import Variable
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator


PROJECT_ROOT = Path(os.environ.get("DELIVERY_PROJECT_ROOT", "/opt/hackumass26"))
CONFIG_PATH = PROJECT_ROOT / "config" / "sources.json"


def enabled_source_ids():
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
    return [
        source["id"]
        for source in config["sources"]
        if isinstance(source, dict) and source.get("enabled", True)
    ]


def run_source(source_id, **context):
    """Run one source with a stable batch identity so retries are idempotent."""
    dag_run = context["dag_run"]
    batch_id = dag_run.run_id
    runtime_env = os.environ.copy()
    for name in (
        "ZENROWS_API_KEY",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
    ):
        if name not in runtime_env:
            value = Variable.get(name, default_var=None)
            if value:
                runtime_env[name] = value
    subprocess.run(
        [
            os.environ.get("PYTHON_BIN", "python"),
            "-m",
            "menu_ingestion.ingest_menu",
            "--source",
            source_id,
            "--batch-id",
            batch_id,
        ],
        cwd=PROJECT_ROOT,
        check=True,
        env=runtime_env,
    )


with DAG(
    dag_id="delivery_menu_ingestion",
    description="Fetch verified menus, persist immutable S3 snapshots, and publish validated BigQuery observations.",
    start_date=datetime(2026, 1, 1),
    schedule=os.environ.get("MENU_INGESTION_SCHEDULE") or "0 * * * *",
    catchup=False,
    is_paused_upon_creation=False,
    max_active_runs=1,
    dagrun_timeout=timedelta(minutes=45),
    default_args={
        "owner": "delivery-platform",
        "depends_on_past": False,
        "retries": 2,
        "retry_delay": timedelta(minutes=5),
    },
    tags=["menus", "zenrows", "bigquery"],
) as dag:
    source_tasks = []
    for source_id in enabled_source_ids():
        source_tasks.append(
            PythonOperator(
                task_id=f"ingest_{source_id.replace('-', '_')}",
                python_callable=run_source,
                op_kwargs={"source_id": source_id},
            )
        )

    dbt_build = BashOperator(
        task_id="dbt_build_and_test",
        bash_command=(
            "dbt build "
            "--project-dir {{ params.dbt_dir }} "
            "--profiles-dir {{ params.dbt_dir }} "
            "--target-path /tmp/delivery-dbt-target "
            "--log-path /tmp/delivery-dbt-logs "
            "--target production"
        ),
        params={"dbt_dir": str(PROJECT_ROOT / "dbt")},
        append_env=True,
        env={
            "DBT_PROFILES_DIR": str(PROJECT_ROOT / "dbt"),
            "DBT_PROJECT_DIR": str(PROJECT_ROOT / "dbt"),
            "AWS_USE_DEFAULT_CREDENTIALS": "true",
            "DELIVERY_ARTIFACTS_ROOT": "/tmp/delivery-artifacts",
        },
    )

    source_tasks >> dbt_build
