"""Read the latest successful whole snapshot for each configured Primo source."""
import json
from google.cloud import bigquery
from shared.bigquery import get_client
from shared.paths import ROOT
from shared.settings import PROJECT


def get_latest_menus():
    config=json.loads((ROOT/"config/sources.json").read_text())
    sources=[{**config["defaults"],**s} for s in config["sources"]
             if s.get("restaurant_id")=="primo-too-amherst" and s.get("enabled",True)
             and s["provider"] in ("ubereats","doordash")]
    client=get_client()
    menus={}
    for source in sources:
        sql=f"""WITH latest AS (
          SELECT o.run_id, MAX(o.observed_at) observed_at
          FROM `{PROJECT}.raw.menu_observations` o
          JOIN `{PROJECT}.raw.ingestion_runs` r USING(run_id)
          WHERE o.provider=@provider AND o.branch_id=@store AND o.source_url=@url
            AND o.currency='USD' AND o.fulfillment_mode='DELIVERY'
            AND r.status IN ('success','success_partial_coverage')
          GROUP BY o.run_id ORDER BY observed_at DESC, o.run_id DESC LIMIT 1
        ) SELECT o.* FROM `{PROJECT}.raw.menu_observations` o
          JOIN latest l USING(run_id)"""
        params=[bigquery.ScalarQueryParameter(k,"STRING",v) for k,v in
                (("provider",source["provider"]),("store",source["store_id"]),("url",source["url"]))]
        job=bigquery.QueryJobConfig(query_parameters=params, maximum_bytes_billed=100*1024**2)
        menus[source["provider"]]=[dict(r) for r in client.query(sql,job_config=job).result(timeout=60)]
    return menus
