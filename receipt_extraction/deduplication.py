"""Stable upload IDs and conservative order IDs for sequential retries."""
import hashlib

def upload_id(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def order_id(session_id, upload, index, order):
    # A visible provider reference can identify the same order across screenshots.
    identity = f"ref:{order.provider}:{order.order_reference}" if order.provider and order.order_reference else f"upload:{upload}:{index}"
    return hashlib.sha256(f"{session_id}:{identity}".encode()).hexdigest()
