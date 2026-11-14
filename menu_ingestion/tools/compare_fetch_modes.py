"""Compare one HTML-only fetch against an existing local rendered snapshot."""
import argparse
from datetime import datetime, timezone
import json
import os
from dotenv import load_dotenv
from menu_ingestion.ingest_menu import load_sources, fetch_menu, extract_snapshot
from shared.paths import ROOT


def compare_items(before, after):
    fields = ("item_name", "price_cents", "variant")
    left = {x["source_item_id"]: x for x in before}
    right = {x["source_item_id"]: x for x in after}
    common = left.keys() & right.keys()
    return {"missing_ids": sorted(left.keys()-right.keys()),
            "added_ids": sorted(right.keys()-left.keys()),
            "changed": [{"id": key, "before": left[key], "after": right[key]} for key in sorted(common)
                        if any(left[key].get(f) != right[key].get(f) for f in fields)]}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source",required=True)
    parser.add_argument("--baseline-run",required=True)
    args=parser.parse_args()
    load_dotenv(ROOT/".env")
    source=next(s for s in load_sources(ROOT/"config/sources.json") if s["id"]==args.source)
    baseline_folder=ROOT/"artifacts"/args.baseline_run
    manifest=json.loads((baseline_folder/"manifest.json").read_text())
    if manifest["source_id"]!=source["id"] or manifest["fetch_options"]["js_render"] is not True:
        raise ValueError("Expected a rendered snapshot for this source.")
    before,rejects,_=extract_snapshot((baseline_folder/"response.html").read_bytes(),manifest,source)
    if any(r.get("severity")!="excluded" for r in rejects):
        raise ValueError("Rendered baseline has parser errors.")
    stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    folder=ROOT/"artifacts"/f"{args.source}-html-comparison-{stamp}"
    folder.mkdir(parents=True)
    report={"tested_at":stamp,"source_id":source["id"],"baseline_run":args.baseline_run,
            "baseline_items":len(before),"matches":False}
    try:
        html,meta=fetch_menu(source["url"],os.environ["ZENROWS_API_KEY"],source["provider"],html_only=True)
        (folder/"response.html").write_bytes(html)
        after,excluded,_=extract_snapshot(html,{**manifest,**meta},source)
        report.update(meta)
        report.update(compare_items(before,after))
        report.update(html_items=len(after),rejects=excluded)
        report["matches"]=bool(after) and not any(report[k] for k in ("missing_ids","added_ids","changed")) and rejects==excluded
        report["outcome"]="compared"
        (folder/"extracted.json").write_text(json.dumps(after,indent=2))
    except (RuntimeError,ValueError) as exc:
        report.update(outcome="fetch_or_parse_failed",error=str(exc))
    (folder/"comparison.json").write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
    print(f"Report: {folder/'comparison.json'}")

if __name__=="__main__":
    main()
