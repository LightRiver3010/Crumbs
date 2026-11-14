"""S3 image storage, independent of menu extraction."""
from io import BytesIO
import boto3
from shared.settings import DEFAULTS, BUCKET

def upload_image(data: bytes, session_id: str, upload_id: str) -> str:
    client = boto3.Session(profile_name=DEFAULTS.get("profile"), region_name=DEFAULTS["region"]).client("s3")
    key = f"private/receipts/{session_id}/{upload_id}.png"
    client.upload_fileobj(BytesIO(data), BUCKET, key, ExtraArgs={"ContentType": "image/png", "ServerSideEncryption": "AES256"})
    return f"s3://{BUCKET}/{key}"
