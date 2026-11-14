"""Import BLS Diary CSVs from S3, optionally loading separate raw BQ tables."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import uuid
from benchmark_data.s3_source import get_s3_client, discover, download
from benchmark_data.organize import organize
from shared.paths import ROOT
from shared.settings import BUCKET


def import_dataset(year, *, bucket=BUCKET, prefix=None, output_root=None,
                   load_bigquery=False, dataset="bls_ce_diaries_raw", allow_partial=False):
    prefix = prefix or f"reference/bls-ce-diaries/{year}"
    root = Path(output_root) if output_root else ROOT / "artifacts/bls-ce-diaries"
    run = root / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")+"-"+uuid.uuid4().hex[:8])
    run.mkdir(parents=True, exist_ok=False)
    manifest = {"status": "running", "year": year, "source": f"s3://{bucket}/{prefix}",
                "started_at": datetime.now(timezone.utc).isoformat(), "files": [],
                "raw_values_preserved": True, "weights_adjusted": False}
    manifest_path = run / "manifest.json"
    def persist():
        temp = manifest_path.with_suffix(".tmp")
        temp.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        temp.replace(manifest_path)
    persist()
    try:
        s3 = get_s3_client()
        sources, missing = discover(s3, bucket, prefix, year, allow_partial)
        manifest["missing_type_quarters"] = missing
        # Validate and organize the complete inventory before any warehouse writes.
        for source in sources:
            folder = run / source.relative_directory
            csv_path = folder / source.filename
            download(s3, bucket, source, csv_path)
            record = organize(source, csv_path, folder / "records.jsonl", f"s3://{bucket}/{source.key}")
            manifest["files"].append(record)
            persist()
        if load_bigquery:
            from benchmark_data.warehouse import load_file
            from shared.bigquery import get_client
            bq = get_client()
            for source, record in zip(sources, manifest["files"]):
                record["bigquery"] = load_file(source, record, dataset, bq)
                persist()
        manifest["status"] = "complete"
    except Exception as exc:
        manifest["status"] = "failed"
        manifest["error_type"] = type(exc).__name__
        raise
    finally:
        manifest["finished_at"] = datetime.now(timezone.utc).isoformat()
        persist()
    return manifest_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, choices=(2024,2025), required=True)
    parser.add_argument("--bucket", default=BUCKET)
    parser.add_argument("--prefix", help="Override S3 year prefix")
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--load-bigquery", action="store_true", help="Replace each selected raw file table via a load job")
    parser.add_argument("--dataset", default="bls_ce_diaries_raw")
    parser.add_argument("--allow-partial", action="store_true")
    args = parser.parse_args()
    try:
        path = import_dataset(**vars(args))
        print(f"Import complete. Manifest: {path}")
        return 0
    except Exception as exc:
        print(f"Import failed ({type(exc).__name__}): {exc}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
