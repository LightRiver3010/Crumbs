"""AWS session construction for local profiles and managed runtimes."""
import os

import boto3

from shared.settings import secret


def session(region: str, profile: str | None = None):
    """Use managed credentials when requested, otherwise preserve local profiles."""
    use_default_chain = os.getenv("AWS_USE_DEFAULT_CREDENTIALS", "").lower() in {"1", "true", "yes"}
    configured_profile = os.getenv("AWS_PROFILE", profile)
    access_key = secret("AWS_ACCESS_KEY_ID")
    secret_key = secret("AWS_SECRET_ACCESS_KEY")
    session_token = secret("AWS_SESSION_TOKEN")
    return boto3.Session(
        profile_name=None if use_default_chain else configured_profile,
        region_name=region,
        aws_access_key_id=None if use_default_chain else access_key,
        aws_secret_access_key=None if use_default_chain else secret_key,
        aws_session_token=None if use_default_chain else session_token,
    )
