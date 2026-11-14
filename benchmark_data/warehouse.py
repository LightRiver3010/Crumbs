"""Optional raw BigQuery load jobs. No SQL, joins or benchmark calculations."""
import re
from google.cloud import bigquery
from shared.bigquery import get_client
from shared.settings import PROJECT, LOCATION


def load_file(source, record, dataset="bls_ce_diaries_raw", client=None):
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", dataset):
        raise ValueError("Invalid dataset name.")
    client = client or get_client()
    dataset_id = f"{PROJECT}.{dataset}"
    definition = bigquery.Dataset(dataset_id)
    definition.location = LOCATION
    actual = client.create_dataset(definition, exists_ok=True)
    if actual.location.upper() != LOCATION.upper():
        raise ValueError("Existing dataset location differs from configured location.")
    schema = [bigquery.SchemaField(name, "STRING") for name in record["columns"]]
    schema += [bigquery.SchemaField(name, kind) for name,kind in (
        ("bls_release_year","INTEGER"),("bls_file_quarter","INTEGER"),
        ("bls_file_type","STRING"),("bls_source_uri","STRING"),
        ("bls_source_sha256","STRING"),("bls_source_row","INTEGER"))]
    config = bigquery.LoadJobConfig(schema=schema,
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        max_bad_records=0, ignore_unknown_values=False)
    table_id = f"{dataset_id}.{source.table_name}"
    with open(record["organized_jsonl"], "rb") as stream:
        job = client.load_table_from_file(stream, table_id, job_config=config, location=LOCATION)
    job.result()
    table = client.get_table(table_id)
    if table.num_rows != record["row_count"]:
        raise ValueError(f"Loaded row count differs for {table_id}")
    return {"table": table_id, "job_id": job.job_id, "rows": table.num_rows}
