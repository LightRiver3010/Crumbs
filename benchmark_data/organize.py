"""Lossless raw ingestion: original strings plus explicit source metadata."""
import csv
import hashlib
import json
import re
from pathlib import Path

METADATA = ("bls_release_year", "bls_file_quarter", "bls_file_type", "bls_source_uri", "bls_source_sha256", "bls_source_row")
REQUIRED = {
    "fmld": {"NEWID", "FINLWT21", "FAM_SIZE"},
    "memd": {"NEWID", "MEMBNO"},
    "expd": {"NEWID", "UCC", "COST"},
    "dtbd": {"NEWID", "UCC", "AMOUNT"},
    "dtid": {"NEWID", "UCC", "AMOUNT", "IMPNUM"},
}


def organize(source, csv_path, output_path, source_uri):
    csv_path, output_path = Path(csv_path), Path(output_path)
    with csv_path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    partial = output_path.with_suffix(".partial")
    count = 0
    seen = set()
    try:
        with csv_path.open(encoding="utf-8-sig", newline="") as inp, partial.open("w", encoding="utf-8") as out:
            reader = csv.DictReader(inp, strict=True)
            columns = reader.fieldnames or []
            if not columns or len({c.lower() for c in columns}) != len(columns):
                raise ValueError("Missing or duplicate CSV headers.")
            if any(not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,299}", c) for c in columns):
                raise ValueError("Invalid CSV column name.")
            if set(c.lower() for c in columns) & set(METADATA):
                raise ValueError("Source columns conflict with provenance metadata.")
            missing = REQUIRED[source.kind] - set(columns)
            if missing:
                raise ValueError(f"Missing required columns: {sorted(missing)}")
            for count, row in enumerate(reader, 1):
                if None in row or any(v is None for v in row.values()):
                    raise ValueError(f"CSV row {count} does not match its header.")
                if not row["NEWID"].strip():
                    raise ValueError(f"Missing NEWID at row {count}.")
                if source.kind in ("fmld", "memd"):
                    identity = (row["NEWID"], row.get("MEMBNO"))
                    if identity in seen:
                        raise ValueError(f"Duplicate {source.kind} identity at row {count}.")
                    seen.add(identity)
                row.update(bls_release_year=source.year, bls_file_quarter=source.quarter,
                    bls_file_type=source.kind, bls_source_uri=source_uri,
                    bls_source_sha256=digest, bls_source_row=count)
                out.write(json.dumps(row, ensure_ascii=False)+"\n")
            if count == 0:
                raise ValueError("Empty CSV file.")
        partial.replace(output_path)
    except Exception:
        partial.unlink(missing_ok=True)
        raise
    return {"file_type": source.kind, "year": source.year, "quarter": source.quarter,
        "source_uri": source_uri, "sha256": digest, "row_count": count,
        "columns": columns, "original_csv": str(csv_path), "organized_jsonl": str(output_path)}
