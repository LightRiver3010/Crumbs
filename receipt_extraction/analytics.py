"""Summaries only for the current anonymous session; currencies stay separate."""
from google.cloud import bigquery
from shared.bigquery import get_client
from shared.paths import ROOT
from shared.settings import PROJECT

def summarize(session_id):
    sql = (ROOT / "sql/receipt_summary.sql").read_text().replace("{project}", PROJECT)
    config = bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("session", "STRING", session_id)])
    return [dict(row) for row in get_client().query(sql, job_config=config).result()]
