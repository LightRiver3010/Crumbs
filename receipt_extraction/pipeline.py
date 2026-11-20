"""Upload -> Gemini -> review draft. Saving is a separate user action."""
from receipt_extraction.images import normalize_image
from receipt_extraction.deduplication import remove_exact_duplicate_orders, upload_id
from receipt_extraction.gemini_client import extract_image
from shared.storage import upload_image

class ReceiptPreparationError(RuntimeError):
    """A safe stage label; the underlying exception is never shown verbatim."""

    def __init__(self, stage):
        self.stage = stage
        super().__init__(f"Receipt preparation failed during {stage}.")


def prepare(data, session_id):
    try:
        normalized = normalize_image(data)
    except Exception as exc:
        raise ReceiptPreparationError("image") from exc
    identifier = upload_id(normalized)
    try:
        uri = upload_image(normalized, session_id, identifier)
    except Exception as exc:
        raise ReceiptPreparationError("storage") from exc
    try:
        extraction = extract_image(normalized)
    except Exception as exc:
        raise ReceiptPreparationError("gemini") from exc
    extraction, _ = remove_exact_duplicate_orders(extraction)
    return identifier, uri, extraction
