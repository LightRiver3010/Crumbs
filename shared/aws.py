"""AWS session construction for local profiles and managed runtimes."""
import os

import boto3


def session(region: str, profile: str | None = None):
    """Use managed credentials when requested, otherwise preserve local profiles."""
    use_default_chain = os.getenv("AWS_USE_DEFAULT_CREDENTIALS", "").lower() in {"1", "true", "yes"}
    configured_profile = os.getenv("AWS_PROFILE", profile)
    return boto3.Session(
        profile_name=None if use_default_chain else configured_profile,
        region_name=region,
    )
