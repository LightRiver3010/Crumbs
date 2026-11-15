"""One bounded ZenRows fetch -> immutable S3 snapshot -> Python -> BigQuery.
Replay a saved run without fetching again: --replay RUN_ID.
"""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import parse_qs, urlsplit
import uuid

import boto3
from botocore.config import Config
from menu_ingestion.menu_parsers import PARSERS, VERSIONS, WAIT_FOR, COVERAGE, parse_menu, store_id_from_url
from dotenv import load_dotenv
from google.cloud import bigquery
import requests

from shared.aws import session
from shared.paths import ARTIFACTS_ROOT, ROOT
def manifest_store_id(manifest):
    # Read old immutable Uber Eats snapshots without requiring the legacy field in new config.
    return manifest.get("store_id", manifest.get("store_uuid"))



def now():
    return datetime.now(timezone.utc).isoformat()




def use_html_only(source):
    return source.get("html_only_tested") is True and source.get("html_only_matches_js") is True


def extract_snapshot(html, manifest, source):
    # Replay follows how this snapshot was fetched, even if source flags changed later.
    return PARSERS[source["provider"]](
        html, manifest_store_id(manifest),
        manifest.get("expected_heading", source.get("expected_heading")),
        html_only=manifest.get("fetch_options", {}).get("js_render", True) is False)


def fetch_menu(url, api_key, provider, *, html_only=False):
    # One request; no automatic paid escalation, including when HTML extraction fails.
    params = {"url": url, "apikey": api_key, "js_render": "false" if html_only else "true",
              "premium_proxy": "false"}
    if not html_only:
        params["wait_for"] = WAIT_FOR[provider]
    try:
        response = requests.get(
            "https://api.zenrows.com/v1/",
            params=params,
            timeout=(15, 120),
        )
    except requests.RequestException:
        # Requests exceptions can contain the API key in the URL.
        raise RuntimeError("ZenRows transport failure; request URL suppressed to protect the key.") from None
    if response.status_code != 200:
        raise RuntimeError(f"ZenRows returned HTTP {response.status_code}; response suppressed to protect credentials.")
    return response.content, {
        "http_status": response.status_code,
        "credit_cost": response.headers.get("X-Request-Cost"),
        "fetch_options": {"js_render": not html_only, "premium_proxy": False},
    }


def read_s3(s3, bucket, key):
    output = io.BytesIO()
    s3.download_fileobj(bucket, key, output)
    return output.getvalue()


def put_json(s3, bucket, key, value, immutable=False):
    args = {"Bucket": bucket, "Key": key,
            "Body": json.dumps(value, indent=2).encode(),
            "ContentType": "application/json"}
    if immutable:
        args["IfNoneMatch"] = "*"
    s3.put_object(**args)


def merge_rows(client, project, location, name, rows, key):
    """Sequential replay is idempotent. Concurrent replays are not supported."""
    destination = f"{project}.raw.{name}"
    schema = client.get_table(destination).schema
    stage_id = f"{project}.raw._stage_{uuid.uuid4().hex}"
    stage = bigquery.Table(stage_id, schema=schema)
    stage.expires = datetime.now(timezone.utc) + timedelta(days=1)
    client.create_table(stage)
    client.load_table_from_json(
        rows, stage_id, location=location,
        job_config=bigquery.LoadJobConfig(schema=schema, write_disposition="WRITE_EMPTY")
    ).result(timeout=120)
    columns = list(rows[0])
    names = ", ".join(f"`{col}`" for col in columns)
    values = ", ".join(f"S.`{col}`" for col in columns)
    # All identifiers are fixed code constants, not scraped input.
    updates = ", ".join(f"T.`{col}`=S.`{col}`" for col in columns if col != key)
    matched = f"WHEN MATCHED THEN UPDATE SET {updates}" if name == "ingestion_runs" else ""
    sql = f"""MERGE `{destination}` T USING `{stage_id}` S ON T.{key}=S.{key}
    {matched}
    WHEN NOT MATCHED THEN INSERT ({names}) VALUES ({values})"""
    client.query(sql, location=location,
                 job_config=bigquery.QueryJobConfig(maximum_bytes_billed=100 * 1024**2)).result(timeout=120)
    try:
        client.delete_table(stage_id, not_found_ok=True)
    except Exception:
        print("Temporary staging table cleanup deferred to its 24-hour expiration.", file=sys.stderr)


def run_source(cfg, args, run_id):
    """Run a single source. Return nonzero on failure so an orchestrator can retry."""
    parser_version = VERSIONS[cfg["provider"]]
    folder = ARTIFACTS_ROOT / run_id
    folder.mkdir(parents=True, exist_ok=True)
    prefix = f"raw/menus/{cfg['provider']}/{cfg['id']}/{run_id}"
    raw_key, manifest_key = f"{prefix}/response.html", f"{prefix}/manifest.json"
    s3 = client = manifest = None
    stage = "preflight"
    try:
        if sum(bool(x) for x in (args.fetch_only, args.replay, args.resume_local)) > 1:
            raise ValueError("Choose only one of --fetch-only, --replay, --resume-local.")
        if not args.fetch_only:
            aws_session = session(cfg["region"], cfg.get("profile"))
            s3 = aws_session.client("s3", config=Config(
                connect_timeout=10, read_timeout=30,
                retries={"total_max_attempts": 3, "mode": "standard"}))
            s3.head_bucket(Bucket=cfg["bucket"])
            client = bigquery.Client(project=cfg["project"])
            dataset = client.get_dataset(f'{cfg["project"]}.raw')
            if dataset.location.lower() != cfg["location"].lower():
                raise ValueError(f"Expected dataset location {cfg['location']}, got {dataset.location}.")
            # Reuse the user's existing versioned raw-table DDL.
            client.query((ROOT / "sql/setup_raw_tables.sql").read_text(encoding="utf-8-sig"),
                         location=cfg["location"]).result(timeout=120)
        if args.batch_id and not args.fetch_only:
            # A retry of the same Airflow run reuses the prior immutable snapshot.
            try:
                read_s3(s3, cfg["bucket"], manifest_key)
                args.replay = run_id
            except s3.exceptions.ClientError as exc:
                if exc.response["Error"]["Code"] not in ("404", "NoSuchKey", "NotFound"):
                    raise
                if (folder / "manifest.json").exists():
                    args.resume_local = run_id
        if args.replay:
            stage = "read saved S3 manifest"
            manifest = json.loads(read_s3(s3, cfg["bucket"], manifest_key))
            if manifest["run_id"] != run_id:
                raise ValueError("Replay manifest run ID mismatch.")
        elif args.resume_local:
            stage = "resume saved local fetch"
            manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
            html_bytes = (folder / "response.html").read_bytes()
            if manifest["run_id"] != run_id or hashlib.sha256(html_bytes).hexdigest() != manifest["sha256"]:
                raise ValueError("Local snapshot integrity check failed.")
            if manifest_store_id(manifest) != cfg["store_id"] or manifest["raw_uri"] != f's3://{cfg["bucket"]}/{raw_key}':
                raise ValueError("Local snapshot belongs to a different source or destination.")
            # Existing identical objects can be safely resumed; never overwrite changed bytes.
            for key, content, mime in (
                (raw_key, html_bytes, "text/html; charset=utf-8"),
                (manifest_key, json.dumps(manifest, indent=2).encode(), "application/json"),
            ):
                try:
                    s3.put_object(Bucket=cfg["bucket"], Key=key, Body=content,
                                  ContentType=mime, IfNoneMatch="*")
                except s3.exceptions.ClientError as exc:
                    if exc.response["Error"]["Code"] not in ("PreconditionFailed", "412"):
                        raise
                    if read_s3(s3, cfg["bucket"], key) != content:
                        raise ValueError("Existing S3 snapshot differs; refusing overwrite.") from exc
            print("PASS: Saved local response persisted to S3.", flush=True)
        else:
            stage = "fetch ZenRows HTML"
            if not os.getenv("ZENROWS_API_KEY"):
                raise ValueError("ZENROWS_API_KEY is missing from the project .env.")
            print(f"Run ID: {run_id}", flush=True)
            started = now()
            html_bytes, fetch_metadata = fetch_menu(cfg["url"], os.environ["ZENROWS_API_KEY"], cfg["provider"], html_only=use_html_only(cfg))
            (folder / "response.html").write_bytes(html_bytes)
            manifest = {
                "run_id": run_id, "requested_at": started, "observed_at": now(),
                "source_url": cfg["url"], "store_id": cfg["store_id"],
                "source_id": cfg["id"], "provider": cfg["provider"],
                "expected_heading": cfg.get("expected_heading"),
                "currency": cfg["currency"], "fulfillment_mode": cfg["fulfillment_mode"],
                "destination_context": "URL-supplied context; not independently verified",
                "raw_uri": f's3://{cfg["bucket"]}/{raw_key}',
                "sha256": hashlib.sha256(html_bytes).hexdigest(),
                "coverage": ("Embedded menu records; full variant coverage unverified" if use_html_only(cfg) else COVERAGE[cfg["provider"]]),
                **fetch_metadata,
            }
            (folder / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
            if not args.fetch_only:
                stage = "persist original HTML and manifest to S3"
                s3.put_object(Bucket=cfg["bucket"], Key=raw_key, Body=html_bytes,
                              ContentType="text/html; charset=utf-8", IfNoneMatch="*")
                put_json(s3, cfg["bucket"], manifest_key, manifest, immutable=True)
                print("PASS: Original response saved to S3.", flush=True)
        if not args.fetch_only:
            stage = "read original HTML from S3"
            html_bytes = read_s3(s3, cfg["bucket"], raw_key)
            if hashlib.sha256(html_bytes).hexdigest() != manifest["sha256"]:
                raise ValueError("S3 snapshot hash mismatch.")
            (folder / "response.html").write_bytes(html_bytes)
        stage = "extract and validate menu cards"
        if manifest_store_id(manifest) != cfg["store_id"] or manifest.get("source_id", cfg["id"]) != cfg["id"]:
            raise ValueError("Snapshot belongs to a different source.")
        items, rejects, card_count = extract_snapshot(html_bytes, manifest, cfg)
        if not items:
            raise ValueError("No menu items were extracted; refusing to publish an empty snapshot.")
        rows = [{
            "observation_id": hashlib.sha256(f'{run_id}|{x["source_item_id"]}'.encode()).hexdigest(),
            "run_id": run_id, "branch_id": manifest_store_id(manifest), "provider": cfg["provider"],
            "source_item_id": x["source_item_id"], "item_name": x["item_name"],
            "variant": x.get("variant"), "price_cents": x["price_cents"], "currency": manifest["currency"],
            "fulfillment_mode": manifest["fulfillment_mode"], "observed_at": manifest["observed_at"],
            "source_url": manifest["source_url"], "raw_uri": manifest["raw_uri"],
        } for x in items]
        report = {"parser_version": parser_version, "run_id": run_id,
                  "card_count": card_count, "item_count": len(items), "rejects": rejects,
                  "coverage": manifest["coverage"], "items": items}
        (folder / "extracted.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        excluded = sum(r.get("severity") == "excluded" for r in rejects)
        print(f"PASS: {len(items)} unique items extracted; {excluded} exclusions; {len(rejects)-excluded} errors.", flush=True)
        if args.fetch_only:
            print(f"LOCAL ONLY: {folder}. No S3 or BigQuery writes.")
            return 0
        # Audit outputs remain versioned by parser version; raw input never changes.
        put_json(s3, cfg["bucket"], f"{prefix}/{parser_version}/extracted.json", report)
        if any(r.get("severity") != "excluded" for r in rejects):
            raise ValueError("Ambiguous cards quarantined in extracted.json; refusing partial warehouse publish.")
        stage = "load BigQuery observations"
        merge_rows(client, cfg["project"], cfg["location"], "menu_observations", rows, "observation_id")
        stage = "record successful ingestion run"
        run_record = {
            "run_id": run_id, "source": cfg["provider"], "requested_at": manifest["requested_at"],
            "finished_at": now(), "status": "success_partial_coverage",
            "raw_uri": manifest["raw_uri"], "row_count": len(rows), "error_message": None,
        }
        merge_rows(client, cfg["project"], cfg["location"], "ingestion_runs", [run_record], "run_id")
        result = list(client.query(
            f'SELECT COUNT(*) AS n, COUNT(DISTINCT observation_id) AS unique_n FROM `{cfg["project"]}.raw.menu_observations` WHERE run_id=@run',
            location=cfg["location"], job_config=bigquery.QueryJobConfig(
                maximum_bytes_billed=100 * 1024**2,
                query_parameters=[bigquery.ScalarQueryParameter("run", "STRING", run_id)])
        ).result(timeout=120))[0]
        if result.n != len(rows) or result.unique_n != len(rows):
            raise ValueError("Warehouse count/deduplication verification failed.")
        print(f"SUCCESS: {result.n} verified observations in {cfg['project']}.raw.menu_observations")
        print(f"Coverage: {manifest['coverage']}")
        print(f"Replay without fetching: python -m menu_ingestion.ingest_menu --source {cfg['id']} --replay {run_id}")
        return 0
    except Exception as exc:
        message = f"{type(exc).__name__}: {exc}"
        secret = os.getenv("ZENROWS_API_KEY")
        if secret:
            message = message.replace(secret, "[REDACTED]")
        failure = {"source_id": cfg["id"], "run_id": run_id, "stage": stage, "error": message, "finished_at": now()}
        (folder / "failure.json").write_text(json.dumps(failure, indent=2), encoding="utf-8")
        if s3 and manifest:
            try:
                put_json(s3, cfg["bucket"], f"{prefix}/failure.json", failure)
                if client:
                    merge_rows(client, cfg["project"], cfg["location"], "ingestion_runs", [{
                        "run_id": run_id, "source": cfg["provider"], "requested_at": manifest["requested_at"],
                        "finished_at": now(), "status": "failed", "raw_uri": manifest["raw_uri"],
                        "row_count": None, "error_message": f"Failed during {stage}; see S3 failure manifest."
                    }], "run_id")
            except Exception:
                print("Could not persist failure status to cloud; local failure.json retained.", file=sys.stderr)
        print(f"FAIL during {stage}: {message}", file=sys.stderr)
        print(f"Local diagnostic folder: {folder}", file=sys.stderr)
        return 1


def load_sources(path):
    config = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    defaults = config.get("defaults", {})
    sources, ids = [], set()
    for entry in config["sources"]:
        source = {**defaults, **entry}
        # Proof belongs to each individual source, never inherited from shared defaults.
        for flag in ("html_only_tested", "html_only_matches_js"):
            source[flag] = entry.get(flag, False)
            if type(source[flag]) is not bool:
                raise ValueError(f"{entry.get('id', 'source')}: {flag} must be true or false.")

        source_id = source.get("id", "")
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", source_id) or source_id in ids:
            raise ValueError("Each source needs a unique lowercase id using letters, numbers, - or _.")
        ids.add(source_id)
        if not isinstance(source.get("enabled", True), bool):
            raise ValueError(f"{source_id}: enabled must be true or false.")
        if not source.get("enabled", True):
            continue
        if source.get("provider") not in PARSERS:
            raise ValueError(f"{source_id}: unsupported provider; add and test a parser first.")
        parsed = urlsplit(source.get("url", ""))
        provider = source["provider"]
        host = {"ubereats": "www.ubereats.com", "doordash": "www.doordash.com"}[provider]
        if parsed.scheme != "https" or parsed.hostname != host or not parsed.path.startswith("/store/"):
            raise ValueError(f"{source_id}: expected an HTTPS {provider} store URL.")
        store_id = source.get("store_id")
        if not isinstance(store_id, str) or not store_id.strip():
            raise ValueError(f"{source_id}: store_id must be a nonempty string.")
        if provider == "doordash" and store_id_from_url(source["url"]) != store_id:
            raise ValueError(f"{source_id}: store_id does not match the DoorDash URL.")
        if source.get("currency") != "USD":
            raise ValueError(f"{source_id}: this parser currently supports USD prices only.")
        if source.get("fulfillment_mode") not in ("DELIVERY", "PICKUP"):
            raise ValueError(f"{source_id}: fulfillment_mode must be DELIVERY or PICKUP.")
        query = parse_qs(parsed.query)
        if provider == "ubereats":
            mode = query.get("diningMode", [None])[0]
        else:
            # DoorDash store URLs omit `pickup` for the default delivery mode.
            mode = {"true": "PICKUP", "false": "DELIVERY"}.get(query.get("pickup", ["false"])[0])
        if mode != source["fulfillment_mode"]:
            raise ValueError(f"{source_id}: URL diningMode must match fulfillment_mode.")
        for field in ("bucket", "project", "region", "location"):
            if not source.get(field):
                raise ValueError(f"{source_id}: missing {field}.")
        # The checked-in SQL creates tables in this project's warehouse.
        if source["project"] != "hackumass26":
            raise ValueError("Update the raw-table DDL before selecting a different Google project.")
        sources.append(source)
    if not sources:
        raise ValueError("No enabled sources configured.")
    return sources


def source_run_id(source_id, batch_id):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"delivery-menu|{batch_id}|{source_id}"))


def run_batch(sources, args, runner=run_source):
    results = []
    batch_id = args.batch_id or str(uuid.uuid4())
    for source in sources:
        run_id = str(uuid.UUID(args.replay or args.resume_local)) if (args.replay or args.resume_local) else source_run_id(source["id"], batch_id)
        per_source_args = argparse.Namespace(**vars(args))
        print(f"Source: {source['id']} | run: {run_id}", flush=True)
        # The runner handles ordinary failures; protect remaining sources from unexpected errors.
        try:
            code = runner(source, per_source_args, run_id)
        except Exception as exc:
            print(f"Source {source['id']} failed unexpectedly ({type(exc).__name__}).", file=sys.stderr)
            code = 1
        results.append({"source_id": source["id"], "run_id": run_id, "status": "success" if code == 0 else "failed"})
    summary = {"batch_id": batch_id, "sources": results}
    folder = ARTIFACTS_ROOT / "batches"
    folder.mkdir(parents=True, exist_ok=True)
    summary_path = folder / (hashlib.sha256(batch_id.encode()).hexdigest() + ".json")
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 1 if any(x["status"] == "failed" for x in results) else 0


def main():
    ap = argparse.ArgumentParser(description="Process every enabled menu source, or select one for Airflow.")
    ap.add_argument("--config", type=Path, default=ROOT / "config/sources.json")
    ap.add_argument("--source", help="Process only this source ID; recommended for one Airflow task per source.")
    ap.add_argument("--batch-id", help="Stable Airflow run ID; reuse on retries to prevent duplicate observations.")
    actions = ap.add_mutually_exclusive_group()
    actions.add_argument("--replay")
    actions.add_argument("--resume-local")
    actions.add_argument("--fetch-only", action="store_true")
    ap.add_argument("--list-sources", action="store_true", help="Validate configuration and print IDs without cloud calls.")
    args = ap.parse_args()
    load_dotenv(ROOT / ".env")
    try:
        sources = load_sources(args.config)
        if args.source:
            sources = [s for s in sources if s["id"] == args.source]
            if not sources:
                raise ValueError("Selected source is missing or disabled.")
        if args.list_sources:
            print("\n".join(s["id"] for s in sources))
            return 0
        if (args.replay or args.resume_local) and len(sources) != 1:
            raise ValueError("Use --source when replaying a run in a multi-source configuration.")
        if args.batch_id and (args.replay or args.resume_local or args.fetch_only):
            raise ValueError("--batch-id is only for normal cloud runs.")
        if args.replay or args.resume_local:
            uuid.UUID(args.replay or args.resume_local)
        return run_batch(sources, args)
    except (ValueError, KeyError, OSError) as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
