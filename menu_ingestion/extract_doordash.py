"""DoorDash extractor for MenuPageItem records embedded in rendered Next.js HTML.
Decode serialized JSON only; never execute page JavaScript.
"""
from decimal import Decimal
import json
import re
from urllib.parse import urlsplit
from bs4 import BeautifulSoup

VERSION = "doordash-flight-v1"
COVERAGE = "Embedded MenuPageItem records; availability and full variant coverage unverified"
PRICE = re.compile(r"^(?:US)?\$([\d,]+\.\d{2})(\+)?$")


def store_id_from_url(url):
    parsed = urlsplit(url)
    match = re.match(r"^/store/[^/]+-(\d+)(?:/|$)", parsed.path)
    if parsed.scheme != "https" or parsed.hostname != "www.doordash.com" or not match:
        raise ValueError("Expected a DoorDash store URL containing its numeric store ID.")
    return match.group(1)


def menu_records(soup):
    chunks = []
    for script in soup.find_all("script"):
        text = (script.string or "").strip()
        prefix = "self.__next_f.push("
        if not text.startswith(prefix):
            continue
        payload = text[len(prefix):].rstrip(";")
        if not payload.endswith(")"):
            continue
        values = json.loads(payload[:-1])
        if isinstance(values, list) and len(values) == 2 and values[0] == 1 and isinstance(values[1], str):
            chunks.append(values[1])
    serialized = "".join(chunks)
    decoder = json.JSONDecoder()
    for match in re.finditer(r'\{"__typename"\s*:\s*"MenuPageItem"', serialized):
        record, _ = decoder.raw_decode(serialized, match.start())
        yield record


def parse_menu(html, store_id, expected_heading=None, *, html_only=False):
    # Both response types can contain the same embedded records. Fetch availability is separate.
    if type(html_only) is not bool:
        raise ValueError("html_only must be a boolean.")
    if not isinstance(store_id, str) or not store_id.isdigit():
        raise ValueError("DoorDash store_id must be a numeric string.")
    text = html.decode("utf-8") if isinstance(html, bytes) else html
    soup = BeautifulSoup(text, "html.parser")
    heading = soup.find("h1")
    if not heading or not heading.get_text(" ", strip=True):
        raise ValueError("Restaurant heading missing.")
    if expected_heading and heading.get_text(" ", strip=True).casefold() != expected_heading.casefold():
        raise ValueError("Unexpected restaurant heading.")
    canonical = soup.select_one('link[rel="canonical"]')
    if not canonical or store_id_from_url(canonical.get("href", "")) != store_id:
        raise ValueError("Canonical page does not match configured store_id.")
    items, rejects, conflicts = {}, [], set()
    records = list(menu_records(soup))
    for record in records:
        item_id = str(record.get("id", ""))
        try:
            if str(record.get("storeId", "")) != store_id:
                raise ValueError("Item belongs to a different store.")
            if not item_id.isdigit() or not isinstance(record.get("name"), str) or not record["name"].strip():
                raise ValueError("Missing native item ID or name.")
            # React Flight escapes literal leading $ as $$.
            display = record.get("displayPrice", "")
            if display.startswith("$$"):
                display = display[1:]
            if not display.strip():
                rejects.append({"item_id": item_id, "reason": "No displayed price", "severity": "excluded"})
                continue
            match = PRICE.fullmatch(display)
            if not match:
                raise ValueError("Unrecognized displayed price.")
            cents = int(Decimal(match.group(1).replace(",", "")) * 100)
            if not 0 <= cents < 2**63:
                raise ValueError("Price outside INT64 range.")
            starting = bool(match.group(2))
            monetary = (record.get("quickAddContext") or {}).get("price") or {}
            if monetary.get("currency") not in (None, "USD"):
                raise ValueError("Unexpected currency.")
            if not starting and monetary.get("unitAmount") is not None:
                if monetary.get("decimalPlaces") != 2 or monetary["unitAmount"] != cents:
                    raise ValueError("Displayed price does not reconcile with monetary fields.")
            fields = record.get("logging", {}).get("fieldsMap", [])
            category = next((v.get("stringValue") for k,v in fields if k=="container_name"), None)
            item = {"source_item_id":item_id, "item_name":record["name"].strip(),
                    "price_cents":cents, "category":category,
                    "price_type":"starting_at" if starting else "displayed",
                    "variant":"starting_price; options_unverified" if starting else None}
            previous = items.get(item_id)
            if previous:
                if any(previous[k] != item[k] for k in ("item_name","price_cents","variant")):
                    conflicts.add(item_id)
                    raise ValueError("Conflicting duplicate item.")
                if previous["category"] == "Most Ordered" and category != "Most Ordered":
                    items[item_id] = item
            else:
                items[item_id] = item
        except (ValueError, KeyError, TypeError) as exc:
            rejects.append({"item_id":item_id,"reason":str(exc),"severity":"error"})
    for item_id in conflicts:
        items.pop(item_id, None)
    if not items:
        raise ValueError("No valid DoorDash menu records found; possible block or layout change.")
    return list(items.values()), rejects, len(records)

