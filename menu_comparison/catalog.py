"""Read configured source snapshots in one warehouse query; never fetch websites."""
import json

from google.cloud import bigquery
from shared.bigquery import get_client
from shared.paths import ROOT
from shared.settings import PROJECT


def configured_sources():
    config = json.loads((ROOT / "config/sources.json").read_text())
    return [{**config.get("defaults", {}), **source}
            for source in config["sources"]
            if isinstance(source, dict) and source.get("enabled", True)]


def get_catalog(sources):
    menus = {source["id"]: [] for source in sources}
    if not sources:
        return menus
    # Source IDs, not providers, keep different restaurants on the same platform apart.
    bindings = [{key: source[key] for key in
                 ("id", "provider", "store_id", "url", "currency", "fulfillment_mode")}
                for source in sources]
    sql = f"""
    WITH sources AS (
      SELECT JSON_VALUE(s, '$.id') AS source_id,
        JSON_VALUE(s, '$.provider') AS provider,
        JSON_VALUE(s, '$.store_id') AS branch_id,
        JSON_VALUE(s, '$.url') AS source_url,
        JSON_VALUE(s, '$.currency') AS currency,
        JSON_VALUE(s, '$.fulfillment_mode') AS fulfillment_mode
      FROM UNNEST(JSON_QUERY_ARRAY(@sources)) s
    ), snapshots AS (
      SELECT s.source_id, o.* , r.status AS snapshot_status
      FROM `{PROJECT}.raw.menu_observations` o
      JOIN sources s USING(provider, branch_id, source_url, currency, fulfillment_mode)
      JOIN `{PROJECT}.raw.ingestion_runs` r USING(run_id)
      WHERE r.status IN ('success', 'success_partial_coverage')
    ), latest AS (
      SELECT source_id, run_id, MAX(observed_at) AS observed_at
      FROM snapshots GROUP BY source_id, run_id
      QUALIFY ROW_NUMBER() OVER (
        PARTITION BY source_id ORDER BY observed_at DESC, run_id DESC
      ) = 1
    )
    SELECT s.* FROM snapshots s JOIN latest USING(source_id, run_id)
    ORDER BY source_id, item_name, source_item_id
    """
    job = bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("sources", "STRING", json.dumps(bindings))],
        maximum_bytes_billed=100 * 1024**2,
    )
    for row in get_client().query(sql, job_config=job).result(timeout=60):
        record = dict(row)
        menus[record.pop("source_id")].append(record)
    return menus
