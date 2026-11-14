"""Read-only S3 discovery and downloads. Never changes source objects."""
from pathlib import Path
import boto3
from benchmark_data.catalog import identify, validate_inventory
from shared.settings import DEFAULTS


def get_s3_client():
    return boto3.Session(profile_name=DEFAULTS.get("profile"), region_name=DEFAULTS["region"]).client("s3")


def discover(client, bucket, prefix, year, allow_partial=False):
    files = []
    for page in client.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix.rstrip("/")+"/"):
        for obj in page.get("Contents", []):
            if obj["Key"].lower().endswith(".csv"):
                files.append(identify(obj["Key"], year))
    missing = validate_inventory(files, allow_partial)
    return sorted(files, key=lambda f: (f.quarter, f.kind)), missing


def download(client, bucket, source, target):
    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    client.download_file(bucket, source.key, str(target))
