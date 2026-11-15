"""Upload -> Gemini -> review draft. Saving is a separate user action."""
from receipt_extraction.images import normalize_image
from receipt_extraction.deduplication import remove_exact_duplicate_orders, upload_id
from receipt_extraction.gemini_client import extract_image
from shared.storage import upload_image

def prepare(data, session_id):
    normalized = normalize_image(data)
    identifier = upload_id(normalized)
    uri = upload_image(normalized, session_id, identifier)
    extraction = extract_image(normalized)
    extraction, _ = remove_exact_duplicate_orders(extraction)
    return identifier, uri, extraction
