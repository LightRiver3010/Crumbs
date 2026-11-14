"""Shared warehouse client; uses Application Default Credentials."""
from google.cloud import bigquery
from shared.settings import PROJECT, LOCATION

def get_client():
    return bigquery.Client(project=PROJECT, location=LOCATION)
