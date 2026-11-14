"""Parameterized, transactional saves; confirmed orders only."""
import json
from google.cloud import bigquery
from shared.bigquery import get_client
from shared.settings import PROJECT
from shared.paths import ROOT
from receipt_extraction.deduplication import order_id

def setup():
    get_client().query((ROOT / "sql/setup_receipt_tables.sql").read_text().replace("{project}", PROJECT)).result()

def save(session_id, upload, raw_uri, extraction):
    orders = [dict(o.model_dump(mode="json"), order_id=order_id(session_id, upload, i, o)) for i, o in enumerate(extraction.orders)]
    ids = [o["order_id"] for o in orders]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate provider/order references: remove repeated orders before saving.")
    params = [bigquery.ScalarQueryParameter(k, "STRING", v) for k,v in {
        "session": session_id, "upload": upload, "uri": raw_uri,
        "payload": extraction.model_dump_json(), "orders": json.dumps(orders)}.items()]
    sql = (ROOT / "sql/save_receipts.sql").read_text().replace("{project}", PROJECT)
    get_client().query(sql, job_config=bigquery.QueryJobConfig(query_parameters=params)).result()

if __name__ == "__main__":
    setup()
