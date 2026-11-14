"""One no-JavaScript DoorDash fetch compared to the latest successful BigQuery run.
Read-only warehouse access; no S3 writes and no production settings changes.
"""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import requests
from dotenv import load_dotenv
from google.cloud import bigquery
from menu_ingestion.extract_doordash import parse_menu

from shared.paths import ROOT

def main():
    load_dotenv(ROOT / ".env")
    config = json.loads((ROOT/"config/sources.json").read_text(encoding="utf-8-sig"))
    cfg = {**config["defaults"], **next(x for x in config["sources"] if x["id"]=="taco-bell")}
    client = bigquery.Client(project=cfg["project"])
    params = [bigquery.ScalarQueryParameter("store","STRING",cfg["store_id"]),
              bigquery.ScalarQueryParameter("url","STRING",cfg["url"])]
    sql = """
    WITH candidate_runs AS (
      SELECT o.run_id, MAX(o.observed_at) AS observed_at
      FROM `hackumass26.raw.menu_observations` o
      JOIN `hackumass26.raw.ingestion_runs` r USING(run_id)
      WHERE o.provider='doordash' AND o.branch_id=@store AND o.source_url=@url
        AND r.status LIKE 'success%'
      GROUP BY o.run_id
    ), latest AS (
      SELECT run_id FROM candidate_runs ORDER BY observed_at DESC, run_id DESC LIMIT 1
    )
    SELECT source_item_id,item_name,price_cents,currency,variant,observed_at,run_id,raw_uri
    FROM `hackumass26.raw.menu_observations`
    WHERE run_id IN (SELECT run_id FROM latest)
    """
    baseline = [dict(row) for row in client.query(sql,location=cfg["location"],
        job_config=bigquery.QueryJobConfig(query_parameters=params, maximum_bytes_billed=100*1024**2)).result(timeout=120)]
    if not baseline:
        raise ValueError("No successful matching source/context baseline in BigQuery.")
    print(f"BigQuery baseline: {len(baseline)} rows; run {baseline[0]['run_id']}",flush=True)
    stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out=ROOT/"artifacts"/f"taco-bell-no-js-{stamp}"
    out.mkdir(parents=True)
    (out/"baseline.json").write_text(json.dumps(baseline,default=str,indent=2),encoding="utf-8")
    key=os.getenv("ZENROWS_API_KEY")
    if not key:
        raise ValueError("Missing local ZenRows key.")
    try:
        response=requests.get("https://api.zenrows.com/v1/",
            params={"url":cfg["url"],"apikey":key,"js_render":"false","premium_proxy":"false"},
            timeout=(15,120))
    except requests.RequestException:
        raise RuntimeError("ZenRows request failed; URL suppressed to protect the key.") from None
    report={"tested_at":stamp,"http_status":response.status_code,"response_bytes":len(response.content),
            "request_options":{"js_render":False,"premium_proxy":False,"wait_for":None},
            "reported_request_cost":response.headers.get("X-Request-Cost"),
            "baseline_run":baseline[0]["run_id"],"baseline_observed_at":str(baseline[0]["observed_at"]),
            "baseline_rows":len(baseline)}
    if response.status_code!=200:
        report["outcome"]="fetch_failed"
    else:
        (out/"response.html").write_bytes(response.content)
        try:
            items,rejects,card_count=parse_menu(response.content,cfg["store_id"],cfg["expected_heading"])
        except ValueError as exc:
            items,rejects,card_count=[],[],0
            report["parse_error"]=str(exc)
        before={r["source_item_id"]:r for r in baseline}
        after={r["source_item_id"]:r for r in items}
        common=before.keys() & after.keys()
        report.update({
            "extracted_items":len(items),"cards":card_count,"rejects":rejects,
            "baseline_unique_ids":len(before),
            "missing":[before[k] for k in sorted(before.keys()-after.keys())],
            "added":[after[k] for k in sorted(after.keys()-before.keys())],
            "price_changes":[{"id":k,"name":after[k]["item_name"],"before":before[k]["price_cents"],
                             "after":after[k]["price_cents"]} for k in sorted(common)
                             if before[k]["price_cents"]!=after[k]["price_cents"]],
            "name_changes":[{"id":k,"before":before[k]["item_name"],"after":after[k]["item_name"]}
                            for k in sorted(common) if before[k]["item_name"]!=after[k]["item_name"]],
            "variant_changes":[{"id":k,"before":before[k]["variant"],"after":after[k].get("variant")} for k in sorted(common) if before[k]["variant"]!=after[k].get("variant")],
            "matching_id_name_price":sum(before[k]["price_cents"]==after[k]["price_cents"] and
                                        before[k]["item_name"]==after[k]["item_name"] for k in common),
            "categories":sorted({r["category"] or "" for r in items}),
        })
        (out/"extracted.json").write_text(json.dumps(items,indent=2),encoding="utf-8")
    (out/"comparison.json").write_text(json.dumps(report,default=str,indent=2),encoding="utf-8")
    summary={k:v for k,v in report.items() if k not in ("missing","added","price_changes","name_changes")}
    for field in ("missing","added","price_changes","name_changes"):
        if field in report:
            summary[field+"_count"]=len(report[field])
            summary[field+"_sample"]=report[field][:5]
    print(json.dumps(summary,default=str,indent=2))
    print(f"Report: {out/'comparison.json'}")
    return 0

if __name__=="__main__":
    sys.exit(main())

