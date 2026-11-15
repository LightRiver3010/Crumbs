"""Stable upload IDs and conservative order IDs for sequential retries."""
import hashlib
import json

from receipt_extraction.schemas import Extraction

def upload_id(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def order_id(session_id, upload, index, order):
    # A visible provider reference can identify the same order across screenshots.
    identity = f"ref:{order.provider}:{order.order_reference}" if order.provider and order.order_reference else f"upload:{upload}:{index}"
    return hashlib.sha256(f"{session_id}:{identity}".encode()).hexdigest()


def remove_exact_duplicate_orders(extraction: Extraction) -> tuple[Extraction, int]:
    """Keep the first order when every extracted field matches exactly."""
    seen = set()
    unique = []
    removed = 0
    for order in extraction.orders:
        fingerprint = json.dumps(order.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        if fingerprint in seen:
            removed += 1
            continue
        seen.add(fingerprint)
        unique.append(order)
    if not removed:
        return extraction, 0
    return Extraction(
        orders=unique,
        warnings=[*extraction.warnings,
                  f"Removed {removed} exact duplicate order{'s' if removed != 1 else ''} before review."],
    ), removed
